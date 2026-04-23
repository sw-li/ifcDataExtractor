"""
Module 1 — Metadata extractor
Reads the IFC file header and IfcProject entity.
Returns a one-row DataFrame per file (suitable for a summary sheet).
"""

import pandas as pd
import ifcopenshell


def extract(ifc_file: ifcopenshell.file, source_filename: str = "") -> pd.DataFrame:
    """
    Extract project metadata from an open IFC file.

    Parameters
    ----------
    ifc_file : ifcopenshell.file
        An already-opened IFC file.
    source_filename : str
        Original filename — included as a column so merged exports stay traceable.

    Returns
    -------
    pd.DataFrame
        One row with all metadata fields.
    """
    header = ifc_file.header

    # --- FILE_NAME header ---
    file_name_header = header.file_name
    timestamp = getattr(file_name_header, "time_stamp", "")
    author = ", ".join(getattr(file_name_header, "author", []) or [])
    organization = ", ".join(getattr(file_name_header, "organization", []) or [])
    originating_system = getattr(file_name_header, "originating_system", "")

    # --- IfcProject entity ---
    projects = ifc_file.by_type("IfcProject")
    project = projects[0] if projects else None

    project_name = getattr(project, "Name", "") or ""
    project_description = getattr(project, "Description", "") or ""
    project_phase = getattr(project, "Phase", "") or ""

    # --- Units ---
    units = _extract_units(ifc_file, project)

    row = {
        "source_file": source_filename,
        "schema_version": ifc_file.schema,
        "timestamp": timestamp,
        "author": author,
        "organization": organization,
        "originating_system": originating_system,
        "project_name": project_name,
        "project_description": project_description,
        "project_phase": project_phase,
        "units": units,
    }

    return pd.DataFrame([row])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_units(ifc_file: ifcopenshell.file, project) -> str:
    """Return a human-readable string summarising the project unit assignment."""
    if project is None:
        return ""

    unit_assignment = getattr(project, "UnitsInContext", None)
    if unit_assignment is None:
        return ""

    unit_strings = []
    for unit in unit_assignment.Units or []:
        unit_type = getattr(unit, "UnitType", "")
        name = getattr(unit, "Name", "") or getattr(unit, "Prefix", "")
        if unit_type and name:
            unit_strings.append(f"{unit_type}={name}")

    return "; ".join(unit_strings)
