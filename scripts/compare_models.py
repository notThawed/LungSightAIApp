"""
Compare a newly-trained model's test F1 against a baseline.

Searches for leaderboard.jsonl in a few likely places:
  - <project_root>/training_output/leaderboard.jsonl
  - <project_root>/../training_output/leaderboard.jsonl
  - user-provided path via --output-dir

Run:
    python scripts/compare_models.py --baseline resnet50=0.942
    python scripts/compare_models.py --baseline resnet50=0.942 --output-dir "C:\\somewhere\\training_output"
"""

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

MIN_IMPROVEMENT = 0.005  # require +0.5% F1 to recommend deploy


def find_leaderboard(explicit_dir=None):
    """Return the first leaderboard.jsonl we can find, or None."""

    candidates = []

    if explicit_dir:
        candidates.append(Path(explicit_dir) / "leaderboard.jsonl")

    candidates.extend([
        PROJECT_ROOT / "training_output" / "leaderboard.jsonl",
        PROJECT_ROOT.parent / "training_output" / "leaderboard.jsonl",
        Path.home() / "Desktop" / "training_output" / "leaderboard.jsonl",
    ])

    for path in candidates:
        if path.exists():
            return path

    return None


def load_leaderboard(path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def latest_per_model(rows):
    latest = {}
    for row in rows:
        model = row.get("model")
        ts = row.get("timestamp", "")
        if model not in latest or ts > latest[model].get("timestamp", ""):
            latest[model] = row
    return latest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--baseline",
        nargs="+",
        required=True,
        metavar="NAME=F1",
        help="Baseline F1 scores, e.g. resnet50=0.942",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Path to the folder containing leaderboard.jsonl",
    )
    args = parser.parse_args()

    # ----------------------------------------------
    # Locate leaderboard
    # ----------------------------------------------

    leaderboard_path = find_leaderboard(args.output_dir)

    if leaderboard_path is None:
        print()
        print("=" * 60)
        print("No leaderboard.jsonl found.")
        print("=" * 60)
        print()
        print("This script compares a NEWLY-trained model against")
        print("a baseline. You haven't trained anything yet, so there's")
        print("nothing to compare.")
        print()
        print("Searched these locations:")
        print(f"  - {PROJECT_ROOT / 'training_output' / 'leaderboard.jsonl'}")
        print(f"  - {PROJECT_ROOT.parent / 'training_output' / 'leaderboard.jsonl'}")
        print(f"  - {Path.home() / 'Desktop' / 'training_output' / 'leaderboard.jsonl'}")
        print()
        print("If your leaderboard lives somewhere else, pass:")
        print('  --output-dir "C:\\path\\to\\training_output"')
        print()
        print("You'll use this script AFTER you retrain a model.")
        print()
        return

    print(f"Reading: {leaderboard_path}")

    # ----------------------------------------------
    # Parse baselines
    # ----------------------------------------------

    baselines = {}
    for item in args.baseline:
        if "=" not in item:
            print(f"!! Bad baseline: {item!r} (expected name=score)")
            return
        name, value = item.split("=", 1)
        baselines[name.strip()] = float(value)

    # ----------------------------------------------
    # Load + compare
    # ----------------------------------------------

    rows = load_leaderboard(leaderboard_path)
    latest = latest_per_model(rows)

    print()
    print("=" * 60)
    print("DEPLOY DECISION")
    print("=" * 60)
    print(f"{'model':<18}{'baseline':>10}{'new':>10}{'delta':>10}  verdict")
    print("-" * 60)

    for name, baseline in sorted(baselines.items()):

        row = latest.get(name)

        if not row:
            print(f"{name:<18}{baseline:>10.4f}{'—':>10}{'—':>10}  no new run")
            continue

        new_f1 = row.get("test_f1_macro", 0.0)
        delta = new_f1 - baseline

        if delta >= MIN_IMPROVEMENT:
            verdict = "DEPLOY"
        elif delta >= 0:
            verdict = "tiny gain (optional)"
        else:
            verdict = "keep old version"

        print(
            f"{name:<18}{baseline:>10.4f}{new_f1:>10.4f}"
            f"{delta:>+10.4f}  {verdict}"
        )

    print("=" * 60)
    print(f"\nThreshold to recommend deploy: +{MIN_IMPROVEMENT:.3f} F1")
    print("If deploying: copy best_model.pt into models/ and bump")
    print("the version string in analyze.py, then restart the app.")


if __name__ == "__main__":
    main()