from typing import Optional

import httpx

from .models import CreateRequest, ExtractedFilament

# Fallback densities (g/cm^3) by material, used when the package doesn't print
# one. Spoolman requires a density to create a filament.
DENSITY_BY_MATERIAL = {
    "PLA": 1.24,
    "PLA+": 1.24,
    "PLA-CF": 1.30,
    "PETG": 1.27,
    "PET": 1.27,
    "PETG-CF": 1.30,
    "ABS": 1.04,
    "ASA": 1.07,
    "TPU": 1.21,
    "TPE": 1.21,
    "PC": 1.20,
    "NYLON": 1.14,
    "PA": 1.14,
    "PA-CF": 1.20,
    "PVA": 1.23,
    "HIPS": 1.04,
    "PP": 0.90,
    "WOOD": 1.28,
}

DEFAULT_DENSITY = 1.24
DEFAULT_DIAMETER = 1.75

# Fallback nozzle temperature ranges (min, max) in Celsius, used to pre-fill the
# review form (and the OpenSpool tag) when the package doesn't print them.
EXTRUDER_TEMP_BY_MATERIAL = {
    "PLA": (190, 220),
    "PLA+": (200, 230),
    "PLA-CF": (200, 230),
    "PETG": (230, 250),
    "PET": (230, 250),
    "PETG-CF": (240, 260),
    "ABS": (230, 260),
    "ASA": (240, 260),
    "TPU": (210, 230),
    "TPE": (210, 230),
    "PC": (260, 300),
    "NYLON": (240, 270),
    "PA": (240, 270),
    "PA-CF": (250, 280),
    "PVA": (190, 220),
    "HIPS": (230, 245),
    "PP": (220, 250),
}

# Fallback bed temperature ranges (min, max) in Celsius by material.
BED_TEMP_BY_MATERIAL = {
    "PLA": (50, 60),
    "PLA+": (55, 65),
    "PLA-CF": (55, 65),
    "PETG": (70, 85),
    "PET": (70, 85),
    "PETG-CF": (70, 85),
    "ABS": (90, 110),
    "ASA": (90, 110),
    "TPU": (40, 60),
    "TPE": (40, 60),
    "PC": (100, 120),
    "NYLON": (70, 90),
    "PA": (70, 90),
    "PA-CF": (80, 100),
    "PVA": (45, 60),
    "HIPS": (90, 110),
    "PP": (85, 100),
}


def clean_hex(value: Optional[str]) -> Optional[str]:
    """Normalize a color to a 6-digit hex string without '#', or None."""
    if not value:
        return None
    h = value.strip().lstrip("#")
    if len(h) == 6 and all(c in "0123456789abcdefABCDEF" for c in h):
        return h.upper()
    return None


def density_for_material(material: Optional[str]) -> Optional[float]:
    if not material:
        return None
    return DENSITY_BY_MATERIAL.get(material.strip().upper())


def extruder_range_for_material(material: Optional[str]) -> tuple:
    if not material:
        return (None, None)
    return EXTRUDER_TEMP_BY_MATERIAL.get(material.strip().upper(), (None, None))


def bed_range_for_material(material: Optional[str]) -> tuple:
    if not material:
        return (None, None)
    return BED_TEMP_BY_MATERIAL.get(material.strip().upper(), (None, None))


def _midpoint(low, high):
    values = [v for v in (low, high) if v is not None]
    return round(sum(values) / len(values)) if values else None


def apply_defaults(extracted: ExtractedFilament) -> dict:
    """Fill in the fields Spoolman requires (density, diameter) and the nozzle
    temperature range (for the OpenSpool tag) so the review form is
    pre-populated with sensible values the user can override."""
    density = (
        extracted.density_g_cm3
        or density_for_material(extracted.material)
        or DEFAULT_DENSITY
    )
    ext_min, ext_max = extruder_range_for_material(extracted.material)
    bed_min, bed_max = bed_range_for_material(extracted.material)
    return {
        "brand": extracted.brand,
        "material": extracted.material,
        "variant": extracted.variant,
        "color_name": extracted.color_name,
        "color_hex": clean_hex(extracted.color_hex),
        "diameter_mm": extracted.diameter_mm or DEFAULT_DIAMETER,
        "net_weight_g": extracted.net_weight_g,
        "spool_weight_g": extracted.spool_weight_g,
        "density_g_cm3": density,
        "extruder_temp_min_c": extracted.extruder_temp_min_c or ext_min,
        "extruder_temp_max_c": extracted.extruder_temp_max_c or ext_max,
        "bed_temp_min_c": extracted.bed_temp_min_c or bed_min,
        "bed_temp_max_c": extracted.bed_temp_max_c or bed_max,
        "article_number": extracted.article_number,
        "price": None,
        "lot_nr": extracted.lot_nr,
        "comment": extracted.notes,
    }


