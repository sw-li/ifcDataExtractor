"""
Module 4 — Quantities extractor

Single-pass approach: iterates IfcRelDefinesByProperties once, branching on
IfcElementQuantity vs IfcPropertySet inside the loop.

  Branch 1 — Formal quantity sets (IfcElementQuantity)
             Standard IFC uses Qto_* names; Revit uses "BaseQuantities".
             All IfcElementQuantity instances are accepted regardless of name.

  Branch 2 — Numeric properties in IfcPropertySet
             Revit and other tools often embed lengths, areas and volumes as
             IfcPropertySingleValue whose NominalValue is a physical measure
             type (IfcAreaMeasure, IfcLengthMeasure, IfcVolumeMeasure, …).
             These are extracted here so auditors see them even when the
             exporter never wrote a proper IfcElementQuantity.

The 'source' column tells you which branch produced each row:
  'IfcElementQuantity'  — formal quantity set (Branch 1)
  'IfcPropertySet'      — numeric property mined from a pset (Branch 2)
"""

import pandas as pd
import ifcopenshell
from typing import Callable, Optional

# IFC quantity sub-types and the attribute that holds their value
_QTY_VALUE_ATTRS = {
    "IfcQuantityLength": "LengthValue",
    "IfcQuantityArea":   "AreaValue",
    "IfcQuantityVolume": "VolumeValue",
    "IfcQuantityCount":  "CountValue",
    "IfcQuantityWeight": "WeightValue",
    "IfcQuantityTime":   "TimeValue",
}

# NominalValue type names that represent a physical numeric measure.
# These are the ones worth pulling out of IfcPropertySet for audit purposes.
_MEASURE_TYPES = {
    "IfcAreaMeasure",
    "IfcVolumeMeasure",
    "IfcLengthMeasure",
    "IfcPositiveLengthMeasure",
    "IfcMassMeasure",
    "IfcMassFlowRateMeasure",
    "IfcPlaneAngleMeasure",
    "IfcCountMeasure",
    "IfcTimeMeasure",
    "IfcThermodynamicTemperatureMeasure",
    "IfcPowerMeasure",
    "IfcPressureMeasure",
    "IfcLinearVelocityMeasure",
    "IfcVolumetricFlowRateMeasure",
    "IfcElectricCurrentMeasure",
    "IfcElectricVoltageMeasure",
    "IfcFrequencyMeasure",
    "IfcNumericMeasure",
    # NOTE: IfcReal and IfcInteger intentionally excluded — they are too
    # generic and capture non-physical values like counts, codes, years, etc.
}

# Column order
_COLUMNS = [
    "source_file",
    "element_global_id",
    "element_ifc_type",
    "element_name",
    "qto_set_name",
    "quantity_name",
    "quantity_value",
    "quantity_type",
    "unit",
    "source",
]

# Report progress every N relationships scanned
_PROGRESS_INTERVAL = 500


