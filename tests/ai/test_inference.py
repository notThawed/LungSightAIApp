"""
Inference with the real model files in models/ (CPU). These check the
contract the UI relies on, not clinical accuracy.
"""

import json
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "test_image.jpeg"


def test_class_names_are_binary():
    names = json.loads((ROOT / "models/class_names.json").read_text())["class_names"]
    assert names == ["negative", "positive"]


@pytest.mark.skipif(not (ROOT / "models/resnet_model.pt").exists(), reason="model file not present")
def test_binary_prediction_contract():
    from backend.ai.pneumonia_model import predict

    result = predict(SAMPLE.read_bytes())

    assert result["label"] in ("negative", "positive")
    assert 0.5 <= result["confidence"] <= 1.0
    assert result["confidence"] == pytest.approx(result["probabilities"][result["label"]])
    assert sum(result["probabilities"].values()) == pytest.approx(1.0, abs=1e-4)


@pytest.mark.skipif(not (ROOT / "models/resnet_model.pt").exists(), reason="model file not present")
def test_prediction_is_deterministic():
    from backend.ai.pneumonia_model import predict

    assert predict(SAMPLE)["confidence"] == pytest.approx(predict(SAMPLE)["confidence"])


@pytest.mark.skipif(not (ROOT / "models/resnet_model.pt").exists(), reason="model file not present")
def test_gradcam_returns_images():
    from backend.ai.pneumonia_model import generate_gradcam

    result = generate_gradcam(SAMPLE.read_bytes())

    assert result["label"] in ("negative", "positive")
    assert result["overlay"] is not None


@pytest.mark.skipif(
    not (ROOT / "models/densenet_121_classification.pt").exists(), reason="model file not present"
)
def test_type_prediction_contract():
    from backend.ai.pneumonia_type_model import predict_type

    result = predict_type(SAMPLE)

    assert result["label"] in ("bacterial_pneumonia", "viral_pneumonia")
    assert sum(result["probabilities"].values()) == pytest.approx(1.0, abs=1e-4)


def test_ood_validator_reports_availability():
    """When CLIP cannot load (offline), the validator fails open; the UI must
    be able to tell so it does not claim the check passed."""
    from backend.ai import ood_validator

    if not ood_validator.validator_available():
        assert ood_validator.is_chest_xray(b"not an image") is True
    else:
        assert ood_validator.is_chest_xray(SAMPLE.read_bytes()) in (True, False)
