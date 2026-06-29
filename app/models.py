from typing import Optional

from pydantic import BaseModel, Field


class ExtractedFilament(BaseModel):
    """What the vision model reads off a filament package.

    Every field is optional — packaging varies, and the model should leave a
    field null rather than guess when the information isn't visible.
    """

    brand: Optional[str] = Field(
        None, description="Manufacturer / vendor, e.g. 'Prusament', 'Polymaker', 'eSUN'."
    )
    material: Optional[str] = Field(
        None, description="Material type, e.g. 'PLA', 'PETG', 'ABS', 'ASA', 'TPU'."
    )
    color_name: Optional[str] = Field(
        None, description="Printed color / variant name, e.g. 'Galaxy Black'."
    )
    color_hex: Optional[str] = Field(
        None,
        description="Best-estimate color as a 6-digit hex code without '#', "
        "based on the printed color name and the spool's visible color.",
    )
    diameter_mm: Optional[float] = Field(
        None, description="Filament diameter in mm, usually 1.75 or 2.85."
    )
    net_weight_g: Optional[float] = Field(
        None, description="Net filament weight in grams, e.g. 1000 for a 1kg spool."
    )
    spool_weight_g: Optional[float] = Field(
        None, description="Empty spool weight in grams, if printed on the package."
    )
    density_g_cm3: Optional[float] = Field(
        None, description="Material density in g/cm^3, only if printed on the package."
    )
    extruder_temp_c: Optional[int] = Field(
        None, description="Recommended nozzle/extruder temperature in Celsius."
    )
    bed_temp_c: Optional[int] = Field(
        None, description="Recommended bed temperature in Celsius."
    )
    article_number: Optional[str] = Field(
        None, description="SKU / article / product number if visible."
    )
    notes: Optional[str] = Field(
        None, description="Anything else useful printed on the package."
    )


class CreateRequest(BaseModel):
    """The (user-reviewed) payload sent back to create the Spoolman records."""

    brand: Optional[str] = None
    material: Optional[str] = None
    color_name: Optional[str] = None
    color_hex: Optional[str] = None
    diameter_mm: float = 1.75
    net_weight_g: Optional[float] = None
    spool_weight_g: Optional[float] = None
    density_g_cm3: float = 1.24
    extruder_temp_c: Optional[int] = None
    bed_temp_c: Optional[int] = None
    article_number: Optional[str] = None
    price: Optional[float] = None
    lot_nr: Optional[str] = None
    comment: Optional[str] = None
