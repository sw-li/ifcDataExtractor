"""
Module 3 — Property Sets extractor
Collects all Pset_* property sets via IfcRelDefinesByProperties.
MVP scope: IfcPropertySingleValue only.
Returns one row per property value (long/tall format).
"""

import pandas as pd
import ifcopenshell
from typing import Callable, Optional

# Column order
_COLUMNS = [
    "source_file",
    "element_global_id",
    "element_ifc_type",
    "element_name",
    "pset_name",
    "property_name",
    "property_value",
    "property_unit",
]

# Report progress every N relationships scanned
_PROGRESS_INTERVAL = 500


def extract(
    ifc_file: ifcopenshell.file,
    source_filename: str = "",
    progress_callback: Optional[Callable[[str], None]] = None,
) -> pd.DataFrame:
    """
    Extract all Pset_* property values for every element in the file.

    Parameters
    ----------
    ifc_file : ifcopenshell.file
    source_filename : str
    progress_callback : callable | None
        If provided, called with a status string every _PROGRESS_INTERVAL
        relationships scanned.

    Returns
    -------
    pd.DataFrame
        Columns: source_file, element_global_id, element_ifc_type,
                 element_name, pset_name, property_name,
                 property_value, property_unit.
    """
    # Column-oriented storage avoids per-row dict allocation overhead
    col_data: dict[str, list] = {c: [] for c in _COLUMNS}
    rel_count = 0

    for rel in ifc_file.by_type("IfcRelDefinesByProperties"):
        rel_count += 1
        if progress_callback and rel_count % _PROGRESS_INTERVAL == 0:
            progress_callback(f"    … {rel_count:,} relationships scanned")

        prop_def = rel.RelatingPropertyDefinition

        # Only handle property sets (not quantity sets — those go to quantities.py)
        if not prop_def.is_a("IfcPropertySet"):
            continue

        pset_name = getattr(prop_def, "Name", "") or ""

        # Skip IfcElementQuantity sets — those are handled by quantities.py
        # Accept ALL IfcPropertySet names: Pset_*, custom Revit sets, etc.
        if not pset_name:
            continue

        for element in rel.RelatedObjects or []:
            global_id    = getattr(element, "GlobalId", "") or ""
            ifc_type     = element.is_a()
            element_name = getattr(element, "Name", "") or ""

            for prop in prop_def.HasProperties or []:
                if not prop.is_a("IfcPropertySingleValue"):
                    # IfcPropertyEnumeratedValue and IfcComplexProperty deferred (MVP)
                    continue

                prop_name     = getattr(prop, "Name", "") or ""
                nominal_value = prop.NominalValue
                prop_value    = (
                    str(getattr(nominal_value, "wrappedValue", ""))
                    if nominal_value else ""
                )
                prop_unit = _get_unit_label(prop)

                col_data["source_file"].append(source_filename)
                col_data["element_global_id"].append(global_id)
                col_data["element_ifc_type"].append(ifc_type)
                col_data["element_name"].append(element_name)
                col_data["pset_name"].append(pset_name)
                col_data["property_name"].append(prop_name)
                col_data["property_value"].append(prop_value)
                col_data["property_unit"].append(prop_unit)

    if progress_callback and rel_count > 0:
        progress_callback(f"    … {rel_count:,} relationships total")

    return pd.DataFrame(col_data)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_unit_label(prop) -> str:
    """Return a unit label string from an IfcPropertySingleValue, if present."""
    unit = getattr(prop, "Unit", None)
    if unit is None:
        return ""
    # IfcNamedUnit
    name = getattr(unit, "Name", None)
    if name:
        prefix = getattr(unit, "Prefix", "") or ""
        return f"{prefix}{name}".strip()
    # IfcDerivedUnit
    us