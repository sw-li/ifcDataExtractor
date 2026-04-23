"""
ui/app.py — IFC Extractor UI (CustomTkinter, landscape two-column layout)

LEFT  column : Files · Modules · Filters
RIGHT column : Export options · Run · Progress · Log

Language switching (EN / FR) is live — no restart required.
"""

import os
import threading
import tkinter as tk

import customtkinter as ctk
import ifcopenshell

from extractor import metadata, hierarchy, psets, quantities
from filter import apply_filters, get_unique_ifc_types, get_unique_storeys
from ui.i18n import t, detect_lang
import exporter

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class IFCExtractorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("IFC Extractor")
        self.geometry("1100x640")
        self.minsize(900, 560)

        # ── Language ──────────────────────────────────────────────────
        self._lang: str = detect_lang()

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
    # Convenience
    # ══════════════════════════════════════════════════════════════════

    def _t(self, key: str, **kwargs) -> str:
        """Translate a key using the current language."""
        return t(key, self._lang, **kwargs)

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

        controls = ctk.CTkFrame(topbar, fg_color="transparent")
        controls.grid(row=0, column=1, sticky="e")

        # Language toggle — EN / FR
        self._lang_seg = ctk.CTkSegmentedButton(
            controls, values=["EN", "FR"],
            width=80, height=28,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._on_lang_change,
        )
        self._lang_seg.set(self._lang.upper())
        self._lang_seg.pack(side="left", padx=(0, 14))

        # Theme switch
        ctk.CTkLabel(controls, text="🌙", font=ctk.CTkFont(size=14)
                     ).pack(side="left", padx=(0, 4))
        self._theme_switch = ctk.CTkSwitch(
            controls, text="", width=46,
            command=self._toggle_theme,
            onvalue="light", offvalue="dark",
        )
        self._theme_switch.pack(side="left")
        ctk.CTkLabel(controls, text="☀️", font=ctk.CTkFont(size=14)
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
        self._lbl_files = self._lbl(parent, r, "sec_files"); r += 1

        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.grid(row=r, column=0, sticky="ew", pady=(0, 4)); r += 1
        self._btn_add = ctk.CTkButton(btn_row, text=self._t("btn_add"), width=95,
                                      command=self._add_files)
        self._btn_add.pack(side="left", padx=(0, 5))
        self._btn_clear = ctk.CTkButton(btn_row, text=self._t("btn_clear"), width=70,
                                        fg_color="gray40", hover_color="gray30",
                                        command=self._clear_files)
        self._btn_clear.pack(side="left", padx=(0, 5))
        self._btn_load = ctk.CTkButton(btn_row, text=self._t("btn_load"), width=105,
                                       command=self._load_files)
        self._btn_load.pack(side="left")
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
        self._lbl_modules = self._lbl(parent, r, "sec_modules"); r += 1
        mod_row = ctk.CTkFrame(parent, fg_color="transparent")
        mod_row.grid(row=r, column=0, sticky="ew", pady=(0, 10)); r += 1
        self._chk_metadata = ctk.CTkCheckBox(mod_row, text=self._t("mod_metadata"),
                                             variable=self._mod_metadata,
                                             font=ctk.CTkFont(size=12))
        self._chk_metadata.pack(side="left", padx=6)
        self._chk_hierarchy = ctk.CTkCheckBox(mod_row, text=self._t("mod_hierarchy"),
                                              variable=self._mod_hierarchy,
                                              font=ctk.CTkFont(size=12))
        self._chk_hierarchy.pack(side="left", padx=6)
        self._chk_psets = ctk.CTkCheckBox(mod_row, text=self._t("mod_psets"),
                                          variable=self._mod_psets,
                                          font=ctk.CTkFont(size=12))
        self._chk_psets.pack(side="left", padx=6)
        self._chk_quantities = ctk.CTkCheckBox(mod_row, text=self._t("mod_quantities"),
                                               variable=self._mod_quantities,
                                               font=ctk.CTkFont(size=12))
        self._chk_quantities.pack(side="left", padx=6)

        # Section: Filters
        self._lbl_filters = self._lbl(parent, r, "sec_filters"); r += 1
        filters_outer = ctk.CTkFrame(parent, fg_color="transparent")
        filters_outer.grid(row=r, column=0, sticky="nsew", pady=(0, 4)); r += 1
        filters_outer.grid_columnconfigure((0, 1), weight=1)
        filters_outer.grid_rowconfigure(0, weight=1)
        parent.grid_rowconfigure(r - 1, weight=1)  # let filters expand

        self._type_panel, self._lbl_type, self._btn_all_type, self._btn_none_type = \
            self._filter_panel(filters_outer, "filter_type", col=0,
                               all_cmd=lambda: self._select_all(self._type_vars),
                               none_cmd=lambda: self._select_none(self._type_vars))

        self._storey_panel, self._lbl_storey, self._btn_all_storey, self._btn_none_storey = \
            self._filter_panel(filters_outer, "filter_storey", col=1,
                               all_cmd=lambda: self._select_all(self._storey_vars),
                               none_cmd=lambda: self._select_none(self._storey_vars))

        self._lbl_filter_hint = ctk.CTkLabel(
            parent, text=self._t("filter_hint"),
            font=ctk.CTkFont(size=10), text_color="gray55", anchor="w")
        self._lbl_filter_hint.grid(row=r, column=0, sticky="w"); r += 1

    # ── RIGHT pane content ────────────────────────────────────────────

    def _build_right(self, parent):
        r = 0

        # Section: Export mode
        self._lbl_export_mode = self._lbl(parent, r, "sec_export_mode"); r += 1
        mode_row = ctk.CTkFrame(parent, fg_color="transparent")
        mode_row.grid(row=r, column=0, sticky="ew", pady=(0, 8)); r += 1
        self._radio_per_ifc = ctk.CTkRadioButton(
            mode_row, text=self._t("mode_per_ifc"),
            variable=self._export_mode, value="per_ifc")
        self._radio_per_ifc.pack(side="left")
        self._radio_merged = ctk.CTkRadioButton(
            mode_row, text=self._t("mode_merged"),
            variable=self._export_mode, value="merged")
        self._radio_merged.pack(side="left", padx=20)

        # Output folder
        self._lbl_output = self._lbl(parent, r, "sec_output"); r += 1
        folder_row = ctk.CTkFrame(parent, fg_color="transparent")
        folder_row.grid(row=r, column=0, sticky="ew", pady=(0, 10)); r += 1
        folder_row.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(folder_row, textvariable=self._output_dir
                     ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self._btn_browse = ctk.CTkButton(folder_row, text=self._t("btn_browse"),
                                         width=80, command=self._browse_output)
        self._btn_browse.grid(row=0, column=1)

        # Run button
        self._run_btn = ctk.CTkButton(
            parent, text=self._t("btn_run"),
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
            parent, text=self._t("btn_cancel"),
            height=28, font=ctk.CTkFont(size=12),
            fg_color="gray35", hover_color="gray25",
            command=self._cancel_load,
        )
        self._cancel_btn.grid(row=r, column=0, sticky="ew", pady=(0, 6)); r += 1
        self._cancel_btn.grid_remove()   # hidden by default

        # Log
        self._lbl_log = self._lbl(parent, r, "sec_log"); r += 1
        self._log = ctk.CTkTextbox(
            parent, font=ctk.CTkFont(family="Consolas", size=11),
            state="disabled",
        )
        self._log.grid(row=r, column=0, sticky="nsew"); r += 1
        parent.grid_rowconfigure(r - 1, weight=1)

    # ══════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════

    def _lbl(self, parent, row, key: str) -> ctk.CTkLabel:
        """Create a bold section-header label and return it for later updates."""
        lbl = ctk.CTkLabel(parent, text=self._t(key),
                           font=ctk.CTkFont(size=13, weight="bold"),
                           anchor="w")
        lbl.grid(row=row, column=0, sticky="ew", pady=(8, 2))
        return lbl

    def _filter_panel(self, parent, title_key: str, col: int,
                      all_cmd, none_cmd):
        """
        Build a filter panel and return
        (scroll_frame, title_label, btn_all, btn_none).
        """
        frame = ctk.CTkFrame(parent)
        frame.grid(row=0, column=col, sticky="nsew",
                   padx=(0, 5) if col == 0 else (5, 0))
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        hdr = ctk.CTkFrame(frame, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))
        lbl = ctk.CTkLabel(hdr, text=self._t(title_key),
                           font=ctk.CTkFont(size=12, weight="bold"))
        lbl.pack(side="left")
        btn_none = ctk.CTkButton(hdr, text=self._t("btn_none"), width=42, height=22,
                                 font=ctk.CTkFont(size=11),
                                 fg_color="gray40", hover_color="gray30",
                                 command=none_cmd)
        btn_none.pack(side="right", padx=(3, 0))
        btn_all = ctk.CTkButton(hdr, text=self._t("btn_all"), width=36, height=22,
                                font=ctk.CTkFont(size=11),
                                command=all_cmd)
        btn_all.pack(side="right")

        scroll = ctk.CTkScrollableFrame(frame)
        scroll.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        return scroll, lbl, btn_all, btn_none

    # ══════════════════════════════════════════════════════════════════
    # Language switching
    # ══════════════════════════════════════════════════════════════════

    def _on_lang_change(self, value: str):
        self._lang = value.lower()
        self._apply_lang()

    def _apply_lang(self):
        """Update every translatable widget text in-place."""
        # Section labels
        self._lbl_files.configure(text=self._t("sec_files"))
        self._lbl_modules.configure(text=self._t("sec_modules"))
        self._lbl_filters.configure(text=self._t("sec_filters"))
        self._lbl_filter_hint.configure(text=self._t("filter_hint"))
        self._lbl_export_mode.configure(text=self._t("sec_export_mode"))
        self._lbl_output.configure(text=self._t("sec_output"))
        self._lbl_log.configure(text=self._t("sec_log"))

        # File buttons
        self._btn_add.configure(text=self._t("btn_add"))
        self._btn_clear.configure(text=self._t("btn_clear"))
        self._btn_load.configure(text=self._t("btn_load"))

        # Module checkboxes
        self._chk_metadata.configure(text=self._t("mod_metadata"))
        self._chk_hierarchy.configure(text=self._t("mod_hierarchy"))
        self._chk_psets.configure(text=self._t("mod_psets"))
        self._chk_quantities.configure(text=self._t("mod_quantities"))

        # Filter panel headers + All/None buttons
        self._lbl_type.configure(text=self._t("filter_type"))
        self._btn_all_type.configure(text=self._t("btn_all"))
        self._btn_none_type.configure(text=self._t("btn_none"))
        self._lbl_storey.configure(text=self._t("filter_storey"))
        self._btn_all_storey.configure(text=self._t("btn_all"))
        self._btn_none_storey.configure(text=self._t("btn_none"))

        # Right pane
        self._radio_per_ifc.configure(text=self._t("mode_per_ifc"))
        self._radio_merged.configure(text=self._t("mode_merged"))
        self._btn_browse.configure(text=self._t("btn_browse"))
        self._run_btn.configure(text=self._t("btn_run"))

        # Cancel button only if it's showing (not cancelling in progress)
        if self._cancel_btn.cget("state") == "normal":
            self._cancel_btn.configure(text=self._t("btn_cancel"))

        # Refresh the file badge text
        self._update_file_badge()

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
            title=self._t("dlg_add_title"),
            filetypes=[
                (self._t("dlg_ifc_files"), "*.ifc"),
                (self._t("dlg_all_files"), "*.*"),
            ],
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
        if n == 0:
            text = ""
        elif n == 1:
            text = self._t("badge_one")
        else:
            text = self._t("badge_many", n=n)
        self._file_badge.configure(text=text)

    # ══════════════════════════════════════════════════════════════════
    # Load
    # ══════════════════════════════════════════════════════════════════

    def _load_files(self):
        if not self._ifc_files:
            self._log_msg(self._t("log_no_files"))
            return
        self._set_busy(True)
        threading.Thread(target=self._load_thread, daemon=True).start()

    def _load_thread(self):
        # Snapshot language at thread start so messages are consistent
        lang = self._lang

        self._log_msg(t("log_loading", lang))
        self._loaded_dfs.clear()
        total_elements = 0
        cancelled = False

        for path in self._ifc_files:
            if self._cancel_event.is_set():
                cancelled = True
                break

            name = os.path.basename(path)
            try:
                self._log_msg(t("log_opening", lang, name=name))
                ifc = ifcopenshell.open(path)
                dfs = {}

                if self._mod_metadata.get():
                    dfs["Metadata"] = metadata.extract(ifc, name, source_filepath=path)

                if not self._cancel_event.is_set() and self._mod_hierarchy.get():
                    self._log_msg(t("log_hierarchy", lang))
                    dfs["Hierarchy"] = hierarchy.extract(
                        ifc, name, progress_callback=self._log_msg
                    )
                    if not dfs["Hierarchy"].empty:
                        total_elements += len(dfs["Hierarchy"])

                if not self._cancel_event.is_set() and self._mod_psets.get():
                    self._log_msg(t("log_psets", lang))
                    dfs["Psets"] = psets.extract(
                        ifc, name, progress_callback=self._log_msg
                    )

                if not self._cancel_event.is_set() and self._mod_quantities.get():
                    self._log_msg(t("log_quantities", lang))
                    dfs["Quantities"] = quantities.extract(
                        ifc, name, progress_callback=self._log_msg
                    )

                self._loaded_dfs[path] = dfs
                self._log_msg(t("log_file_ok", lang, name=name))

            except Exception as exc:
                self._log_msg(t("log_file_err", lang, name=name, exc=exc))

        # Build filters
        all_flat = {k: df
                    for src in self._loaded_dfs.values()
                    for k, df in src.items()}
        ifc_types = get_unique_ifc_types(all_flat)
        storeys   = get_unique_storeys(all_flat)

        loaded = len(self._loaded_dfs)
        total  = len(self._ifc_files)
        if cancelled:
            summary = t("log_cancelled", lang,
                        loaded=loaded, total=total, rows=total_elements)
        else:
            summary = t("log_ready", lang, loaded=loaded, rows=total_elements)

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
        folder = filedialog.askdirectory(title=self._t("dlg_output"))
        if folder:
            self._output_dir.set(folder)

    def _run(self):
        if not self._loaded_dfs:
            self._log_msg(self._t("log_no_loaded"))
            return
        self._set_busy(True)
        threading.Thread(target=self._run_thread, daemon=True).start()

    def _run_thread(self):
        lang = self._lang

        self._log_msg(t("log_exporting", lang))

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
                self._log_msg(t("log_done_per", lang, n=len(out), folder=output_dir))
            else:
                out = exporter.export_merged(
                    filtered, output_dir,
                    progress_callback=self._log_msg,
                )
                self._log_msg(t("log_done_merged", lang, path=out))
        except Exception as exc:
            self._log_msg(t("log_export_err", lang, exc=exc))

        self.after(0, lambda: self._set_busy(False))

    # ══════════════════════════════════════════════════════════════════
    # Busy state
    # ══════════════════════════════════════════════════════════════════

    def _set_busy(self, busy: bool):
        if busy:
            self._cancel_event.clear()
            self._run_btn.configure(state="disabled")
            self._cancel_btn.configure(state="normal",
                                       text=self._t("btn_cancel"))
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
        self._cancel_btn.configure(state="disabled",
                                   text=self._t("btn_cancelling"))
        self._log_msg(self._t("log_cancel_req"))

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
