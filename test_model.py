"""
Quick standalone test for the pneumonia model.
Run from project root:  python test_model.py
"""

from backend.ai.pneumonia_model import predict

# ------------------------------------------------------------
# Put the path to a test X-ray image here
# ------------------------------------------------------------
IMAGE_PATH = r"C:\Users\ryume\Desktop\LungSightAIApp-LungSightV2\test_image.jpeg"   # ← CHANGE THIS


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