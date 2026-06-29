import base64

from anthropic import Anthropic

from .config import settings
from .models import ExtractedFilament

SYSTEM_PROMPT = """\
You are an expert at reading 3D printer filament packaging and spool labels.
Given a photo of a filament package or spool, extract the product details into
the structured schema.

Rules:
- Only report what you can actually see or confidently infer from the label.
  Leave a field null rather than guessing.
- `material` should be the short code (PLA, PLA+, PETG, ABS, ASA, TPU, PC,
  Nylon/PA, PVA, HIPS, etc.), not a marketing name.
- `color_hex` is your best estimate of the actual filament color as a 6-digit
  hex code (no leading '#'), informed by the printed color name and the visible
  color of the spool/filament in the photo.
- `diameter_mm` is almost always 1.75 or 2.85.
- `net_weight_g` is the filament weight (e.g. 1000 for "1 kg"), not gross weight.
- Temperatures are in Celsius. If a range is printed, use a representative
  midpoint.
"""

USER_PROMPT = (
    "Extract the filament details from this package photo into the schema. "
    "Leave anything you cannot read as null."
)

_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def analyze_image(image_bytes: bytes, media_type: str) -> ExtractedFilament:
    """Send the image to Claude and return structured filament data."""
    if media_type not in _MEDIA_TYPES:
        raise ValueError(f"Unsupported image media type: {media_type}")

    client = Anthropic(api_key=settings.anthropic_api_key)
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    response = client.messages.parse(
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
        output_format=ExtractedFilament,
    )

    parsed = response.parsed_output
    if parsed is None:
        raise RuntimeError("The model did not return structured data for this image.")
    return parsed