def build_openspool(req: CreateRequest, spool_id: int) -> dict:
    """Assemble the NDEF JSON payload written to the NFC tag.

    Follows the OpenSpool format (an application/json record) and, like
    SpoolPainter / OpenSpoolMan, adds a `spool_id` linking the tag to the
    Spoolman spool. Extra keys (variant, bed temps) are additive; OpenSpool
    readers ignore fields they don't recognise.
    """
    # Field names, ordering, and string typing match real SpoolPainter tag
    # dumps: all temperatures AND spool_id are strings; the product line is
    # written as `subtype`.
    payload = {
        "protocol": "openspool",
        "version": "1.0",
        "type": (req.material or "").strip(),
        "color_hex": clean_hex(req.color_hex) or "FFFFFF",
        "brand": (req.brand or "Generic").strip(),
    }
    if req.extruder_temp_min_c is not None:
        payload["min_temp"] = str(int(req.extruder_temp_min_c))
    if req.extruder_temp_max_c is not None:
        payload["max_temp"] = str(int(req.extruder_temp_max_c))
    if req.bed_temp_min_c is not None:
        payload["bed_min_temp"] = str(int(req.bed_temp_min_c))
    if req.bed_temp_max_c is not None:
        payload["bed_max_temp"] = str(int(req.bed_temp_max_c))
    payload["spool_id"] = str(spool_id)
    if req.variant and req.variant.strip():
        payload["subtype"] = req.variant.strip()
    if req.lot_nr and req.lot_nr.strip():
        payload["lot_nr"] = req.lot_nr.strip()
    return payload


class SpoolmanClient:
    """Thin async client for the Spoolman REST API (/api/v1)."""

    def __init__(self, base_url: str, public_url: Optional[str] = None):
        self.base = base_url.rstrip("/")
        self.api = f"{self.base}/api/v1"
        # Used only for user-clickable links; the backend may reach Spoolman at
        # an internal address that the browser cannot.
        self.public = (public_url or base_url).rstrip("/")

    async def ping(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.api}/info")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def _find_or_create_vendor(
        self, client: httpx.AsyncClient, name: str
    ) -> int:
        resp = await client.get(f"{self.api}/vendor")
        resp.raise_for_status()
        target = name.strip().lower()
        for vendor in resp.json():
            if (vendor.get("name") or "").strip().lower() == target:
                return vendor["id"]
        resp = await client.post(f"{self.api}/vendor", json={"name": name.strip()})
        resp.raise_for_status()
        return resp.json()["id"]

    async def create_all(self, req: CreateRequest) -> dict:
        """Create vendor (if needed), filament, and one full spool."""
        async with httpx.AsyncClient(timeout=30) as client:
            vendor_id: Optional[int] = None
            if req.brand and req.brand.strip():
                vendor_id = await self._find_or_create_vendor(client, req.brand)

            filament: dict = {
                "diameter": req.diameter_mm,
                "density": req.density_g_cm3,
            }
            base_name = req.color_name or req.material
            name = " ".join(p for p in (base_name, req.variant) if p) or None
            if name:
                filament["name"] = name
            if vendor_id is not None:
                filament["vendor_id"] = vendor_id
            if req.material:
                filament["material"] = req.material
            if req.net_weight_g is not None:
                filament["weight"] = req.net_weight_g
            if req.spool_weight_g is not None:
                filament["spool_weight"] = req.spool_weight_g
            hex_value = clean_hex(req.color_hex)
            if hex_value:
                filament["color_hex"] = hex_value
            # Spoolman stores single recommended temps; use the range midpoints.
            extruder_temp = _midpoint(req.extruder_temp_min_c, req.extruder_temp_max_c)
            if extruder_temp is not None:
                filament["settings_extruder_temp"] = extruder_temp
            bed_temp = _midpoint(req.bed_temp_min_c, req.bed_temp_max_c)
            if bed_temp is not None:
                filament["settings_bed_temp"] = bed_temp
            if req.article_number:
                filament["article_number"] = req.article_number
            if req.price is not None:
                filament["price"] = req.price

            resp = await client.post(f"{self.api}/filament", json=filament)
            resp.raise_for_status()
            filament_obj = resp.json()

            spool: dict = {"filament_id": filament_obj["id"]}
            if req.net_weight_g is not None:
                # A brand-new spool starts full.
                spool["remaining_weight"] = req.net_weight_g
            if req.price is not None:
                spool["price"] = req.price
            if req.lot_nr:
                spool["lot_nr"] = req.lot_nr
            if req.comment:
                spool["comment"] = req.comment

            resp = await client.post(f"{self.api}/spool", json=spool)
            resp.raise_for_status()
            spool_obj = resp.json()

            return {
                "vendor_id": vendor_id,
                "filament_id": filament_obj["id"],
                "spool_id": spool_obj["id"],
                "spool_url": f"{self.public}/spool/show/{spool_obj['id']}",
                "openspool": build_openspool(req, spool_obj["id"]),
            }
