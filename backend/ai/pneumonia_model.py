"""
Pneumonia inference — loads resnet_model.pt and predicts
"positive" or "negative" for a chest X-ray image.
Supports PNG, JPG, and DICOM (.dcm) input.
"""

import json
from pathlib import Path

import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
import io

import numpy as np
from matplotlib import colormaps

from backend.ai.image_loader import load_image


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODELS_DIR = PROJECT_ROOT / "models"
MODEL_PATH = MODELS_DIR / "resnet_model.pt"
CLASS_NAMES_PATH = MODELS_DIR / "class_names.json"


# ============================================================
# CONFIG (must match training)
# ============================================================

IMG_SIZE = 224
CALIBRATION_T = 1.3542
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ============================================================
# SINGLETON CACHE
# ============================================================

_model = None
_class_names = None


# ============================================================
# PREPROCESSING
# ============================================================

def _build_transform():
    return transforms.Compose([
        transforms.Resize(int(IMG_SIZE * 1.14)),
        transforms.CenterCrop(IMG_SIZE),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])


# ============================================================
# MODEL BUILDER
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
# LOAD
# ============================================================

def _load():
    global _model, _class_names

    if _model is not None:
        return _model, _class_names

    if not CLASS_NAMES_PATH.exists():
        raise FileNotFoundError(
            f"class_names.json not found at: {CLASS_NAMES_PATH}"
        )

    with open(CLASS_NAMES_PATH, "r") as f:
        data = json.load(f)
    _class_names = data["class_names"]

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
    model, class_names = _load()
    transform = _build_transform()

    img = load_image(image_input)

    tensor = transform(img).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        outputs = model(tensor)
        calibrated_logits = outputs / CALIBRATION_T
        probs = torch.softmax(calibrated_logits, dim=1)[0]

    probs_list = probs.cpu().tolist()
    pred_idx = int(torch.argmax(probs).item())

    return {
        "label": class_names[pred_idx],
        "confidence": float(probs_list[pred_idx]),
        "probabilities": {
            name: float(p) for name, p in zip(class_names, probs_list)
        },
    }


# ============================================================
# GRAD-CAM
# ============================================================

def generate_gradcam(image_input):
    model, class_names = _load()
    transform = _build_transform()

    original_img = load_image(image_input)

    input_tensor = transform(original_img).unsqueeze(0).to(DEVICE)

    display_img = original_img.resize((IMG_SIZE, IMG_SIZE))

    activations = []
    gradients = []

    target_layer = model.layer4[-1]

    def save_activation(module, inputs, output):
        activations.append(output)

    def save_gradient(module, grad_input, grad_output):
        gradients.append(grad_output[0])

    activation_handle = target_layer.register_forward_hook(
        save_activation
    )
    gradient_handle = target_layer.register_full_backward_hook(
        save_gradient
    )

    try:
        model.eval()
        model.zero_grad(set_to_none=True)

        with torch.enable_grad():
            outputs = model(input_tensor)

            calibrated_logits = outputs / CALIBRATION_T
            probabilities = torch.softmax(calibrated_logits, dim=1)[0]
            pred_idx = int(torch.argmax(probabilities).item())

            target_score = outputs[0, pred_idx]
            target_score.backward()

        feature_maps = activations[0].detach()
        feature_gradients = gradients[0].detach()

        weights = feature_gradients.mean(dim=(2, 3), keepdim=True)

        cam = (weights * feature_maps).sum(dim=1, keepdim=True)
        cam = torch.relu(cam)

        cam = torch.nn.functional.interpolate(
            cam,
            size=(IMG_SIZE, IMG_SIZE),
            mode="bilinear",
            align_corners=False,
        )

        cam = cam[0, 0]
        cam_min = cam.min()
        cam_max = cam.max()

        if (cam_max - cam_min).item() > 1e-8:
            cam = (cam - cam_min) / (cam_max - cam_min)
        else:
            cam = torch.zeros_like(cam)

        heatmap = cam.cpu().numpy()

        color_map = colormaps["jet"]
        colored_heatmap = color_map(heatmap)[..., :3]
        colored_heatmap = (colored_heatmap * 255).astype(np.uint8)

        heatmap_img = Image.fromarray(colored_heatmap).resize(
            display_img.size,
            Image.Resampling.BILINEAR,
        )

        overlay = Image.blend(
            display_img.convert("RGB"),
            heatmap_img.convert("RGB"),
            alpha=0.4,
        )

        probabilities_list = probabilities.detach().cpu().tolist()

        return {
            "label": class_names[pred_idx],
            "confidence": float(probabilities_list[pred_idx]),
            "heatmap": heatmap,
            "overlay": overlay,
        }

    finally:
        activation_handle.remove()
        gradient_handle.remove()
        model.zero_grad(set_to_none=True)