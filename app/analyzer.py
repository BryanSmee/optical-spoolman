import base64
import json

from anthropic import Anthropic

from .config import settings
from .models import ExtractedFilament

_FIELDS = (
    "brand, material, variant, color_name, color_hex, diameter_mm, "
    "net_weight_g, spool_weight_g, density_g_cm3, extruder_temp_min_c, "
    "extruder_temp_max_c, bed_temp_min_c, bed_temp_max_c, article_number, "
    "lot_nr, notes"
)

SYSTEM_PROMPT = f"""\
You are an expert at reading 3D printer filament packaging and spool labels.
Given a photo of a filament package or spool, extract the product details.

Respond with ONLY a single JSON object (no prose, no markdown code fences) with
exactly these keys: {_FIELDS}.

Rules:
- Use null for any value you cannot read or confidently infer. Do not guess.
- `material` is the short code (PLA, PLA+, PETG, ABS, ASA, TPU, PC, Nylon/PA,
  PVA, HIPS, ...), not a marketing name.
- `variant` is the product line / sub-type if the package shows one (e.g. 'HS',
  'High Speed', 'Premium', 'Matte', 'Silk'); null otherwise.
- `color_hex` is your best estimate of the actual filament color as 6 hex digits
  WITHOUT a leading '#', informed by the printed color name and the visible
  color of the spool/filament.
- `diameter_mm` is almost always 1.75 or 2.85.
- `net_weight_g` is the filament weight in grams (e.g. 1000 for "1 kg"), not the
  gross weight.
- Temperatures are in Celsius. Read the printed nozzle/extruder range into
  extruder_temp_min_c / extruder_temp_max_c and the bed range into
  bed_temp_min_c / bed_temp_max_c. If only a single temperature is printed for
  either, use it for both min and max.
- `lot_nr` is the lot / batch number if printed on the package; null otherwise.
- All numeric fields must be plain numbers with no units.
"""

USER_PROMPT = (
    "Extract the filament details from this package photo as the JSON object "
    "described. Leave anything you cannot read as null."
)

_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def _parse_json_object(text: str) -> dict:
    """Pull the JSON object out of the model's text response."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("The model did not return a JSON object.")
    return json.loads(text[start : end + 1])


def analyze_image(image_bytes: bytes, media_type: str) -> ExtractedFilament:
    """Send the image to Claude and return structured filament data."""
    if media_type not in _MEDIA_TYPES:
        raise ValueError(f"Unsupported image media type: {media_type}")

    client = Anthropic(api_key=settings.anthropic_api_key)
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": USER_PROMPT},
                ],
            }
        ],
    )

    text = "".join(block.text for block in response.content if block.type == "text")
    data = _parse_json_object(text)
    return ExtractedFilament.model_validate(data)
