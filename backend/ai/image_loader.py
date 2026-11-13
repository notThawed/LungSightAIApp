"""
Universal image loader.

Handles:
  - Standard images (PNG, JPG, JPEG, WEBP)
  - DICOM files (.dcm)
  - Raw bytes from either format

Returns a PIL.Image in RGB mode, ready for the AI pipeline.
"""

import io
from pathlib import Path

from PIL import Image

try:
    import pydicom
    from pydicom.pixel_data_handlers.util import apply_voi_lut
    HAS_PYDICOM = True
except ImportError:
    HAS_PYDICOM = False


def is_dicom(image_input):
    """
    Check if the input looks like a DICOM file.
    Works on bytes, paths, or file-like objects.
    """

    if not HAS_PYDICOM:
        return False

    try:
        if isinstance(image_input, bytes):
            if len(image_input) > 132:
                return image_input[128:132] == b"DICM"
            return False

        if isinstance(image_input, (str, Path)):
            with open(image_input, "rb") as f:
                f.seek(128)
                return f.read(4) == b"DICM"

    except Exception:
        return False

    return False


def _dicom_to_pil(dicom_data):
    """
    Convert a pydicom Dataset to a PIL.Image (RGB).
    Handles different photometric interpretations and bit depths.
    """

    import numpy as np

    pixel_data = dicom_data.pixel_array

    try:
        pixel_data = apply_voi_lut(pixel_data, dicom_data)
    except Exception:
        pass

    if pixel_data.dtype != "uint8":
        pixel_data = pixel_data.astype("float32")
        min_val = pixel_data.min()
        max_val = pixel_data.max()
        if max_val - min_val > 0:
            pixel_data = (pixel_data - min_val) / (max_val - min_val) * 255.0
        pixel_data = pixel_data.astype("uint8")

    photometric = getattr(dicom_data, "PhotometricInterpretation", "")
    if photometric == "MONOCHROME1":
        pixel_data = 255 - pixel_data

    if len(pixel_data.shape) == 2:
        img = Image.fromarray(pixel_data, mode="L")
    elif len(pixel_data.shape) == 3:
        img = Image.fromarray(pixel_data)
    else:
        raise ValueError(
            f"Unsupported pixel shape: {pixel_data.shape}"
        )

    return img.convert("RGB")


def load_image(image_input):
    """
    Universal loader. Accepts:
      - bytes
      - file path (str / Path)
      - PIL.Image (returns as-is)

    Returns:
      PIL.Image in RGB mode.
    """

    if isinstance(image_input, Image.Image):
        return image_input.convert("RGB")

    if HAS_PYDICOM and is_dicom(image_input):
        if isinstance(image_input, bytes):
            dicom_data = pydicom.dcmread(io.BytesIO(image_input))
        else:
            dicom_data = pydicom.dcmread(str(image_input))

        return _dicom_to_pil(dicom_data)

    if isinstance(image_input, bytes):
        img = Image.open(io.BytesIO(image_input))
    elif isinstance(image_input, (str, Path)):
        img = Image.open(image_input)
    else:
        raise TypeError(
            f"Unsupported image type: {type(image_input)}"
        )

    return img.convert("RGB")