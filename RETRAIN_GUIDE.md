# Retraining Pipeline

How to retrain the AI models using doctor-confirmed data.

## The loop

```
Doctors review X-rays → confirm labels
        │
        ▼
Superadmin approves labels (Training page)
        │
        ▼
[Manual] Export + retrain + compare + deploy
        │
        ▼
New model version live in the app
```

**Nothing is automatic.** You (the ML engineer) decide when to retrain.

---

## Step 1 — Export approved data

```bash
python scripts/export_approved_candidates.py
```

This:
- Fetches all `status = "approved"` candidates
- Downloads their X-rays from Supabase
- Sorts them into:
  - `hybrid_negative_positive/approved_YYYY_MM_DD/`
  - `international_classification/approved_YYYY_MM_DD/`
- Marks those candidates as `used_in_training`

---

## Step 2 — Merge into training dataset

Open **your ResNet-50 training script** (`train_compare.py`, the binary one).

Find `DATA_DIRS`:

```python
DATA_DIRS = [
    ("international", r"C:\...\positive_negative_international"),
    ("local",         r"C:\...\positive_negative_local"),
]
```

Add the newly exported folder:

```python
DATA_DIRS = [
    ("international", r"C:\...\positive_negative_international"),
    ("local",         r"C:\...\positive_negative_local"),
    ("approved_2026_10_16", r"C:\Users\ryume\Desktop\hybrid_negative_positive\approved_2026_10_16"),
]
```

Do the same for the **DenseNet-121 training script** (the classification one):

```python
DATA_DIRS = [
    ("international", r"C:\Users\ryume\Desktop\international_classification"),
    ("approved_2026_10_16", r"C:\Users\ryume\Desktop\international_classification\approved_2026_10_16"),
]
```

Also change `OUTPUT_DIR` so you don't overwrite the previous run:

```python
OUTPUT_DIR = "training_output_v2"   # was "training_output"
```

---

## Step 3 — Retrain

Run each script:

```bash
python train_compare.py
```

This takes hours. When done, you'll have:

```
training_output_v2/
    resnet50/
        best_model.pt
        config.json
        completed.json
    densenet121/
        best_model.pt
        ...
    leaderboard.jsonl
```

---

## Step 4 — Compare against baseline

Find your **old** model's test F1. It's in the old leaderboard:

```bash
cat training_output/leaderboard.jsonl | findstr resnet50
```

Or check the app — the "AI Findings Summary" text on any completed X-ray.

Then run:

```bash
python scripts/compare_models.py --baseline resnet50=0.942 densenet121=0.918
```

Output:

```
model                baseline       new     delta  verdict
resnet50               0.9420    0.9480   +0.0060  DEPLOY
densenet121            0.9180    0.9165   -0.0015  keep old version
```

---

## Step 5 — Deploy (if recommended)

**Only if `compare_models.py` says DEPLOY.**

### 5a. Copy the new weights

```bash
copy training_output_v2\resnet50\best_model.pt models\resnet_model.pt
```

**⚠️ Back up the old one first:**

```bash
copy models\resnet_model.pt models\resnet_model_v1_backup.pt
```

### 5b. Verify IMG_SIZE matches training

Open `backend/ai/pneumonia_model.py`. Check:

```python
IMG_SIZE = 224
```

Compare to the training config you just used. If training used `img_size=256`, update the inference file to `256`. **They must match.**

(Your `pneumonia_type_model.py` already uses 256 — check if the DenseNet retrain also used 256.)

### 5c. Bump version strings

Open `streamlit_app/pages/radtech/analyze.py` (or wherever `analyze.py` lives):

```python
AI_MODEL_VERSION = "pneumonia_resnet50_v2"          # was v1
CLASSIFICATION_MODEL_VERSION = "pneumonia_densenet121_v2"  # was v1
```

### 5d. Update Supabase

New predictions will now say `v2`. Old rows in `xray_ai_results` keep saying `v1`. **That's correct** — you always know which model produced which result.

### 5e. Restart the app

Kill and restart Streamlit. The new `.pt` gets loaded on the first prediction.

---

## Rollback

If v2 turns out worse in production:

```bash
copy models\resnet_model_v1_backup.pt models\resnet_model.pt
```

Then revert the version string in `analyze.py` and restart.

---

## When should you retrain?

**Rule of thumb:** at least **50 approved candidates** since the last retrain.

Why?
- 10 images → the model barely changes, not worth the GPU time
- 50 images → visible improvement if labels are good
- 500+ images → meaningful jump, but only if labels are high quality

**Don't retrain on `other_uncertain` labels.** Those get excluded automatically.

---

## Quick checklist

- [ ] Ran `export_approved_candidates.py`
- [ ] Added the new folder to both training scripts' `DATA_DIRS`
- [ ] Changed `OUTPUT_DIR` to a new name
- [ ] Ran both training scripts
- [ ] Ran `compare_models.py` with the correct baseline
- [ ] Backed up the old `.pt` files
- [ ] Copied the new `.pt` files into `models/`
- [ ] Verified `IMG_SIZE` matches training
- [ ] Bumped version strings in `analyze.py`
- [ ] Restarted the Streamlit app
- [ ] Tested one X-ray on the new model