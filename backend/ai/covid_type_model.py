import io
from pathlib import Path

import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image

# --------------------------------------------------
# PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = PROJECT_ROOT / "models" / "covid_classification.pt"  # <-- Your new .pt

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

IMG_SIZE = 256
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

CLASS_NAMES = [
    "viral_pneumonia",
    "covid_pneumonia",
]

_model = None


# --------------------------------------------------
# MODEL HEAD — must match your training script
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


def _load_model():
    global _model

    if _model is not None:
        return _model

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"COVID model not found: {MODEL_PATH}"
        )

    model = models.resnet50(weights=None)
    in_features = model.fc.in_features
    model.fc = _make_head(in_features, len(CLASS_NAMES))

    state = torch.load(MODEL_PATH, map_location=DEVICE, weights_only=True)
    model.load_state_dict(state)
    model.to(DEVICE)
    model.eval()

    _model = model
    return _model


def _build_transform():
    return transforms.Compose([
        transforms.Resize(int(IMG_SIZE * 1.05)),
        transforms.CenterCrop(IMG_SIZE),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])


def predict_covid_type(image_input):
    model = _load_model()
    transform = _build_transform()

    if isinstance(image_input, (str, Path)):
        img = Image.open(image_input).convert("RGB")
    elif isinstance(image_input, bytes):
        img = Image.open(io.BytesIO(image_input)).convert("RGB")
    elif isinstance(image_input, Image.Image):
        img = image_input.convert("RGB")
    else:
        raise TypeError(f"Unsupported image type: {type(image_input)}")

    tensor = transform(img).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        outputs = model(tensor)
        probs = torch.softmax(outputs, dim=1)[0]

    probabilities = probs.cpu().tolist()
    pred_idx = int(torch.argmax(probs).item())

    return {
        "label": CLASS_NAMES[pred_idx],
        "confidence": float(probabilities[pred_idx]),
        "probabilities": {
            name: float(prob) for name, prob in zip(CLASS_NAMES, probabilities)
        },
    }