"""
Export approved training candidates from Supabase into local folders
ready to be merged into the training datasets.

What it does:
  1. Fetches all `xray_training_candidates` rows where status = "approved"
  2. Downloads each candidate's X-ray image from Supabase Storage
  3. Sorts them into two dataset trees:
       hybrid_negative_positive/approved_<DATE>/
           positive/{train,val,test}
           negative/{train,val,test}
       international_classification/approved_<DATE>/
           train/{bacterial_pneumonia,viral_pneumonia}
           val/{bacterial_pneumonia,viral_pneumonia}
           test/{bacterial_pneumonia,viral_pneumonia}
  4. Marks each exported candidate as status = "used_in_training"
     with used_in_model_version = "pending"

Split:   80% train / 10% val / 10% test (seeded, reproducible)
Excludes: confirmed_label = "other_uncertain"

Run:
    python scripts/export_approved_candidates.py
"""

import io
import random
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# --------------------------------------------------
# Make sure we can import backend.*
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.supabase_client import admin_supabase  # noqa: E402
from datetime import timezone  # noqa: E402


# --------------------------------------------------
# CONFIG
# --------------------------------------------------

SPLIT_SEED = 42
SPLIT_RATIOS = (0.80, 0.10, 0.10)  # train, val, test

BINARY_ROOT = PROJECT_ROOT / "hybrid_negative_positive"
CLASSIFICATION_ROOT = PROJECT_ROOT / "international_classification"

EXCLUDED_LABELS = {"other_uncertain"}

# Maps confirmed_label → (binary_folder, classification_folder)
LABEL_ROUTING = {
    "normal":              ("negative", None),
    "bacterial_pneumonia": ("positive", "bacterial_pneumonia"),
    "viral_pneumonia":     ("positive", "viral_pneumonia"),
}

STORAGE_BUCKET = "xray-images"


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def fetch_approved_candidates():
    """Return all approved candidates with their image info."""

    print("Fetching approved candidates from Supabase...")

    response = (
        admin_supabase
        .table("xray_training_candidates")
        .select("""
            candidate_id,
            image_id,
            confirmed_label,
            ai_findings,
            ai_pneumonia_type,
            confirmed_at
        """)
        .eq("status", "approved")
        .order("confirmed_at", desc=False)
        .execute()
    )

    rows = response.data or []

    print(f"  -> {len(rows)} approved candidate(s) found")

    # Attach image_path by looking up xray_images in bulk
    if rows:
        image_ids = [r["image_id"] for r in rows if r.get("image_id")]

        img_response = (
            admin_supabase
            .table("xray_images")
            .select("image_id, image_path")
            .in_("image_id", image_ids)
            .execute()
        )

        path_by_image = {
            img["image_id"]: img["image_path"]
            for img in (img_response.data or [])
        }

        for row in rows:
            row["image_path"] = path_by_image.get(row.get("image_id"))

    return rows


def download_image(image_path):
    """Download bytes from Supabase Storage."""

    try:
        data = (
            admin_supabase
            .storage
            .from_(STORAGE_BUCKET)
            .download(image_path)
        )
        return data

    except Exception as exc:
        print(f"  !! Download failed for {image_path}: {exc}")
        return None


def split_indices(n, seed):
    """Return three lists of indices: train, val, test (80/10/10)."""

    idx = list(range(n))
    rng = random.Random(seed)
    rng.shuffle(idx)

    train_end = int(n * SPLIT_RATIOS[0])
    val_end = train_end + int(n * SPLIT_RATIOS[1])

    return (
        idx[:train_end],
        idx[train_end:val_end],
        idx[val_end:],
    )


def ensure_dirs(root, subdirs):
    """Create <root>/<subdir>/ for each subdir."""
    for sub in subdirs:
        (root / sub).mkdir(parents=True, exist_ok=True)


def save_image(image_bytes, out_path):
    """Write bytes to disk, skipping if it already exists."""
    if out_path.exists():
        return False
    out_path.write_bytes(image_bytes)
    return True


def mark_as_used(candidate_id):
    """Set status = used_in_training for one candidate."""
    try:
        admin_supabase.table("xray_training_candidates").update({
            "status": "used_in_training",
            "used_in_model_version": "pending",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("candidate_id", candidate_id).execute()
    except Exception as exc:
        print(f"  !! Failed to mark {candidate_id} as used: {exc}")


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():
    timestamp = datetime.now().strftime("%Y_%m_%d")
    binary_out = BINARY_ROOT / f"approved_{timestamp}"
    class_out = CLASSIFICATION_ROOT / f"approved_{timestamp}"

    # ----------------------------------------------
    # 1. Fetch
    # ----------------------------------------------

    candidates = fetch_approved_candidates()

    if not candidates:
        print("\nNo approved candidates to export. Nothing to do.")
        return

    # ----------------------------------------------
    # 2. Filter
    # ----------------------------------------------

    usable = []

    for row in candidates:
        label = row.get("confirmed_label")
        image_path = row.get("image_path")

        if label in EXCLUDED_LABELS:
            print(f"  skip {row['candidate_id']}: label={label}")
            continue

        if label not in LABEL_ROUTING:
            print(f"  skip {row['candidate_id']}: unknown label {label!r}")
            continue

        if not image_path:
            print(f"  skip {row['candidate_id']}: missing image_path")
            continue

        usable.append(row)

    if not usable:
        print("\nNo usable candidates after filtering. Nothing to do.")
        return

    # ----------------------------------------------
    # 3. Group by label
    # ----------------------------------------------

    by_label = defaultdict(list)

    for row in usable:
        by_label[row["confirmed_label"]].append(row)

    # ----------------------------------------------
    # 4. Prepare output folders
    # ----------------------------------------------

    ensure_dirs(binary_out, [
        "positive/train", "positive/val", "positive/test",
        "negative/train", "negative/val", "negative/test",
    ])

    ensure_dirs(class_out, [
        "train/bacterial_pneumonia", "val/bacterial_pneumonia", "test/bacterial_pneumonia",
        "train/viral_pneumonia",     "val/viral_pneumonia",     "test/viral_pneumonia",
    ])

    # ----------------------------------------------
    # 5. Split + download
    # ----------------------------------------------

    print(f"\nExporting to:")
    print(f"  {binary_out}")
    print(f"  {class_out}")

    total_saved = 0
    total_skipped = 0

    for label, rows in sorted(by_label.items()):

        binary_sub, class_sub = LABEL_ROUTING[label]

        train_i, val_i, test_i = split_indices(len(rows), SPLIT_SEED)
        split_map = {
            "train": [rows[i] for i in train_i],
            "val":   [rows[i] for i in val_i],
            "test":  [rows[i] for i in test_i],
        }

        for split_name, split_rows in split_map.items():

            for row in split_rows:

                candidate_id = row["candidate_id"]
                image_bytes = download_image(row["image_path"])

                if image_bytes is None:
                    total_skipped += 1
                    continue

                filename = f"{candidate_id}.png"

                # Binary dataset
                binary_path = (
                    binary_out / binary_sub / split_name / filename
                )
                save_image(image_bytes, binary_path)

                # Classification dataset (only for positive cases)
                if class_sub is not None:
                    class_path = (
                        class_out / split_name / class_sub / filename
                    )
                    save_image(image_bytes, class_path)

                mark_as_used(candidate_id)
                total_saved += 1

    print(f"\nDone.")
    print(f"  saved:   {total_saved}")
    print(f"  skipped: {total_skipped}")
    print(f"\nNext: add the new folders to your training scripts' DATA_DIRS,")
    print(f"then re-run training.")


if __name__ == "__main__":
    main()