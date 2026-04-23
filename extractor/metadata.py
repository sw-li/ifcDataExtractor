"""
Module 1 — Metadata extractor
Reads the IFC file header, IfcProject entity, and all georeferencing data.

Georeferencing sources (works for both IFC2X3 and IFC4):
  - IfcSite.RefLatitude / RefLongitude / RefElevation
  - IfcGeometricRepresentationContext.TrueNorth
  - IfcMapConversion       (IFC4 — Eastings, Northings, scale, rotation)
  - IfcProjectedCRS        (IFC4 — EPSG code, datum, projection, zone)

Returns a one-row DataFrame per file (suitable for a summary sheet).
"""

import pandas as pd
import ifcopenshell


def extract(
    ifc_file: ifcopenshell.file,
    source_filename: str = "",
    progress_callback=None,   # accepted for API consistency; metadata is fast
) -> pd.DataFrame:
    """
    Extract project metadata and georeferencing from an open IFC file.

    Parameters
    ----------
    ifc_file : ifcopenshell.file
    source_filename : str

    Returns
    -------
    pd.DataFrame  — one row with all metadata + georeference fields.
    """
    # ── File header ───────────────────────────────────────────────────
    file_name_header = ifc_file.header.file_name
    timestamp          = getattr(file_name_header, "time_stamp", "") or ""
    author             = ", ".join(getattr(file_name_header, "author", []) or [])
    organization       = ", ".join(getattr(file_name_header, "organization", []) or [])
    originating_system = getattr(file_name_header, "originating_system", "") or ""

    # ── IfcProject ────────────────────────────────────────────────────
    projects = ifc_file.by_type("IfcProject")
    project  = projects[0] if projects else None

    project_name        = getattr(project, "Name", "")        or ""
    project_description = getattr(project, "Description", "") or ""
    project_phase       = getattr(project, "Phase", "")       or ""
    units               = _extract_units(ifc_file, project)

    # ── IfcSite (lat / lon / elevation) ──────────────────────────────
    sites = ifc_file.by_type("IfcSite")
    site  = sites[0] if sites else None

    site_name      = getattr(site, "Name", "")      or ""
    site_latitude  = _compound_angle(getattr(site, "RefLatitude",  None))
    site_longitude = _compound_angle(getattr(site, "RefLongitude", None))
    site_elevation = getattr(site, "RefElevation", None)
    site_land_title = getattr(site, "LandTitleNumber", "") or ""

    # ── True North (from IfcGeometricRepresentationContext) ───────────
    true_north = _extract_true_north(ifc_file)

    # ── IfcMapConversion + IfcProjectedCRS (IFC4 only) ────────────────
    map_conv = _extract_map_conversion(ifc_file)
    proj_crs = _extract_projected_crs(ifc_file)

    row = {
        # File / project
        "source_file":         source_filename,
        "schema_version":      ifc_file.schema,
        "timestamp":           timestamp,
        "author":              author,
        "organization":        organization,
        "originating_system":  originating_system,
        "project_name":        project_name,
        "project_description": project_description,
        "project_phase":       project_phase,
        "units":               units,
        # Site
        "site_name":           site_name,
        "site_land_title":     site_land_title,
        "latitude_dd":         site_latitude,
        "longitude_dd":        site_longitude,
        "site_elevation_m":    site_elevation,
        # True North
        "true_north_deg":      true_north,
        # IfcMapConversion (IFC4)
        "map_eastings":        map_conv.get("Eastings"),
        "map_northings":       map_conv.get("Northings"),
        "map_orthogonal_height": map_conv.get("OrthogonalHeight"),
        "map_x_axis_abscissa": map_conv.get("XAxisAbscissa"),
        "map_x_axis_ordinate": map_conv.get("XAxisOrdinate"),
        "map_scale":           map_conv.get("Scale"),
        # IfcProjectedCRS (IFC4)
        "crs_name":            proj_crs.get("Name"),
        "crs_description":     proj_crs.get("Description"),
        "crs_geodetic_datum":  proj_crs.get("GeodeticDatum"),
        "crs_map_projection":  proj_crs.get("MapProjection"),
        "crs_map_zone":        proj_crs.get("MapZone"),
    }

    return pd.DataFrame([row])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compound_angle(value) -> float | None:
    """
    Convert an IfcCompoundPlaneAngleMeasure (list of
    [degrees, minutes, seconds, (microseconds)]) to decimal degrees.
    Returns None if value is absent.
    """
    if value is None:
        return None
    try:
        parts = list(value)
        deg = parts[0] if len(parts) > 0 else 0
        mnt = parts[1] if len(parts) > 1 else 0
        sec = parts[2] if len(parts) > 2 else 0
        mic = parts[3] if len(parts) > 3 else 0
        sign = -1 if deg < 0 else 1
        dd = abs(deg) + abs(mnt) / 60 + abs(sec) / 3600 + abs(mic) / 3_600_000_000
        return round(sign * dd, 8)
    except Exception:
        return None


def _extract_units(ifc_file: ifcopenshell.file, project) -> str:
    if project is None:
        return ""
    unit_assignment = getattr(project, "UnitsInContext", None)
    if unit_assignment is None:
        return ""
    parts = []
    for unit in unit_assignment.Units or []:
        unit_type = getattr(unit, "UnitType", "")
        name      = getattr(unit, "Name", "") or getattr(unit, "Prefix", "") or ""
        if unit_type and name:
            parts.append(f"{unit_type}={name}")
    return "; ".join(parts)


def _extract_true_north(ifc_file: ifcopenshell.file) -> float | None:
    """
    Return the True North angle in decimal degrees (clockwise from Y-axis),
    read from IfcGeometricRepresentationContext.TrueNorth.
    """
    import math
    for ctx in ifc_file.by_type("IfcGeometricRepresentationContext"):
        tn = getattr(ctx, "TrueNorth", None)
        if tn is None:
            continue
        dirs = getattr(tn, "DirectionRatios", None)
        if dirs and len(dirs) >= 2:
            # DirectionRatios = (X, Y) of the true-north vector
            x, y = float(dirs[0]), float(dirs[1])
            angle_rad = math.atan2(x, y)          # angle from Y-axis
            angle_deg = math.degrees(angle_rad)
            return round(angle_deg, 4)
    return None


def _extract_map_conversion(ifc_file: ifcopenshell.file) -> dict:
    """Extract IfcMapConversion fields (IFC4 only)."""
    result = {}
    try:
        conversions = ifc_file.by_type("IfcMapConversion")
        if not conversions:
            return result
        mc = conversions[0]
        for field in ("Eastings", "Northings", "OrthogonalHeight",
                      "XAxisAbscissa", "XAxisOrdinate", "Scale"):
            val = getattr(mc, field, None)
            result[field] = float(val) if val is not None else None
    except Exception:
        pass
    return result


def _extract_projected_crs(ifc_file: ifcopenshell.file) -> dict:
    """Extract IfcProjectedCRS fields (IFC4 only)."""
    result = {}
    try:
        crs_list = ifc_file.by_type("IfcProjectedCRS")
        if not crs_list:
            return result
        crs = crs_list[0]
        for field in ("Name", "Descr