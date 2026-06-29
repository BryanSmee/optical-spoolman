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


def apply_defaults(extracted: ExtractedFilament) -> dict:
    """Fill in the fields Spoolman requires (density, diameter) so the review
    form is pre-populated with sensible values the user can override."""
    density = (
        extracted.density_g_cm3
        or density_for_material(extracted.material)
        or DEFAULT_DENSITY
    )
    return {
        "brand": extracted.brand,
        "material": extracted.material,
        "color_name": extracted.color_name,
        "color_hex": clean_hex(extracted.color_hex),
        "diameter_mm": extracted.diameter_mm or DEFAULT_DIAMETER,
        "net_weight_g": extracted.net_weight_g,
        "spool_weight_g": extracted.spool_weight_g,
        "density_g_cm3": density,
        "extruder_temp_c": extracted.extruder_temp_c,
        "bed_temp_c": extracted.bed_temp_c,
        "article_number": extracted.article_number,
        "price": None,
        "lot_nr": None,
        "comment": extracted.notes,
    }


class SpoolmanClient:
    """Thin async client for the Spoolman REST API (/api/v1)."""

    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")
        self.api = f"{self.base}/api/v1"

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
            name = req.color_name or req.material
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
            if req.extruder_temp_c is not None:
                filament["settings_extruder_temp"] = req.extruder_temp_c
            if req.bed_temp_c is not None:
                filament["settings_bed_temp"] = req.bed_temp_c
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
                "spool_url": f"{self.base}/spool/show/{spool_obj['id']}",
            }
