"""
Quick standalone test for the pneumonia model.
Run from project root:  python test_model.py
"""

import sys
from pathlib import Path

from backend.ai.pneumonia_model import predict

# ------------------------------------------------------------
# Image to test: first command-line argument, or the sample
# test_image.jpeg in the project root.
# ------------------------------------------------------------
IMAGE_PATH = sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "test_image.jpeg"


if __name__ == "__main__":
    print("Loading model and predicting...\n")

    result = predict(IMAGE_PATH)

    print("=" * 50)
    print(f"Label      : {result['label']}")
    print(f"Confidence : {result['confidence'] * 100:.2f}%")
    print("=" * 50)
    print("Probabilities:")

    for name, p in result["probabilities"].items():
        print(f"  {name:<10}: {p * 100:.2f}%")
    print("=" * 50)