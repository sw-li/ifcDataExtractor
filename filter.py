"""
filter.py — Post-extraction, pre-export filtering logic.

Two independent filters (can be combined):
  1. By IFC type   — keep only rows whose element_ifc_type is in the selected set.
  2. By storey     — keep only rows whose storey_name is in the selected set.

Filtering operates in memory on extracted DataFrames before writing to Excel.
"""

import pandas as pd
from typing import Optional


def apply_filters(
    dfs: dict[str, pd.DataFrame],
    ifc_types: Optional[list[str]] = None,
    storeys: Optional[list[str]] = None,
) -> dict[str, pd.DataFrame]:
    """
    Apply type and/or storey filters to the extracted DataFrames.

    Parameters
    ----------
    dfs : dict
        Keys are sheet names ("Metadata", "Hierarchy", "Psets", "Quantities").
        Values are the corresponding DataFrames.
    ifc_types : list[str] | None
        If provided and non-empty, keep only rows where element_ifc_type is
        in this list. Sheets without that column are left untouched.
    storeys : list[str] | None
        If provided and non-empty, keep only rows where storey_name is in
        this list. Sheets without that column are left untouched.

    Returns
    -------
    dict[str, pd.DataFrame]
        Filtered DataFrames (same keys).
    """
    result = {}
    for sheet_name, df in dfs.items():
        # Start with the original reference — no copy needed.
        # _filter_by_column returns a new DataFrame via boolean indexing
        # only when filtering is actually applied, so this is safe.
        filtered = df

        if ifc_types:
            filtered = _filter_by_column(filtered, "element_ifc_type", ifc_types)

        if storeys:
            filtered = _filter_by_column(filtered, "storey_name", storeys)

        result[sheet_name] = filtered

    return result


def get_unique_ifc_types(dfs: dict[str, pd.DataFrame]) -> list[str]:
    """
    Return a sorted list of all unique IFC types across all DataFrames
    that contain an 'element_ifc_type' column.
    Useful for populating the filter dropdown in the UI.
    """
    types: set[str] = set()
    for df in dfs.values():
        if "element_ifc_type" in df.columns:
            types.update(df["element_ifc_type"].dropna().unique())
    return sorted(types)


def get_unique_storeys(dfs: dict[str, pd.DataFrame]) -> list[str]:
    """
    Return a sorted list of all unique storey names across all DataFrames
    that contain a 'storey_name' column.
    Useful for populating the filter dropdown in the UI.
    """
    storeys: set[str] = set()
    for df in dfs.values():
        if "storey_name" in df.columns:
            storeys.update(df["storey_name"].dropna().unique())
    return sorted(storeys)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _filter_by_column(
    df: pd.DataFrame,
    column: str,
    allowed_values: list[str],
) -> pd.DataFrame:
    """
    If the DataFrame has the given column, keep only rows whose value is
    in allowed_values. Otherwise return df unchanged.
    """
    if column not in df.columns or not allowed_