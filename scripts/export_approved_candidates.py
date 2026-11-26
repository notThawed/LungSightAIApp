"""
Export approved training candidates from Supabase into ONE flat dataset
folder with 4 classes and train/val/test splits.

Output:
    approved_dataset/approved_<DATE>/
        train/
            normal/
            bacterial_pneumonia/
            viral_pneumonia/
            covid_pneumonia/
        val/
            normal/
            bacterial_pneumonia/
            viral_pneumonia/
            covid_pneumonia/
        test/
            normal/
            bacterial_pneumonia/
            viral_pneumonia/
            covid_pneumonia/

Split:   80% train / 10% val / 10% test (seeded, reproducible)
Excludes: labels not in the 4 allowed classes (other_uncertain,
          pneumonia_unspecified, NULL, etc.)

Run:
    python scripts/export_approved_candidates.py
"""

import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------
# Make sure we can import backend.*
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.supabase_client import admin_supabase  # noqa: E402


# --------------------------------------------------
# CONFIG
# --------------------------------------------------

SPLIT_SEED = 42
SPLIT_RATIOS = (0.80, 0.10, 0.10)  # train, val, test

# ONE output folder with 4 classes
DATASET_ROOT = PROJECT_ROOT / "approved_dataset"

# The only labels we export
ALLOWED_LABELS = [
    "normal",
    "bacterial_pneumonia",
    "viral_pneumonia",
    "covid_pneumonia",
]

STORAGE_BUCKET = "xray-images"


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def fetch_approved_candidates():
    """
    Return all approved candidates with their image info.

    confirmed_label lives on `examinations`, not on
    `xray_training_candidates`, so it is fetched via an
    inner join and flattened into each row.
    """

    print("Fetching approved candidates from Supabase...")

    response = (
        admin_supabase
        .table("xray_training_candidates")
        .select("""
            candidate_id,
            image_id,
            ai_findings,
            ai_pneumonia_type,
            confirmed_at,

            examinations!inner (
                confirmed_label
            )
        """)
        .eq("status", "approved")
        .order("confirmed_at", desc=False)
        .execute()
    )

    rows = response.data or []

    print(f"  -> {len(rows)} approved candidate(s) found")

    # Flatten confirmed_label from the joined examination
    for row in rows:
        exam = row.get("examinations") or {}
        if isinstance(exam, list):
            exam = exam[0] if exam else {}
        row["confirmed_label"] = exam.get("confirmed_label")

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
        return (
            admin_supabase
            .storage
            .from_(STORAGE_BUCKET)
            .download(image_path)
        )
    except Exception as exc:
        print(f"  !! Download failed for {image_path}: {exc}")
        return None


def split_indices(n, seed):
    """Return three lists of indices: train, val, test (80/10/10)."""
    idx = list(range(n))
    random.Random(seed).shuffle(idx)

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
    dataset_out = DATASET_ROOT / f"approved_{timestamp}"

    # ----------------------------------------------
    # 1. Fetch
    # ----------------------------------------------

    candidates = fetch_approved_candidates()

    if not candidates:
        print("\nNo approved candidates to export. Nothing to do.")
        return

    # ----------------------------------------------
    # 2. Filter to the 4 allowed labels
    # ----------------------------------------------

    usable = []

    for row in candidates:
        label = row.get("confirmed_label")
        image_path = row.get("image_path")

        if label not in ALLOWED_LABELS:
            print(f"  skip {row['candidate_id']}: label={label!r} (not allowed)")
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
    # 4. Prepare folders: train/val/test × 4 classes
    # ----------------------------------------------

    ensure_dirs(dataset_out, [
        f"{split}/{label}"
        for split in ("train", "val", "test")
        for label in ALLOWED_LABELS
    ])

    # ----------------------------------------------
    # 5. Split + download
    # ----------------------------------------------

    print(f"\nExporting to:\n  {dataset_out}")

    total_saved = 0
    total_skipped = 0

    for label, rows in sorted(by_label.items()):

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

                out_path = (
                    dataset_out / split_name / label
                    / f"{candidate_id}.png"
                )
                save_image(image_bytes, out_path)

                mark_as_used(candidate_id)
                total_saved += 1

    print(f"\nDone.")
    print(f"  saved:   {total_saved}")
    print(f"  skipped: {total_skipped}")
    print(f"\nDataset root:\n  {dataset_out}")


if __name__ == "__main__":
    main()