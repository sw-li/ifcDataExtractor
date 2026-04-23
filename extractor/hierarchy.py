"""
Module 2 — Hierarchy extractor
Walks the spatial decomposition tree via IfcRelAggregates and
IfcRelContainedInSpatialStructure.
Returns one row per element with its parent hierarchy columns populated.
"""

import pandas as pd
import ifcopenshell
import ifcopenshell.util.element as ifc_element_util


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
        One row per element; columns: source_file, site_name, building_name,
        storey_name, storey_elevation, space_name, space_long_name,
        element_global_id, element_ifc_type, element_name.
    """
    rows = []

    for site in ifc_file.by_type("IfcSite"):
        site_name = getattr(site, "Name", "") or ""

        for building in _get_children(site, "IfcBuilding"):
            building_name = getattr(building, "Name", "") or ""

            for storey in _get_children(building, "IfcBuildingStorey"):
                storey_name = getattr(storey, "Name", "") or ""
                storey_elevation = getattr(storey, "Elevation", None)

                # Elements directly contained in this storey
                for element in _get_contained_elements(storey):
                    rows.append(_make_row(
                        source_filename,
                        site_name, building_name,
                        storey_name, storey_elevation,
                        "", "",  # no space
                        element,
                    ))

                # Elements inside spaces within this storey
                for space in _get_children(storey, "IfcSpace"):
                    space_name = getattr(space, "Name", "") or ""
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
    ])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_children(spatial_element, ifc_type: str) -> list:
    """Return direct aggregate children of a given IFC type."""
    children = []
    for rel in getattr(spatial_element, "IsDecomposedBy", []) or []:
        for obj in rel.RelatedObjects or []:
            if obj.is_a(ifc_type):
                children.append(obj)
    return children


def _get_contained_elements(spatial_element) -> list:
    """Return all elements directly contained in a spatial structure element."""
    elements = []
    for rel in getattr(spatial_element, "ContainsElements", []) or []:
        for obj in rel.RelatedElements or []:
            elements.append(obj)
    return elements


def _make_row(
    source_filename,
    site_name, building_name,
    storey_name, storey_elevation,
    space_name, space_long_name,
    element,
) -> dict:
    return {
        "source_file": source_filename,
        "site_name": site_name,
        "building_name": building_name,
        "storey_name": storey_name,
        "storey_elevation": storey_elevation,
        "space_name": space_name,
        "space_long_name": space_long_name,
        "element_global_id": getattr(element, "GlobalId", "") or "",
        "element_ifc_type": element.is_a(),
        "element_name": getattr(element, "Name", "") or "",
    }
