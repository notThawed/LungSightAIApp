"""
Pneumonia inference — loads resnet_model.pt and predicts
"positive" or "negative" for a chest X-ray image.
"""

import json
from pathlib import Path

import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
import io

# ============================================================
# PATHS
# ============================================================

# This file lives at:  backend/ai/pneumonia_model.py
# So the project root is two levels up.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODELS_DIR = PROJECT_ROOT / "models"
MODEL_PATH = MODELS_DIR / "resnet_model.pt"
CLASS_NAMES_PATH = MODELS_DIR / "class_names.json"


# ============================================================
# CONFIG (must match training)
# ============================================================

IMG_SIZE = 224
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ============================================================
# SINGLETON CACHE (avoid reloading every call)
# ============================================================

_model = None
_class_names = None


# ============================================================
# PREPROCESSING (matches training eval_transform)
# ============================================================

def _build_transform():
    return transforms.Compose([
        transforms.Resize(int(IMG_SIZE * 1.14)),
        transforms.CenterCrop(IMG_SIZE),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])


# ============================================================
# MODEL BUILDER (must match training build_model)
# ============================================================

def _make_head(in_features, num_classes, hidden=256, p_drop1=0.5, p_drop2=0.4):
    return nn.Sequential(
        nn.Dropout(p=p_drop1),
        nn.Linear(in_features, hidden),
        nn.BatchNorm1d(hidden),
        nn.ReLU(inplace=True),
        nn.Dropout(p=p_drop2),
        nn.Linear(hidden, num_classes),
    )


def _build_resnet50(num_classes):
    model = models.resnet50(weights=None)
    in_features = model.fc.in_features
    model.fc = _make_head(in_features, num_classes)
    return model


# ============================================================
# LOAD (once, cached)
# ============================================================

def _load():
    global _model, _class_names

    if _model is not None:
        return _model, _class_names

    # 1. Load class names
    if not CLASS_NAMES_PATH.exists():
        raise FileNotFoundError(
            f"class_names.json not found at: {CLASS_NAMES_PATH}"
        )

    with open(CLASS_NAMES_PATH, "r") as f:
        data = json.load(f)
    _class_names = data["class_names"]

    # 2. Load model
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model file not found at: {MODEL_PATH}"
        )

    model = _build_resnet50(num_classes=len(_class_names))
    state = torch.load(MODEL_PATH, map_location=DEVICE, weights_only=True)
    model.load_state_dict(state)
    model.to(DEVICE)
    model.eval()

    _model = model
    return _model, _class_names


# ============================================================
# PREDICT
# ============================================================

def predict(image_input):
    """
    Predict pneumonia from a chest X-ray.

    Args:
        image_input: either a file path (str/Path) OR bytes OR PIL.Image

    Returns:
        dict with:
            - label: "positive" or "negative"
            - confidence: 0.0 - 1.0
            - probabilities: {class_name: prob, ...}
    """

    model, class_names = _load()
    transform = _build_transform()

    # Convert input → PIL image
    if isinstance(image_input, (str, Path)):
        img = Image.open(image_input).convert("RGB")
    elif isinstance(image_input, bytes):
        img = Image.open(io.BytesIO(image_input)).convert("RGB")
    elif isinstance(image_input, Image.Image):
        img = image_input.convert("RGB")
    else:
        raise TypeError(f"Unsupported image type: {type(image_input)}")

    # Preprocess
    tensor = transform(img).unsqueeze(0).to(DEVICE)

    # Predict
    with torch.no_grad():
        outputs = model(tensor)
        probs = torch.softmax(outputs, dim=1)[0]

    probs_list = probs.cpu().tolist()
    pred_idx = int(torch.argmax(probs).item())

    return {
        "label": class_names[pred_idx],
        "confidence": float(probs_list[pred_idx]),
        "probabilities": {
            name: float(p) for name, p in zip(class_names, probs_list)
        },
    }