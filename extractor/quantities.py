"""
Module 4 — Quantities extractor
Collects all Qto_* quantity sets via IfcRelDefinesByProperties where the
definition is an IfcElementQuantity.
Returns one row per quantity value.
"""

import pandas as pd
import ifcopenshell


# Map IFC quantity measure types to their attribute names
_QTY_VALUE_ATTRS = {
    "IfcQuantityLength": "LengthValue",
    "IfcQuantityArea": "AreaValue",
    "IfcQuantityVolume": "VolumeValue",
    "IfcQuantityCount": "CountValue",
    "IfcQuantityWeight": "WeightValue",
    "IfcQuantityTime": "TimeValue",
}


def extract(ifc_file: ifcopenshell.file, source_filename: str = "") -> pd.DataFrame:
    """
    Extract all Qto_* quantity values for every element in the file.

    Parameters
    ----------
    ifc_file : ifcopenshell.file
    source_filename : str

    Returns
    -------
    pd.DataFrame
        Columns: source_file, element_global_id, element_ifc_type,
                 element_name, qto_set_name, quantity_name,
                 quantity_value, quantity_type, unit.
    """
    rows = []

    # Build a unit map from project units for later lookup
    unit_map = _build_unit_map(ifc_file)

    for rel in ifc_file.by_type("IfcRelDefinesByProperties"):
        prop_def = rel.RelatingPropertyDefinition

        if not prop_def.is_a("IfcElementQuantity"):
            continue

        qto_name = getattr(prop_def, "Name", "") or ""

        for element in rel.RelatedObjects or []:
            global_id = getattr(element, "GlobalId", "") or ""
            ifc_type = element.is_a()
            element_name = getattr(element, "Name", "") or ""

            for qty in prop_def.Quantities or []:
                qty_type = qty.is_a()
                qty_name = getattr(qty, "Name", "") or ""
                value_attr = _QTY_VALUE_ATTRS.get(qty_type)
                qty_value = getattr(qty, value_attr, None) if value_attr else None
                unit = unit_map.get(qty_type, "")

                rows.append({
                    "source_file": source_filename,
                    "element_global_id": global_id,
                    "element_ifc_type": ifc_type,
                    "element_name": element_name,
                    "qto_set_name": qto_name,
                    "quantity_name": qty_name,
                    "quantity_value": qty_value,
                    "quantity_type": qty_type,
                    "unit": unit,
                })

    return pd.DataFrame(rows, columns=[
        "source_file",
        "element_global_id",
        "element_ifc_type",
        "element_name",
        "qto_set_name",
        "quantity_name",
        "quantity_value",
        "quantity_type",
        "unit",
    ])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_unit_map(ifc_file: ifcopenshell.file) -> dict:
    """
    Build a lightweight mapping from IFC quantity type → unit label,
    derived from the project's IfcUnitAssignment.
    """
    unit_map = {}
    projects = ifc_file.by_type("IfcProject")
    if not projects:
        return unit_map

    unit_assignment = getattr(projects[0], "UnitsInContext", None)
    if unit_assignment is None:
        return unit_map

    for unit in unit_assignment.Units or []:
        unit_type = getattr(unit, "UnitType", "")
        name = getattr(unit, "Name", "") or ""
        prefix = getattr(unit, "Prefix", "") or ""
        label = f"{prefix}{name}".strip()

        if unit_type == "LENGTHUNIT":
            unit_map["IfcQuantityLength"] = label
        elif unit_type == "AREAUNIT":
            unit_map["IfcQuantityArea"] = label
        elif unit_type == "VOLUMEUNIT":
            unit_map["IfcQuantityVolume"] = label
        elif unit_type == "MASSUNIT":
            unit_map["IfcQuantityWeight"] = label
        elif unit_type == "TIMEUNIT":
            unit_map["IfcQuantityTime"] = label

    return unit_map
