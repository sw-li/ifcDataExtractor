"""
Module 2 — Hierarchy extractor
Walks the spatial decomposition tree via IfcRelAggregates and
IfcRelContainedInSpatialStructure.
Returns one row per element with its parent hierarchy columns and
absolute X / Y / Z coordinates (in project units, typically metres).
"""

import pandas as pd
import ifcopenshell
import ifcopenshell.util.placement


def extract(ifc_file: ifcopenshell.file, source_filename: str = "") -> pd.DataFrame:
    """
    Extract the spatial hierarchy and all elements contained within it.

    Parameters
    ----------
    ifc_file : ifcopenshell.file
    source_filename : str

    Returns
    -------
    pd.DataFrame
        One row per element; columns include source_file, spatial hierarchy,
        element identity, and absolute coordinates (x, y, z).
    """
    rows = []

    for site in ifc_file.by_type("IfcSite"):
        site_name = getattr(site, "Name", "") or ""

        for building in _get_children(site, "IfcBuilding"):
            building_name = getattr(building, "Name", "") or ""

            for storey in _get_children(building, "IfcBuildingStorey"):
                storey_name      = getattr(storey, "Name", "") or ""
                storey_elevation = getattr(storey, "Elevation", None)

                for element in _get_contained_elements(storey):
                    rows.append(_make_row(
                        source_filename,
                        site_name, building_name,
                        storey_name, storey_elevation,
                        "", "",
                        element,
                    ))

                for space in _get_children(storey, "IfcSpace"):
                    space_name      = getattr(space, "Name", "") or ""
                    space_long_name = getattr(space, "LongName", "") or ""

                    for element in _get_contained_elements(space):
                        rows.append(_make_row(
                            source_filename,
                            site_name, building_name,
                            storey_name, storey_elevation,
                            space_name, space_long_name,
                            element,
                        ))

    return pd.DataFrame(rows, columns=[
        "source_file",
        "site_name",
        "building_name",
        "storey_name",
        "storey_elevation",
        "space_name",
        "space_long_name",
        "element_global_id",
        "element_ifc_type",
        "element_name",
        "x", "y", "z",
    ])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_children(spatial_element, ifc_type: str) -> list:
    children = []
    for rel in getattr(spatial_element, "IsDecomposedBy", []) or []:
        for obj in rel.RelatedObjects or []:
            if obj.is_a(ifc_type):
                children.append(obj)
    return children


def _get_contained_elements(spatial_element) -> list:
    elements = []
    for rel in getattr(spatial_element, "ContainsElements", []) or []:
        for obj in rel.RelatedElements or []:
            elements.append(obj)
    return elements


def _get_xyz(element) -> tuple:
    """
    Return the absolute (X, Y, Z) origin of an element's placement
    in project coordinates.

    Uses ifcopenshell.util.placement.get_local_placement() which walks
    the full placement chain (relative placements are resolved to absolute).
    Returns (None, None, None) if the element has no placement.
    """
    try:
        placement = getattr(element, "ObjectPlacement", None)
        if placement is None:
            return None, None, None
        matrix = ifcopenshell.util.placement.get_local_placement(placement)
        # matrix is a 4×4 numpy array; column 3 is the translation vector
        return round(float(matrix[0][3]), 4), \
               round(float(matrix[1][3]), 4), \
               round(float(matrix[2][3]), 4)
    except Exception:
        return None, None, None


def _make_row(
    source_filename,
    site_name, building_name,
    storey_name, storey_elevation,
    space_name, space_long_name,
    element,
) -> dict:
    x, y, z = _get_xyz(element)
    return {
        "source_file":       source_filename,
        "site_name":         site_name,
        "building_name":     building_name,
        "storey_name":       storey_name,
        "storey_elevation":  storey_elevation,
        "space_name":        space_name,
        "space_long_name":   space_long_name,
        "element_global_id": getattr(element, "GlobalId", "") or "",
        "element_ifc_type":  element.is_a(),
        "element_name":      getattr(element, "Name", "") or "",
        "x":                 x,
        "y":                 y,
        "z":                 z,
    }
