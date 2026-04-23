"""
ui/app.py — IFC Extractor UI (CustomTkinter, landscape two-column layout)

LEFT  column : Files · Modules · Filters
RIGHT column : Export options · Run · Progress · Log
"""

import os
import threading
import tkinter as tk

import customtkinter as ctk
import ifcopenshell

from extractor import metadata, hierarchy, psets, quantities
from filter import apply_filters, get_unique_ifc_types, get_unique_storeys
import exporter

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class IFCExtractorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("IFC Extractor")
        self.geometry("1100x640")
        self.minsize(900, 560)

        # ── State ─────────────────────────────────────────────────────
        self._ifc_files: list[str] = []
        self._loaded_dfs: dict = {}
        _downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        self._output_dir   = tk.StringVar(
            value=_downloads if os.path.isdir(_downloads) else os.path.expanduser("~")
        )
        self._export_mode  = tk.StringVar(value="per_ifc")

        self._mod_metadata   = tk.BooleanVar(value=True)
        self._mod_hierarchy  = tk.BooleanVar(value=True)
        self._mod_psets      = tk.BooleanVar(value=True)
        self._mod_quantities = tk.BooleanVar(value=True)

        self._type_vars:   dict[str, tk.BooleanVar] = {}
        self._storey_vars: dict[str, tk.BooleanVar] = {}

        # Cancellation signal — set by the Cancel button, polled by the load thread
        self._cancel_event = threading.Event()

        self._build_ui()

    # ══════════════════════════════════════════════════════════════════
    # UI construction
    # ══════════════════════════════════════════════════════════════════

    def _build_ui(self):
        # Root grid: one top-bar row + one body row; two body columns
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ── Top bar (spans both columns) ──────────────────────────────
        topbar = ctk.CTkFrame(self, fg_color="transparent")
        topbar.grid(row=0, column=0, columnspan=2, sticky="ew",
                    padx=16, pady=(12, 6))
        topbar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(topbar, text="IFC Extractor",
                     font=ctk.CTkFont(size=20, weight="bold")
                     ).grid(row=0, column=0, sticky="w")

        theme_row = ctk.CTkFrame(topbar, fg_color="transparent")
        theme_row.grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(theme_row, text="🌙", font=ctk.CTkFont(size=14)
                     ).pack(side="left", padx=(0, 4))
        self._theme_switch = ctk.CTkSwitch(
            theme_row, text="", width=46,
            command=self._toggle_theme,
            onvalue="light", offvalue="dark",
        )
        self._theme_switch.pack(side="left")
        ctk.CTkLabel(theme_row, text="☀️", font=ctk.CTkFont(size=14)
                     ).pack(side="left", padx=(4, 0))

        # ── Left pane ─────────────────────────────────────────────────
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=(0, 12))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(4, weight=1)   # filters row expands

        self._build_left(left)

        # ── Right pane ────────────────────────────────────────────────
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=(0, 12))
        right.grid_columnconfigure(0, weight=1)
        # row weight for the log textbox is set dynamically inside _build_right

        self._build_right(right)

    # ── LEFT pane content ─────────────────────────────────────────────

    def _build_left(self, parent):
        r = 0

        # Section: Files
        self._lbl(parent, r, "📂  IFC Files"); r += 1

        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.grid(row=r, column=0, sticky="ew", pady=(0, 4)); r += 1
        ctk.CTkButton(btn_row, text="Add Files", width=95,
                      command=self._add_files).pack(side="left", padx=(0, 5))
        ctk.CTkButton(btn_row, text="Clear", width=70,
                      fg_color="gray40", hover_color="gray30",
                      command=self._clear_files).pack(side="left", padx=(0, 5))
        ctk.CTkButton(btn_row, text="Load Files ▶", width=105,
                      command=self._load_files).pack(side="left")
        self._file_badge = ctk.CTkLabel(btn_row, text="",
                                         font=ctk.CTkFont(size=11),
                                         text_color="gray60")
        self._file_badge.pack(side="left", padx=8)

        file_frame = ctk.CTkFrame(parent)
        file_frame.grid(row=r, column=0, sticky="ew", pady=(0, 10)); r += 1
        file_frame.grid_columnconfigure(0, weight=1)
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

        # Section: Modules
        self._lbl(parent, r, "⚙️  Modules"); r += 1
        mod_row = ctk.CTkFrame(parent, fg_color="transparent")
        mod_row.grid(row=r, column=0, sticky="ew", pady=(0, 10)); r += 1
        for text, var in [
            ("Metadata",   self._mod_metadata),
            ("Hierarchy",  self._mod_hierarchy),
            ("Psets",      self._mod_psets),
            ("Quantities", self._mod_quantities),
        ]:
            ctk.CTkCheckBox(mod_row, text=text, variable=var,
                            font=ctk.CTkFont(size=12)).pack(side="left", padx=6)

        # Section: Filters
        self._lbl(parent, r, "🔍  Filters  (populated after Load)"); r += 1
        filters_outer = ctk.CTkFrame(parent, fg_color="transparent")
        filters_outer.grid(row=r, column=0, sticky="nsew", pady=(0, 4)); r += 1
        filters_outer.grid_columnconfigure((0, 1), weight=1)
        filters_outer.grid_rowconfigure(0, weight=1)
        parent.grid_rowconfigure(r - 1, weight=1)  # let filters expand

        self._type_panel = self._filter_panel(
            filters_outer, "IFC Type", col=0,
            select_all_cmd=lambda: self._select_all(self._type_vars),
            select_none_cmd=lambda: self._select_none(self._type_vars),
        )
        self._storey_panel = self._filter_panel(
            filters_outer, "Storey / Level", col=1,
            select_all_cmd=lambda: self._select_all(self._storey_vars),
            select_none_cmd=lambda: self._select_none(self._storey_vars),
        )

        ctk.CTkLabel(parent, text="Leave all unchecked to export everything",
                     font=ctk.CTkFont(size=10), text_color="gray55",
                     anchor="w").grid(row=r, column=0, sticky="w"); r += 1

    # ── RIGHT pane content ────────────────────────────────────────────

    def _build_right(self, parent):
        r = 0

        # Section: Export mode
        self._lbl(parent, r, "💾  Export mode"); r += 1
        mode_row = ctk.CTkFrame(parent, fg_color="transparent")
        mode_row.grid(row=r, column=0, sticky="ew", pady=(0, 8)); r += 1
        ctk.CTkRadioButton(mode_row, text="One file per IFC",
                           variable=self._export_mode,
                           value="per_ifc").pack(side="left")
        ctk.CTkRadioButton(mode_row, text="Merged (single file)",
                           variable=self._export_mode,
                           value="merged").pack(side="left", padx=20)

        # Output folder
        self._lbl(parent, r, "📁  Output folder"); r += 1
        folder_row = ctk.CTkFrame(parent, fg_color="transparent")
        folder_row.grid(row=r, column=0, sticky="ew", pady=(0, 10)); r += 1
        folder_row.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(folder_row, textvariable=self._output_dir
                     ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(folder_row, text="Browse", width=80,
                      command=self._browse_output
                      ).grid(row=0, column=1)

        # Run button
        self._run_btn = ctk.CTkButton(
            parent, text="▶   Run Extraction",
            height=44, font=ctk.CTkFont(size=15, weight="bold"),
            command=self._run,
        )
        self._run_btn.grid(row=r, column=0, sticky="ew", pady=(0, 6)); r += 1

        # Progress bar
        self._progress = ctk.CTkProgressBar(parent, mode="indeterminate", height=8)
        self._progress.grid(row=r, column=0, sticky="ew", pady=(0, 4)); r += 1
        self._progress.set(0)

        # Cancel button — hidden until a load is running
        self._cancel_btn = ctk.CTkButton(
            parent, text="⏹  Cancel",
            height=28, font=ctk.CTkFont(size=12),
            fg_color="gray35", hover_color="gray25",
            command=self._cancel_load,
        )
        self._cancel_btn.grid(row=r, column=0, sticky="ew", pady=(0, 6)); r += 1
        self._cancel_btn.grid_remove()   # hidden by default

        # Log
        self._lbl(parent, r, "📋  Log"); r += 1
        self._log = ctk.CTkTextbox(
            parent, font=ctk.CTkFont(family="Consolas", size=11),
            state="disabled",
        )
        self._log.grid(row=r, column=0, sticky="nsew"); r += 1
        parent.grid_rowconfigure(r - 1, weight=1)

    # ══════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════

    def _lbl(self, parent, row, text):
        ctk.CTkLabel(parent, text=text,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").grid(row=row, column=0, sticky="ew",
                                      pady=(8, 2))

    def _filter_panel(self, parent, title, col, select_all_cmd, select_none_cmd):
        frame = ctk.CTkFrame(parent)
        frame.grid(row=0, column=col, sticky="nsew",
                   padx=(0, 5) if col == 0 else (5, 0))
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        hdr = ctk.CTkFrame(frame, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))
        ctk.CTkLabel(hdr, text=title,
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        ctk.CTkButton(hdr, text="None", width=42, height=22,
                      font=ctk.CTkFont(size=11),
                      fg_color="gray40", hover_color="gray30",
                      command=select_none_cmd).pack(side="right", padx=(3, 0))
        ctk.CTkButton(hdr, text="All", width=36, height=22,
                      font=ctk.CTkFont(size=11),
                      command=select_all_cmd).pack(side="right")

        scroll = ctk.CTkScrollableFrame(frame)
        scroll.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        return scroll

    # ══════════════════════════════════════════════════════════════════
    # Theme
    # ══════════════════════════════════════════════════════════════════

    def _toggle_theme(self):
        mode = self._theme_switch.get()
        ctk.set_appearance_mode(mode)
        bg = "#2b2b2b" if mode == "dark" else "#ebebeb"
        fg = "white"   if mode == "dark" else "black"
        self._file_listbox.configure(bg=bg, fg=fg)

    # ══════════════════════════════════════════════════════════════════
    # File management
    # ══════════════════════════════════════════════════════════════════

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
        self._clear_filter_panel(self._type_panel,   self._type_vars)
        self._clear_filter_panel(self._storey_panel, self._storey_vars)

    def _update_file_badge(self):
        n = len(self._ifc_files)
        self._file_badge.configure(
            text=f"{n} file{'s' if n != 1 else ''} added" if n else ""
        )

    # ══════════════════════════════════════════════════════════════════
    # Load
    # ══════════════════════════════════════════════════════════════════

    def _load_files(self):
        if not self._ifc_files:
            self._log_msg("No files added — use 'Add Files' first.")
            return
        self._set_busy(True)
        threading.Thread(target=self._load_thread, daemon=True).start()

    def _load_thread(self):
        self._log_msg("Loading files…")
        self._loaded_dfs.clear()
        total_elements = 0
        cancelled = False

        for path in self._ifc_files:
            # ── Check for cancellation before starting each file ──────
            if self._cancel_event.is_set():
                cancelled = True
                break

            name = os.path.basename(path)
            try:
                self._log_msg(f"  Opening {name}…")
                ifc = ifcopenshell.open(path)
                dfs = {}

                if self._mod_metadata.get():
                    dfs["Metadata"] = metadata.extract(ifc, name, source_filepath=path)

                if not self._cancel_event.is_set() and self._mod_hierarchy.get():
                    self._log_msg("  Extracting hierarchy…")
                    dfs["Hierarchy"] = hierarchy.extract(
                        ifc, name, progress_callback=self._log_msg
                    )
                    if not dfs["Hierarchy"].empty:
                        total_elements += len(dfs["Hierarchy"])

                if not self._cancel_event.is_set() and self._mod_psets.get():
                    self._log_msg("  Extracting property sets…")
                    dfs["Psets"] = psets.extract(
                        ifc, name, progress_callback=self._log_msg
                    )

                if not self._cancel_event.is_set() and self._mod_quantities.get():
                    self._log_msg("  Extracting quantities…")
                    dfs["Quantities"] = quantities.extract(
                        ifc, name, progress_callback=self._log_msg
                    )

                self._loaded_dfs[path] = dfs
                self._log_msg(f"  ✓ {name} loaded.")

            except Exception as exc:
                self._log_msg(f"  ✗ Error loading {name}: {exc}")

        # ── Build filters from whatever was loaded ────────────────────
        all_flat = {k: df
                    for src in self._loaded_dfs.values()
                    for k, df in src.items()}
        ifc_types = get_unique_ifc_types(all_flat)
        storeys   = get_unique_storeys(all_flat)

        if cancelled:
            summary = (f"Cancelled — {len(self._loaded_dfs)} of "
                       f"{len(self._ifc_files)} file(s) loaded, "
                       f"{total_elements:,} hierarchy rows")
        else:
            summary = (f"Ready — {len(self._loaded_dfs)} file(s), "
                       f"{total_elements:,} hierarchy rows")

        self.after(0, lambda: self._on_load_done(ifc_types, storeys, summary))

    def _on_load_done(self, ifc_types, storeys, summary):
        self._populate_filter_panel(self._type_panel,   self._type_vars,   ifc_types)
        self._populate_filter_panel(self._storey_panel, self._storey_vars, storeys)
        self._file_badge.configure(text=summary, text_color="#3a9ad9")
        self._log_msg(summary)
        self._set_busy(False)

    # ══════════════════════════════════════════════════════════════════
    # Filters
    # ══════════════════════════════════════════════════════════════════

    def _populate_filter_panel(self, panel, var_dict, items):
        self._clear_filter_panel(panel, var_dict)
        for item in items:
            var = tk.BooleanVar(value=False)
            var_dict[item] = var
            ctk.CTkCheckBox(panel, text=item, variable=var,
                            font=ctk.CTkFont(size=11)).pack(anchor="w", pady=1)

    def _clear_filter_panel(self, panel, var_dict):
        for w in panel.winfo_children():
            w.destroy()
        var_dict.clear()

    def _select_all(self, var_dict):
        for v in var_dict.values():
            v.set(True)

    def _select_none(self, var_dict):
        for v in var_dict.values():
            v.set(False)

    # ══════════════════════════════════════════════════════════════════
    # Export
    # ══════════════════════════════════════════════════════════════════

    def _browse_output(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self._output_dir.set(folder)

    def _run(self):
        if not self._loaded_dfs:
            self._log_msg("No files loaded — click 'Load Files' first.")
            return
        self._set_busy(True)
        threading.Thread(target=self._run_thread, daemon=True).start()

    def _run_thread(self):
        self._log_msg("Applying filters and exporting…")

        selected_types   = [k for k, v in self._type_vars.items()   if v.get()]
        selected_storeys = [k for k, v in self._storey_vars.items() if v.get()]

        filtered = {
            src: apply_filters(
                dfs,
                ifc_types=selected_types   or None,
                storeys=selected_storeys or None,
            )
            for src, dfs in self._loaded_dfs.items()
        }

        output_dir = self._output_dir.get()
        try:
            if self._export_mode.get() == "per_ifc":
                out = exporter.export_per_ifc(
                    filtered, output_dir,
                    progress_callback=self._log_msg,
                )
                self._log_msg(f"✅  Done — {len(out)} file(s) written to {output_dir}")
            else:
                out = exporter.export_merged(
                    filtered, output_dir,
                    progress_callback=self._log_msg,
                )
                self._log_msg(f"✅  Done — merged file written to {out}")
        except Exception as exc:
            self._log_msg(f"❌  Export error: {exc}")

        self.after(0, lambda: self._set_busy(False))

    # ══════════════════════════════════════════════════════════════════
    # Busy state
    # ══════════════════════════════════════════════════════════════════

    def _set_busy(self, busy: bool):
        if busy:
            self._cancel_event.clear()
            self._run_btn.configure(state="disabled")
            self._cancel_btn.configure(state="normal", text="⏹  Cancel")
            self._cancel_btn.grid()          # show
            self._progress.configure(mode="indeterminate")
            self._progress.start()
        else:
            self._progress.stop()
            self._progress.configure(mode="determinate")
            self._progress.set(1)
            self._cancel_btn.grid_remove()   # hide
            self._run_btn.configure(state="normal")

    def _cancel_load(self):
        """Signal the running load thread to stop after its current operation."""
        self._cancel_event.set()
        self._cancel_btn.configure(state="disabled", text="Cancelling…")
        self._log_msg("  ⏹  Cancel requested — stopping after current step…")

    # ══════════════════════════════════════════════════════════════════
    # Log
    # ══════════════════════════════════════════════════════════════════

    def _log_msg(self, msg: str):
        """Append a line to the log textbox (safe to call from any thread)."""
        def _append():
            self._log.configure(state="normal")
            self._log.insert("end", msg + "\n")
            self._log.see("end")
            self._log.configure(state="disabled")
        self.after(0, _append)
