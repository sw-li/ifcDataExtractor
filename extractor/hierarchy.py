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
from typing import Callable, Optional

# Column order — defined once so extract() and the schema stay in sync
_COLUMNS = [
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
]

# Report progress every N elements to avoid flooding the log
_PROGRESS_INTERVAL = 500


def extract(
    ifc_file: ifcopenshell.file,
    source_filename: str = "",
    progress_callback: Optional[Callable[[str], None]] = None,
) -> pd.DataFrame:
    """
    Extract the spatial hierarchy and all elements contained within it.

    Parameters
    ----------
    ifc_file : ifcopenshell.file
    source_filename : str
    progress_callback : callable | None
        If provided, called with a status string every _PROGRESS_INTERVAL elements.

    Returns
    -------
    pd.DataFrame
        One row per element; columns include source_file, spatial hierarchy,
        element identity, and absolute coordinates (x, y, z).
    """
    # Build rows as parallel lists (faster than list-of-dicts for large datasets)
    col_data: dict[str, list] = {c: [] for c in _COLUMNS}

    # Per-extraction placement cache: element.id() -> (x, y, z)
    # Avoids recomputing the full placement chain for elements encountered
    # more than once (e.g. when an element is both contained in a storey and a space).
    _placement_cache: dict[int, tuple] = {}

    count = 0

    for site in ifc_file.by_type("IfcSite"):
        site_name = getattr(site, "Name", "") or ""

        for building in _get_children(site, "IfcBuilding"):
            building_name = getattr(building, "Name", "") or ""

            for storey in _get_children(building, "IfcBuildingStorey"):
                storey_name      = getattr(storey, "Name", "") or ""
                storey_elevation = getattr(storey, "Elevation", None)

                for element in _get_contained_elements(storey):
                    _append_row(
                        col_data, source_filename,
                        site_name, building_name,
                        storey_name, storey_elevation,
                        "", "",
                        element, _placement_cache,
                    )
                    count += 1
                    if progress_callback and count % _PROGRESS_INTERVAL == 0:
                        progress_callback(f"    … {count:,} elements processed")

                for space in _get_children(storey, "IfcSpace"):
                    space_name      = getattr(space, "Name", "") or ""
                    space_long_name = getattr(space, "LongName", "") or ""

                    for element in _get_contained_elements(space):
                        _append_row(
                            col_data, source_filename,
                            site_name, building_name,
                            storey_name, storey_elevation,
                            space_name, space_long_name,
                            element, _placement_cache,
                        )
                        count += 1
                        if progress_callback and count % _PROGRESS_INTERVAL == 0:
                            progress_callback(f"    … {count:,} elements processed")

    if progress_callback and count > 0:
        progress_callback(f"    … {count:,} elements total")

    return pd.DataFrame(col_data)


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


def _get_xyz(element, cache: dict) -> tuple:
    """
    Return the absolute (X, Y, Z) origin of an element's placement
    in project coordinates.

    Results are memoised in *cache* (keyed by element.id()) so that shared
    placement chains are only computed once per extraction run.
    """
    eid = element.id()
    if eid in cache:
        return cache[eid]

    try:
        placement = getattr(element, "ObjectPlacement", None)
        if placement is None:
            result = (None, None, None)
        else:
            # get_local_placement walks the full placement chain
            matrix = ifcopenshell.util.placement.get_local_placement(placement)
            # matrix is a 4×4 numpy array; column 3 is the translation vector
            result = (
                round(float(matrix[0][3]), 4),
                round(float(matrix[1][3]), 4),
                round(float(matrix[2][3]), 4),
            )
    except Exception:
        result = (None, None, None)

    cache[eid] = result
    return result


def _append_row(
    col_data: dict,
    source_filename: str,
    site_name: str,
    building_name: str,
    storey_name: str,
    storey_elevation,
    space_name: str,
    space_long_name: str,
    element,
    placement_cache: dict,
) -> None:
    """Append one element's data directly into the column-oriented dict."""
    x, y, z = _get_xyz(element, placement_cache)
    col_data["source_file"].append(source_filename)
    col_data["site_name"].append(site_name)
    col_data["building_name"].append(building_name)
    col_data["storey_name"].append(storey_name)
    col_data["storey_elevation"].append(storey_elevation)
    col_data["space_name"].append(space_name)
    col_data["space_long_name"].append(space_long_name)
    col_data["element_global_id"].append(getattr(element, "GlobalId", "") or "")
    col_data["element_ifc_type"].append(element.is_a())
    col_data["element_name"].append(getattr(element, "Name", "") or "")
    col_data["x"].append(x)
    col_data["y"].append(y)
    col_data["z"].append(z)
