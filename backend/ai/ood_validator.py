# backend/ai/ood_validator.py (or just add this to analyze.py)

import io
import torch
from PIL import Image
from transformers import CLIPProcessor, CLIPModel

# Load CLIP once (similar to how you load your pneumonia model)
_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
_model_name = "openai/clip-vit-base-patch32"

try:
    _clip_model = CLIPModel.from_pretrained(_model_name).to(_device)
    _clip_processor = CLIPProcessor.from_pretrained(_model_name)
    _clip_model.eval()
except Exception as e:
    print(f"Warning: Could not load CLIP validator: {e}")
    _clip_model = None

def is_chest_xray(image_bytes: bytes, threshold: float = 0.85) -> bool:
    """
    Returns True if the image looks like a chest X-ray, False otherwise.
    """
    if _clip_model is None:
        # If CLIP failed to load, fail open (allow the image) so the app doesn't break
        return True 
        
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        # The descriptions we compare the image against
        texts = [
            "a chest X-ray radiograph",
            "a photograph of an animal, person, or object", # Generic non-X-ray
            "a screenshot or text document",
            "a random picture",
            "a photo of a physical film of an X-ray"
        ]
        
        inputs = _clip_processor(text=texts, images=image, return_tensors="pt", padding=True).to(_device)
        
        with torch.no_grad():
            outputs = _clip_model(**inputs)
            # Get the probability of each text matching the image
            probs = outputs.logits_per_image.softmax(dim=1)
            
        # probs[0][0] is the probability for "a chest X-ray radiograph"
        # We check if the model is confident enough that it's an X-ray
        xray_prob = probs[0][0].item()
        
        print(f"OOD Check: X-ray probability = {xray_prob:.3f}")
        
        return xray_prob >= threshold
        
    except Exception as e:
        print(f"OOD validation error: {e}")
        return True # Fail open if something goes wrong