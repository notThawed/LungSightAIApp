# backend/ai/ood_validator.py

import io
import torch
from PIL import Image
from transformers import CLIPProcessor, CLIPModel

from backend.ai.image_loader import load_image

# Load CLIP once
_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
_model_name = "openai/clip-vit-base-patch32"

try:
    _clip_model = CLIPModel.from_pretrained(_model_name).to(_device)
    _clip_processor = CLIPProcessor.from_pretrained(_model_name)
    _clip_model.eval()
except Exception as e:
    print(f"Warning: Could not load CLIP validator: {e}")
    _clip_model = None


def is_chest_xray(image_input, threshold: float = 0.85) -> bool:
    """
    Returns True if the image looks like a chest X-ray, False otherwise.
    Supports PNG, JPG, and DICOM (.dcm) input.
    """
    if _clip_model is None:
        # If CLIP failed to load, fail open (allow the image) so the app doesn't break
        return True 
        
    try:
        # Use our universal loader (handles both standard images and DICOM)
        image = load_image(image_input)
        
        # The descriptions we compare the image against.
        # We explicitly list other body parts so CLIP knows the difference.
        texts = [
            "a chest X-ray radiograph showing lungs and ribs",
            "an X-ray of a hand, arm, leg, or foot",
            "an X-ray of a skull, spine, or pelvis",
            "a photograph of an animal, person, or object",
            "a text document or screenshot",
        ]
        
        inputs = _clip_processor(
            text=texts, 
            images=image, 
            return_tensors="pt", 
            padding=True
        ).to(_device)
        
        with torch.no_grad():
            outputs = _clip_model(**inputs)
            probs = outputs.logits_per_image.softmax(dim=1)
            
        # probs[0][0] is the probability for "a chest X-ray radiograph"
        chest_xray_prob = probs[0][0].item()
        
        # probs[0][1] is the probability for the hand/limb X-ray
        limb_xray_prob = probs[0][1].item()
        
        print(f"OOD Check: Chest X-ray prob = {chest_xray_prob:.3f} | Limb X-ray prob = {limb_xray_prob:.3f}")
        
        # Rule: It must be a chest X-ray AND it must not look more like a limb.
        if chest_xray_prob < threshold:
            return False
            
        if limb_xray_prob > chest_xray_prob:
            return False
            
        return True
        
    except Exception as e:
        print(f"OOD validation error: {e}")
        return True # Fail open if something goes wrong