def extract(
    ifc_file: ifcopenshell.file,
    source_filename: str = "",
    progress_callback: Optional[Callable[[str], None]] = None,
) -> pd.DataFrame:
    """
    Extract quantity data from an IFC file in a single pass.

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
                 element_name, qto_set_name, quantity_name,
                 quantity_value, quantity_type, unit, source.
    """
    unit_map = _build_unit_map(ifc_file)

    # Column-oriented storage avoids per-row dict allocation overhead
    col_data: dict[str, list] = {c: [] for c in _COLUMNS}
    rel_count = 0

    for rel in ifc_file.by_type("IfcRelDefinesByProperties"):
        rel_count += 1
        if progress_callback and rel_count % _PROGRESS_INTERVAL == 0:
            progress_callback(f"    … {rel_count:,} relationships scanned")

        prop_def = rel.RelatingPropertyDefinition

        # ── Branch 1: formal IfcElementQuantity ──────────────────────────
        if prop_def.is_a("IfcElementQuantity"):
            qto_name = getattr(prop_def, "Name", "") or ""
            for element in rel.RelatedObjects or []:
                gid   = getattr(element, "GlobalId", "") or ""
                itype = element.is_a()
                ename = getattr(element, "Name", "") or ""
                for qty in prop_def.Quantities or []:
                    qty_type   = qty.is_a()
                    qty_name   = getattr(qty, "Name", "") or ""
                    value_attr = _QTY_VALUE_ATTRS.get(qty_type)
                    qty_value  = getattr(qty, value_attr, None) if value_attr else None
                    unit       = unit_map.get(qty_type, "")
                    _append_row(col_data, source_filename, gid, itype, ename,
                                qto_name, qty_name, qty_value,
                                qty_type, unit, "IfcElementQuantity")

        # ── Branch 2: numeric values inside IfcPropertySet ───────────────
        elif prop_def.is_a("IfcPropertySet"):
            pset_name = getattr(prop_def, "Name", "") or ""
            for element in rel.RelatedObjects or []:
                gid   = getattr(element, "GlobalId", "") or ""
                itype = element.is_a()
                ename = getattr(element, "Name", "") or ""
                for prop in prop_def.HasProperties or []:
                    if not prop.is_a("IfcPropertySingleValue"):
                        continue
                    nominal = prop.NominalValue
                    if nominal is None:
                        continue
                    measure_type = nominal.is_a()
                    if measure_type not in _MEASURE_TYPES:
                        continue
                    prop_name = getattr(prop, "Name", "") or ""
                    value     = getattr(nominal, "wrappedValue", None)
                    # Skip non-numeric or zero-ish noise
                    try:
                        float(value)
                    except (TypeError, ValueError):
                        continue
                    unit = _unit_label_from_measure(measure_type, unit_map)
                    _append_row(col_data, source_filename, gid, itype, ename,
                                pset_name, prop_name, value,
                                measure_type, unit, "IfcPropertySet")

    if progress_callback and rel_count > 0:
        progress_callback(f"    … {rel_count:,} relationships total")

    return pd.DataFrame(col_data)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _append_row(
    col_data: dict,
    source_filename: str,
    gid: str, itype: str, ename: str,
    qto_name: str, qty_name: str, qty_value,
    qty_type: str, unit: str, source: str,
) -> None:
    col_data["source_file"].append(source_filename)
    col_data["element_global_id"].append(gid)
    col_data["element_ifc_type"].append(itype)
    col_data["element_name"].append(ename)
    col_data["qto_set_name"].append(qto_name)
    col_data["quantity_name"].append(qty_name)
    col_data["quantity_value"].append(qty_value)
    col_data["quantity_type"].append(qty_type)
    col_data["unit"].append(unit)
    col_data["source"].append(source)


def _build_unit_map(ifc_file: ifcopenshell.file) -> dict:
    """Map IFC quantity type → unit label from the project unit assignment."""
    unit_map = {}
    projects = ifc_file.by_type("IfcProject")
    if not projects:
        return unit_map
    unit_assignment = getattr(projects[0], "UnitsInContext", None)
    if unit_assignment is None:
        return unit_map
    for unit in unit_assignment.Units or []:
        unit_type = getattr(unit, "UnitType", "")
        name      = getattr(unit, "Name", "") or ""
        prefix    = getattr(unit, "Prefix", "") or ""
        label     = f"{prefix}{name}".strip()
        mapping   = {
            "LENGTHUNIT":      ["IfcQuantityLength", "IfcLengthMeasure", "IfcPositiveLengthMeasure"],
            "AREAUNIT":        ["IfcQuantityArea",   "IfcAreaMeasure"],
            "VOLUMEUNIT":      ["IfcQuantityVolume", "IfcVolumeMeasure"],
            "MASSUNIT":        ["IfcQuantityWeight", "IfcMassMeasure"],
            "TIMEUNIT":        ["IfcQuantityTime",   "IfcTimeMeasure"],
            "THERMODYNAMICTEMPERATUREUNIT": ["IfcThermodynamicTemperatureMeasure"],
            "POWERUNIT":       ["IfcPowerMeasure"],
            "PRESSUREUNIT":    ["IfcPressureMeasure"],
            "ELECTRICCURRENTUNIT": ["IfcElectricCurrentMeasure"],
            "ELECTRICVOLTAGEUNIT": ["IfcElectricVoltageMeasure"],
            "FREQUENCYUNIT":   ["IfcFrequencyMeasure"],
        }
        for ifc_types in mapping.get(unit_type, []):
            