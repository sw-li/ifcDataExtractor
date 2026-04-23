"""
exporter.py — Assembles extracted DataFrames and writes .xlsx output.

Sheet layout:
  Metadata    — one row per IFC file
  Hierarchy   — full spatial tree with element rows
  Psets       — all property values (long format)
  Quantities  — all quantity values

Export modes:
  per_ifc  — one .xlsx per input IFC, named {ifc_filename}_export.xlsx
  merged   — one .xlsx with a source_file column in every sheet, named merged_export.xlsx

Formatting:
  - Frozen header row
  - Auto column width
  - Light alternating row shading
"""

import os
import pandas as pd
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
HEADER_FILL = PatternFill("solid", fgColor="1F4E79")   # dark blue
HEADER_FONT = Font(color="FFFFFF", bold=True)
ROW_FILL_ODD = PatternFill("solid", fgColor="FFFFFF")  # white
ROW_FILL_EVEN = PatternFill("solid", fgColor="DCE6F1") # very light blue


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_per_ifc(
    results: dict[str, dict[str, pd.DataFrame]],
    output_dir: str,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> list[str]:
    """
    Write one .xlsx file per IFC source.

    Parameters
    ----------
    results : dict
        {source_filename: {"Metadata": df, "Hierarchy": df, "Psets": df, "Quantities": df}}
    output_dir : str
        Folder where output files are written.
    progress_callback : callable | None
        Called with a status string after each file is written.

    Returns
    -------
    list[str]
        Paths of created files.
    """
    os.makedirs(output_dir, exist_ok=True)
    created = []

    for source_filename, dfs in results.items():
        base = os.path.splitext(os.path.basename(source_filename))[0]
        out_path = os.path.join(output_dir, f"{base}_export.xlsx")
        _write_workbook(dfs, out_path)
        created.append(out_path)
        if progress_callback:
            progress_callback(f"Written → {out_path}")

    return created


def export_merged(
    results: dict[str, dict[str, pd.DataFrame]],
    output_dir: str,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> str:
    """
    Write all IFC sources into a single merged .xlsx file.

    Parameters
    ----------
    results : dict
        {source_filename: {"Metadata": df, "Hierarchy": df, "Psets": df, "Quantities": df}}
    output_dir : str
    progress_callback : callable | None

    Returns
    -------
    str
        Path of the created file.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Concatenate each sheet across all source files
    sheet_names = ["Metadata", "Hierarchy", "Psets", "Quantities"]
    merged: dict[str, pd.DataFrame] = {}

    for sheet in sheet_names:
        frames = [
            dfs[sheet]
            for dfs in results.values()
            if sheet in dfs and not dfs[sheet].empty
        ]
        merged[sheet] = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    out_path = os.path.join(output_dir, "merged_export.xlsx")
    _write_workbook(merged, out_path)

    if progress_callback:
        progress_callback(f"Written → {out_path}")

    return out_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _write_workbook(dfs: dict[str, pd.DataFrame], path: str) -> None:
    """Write a dict of DataFrames to an .xlsx workbook, one sheet each."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # remove default empty sheet

    sheet_order = ["Metadata", "Hierarchy", "Psets", "Quantities"]
    for sheet_name in sheet_order:
        df = dfs.get(sheet_name, pd.DataFrame())
        ws = wb.create_sheet(title=sheet_name)
        _write_sheet(ws, df)

    wb.save(path)


def _write_sheet(ws, df: pd.DataFrame) -> None:
    """Write a DataFrame to an openpyxl worksheet with formatting."""
    if df.empty:
        ws.append(["(no data)"])
        return

    # Header row
    headers = list(df.columns)
    ws.append(headers)
    header_row = ws[1]
    for cell in header_row:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=False)

    # Freeze header
    ws.freeze_panes = "A2"

    # Data rows with alternating shading
    for row_idx, row in enumerate(df.itertuples(index=False), start=2):
        ws.append(list(row))
        fill = ROW_FILL_EVEN if row_idx % 2 == 0 else ROW_FILL_ODD
        for cell in ws[row_idx]:
            cell.fill = fill
            cell.alignment = Alignment(vertical="center")

    # Auto column width
    for col_idx, col_cells in enumerate(ws.columns, start=1):
        max_len = max(
            (len(str(cell.value)) for cell in col_cells if cell.value is not None),
            default=8,
        )
        adjusted = min(max_len + 4, 60)  # cap at 60 chars
        ws.column_dimensions[get_column_letter(col_idx)].width = adjusted
