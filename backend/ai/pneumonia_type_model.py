"""
Bacterial vs Viral classification — DenseNet-121.
Supports PNG, JPG, and DICOM (.dcm) input.
"""

import io
from pathlib import Path

import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image

from backend.ai.image_loader import load_image


# --------------------------------------------------
# PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = PROJECT_ROOT / "models" / "densenet_121_classification.pt"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

IMG_SIZE = 256
CALIBRATION_T = 1.3183
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

CLASS_NAMES = [
    "bacterial_pneumonia",
    "viral_pneumonia",
]

_model = None


# --------------------------------------------------
# MODEL HEAD — must match training
# --------------------------------------------------

def _make_head(in_features, num_classes, hidden=256):
    return nn.Sequential(
        nn.Dropout(0.3),
        nn.Linear(in_features, hidden),
        nn.BatchNorm1d(hidden),
        nn.ReLU(inplace=True),
        nn.Dropout(0.2),
        nn.Linear(hidden, num_classes),
    )


# --------------------------------------------------
# LOAD MODEL ONCE
# --------------------------------------------------

def _load_model():
    global _model

    if _model is not None:
        return _model

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"DenseNet model not found: {MODEL_PATH}"
        )

    model = models.densenet121(weights=None)
    in_features = model.classifier.in_features
    model.classifier = _make_head(in_features, len(CLASS_NAMES))

    state = torch.load(
        MODEL_PATH,
        map_location=DEVICE,
        weights_only=True,
    )

    model.load_state_dict(state)
    model.to(DEVICE)
    model.eval()

    _model = model
    return _model


# --------------------------------------------------
# EVALUATION PREPROCESSING — matches training
# --------------------------------------------------

def _build_transform():
    return transforms.Compose([
        transforms.Resize(int(IMG_SIZE * 1.05)),
        transforms.CenterCrop(IMG_SIZE),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])


# --------------------------------------------------
# PREDICT PNEUMONIA TYPE
# --------------------------------------------------

def predict_type(image_input):
    model = _load_model()
    transform = _build_transform()

    img = load_image(image_input)

    tensor = transform(img).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        outputs = model(tensor)
        calibrated_logits = outputs / CALIBRATION_T
        probs = torch.softmax(calibrated_logits, dim=1)[0]

    probabilities = probs.cpu().tolist()
    pred_idx = int(torch.argmax(probs).item())

    return {
        "label": CLASS_NAMES[pred_idx],
        "confidence": float(probabilities[pred_idx]),
        "probabilities": {
            name: float(prob)
            for name, prob in zip(CLASS_NAMES, probabilities)
        },
    }