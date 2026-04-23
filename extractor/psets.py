"""
Module 3 — Property Sets extractor
Collects all Pset_* property sets via IfcRelDefinesByProperties.
MVP scope: IfcPropertySingleValue only.
Returns one row per property value (long/tall format).
"""

import pandas as pd
import ifcopenshell


def extract(ifc_file: ifcopenshell.file, source_filename: str = "") -> pd.DataFrame:
    """
    Extract all Pset_* property values for every element in the file.

    Parameters
    ----------
    ifc_file : ifcopenshell.file
    source_filename : str

    Returns
    -------
    pd.DataFrame
        Columns: source_file, element_global_id, element_ifc_type,
                 element_name, pset_name, property_name,
                 property_value, property_unit.
    """
    rows = []

    for rel in ifc_file.by_type("IfcRelDefinesByProperties"):
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
            global_id = getattr(element, "GlobalId", "") or ""
            ifc_type = element.is_a()
            element_name = getattr(element, "Name", "") or ""

            for prop in prop_def.HasProperties or []:
                if not prop.is_a("IfcPropertySingleValue"):
                    # IfcPropertyEnumeratedValue and IfcComplexProperty deferred (MVP)
                    continue

                prop_name = getattr(prop, "Name", "") or ""
                nominal_value = prop.NominalValue
                prop_value = str(getattr(nominal_value, "wrappedValue", "")) if nominal_value else ""
                prop_unit = _get_unit_label(prop)

                rows.append({
                    "source_file": source_filename,
                    "element_global_id": global_id,
                    "element_ifc_type": ifc_type,
                    "element_name": element_name,
                    "pset_name": pset_name,
                    "property_name": prop_name,
                    "property_value": prop_value,
                    "property_unit": prop_unit,
                })

    return pd.DataFrame(rows, columns=[
        "source_file",
        "element_global_id",
        "element_ifc_type",
        "element_name",
        "pset_name",
        "property_name",
        "property_value",
        "property_unit",
    ])


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
    user_defined = getattr(unit, "UserDefinedType", None)
    if user_defined:
        return str(user_defined)
    return ""
