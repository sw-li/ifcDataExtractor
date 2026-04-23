"""
Module 4 — Quantities extractor

Two-pass approach designed for audit use-cases where the IFC provider
cannot be asked to re-export:

  Pass 1 — Formal quantity sets (IfcElementQuantity)
            Standard IFC uses Qto_* names; Revit uses "BaseQuantities".
            All IfcElementQuantity instances are accepted regardless of name.

  Pass 2 — Numeric properties in IfcPropertySet
            Revit and other tools often embed lengths, areas and volumes as
            IfcPropertySingleValue whose NominalValue is a physical measure
            type (IfcAreaMeasure, IfcLengthMeasure, IfcVolumeMeasure, …).
            These are extracted here so auditors see them even when the
            exporter never wrote a proper IfcElementQuantity.

The 'source' column tells you which pass produced each row:
  'IfcElementQuantity'  — formal quantity set (Pass 1)
  'IfcPropertySet'      — numeric property mined from a pset (Pass 2)
"""

import pandas as pd
import ifcopenshell

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
    "IfcReal",
    "IfcInteger",
}


def extract(ifc_file: ifcopenshell.file, source_filename: str = "") -> pd.DataFrame:
    """
    Extract quantity data from an IFC file using both passes.

    Parameters
    ----------
    ifc_file : ifcopenshell.file
    source_filename : str

    Returns
    -------
    pd.DataFrame
        Columns: source_file, element_global_id, element_ifc_type,
                 element_name, qto_set_name, quantity_name,
                 quantity_value, quantity_type, unit, source.
    """
    unit_map = _build_unit_map(ifc_file)
    rows = []

    for rel in ifc_file.by_type("IfcRelDefinesByProperties"):
        prop_def = rel.RelatingPropertyDefinition

        # ── Pass 1: formal IfcElementQuantity ────────────────────────
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
                    rows.append(_row(source_filename, gid, itype, ename,
                                     qto_name, qty_name, qty_value,
                                     qty_type, unit, "IfcElementQuantity"))

        # ── Pass 2: numeric values inside IfcPropertySet ─────────────
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
                    rows.append(_row(source_filename, gid, itype, ename,
                                     pset_name, prop_name, value,
                                     measure_type, unit, "IfcPropertySet"))

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
        "source",
    ])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row(source_filename, gid, itype, ename,
         qto_name, qty_name, qty_value, qty_type, unit, source):
    return {
        "source_file":       source_filename,
        "element_global_id": gid,
        "element_ifc_type":  itype,
        "element_name":      ename,
        "qto_set_name":      qto_name,
        "quantity_name":     qty_name,
        "quantity_value":    qty_value,
        "quantity_type":     qty_type,
        "unit":              unit,
        "source":            source,
    }


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
            unit_map[ifc_types] = label
    return unit_map


def _unit_label_from_measure(measure_type: str, unit_map: dict) -> str:
    """Best-effort unit label for a measure type."""
    return unit_map.get(measure_type, "")
