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

import numpy as np
from matplotlib import colormaps

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

    
# ============================================================
# GRAD-CAM — GENERATE A HEATMAP FOR THE PREDICTED CLASS
# ============================================================


def generate_gradcam(image_input):
    """
    Generate a Grad-CAM heatmap and overlay for a chest X-ray.

    Args:
        image_input: file path (str/Path), bytes, or PIL.Image.

    Returns:
        dict containing:
            - label: predicted class
            - confidence: predicted class confidence
            - heatmap: raw heatmap as a NumPy array (0.0 to 1.0)
            - overlay: PIL.Image with heatmap over the X-ray

    This function does not upload files or modify predict().
    """

    model, class_names = _load()
    transform = _build_transform()

    # 1. Convert input to a PIL image.
    if isinstance(image_input, (str, Path)):
        original_img = Image.open(image_input).convert("RGB")
    elif isinstance(image_input, bytes):
        original_img = Image.open(io.BytesIO(image_input)).convert("RGB")
    elif isinstance(image_input, Image.Image):
        original_img = image_input.convert("RGB")
    else:
        raise TypeError(
            f"Unsupported image type: {type(image_input)}"
        )

    # 2. Prepare the image exactly as the model expects.
    input_tensor = transform(original_img).unsqueeze(0).to(DEVICE)

    # Keep the original image for the final overlay.
    display_img = original_img.resize((IMG_SIZE, IMG_SIZE))

    # 3. Store activations and gradients from the final
    #    convolutional block of ResNet-50.
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
        # 4. Run the model with gradients enabled.
        model.eval()
        model.zero_grad(set_to_none=True)

        with torch.enable_grad():
            outputs = model(input_tensor)

            probabilities = torch.softmax(outputs, dim=1)[0]
            pred_idx = int(torch.argmax(probabilities).item())

            # Calculate gradients for the predicted class score.
            target_score = outputs[0, pred_idx]
            target_score.backward()

        # 5. Retrieve saved activations and gradients.
        feature_maps = activations[0].detach()
        feature_gradients = gradients[0].detach()

        # Average gradients spatially to obtain channel weights.
        weights = feature_gradients.mean(dim=(2, 3), keepdim=True)

        # Combine feature maps using the Grad-CAM weights.
        cam = (weights * feature_maps).sum(dim=1, keepdim=True)
        cam = torch.relu(cam)

        # Normalize the heatmap between 0 and 1.
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

        # 6. Convert the heatmap to a colored image.
        color_map = colormaps["jet"]
        colored_heatmap = color_map(heatmap)[..., :3]
        colored_heatmap = (colored_heatmap * 255).astype(np.uint8)

        heatmap_img = Image.fromarray(colored_heatmap).resize(
            display_img.size,
            Image.Resampling.BILINEAR,
        )

        # 7. Blend the heatmap with the original X-ray.
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
        # Always remove hooks so repeated predictions don't
        # accumulate callbacks or consume unnecessary memory.
        activation_handle.remove()
        gradient_handle.remove()
        model.zero_grad(set_to_none=True)
