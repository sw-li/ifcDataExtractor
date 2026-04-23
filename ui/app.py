"""
ui/app.py — IFC Extractor UI (CustomTkinter)

Features:
  - Modern dark / light mode with toggle switch
  - File list with Add / Clear / Load and a file-count badge
  - Module checkboxes (Metadata, Hierarchy, Psets, Quantities)
  - Filter panels with Select All / None buttons
  - Animated progress bar during extraction
  - Scrollable log area
"""

import os
import threading
import tkinter as tk

import customtkinter as ctk
import ifcopenshell

from extractor import metadata, hierarchy, psets, quantities
from filter import apply_filters, get_unique_ifc_types, get_unique_storeys
import exporter

# ---------------------------------------------------------------------------
# Default appearance
# ---------------------------------------------------------------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class IFCExtractorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("IFC Extractor")
        self.geometry("720x860")
        self.minsize(640, 760)

        # State
        self._ifc_files: list[str] = []
        self._loaded_dfs: dict = {}
        self._output_dir = tk.StringVar(value=os.path.expanduser("~"))
        self._export_mode = tk.StringVar(value="per_ifc")

        # Module toggles
        self._mod_metadata   = tk.BooleanVar(value=True)
        self._mod_hierarchy  = tk.BooleanVar(value=True)
        self._mod_psets      = tk.BooleanVar(value=True)
        self._mod_quantities = tk.BooleanVar(value=True)

        # Filter checkbox state (populated dynamically)
        self._type_vars:   dict[str, tk.BooleanVar] = {}
        self._storey_vars: dict[str, tk.BooleanVar] = {}

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        row = 0

        # ── Top bar: title + dark/light toggle ───────────────────────
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=row, column=0, sticky="ew", padx=16, pady=(14, 2))
        top.grid_columnconfigure(0, weight=1)
        row += 1

        ctk.CTkLabel(top, text="IFC Extractor",
                     font=ctk.CTkFont(size=20, weight="bold")).grid(
            row=0, column=0, sticky="w")

        mode_frame = ctk.CTkFrame(top, fg_color="transparent")
        mode_frame.grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(mode_frame, text="🌙", font=ctk.CTkFont(size=14)).pack(side="left", padx=(0, 4))
        self._theme_switch = ctk.CTkSwitch(
            mode_frame, text="", width=46,
            command=self._toggle_theme,
            onvalue="light", offvalue="dark",
        )
        self._theme_switch.pack(side="left")
        ctk.CTkLabel(mode_frame, text="☀️", font=ctk.CTkFont(size=14)).pack(side="left", padx=(4, 0))

        # ── Section 1: Files ─────────────────────────────────────────
        row = self._section(row, "📂  IFC Files")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 4))
        row += 1

        ctk.CTkButton(btn_row, text="Add Files", width=100,
                      command=self._add_files).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row, text="Clear", width=80, fg_color="gray40",
                      hover_color="gray30",
                      command=self._clear_files).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row, text="Load Files ▶", width=110,
                      command=self._load_files).pack(side="left")
        self._file_badge = ctk.CTkLabel(btn_row, text="",
                                         font=ctk.CTkFont(size=12),
                                         text_color="gray60")
        self._file_badge.pack(side="left", padx=10)

        # File listbox (plain tk inside a CTkFrame for scrolling)
        file_frame = ctk.CTkFrame(self)
        file_frame.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 8))
        file_frame.grid_columnconfigure(0, weight=1)
        row += 1

        self._file_listbox = tk.Listbox(
            file_frame, height=4, selectmode=tk.EXTENDED,
            bg="#2b2b2b", fg="white", selectbackground="#1f6aa5",
            relief="flat", borderwidth=0, font=("Segoe UI", 10),
        )
        sb = tk.Scrollbar(file_frame, orient="vertical",
                          command=self._file_listbox.yview)
        self._file_listbox.configure(yscrollcommand=sb.set)
        self._file_listbox.grid(row=0, column=0, sticky="ew", padx=(6, 0), pady=4)
        sb.grid(row=0, column=1, sticky="ns", pady=4)

        # ── Section 2: Modules ────────────────────────────────────────
        row = self._section(row, "⚙️  Modules to extract")

        mod_row = ctk.CTkFrame(self, fg_color="transparent")
        mod_row.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 8))
        row += 1

        for text, var in [
            ("Metadata",   self._mod_metadata),
            ("Hierarchy",  self._mod_hierarchy),
            ("Psets",      self._mod_psets),
            ("Quantities", self._mod_quantities),
        ]:
            ctk.CTkCheckBox(mod_row, text=text, variable=var,
                            font=ctk.CTkFont(size=13)).pack(side="left", padx=10)

        # ── Section 3: Filters ────────────────────────────────────────
        row = self._section(row, "🔍  Filters  (populated after Load Files)")

        filters_outer = ctk.CTkFrame(self, fg_color="transparent")
        filters_outer.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 8))
        filters_outer.grid_columnconfigure((0, 1), weight=1)
        row += 1

        # IFC Type panel
        self._type_panel = self._filter_panel(
            filters_outer, "IFC Type", col=0,
            select_all_cmd=lambda: self._select_all(self._type_vars),
            select_none_cmd=lambda: self._select_none(self._type_vars),
        )

        # Storey panel
        self._storey_panel = self._filter_panel(
            filters_outer, "Storey", col=1,
            select_all_cmd=lambda: self._select_all(self._storey_vars),
            select_none_cmd=lambda: self._select_none(self._storey_vars),
        )

        ctk.CTkLabel(self,
                     text="Leave all unchecked to export everything",
                     font=ctk.CTkFont(size=11), text_color="gray55"
                     ).grid(row=row, column=0, sticky="w", padx=18, pady=(0, 4))
        row += 1

        # ── Section 4: Export ─────────────────────────────────────────
        row = self._section(row, "💾  Export")

        export_frame = ctk.CTkFrame(self, fg_color="transparent")
        export_frame.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 8))
        row += 1

        ctk.CTkRadioButton(export_frame, text="Per IFC file",
                           variable=self._export_mode, value="per_ifc").pack(side="left")
        ctk.CTkRadioButton(export_frame, text="Merged (one file)",
                           variable=self._export_mode, value="merged").pack(side="left", padx=20)

        folder_row = ctk.CTkFrame(self, fg_color="transparent")
        folder_row.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 8))
        folder_row.grid_columnconfigure(1, weight=1)
        row += 1

        ctk.CTkLabel(folder_row, text="Output folder:").grid(row=0, column=0, padx=(0, 8))
        ctk.CTkEntry(folder_row, textvariable=self._output_dir).grid(
            row=0, column=1, sticky="ew")
        ctk.CTkButton(folder_row, text="Browse", width=80,
                      command=self._browse_output).grid(row=0, column=2, padx=(8, 0))

        # ── Run button ────────────────────────────────────────────────
        self._run_btn = ctk.CTkButton(
            self, text="▶   Run Extraction",
            height=42, font=ctk.CTkFont(size=15, weight="bold"),
            command=self._run,
        )
        self._run_btn.grid(row=row, column=0, padx=16, pady=6, sticky="ew")
        row += 1

        # ── Progress bar ──────────────────────────────────────────────
        self._progress = ctk.CTkProgressBar(self, mode="indeterminate", height=8)
        self._progress.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 6))
        self._progress.set(0)
        row += 1

        # ── Log ───────────────────────────────────────────────────────
        row = self._section(row, "📋  Log")
        self._log = ctk.CTkTextbox(self, height=150,
                                    font=ctk.CTkFont(family="Consolas", size=11),
                                    state="disabled")
        self._log.grid(row=row, column=0, sticky="nsew", padx=16, pady=(0, 12))
        self.grid_rowconfigure(row, weight=1)

    # ------------------------------------------------------------------
    # Section header helper
    # ------------------------------------------------------------------

    def _section(self, row: int, title: str) -> int:
        ctk.CTkLabel(self, text=title,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").grid(row=row, column=0, sticky="ew",
                                      padx=16, pady=(10, 2))
        return row + 1

    # ------------------------------------------------------------------
    # Filter panel helper
    # ------------------------------------------------------------------

    def _filter_panel(self, parent, title, col,
                      select_all_cmd, select_none_cmd):
        frame = ctk.CTkFrame(parent)
        frame.grid(row=0, column=col, sticky="nsew", padx=(0 if col else 0, 6 if col == 0 else 0))
        frame.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))
        ctk.CTkLabel(header, text=title,
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        ctk.CTkButton(header, text="All", width=36, height=22,
                      font=ctk.CTkFont(size=11),
                      command=select_all_cmd).pack(side="right", padx=(4, 0))
        ctk.CTkButton(header, text="None", width=40, height=22,
                      font=ctk.CTkFont(size=11), fg_color="gray40",
                      hover_color="gray30",
                      command=select_none_cmd).pack(side="right")

        scroll = ctk.CTkScrollableFrame(frame, height=110)
        scroll.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        frame.grid_rowconfigure(1, weight=1)

        return scroll  # return scrollable area so we can populate it later

    # ------------------------------------------------------------------
    # Theme toggle
    # ------------------------------------------------------------------

    def _toggle_theme(self):
        mode = self._theme_switch.get()
        ctk.set_appearance_mode(mode)
        # Keep listbox colours in sync
        bg = "#2b2b2b" if mode == "dark" else "#ebebeb"
        fg = "white"   if mode == "dark" else "black"
        self._file_listbox.configure(bg=bg, fg=fg)

    # ------------------------------------------------------------------
    # File management
    # ------------------------------------------------------------------

    def _add_files(self):
        from tkinter import filedialog
        paths = filedialog.askopenfilenames(
            title="Select IFC files",
            filetypes=[("IFC files", "*.ifc"), ("All files", "*.*")],
        )
        for p in paths:
            if p not in self._ifc_files:
                self._ifc_files.append(p)
                self._file_listbox.insert(tk.END, os.path.basename(p))
        self._update_file_badge()

    def _clear_files(self):
        self._ifc_files.clear()
        self._file_listbox.delete(0, tk.END)
        self._loaded_dfs.clear()
        self._update_file_badge()
        self._clear_filter_panel(self._type_panel, self._type_vars)
        self._clear_filter_panel(self._storey_panel, self._storey_vars)

    def _update_file_badge(self):
        n = len(self._ifc_files)
        self._file_badge.configure(
            text=f"{n} file{'s' if n != 1 else ''} added" if n else ""
        )

    # ------------------------------------------------------------------
    # Load files
    # ------------------------------------------------------------------

    def _load_files(self):
        if not self._ifc_files:
            self._log_msg("No files added. Use 'Add Files' first.")
            return
        self._set_busy(True)
        threading.Thread(target=self._load_thread, daemon=True).start()

    def _load_thread(self):
        self._log_msg("Loading files…")
        self._loaded_dfs.clear()
        total_elements = 0

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
                    if not dfs["Hierarchy"].empty:
                        total_elements += len(dfs["Hierarchy"])

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

        # Populate filters
        all_flat = {k: df for src in self._loaded_dfs.values() for k, df in src.items()}
        ifc_types = get_unique_ifc_types(all_flat)
        storeys   = get_unique_storeys(all_flat)

        summary = f"Ready — {len(self._loaded_dfs)} file(s), {total_elements:,} hierarchy rows"
        self.after(0, lambda: self._on_load_done(ifc_types, storeys, summary))

    def _on_load_done(self, ifc_types, storeys, summary):
        self._populate_filter_panel(self._type_panel,   self._type_vars,   ifc_types)
        self._populate_filter_panel(self._storey_panel, self._storey_vars, storeys)
        self._file_badge.configure(text=summary, text_color="#3a9ad9")
        self._log_msg(summary)
        self._set_busy(False)

    # ------------------------------------------------------------------
    # Filter panel helpers
    # ------------------------------------------------------------------

    def _populate_filter_panel(self, panel, var_dict: dict, items: list[str]):
        self._clear_filter_panel(panel, var_dict)
        for item in items:
            var = tk.BooleanVar(value=False)
            var_dict[item] = var
            ctk.CTkCheckBox(panel, text=item, variable=var,
                            font=ctk.CTkFont(size=11)).pack(anchor="w", pady=1)

    def _clear_filter_panel(self, panel, var_dict: dict):
        for widget in panel.winfo_children():
            widget.destroy()
        var_dict.clear()

    def _select_all(self, var_dict: dict):
        for v in var_dict.values():
            v.set(True)

    def _select_none(self, var_dict: dict):
        for v in var_dict.values():
            v.set(False)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _browse_output(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self._output_dir.set(folder)

    def _run(self):
        if not self._loaded_dfs:
            self._log_msg("No files loaded. Click 'Load Files' first.")
            return
        self._set_busy(True)
        threading.Thread(target=self._run_thread, daemon=True).start()

    def _run_thread(self):
        self._log_msg("Applying filters and exporting…")

        selected_types   = [k for k, v in self._type_vars.items()   if v.get()]
        selected_storeys = [k for k, v in self._storey_vars.items() if v.get()]

        filtered = {}
        for src, dfs in self._loaded_dfs.items():
            filtered[src] = apply_filters(
                dfs,
                ifc_types=selected_types   or None,
                storeys=selected_storeys or None,
            )

        output_dir = self._output_dir.get()
        mode = self._export_mode.get()

        try:
            if mode == "per_ifc":
                paths = exporter.export_per_ifc(
                    filtered, output_dir,
                    progress_callback=self._log_msg,
                )
                self._log_msg(f"✅  Done — {len(paths)} file(s) written to {output_dir}")
            else:
                path = exporter.export_merged(
                    filtered, output_dir,
                    progress_callback=self._log_msg,
                )
                self._log_msg(f"✅  Done — merged file written to {path}")
        except Exception as exc:
            self._log_msg(f"❌  Export error: {exc}")

        self.after(0, lambda: self._set_busy(False))

    # ------------------------------------------------------------------
    # Busy state (progress bar + button disable)
    # ------------------------------------------------------------------

    def _set_busy(self, busy: bool):
        if busy:
            self._run_btn.configure(state="disabled")
            self._progress.configure(mode="indeterminate")
            self._progress.start()
        else:
            self._progress.stop()
            self._progress.configure(mode="determinate")
            self._progress.set(1)
            self._run_btn.configure(state="normal")

    # ------------------------------------------------------------------
    # Log
    # ------------------------------------------------------------------

    def _log_msg(self, msg: str):
        def _append():
            self._log.configure(state="normal")
            self._log.insert("end", msg + "\n")
            self._log.see("end")
            self._log.configure(state="disabled")
        self.after(0, _append)
