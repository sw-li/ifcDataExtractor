# IFC Extractor

A local desktop Python application that loads one or multiple IFC files, extracts structured BIM data, and exports results to Excel.

## Features

- Load and parse one or multiple `.ifc` files locally (no server, no uploads)
- Extract four categories of BIM data:
  - **Metadata** — IFC header & project info
  - **Hierarchy** — Site › Building › Storey › Space › Element tree
  - **Property Sets** — All `Pset_*` property values
  - **Quantities** — All `Qto_*` quantity sets
- Filter by IFC type and/or storey/space before export
- Export to `.xlsx` — one file per IFC or one merged file

## Requirements

- Python 3.9+
- `ifcopenshell >= 0.8.0`
- `openpyxl >= 3.1.0`
- `tkinter` (standard library — no install needed)

## Installation

```bash
pip install ifcopenshell openpyxl
```

> **Note:** `ifcopenshell` may require a specific wheel for your platform.
> See [ifcopenshell.org](https://ifcopenshell.org/python) for details.

## Usage

```bash
python main.py
```

1. Click **Add Files** to select one or more `.ifc` files.
2. Tick the modules you want to extract (Metadata, Hierarchy, Psets, Quantities).
3. Optionally filter by IFC type and/or storey.
4. Choose **Per IFC** or **Merged** export mode.
5. Select an output folder and click **Run Extraction**.

## Project Structure

```
ifc_extractor/
├── main.py
├── ui/
│   └── app.py
├── extractor/
│   ├── __init__.py
│   ├── metadata.py
│   ├── hierarchy.py
│   ├── psets.py
│   └── quantities.py
├── exporter.py
├── filter.py
├── requirements.txt
└── README.md
```

## IFC Version Support

- IFC2X3
- IFC4
- IFC4.3 (depends on installed ifcopenshell version)

## Roadmap

- [ ] Geometry / bounding-box extraction
- [ ] IDS rule checking
- [ ] HTML report output
- [ ] In-app table preview before export
