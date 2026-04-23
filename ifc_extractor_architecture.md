# IFC Extractor — Architecture Document

## 1. Overview

A local desktop Python application that loads one or multiple IFC files, extracts structured BIM data across four categories, and exports results to Excel. No server, no uploads — all processing happens on the user's machine.

---

## 2. Goals & Non-Goals

### Goals
- Load and parse one or multiple IFC files locally
- Extract metadata, element hierarchy, property sets, and quantities
- Filter extracted data by IFC type and/or storey/space
- Export to `.xlsx` — one file per IFC or one merged file
- Simple Tkinter UI: file picker, module toggles, export options, progress log

### Non-Goals (deferred to future modules)
- Geometry / coordinate extraction
- IDS / rule checking
- Cloud or server deployment
- 3D visualization

---

## 3. Project Structure

```
ifc_extractor/
│
├── main.py                  # Entry point — launches the Tkinter UI
│
├── ui/
│   └── app.py               # Tkinter window: file picker, checkboxes, run button, log
│
├── extractor/
│   ├── __init__.py
│   ├── metadata.py          # Module 1 — IFC header & project info
│   ├── hierarchy.py         # Module 2 — Site > Building > Storey > Space tree
│   ├── psets.py             # Module 3 — All Pset_* property sets
│   └── quantities.py        # Module 4 — All Qto_* quantity sets
│
├── exporter.py              # Assembles extracted data and writes .xlsx
├── filter.py                # Filtering logic: by IFC type and/or storey/space
│
├── requirements.txt
└── README.md
```

---

## 4. Modules

### 4.1 `extractor/metadata.py`

Reads the IFC file header and the `IfcProject` entity.

**Extracted fields:**

| Field | IFC Source |
|---|---|
| Schema version | `ifc_file.schema` (e.g. IFC2X3, IFC4) |
| File name | Header `FILE_NAME` |
| Time stamp | Header `FILE_NAME` |
| Author | Header `FILE_NAME` |
| Organization | Header `FILE_NAME` |
| Originating system | Header `FILE_NAME` |
| Project name | `IfcProject.Name` |
| Project description | `IfcProject.Description` |
| Project phase | `IfcProject.Phase` |
| Units | `IfcUnitAssignment` linked to `IfcProject` |

**Output shape:** one row per file (suitable for a summary sheet)

---

### 4.2 `extractor/hierarchy.py`

Walks the spatial decomposition tree using `IfcRelAggregates` and `IfcRelContainedInSpatialStructure`.

**Extracted fields:**

| Field | Notes |
|---|---|
| Site name | `IfcSite.Name` |
| Building name | `IfcBuilding.Name` |
| Storey name | `IfcBuildingStorey.Name` |
| Storey elevation | `IfcBuildingStorey.Elevation` |
| Space name | `IfcSpace.Name` |
| Space long name | `IfcSpace.LongName` |
| Element GlobalId | For elements contained in each storey/space |
| Element IFC type | e.g. `IfcWall`, `IfcDoor` |
| Element name | `IfcElement.Name` |

**Output shape:** one row per element, with its parent hierarchy columns populated

---

### 4.3 `extractor/psets.py`

Iterates all elements and collects their property sets via `IfcRelDefinesByProperties`.

**Extracted fields:**

| Field | Notes |
|---|---|
| Element GlobalId | |
| Element IFC type | |
| Element name | |
| Pset name | e.g. `Pset_WallCommon` |
| Property name | e.g. `FireRating` |
| Property value | Cast to string |
| Property unit | If available via `IfcPropertySingleValue` |

**Output shape:** one row per property (tall/long format) — pivoting to wide can be done in Excel

**Note:** Only `IfcPropertySingleValue` in scope for MVP. `IfcPropertyEnumeratedValue` and `IfcComplexProperty` deferred.

---

### 4.4 `extractor/quantities.py`

Collects quantity sets (`Qto_*`) via `IfcRelDefinesByProperties` where the definition is an `IfcElementQuantity`.

**Extracted fields:**

