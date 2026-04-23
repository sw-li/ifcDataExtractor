"""
ui/app.py — Main Tkinter window for IFC Extractor.

Layout:
  1. File list  — Add Files / Clear
  2. Modules    — Metadata | Hierarchy | Psets | Quantities (checkboxes)
  3. Filters    — IFC type (multi-select) | Storey (multi-select)
              populated dynamically after files are loaded
  4. Export     — Per IFC / Merged radio + output folder picker
  5. Run button
  6. Log area   — scrolled text widget
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext

import ifcopenshell

from extractor import metadata, hierarchy, psets, quantities
from filter import apply_filters, get_unique_ifc_types, get_unique_storeys
import exporter


class IFCExtractorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("IFC Extractor")
        self.resizable(True, True)
        self.minsize(600, 700)

        # Internal state
        self._ifc_files: list[str] = []
        self._loaded_dfs: dict[str, dict[str, object]] = {}   # source → sheet → df
        self._output_dir = tk.StringVar(value=os.path.expanduser("~"))
        self._export_mode = tk.StringVar(value="per_ifc")

        # Module toggles
        self._mod_metadata = tk.BooleanVar(value=True)
        self._mod_hierarchy = tk.BooleanVar(value=True)
        self._mod_psets = tk.BooleanVar(value=True)
        self._mod_quantities = tk.BooleanVar(value=True)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        # ── Section 1: File List ──────────────────────────────────────
        frm_files = ttk.LabelFrame(self, text="IFC Files")
        frm_files.pack(fill="x", **pad)

        btn_row = ttk.Frame(frm_files)
        btn_row.pack(fill="x", padx=4, pady=2)
        ttk.Button(btn_row, text="Add Files", command=self._add_files).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Clear", command=self._clear_files).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Load Files", command=self._load_files).pack(side="left", padx=2)

        self._file_listbox = tk.Listbox(frm_files, height=5, selectmode=tk.EXTENDED)
        self._file_listbox.pack(fill="x", padx=4, pady=2)

        # ── Section 2: Modules ────────────────────────────────────────
        frm_modules = ttk.LabelFrame(self, text="Modules to extract")
        frm_modules.pack(fill="x", **pad)

        row1 = ttk.Frame(frm_modules)
        row1.pack(fill="x", padx=4, pady=2)
        ttk.Checkbutton(row1, text="Metadata",   variable=self._mod_metadata).pack(side="left", padx=8)
        ttk.Checkbutton(row1, text="Hierarchy",  variable=self._mod_hierarchy).pack(side="left", padx=8)
        ttk.Checkbutton(row1, text="Psets",      variable=self._mod_psets).pack(side="left", padx=8)
        ttk.Checkbutton(row1, text="Quantities", variable=self._mod_quantities).pack(side="left", padx=8)

        # ── Section 3: Filters ────────────────────────────────────────
        frm_filters = ttk.LabelFrame(self, text="Filters  (populated after loading files)")
        frm_filters.pack(fill="x", **pad)

        # IFC type filter
        type_row = ttk.Frame(frm_filters)
        type_row.pack(fill="x", padx=4, pady=2)
        ttk.Label(type_row, text="IFC type:", width=12).pack(side="left")
        self._type_listbox = tk.Listbox(type_row, selectmode=tk.MULTIPLE, height=4, exportselection=False)
        type_scroll = ttk.Scrollbar(type_row, orient="vertical", command=self._type_listbox.yview)
        self._type_listbox.configure(yscrollcommand=type_scroll.set)
        self._type_listbox.pack(side="left", fill="x", expand=True)
        type_scroll.pack(side="left", fill="y")

        # Storey filter
        storey_row = ttk.Frame(frm_filters)
        storey_row.pack(fill="x", padx=4, pady=2)
        ttk.Label(storey_row, text="Storey:", width=12).pack(side="left")
        self._storey_listbox = tk.Listbox(storey_row, selectmode=tk.MULTIPLE, height=4, exportselection=False)
        storey_scroll = ttk.Scrollbar(storey_row, orient="vertical", command=self._storey_listbox.yview)
        self._storey_listbox.configure(yscrollcommand=storey_scroll.set)
        self._storey_listbox.pack(side="left", fill="x", expand=True)
        storey_scroll.pack(side="left", fill="y")

        ttk.Label(frm_filters, text="(Leave all unselected to export everything)", foreground="grey").pack(anchor="w", padx=4)

        # ── Section 4: Export ─────────────────────────────────────────
        frm_export = ttk.LabelFrame(self, text="Export")
        frm_export.pack(fill="x", **pad)

        mode_row = ttk.Frame(frm_export)
        mode_row.pack(fill="x", padx=4, pady=2)
        ttk.Radiobutton(mode_row, text="Per IFC", variable=self._export_mode, value="per_ifc").pack(side="left")
        ttk.Radiobutton(mode_row, text="Merged",  variable=self._export_mode, value="merged").pack(side="left", padx=8)

        folder_row = ttk.Frame(frm_export)
        folder_row.pack(fill="x", padx=4, pady=2)
        ttk.Label(folder_row, text="Output folder:").pack(side="left")
        ttk.Entry(folder_row, textvariable=self._output_dir, width=40).pack(side="left", padx=4)
        ttk.Button(folder_row, text="Browse", command=self._browse_output).pack(side="left")

        # ── Section 5: Run ────────────────────────────────────────────
        self._run_btn = ttk.Button(self, text="▶  Run Extraction", command=self._run)
        self._run_btn.pack(pady=6)

        # ── Section 6: Log ────────────────────────────────────────────
        frm_log = ttk.LabelFrame(self, text="Log")
        frm_log.pack(fill="both", expand=True, **pad)

        self._log = scrolledtext.ScrolledText(frm_log, height=12, state="disabled",
                                               font=("Consolas", 9))
        self._log.pack(fill="both", expand=True, padx=4, pady=4)

    # ------------------------------------------------------------------
    # File management
    # ------------------------------------------------------------------

    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="Select IFC files",
            filetypes=[("IFC files", "*.ifc"), ("All files", "*.*")],
        )
        for p in paths:
            if p not in self._ifc_files:
                self._ifc_files.append(p)
                self._file_listbox.insert(tk.END, os.path.basename(p))

    def _clear_files(self):
        self._ifc_files.clear()
        self._file_listbox.delete(0, tk.END)
        self._type_listbox.delete(0, tk.END)
        self._storey_listbox.delete(0, tk.END)
        self._loaded_dfs.clear()

    # ------------------------------------------------------------------
    # Load files (parse IFC, populate filters)
    # ------------------------------------------------------------------

    def _load_files(self):
        if not self._ifc_files:
            self._log_msg("No files added. Use 'Add Files' first.")
            return
        self._run_btn.config(state="disabled")
        threading.Thread(target=self._load_thread, daemon=True).start()

    def _load_thread(self):
        self._log_msg("Loading files…")
        self._loaded_dfs.clear()

        for path in self._ifc_files:
            name = os.path.basename(path)
            try:
                self._log_msg(f"  Opening {name}…")
                ifc = ifcopenshell.open(path)
                dfs = {}

                if self._mod_metadata.get():
                    dfs["Metadata"] = metadata.extract(ifc, name)
                if self._mod_hierarchy.get():
                    self._log_msg(f"  Extracting hierarchy…")
                    dfs["Hierarchy"] = hierarchy.extract(ifc, name)
                if self._mod_psets.get():
                    self._log_msg(f"  Extracting property sets…")
                    dfs["Psets"] = psets.extract(ifc, name)
                if self._mod_quantities.get():
                    self._log_msg(f"  Extracting quantities…")
                    dfs["Quantities"] = quantities.extract(ifc, name)

                self._loaded_dfs[path] = dfs
                self._log_msg(f"  ✓ {name} loaded.")

            except Exception as exc:
                self._log_msg(f"  ✗ Error loading {name}: {exc}")

        # Populate filter dropdowns
        all_dfs_flat = {k: df for source in self._loaded_dfs.values() for k, df in source.items()}
        ifc_types = get_unique_ifc_types(all_dfs_flat)
        storeys = get_unique_storeys(all_dfs_flat)

        self.after(0, lambda: self._populate_filters(ifc_types, storeys))
        self.after(0, lambda: self._run_btn.config(state="normal"))
        self._log_msg("Files loaded. Ready to run extraction.")

    def _populate_filters(self, ifc_types: list[str], storeys: list[str]):
        self._type_listbox.delete(0, tk.END)
        for t in ifc_types:
            self._type_listbox.insert(tk.END, t)

        self._storey_listbox.delete(0, tk.END)
        for s in storeys:
            self._storey_listbox.insert(tk.END, s)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _browse_output(self):
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self._output_dir.set(folder)

    def _run(self):
        if not self._loaded_dfs:
            self._log_msg("No files loaded. Click 'Load Files' first.")
            return
        self._run_btn.config(state="disabled")
        threading.Thread(target=self._run_thread, daemon=True).start()

    def _run_thread(self):
        self._log_msg("Starting extraction…")

        # Read filter selections
        selected_types = [
            self._type_listbox.get(i)
            for i in self._type_listbox.curselection()
        ]
        selected_storeys = [
            self._storey_listbox.get(i)
            for i in self._storey_listbox.curselection()
        ]

        # Apply filters to each source
        filtered_results = {}
        for source_path, dfs in self._loaded_dfs.items():
            filtered_results[source_path] = apply_filters(
                dfs,
                ifc_types=selected_types or None,
                storeys=selected_storeys or None,
            )

        output_dir = self._output_dir.get()
        mode = self._export_mode.get()

        try:
            if mode == "per_ifc":
                paths = exporter.export_per_ifc(
                    filtered_results,
                    output_dir,
                    progress_callback=self._log_msg,
                )
                self._log_msg(f"Done. {len(paths)} file(s) written to {output_dir}")
            else:
                path = exporter.export_merged(
                    filtered_results,
                    output_dir,
                    progress_callback=self._log_msg,
                )
                self._log_msg(f"Done. Merged file written to {path}")

        except Exception as exc:
            self._log_msg(f"Export error: {exc}")

        self.after(0, lambda: self._run_btn.config(state="normal"))

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log_msg(self, msg: str):
        def _append():
            self._log.config(state="normal")
            self._log.insert(tk.END, msg + "\n")
            self._log.see(tk.END)
            self._log.config(state="disabled")
        self.after(0, _append)