| Field | Notes |
|---|---|
| Element GlobalId | |
| Element IFC type | |
| Element name | |
| Qto set name | e.g. `Qto_WallBaseQuantities` |
| Quantity name | e.g. `NetSideArea` |
| Quantity value | Numeric |
| Quantity type | `IfcAreaMeasure`, `IfcVolumeMeasure`, `IfcMassMeasure`, etc. |
| Unit | Derived from project unit assignment |

**Output shape:** one row per quantity value

---

### 4.5 `filter.py`

Applied after extraction, before export. Two independent filters that can be combined:

- **By IFC type** — user selects one or more types (e.g. `IfcWall`, `IfcSlab`). Populated dynamically from the loaded files.
- **By storey/space** — user selects one or more storeys or spaces. Populated dynamically from the hierarchy extraction.

Filtering is done in memory on the extracted dataframes before writing to Excel.

---

### 4.6 `exporter.py`

Takes extracted dataframes and writes an `.xlsx` file using `openpyxl`.

**Sheet layout:**

| Sheet name | Content |
|---|---|
| `Metadata` | One row per IFC file |
| `Hierarchy` | Full spatial tree with element rows |
| `Psets` | All property values (long format) |
| `Quantities` | All quantity values |

**Export modes (user chooses at runtime):**

- **Per IFC:** one `.xlsx` file per input IFC, named `{ifc_filename}_export.xlsx`
- **Merged:** one `.xlsx` file with a `source_file` column in every sheet, named `merged_export.xlsx`

**Formatting:** frozen header row, auto column width, light alternating row shading.

---

## 5. UI — `ui/app.py`

Built with Tkinter (stdlib, no install required).

**Layout:**

```
┌─────────────────────────────────────────────┐
│  IFC Extractor                              │
├─────────────────────────────────────────────┤
│  IFC Files:  [Add Files]  [Clear]           │
│  ┌─────────────────────────────────────┐    │
│  │ file1.ifc                           │    │
│  │ file2.ifc                           │    │
│  └─────────────────────────────────────┘    │
├─────────────────────────────────────────────┤
│  Modules to extract:                        │
│  ☑ Metadata   ☑ Hierarchy                  │
│  ☑ Psets      ☑ Quantities                 │
├─────────────────────────────────────────────┤
│  Filter by IFC type:   [dropdown / multi]   │
│  Filter by Storey:     [dropdown / multi]   │
│  (populated after loading files)            │
├─────────────────────────────────────────────┤
│  Export mode:  ● Per IFC   ○ Merged         │
│  Output folder: [Browse]  /path/to/output   │
├─────────────────────────────────────────────┤
│  [Run Extraction]                           │
├─────────────────────────────────────────────┤
│  Log:                                       │
│  ┌─────────────────────────────────────┐    │
│  │ Loading file1.ifc...                │    │
│  │ Extracting psets... 142 elements    │    │
│  │ Done. Written to /output/file1.xlsx │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

---

## 6. Data Flow

```
IFC files (local disk)
        │
        ▼
   ifcopenshell.open()
        │
        ├──▶ metadata.py   ──▶ DataFrame (1 row/file)
        ├──▶ hierarchy.py  ──▶ DataFrame (1 row/element)
        ├──▶ psets.py      ──▶ DataFrame (1 row/property)
        └──▶ quantities.py ──▶ DataFrame (1 row/quantity)
                │
                ▼
           filter.py
        (by type, by storey)
                │
                ▼
           exporter.py
        (per-IFC or merged)
                │
                ▼
          output .xlsx files
```

---

## 7. Dependencies

```
ifcopenshell>=0.8.0     # IFC parsing
openpyxl>=3.1.0         # Excel export
tkinter                 # UI (stdlib, no install needed)
```

`requirements.txt`:
```
ifcopenshell
openpyxl
```

---

## 8. IFC Version Compatibility

Target: **IFC2X3** and **IFC4** (most common in practice).
IFC4.3 support depends on the ifcopenshell version installed — no special handling needed, the same API applies.

---

## 9. Future Modules (out of scope for MVP)

| Module | Description |
|---|---|
| `extractor/geometry.py` | Bounding box and placement point extraction |
| `checker/ids_runner.py` | Load an IDS XML and validate IFC files against it |
| `reporter/html.py` | HTML report output in addition to Excel |
| `ui/preview.py` | In-app table preview before export |
