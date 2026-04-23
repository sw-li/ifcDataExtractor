"""
ui/i18n.py — String table for the IFC Extractor UI.

Usage
-----
    from ui.i18n import t

    # simple lookup
    label_text = t("btn_add", lang)

    # with placeholders
    msg = t("log_opening", lang, name="project.ifc")

Supported languages: "en", "fr"
Default fallback:    "en"
"""

from __future__ import annotations

_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # ── Section headers ───────────────────────────────────────────
        "sec_files":        "📂  IFC Files",
        "sec_modules":      "⚙️  Modules",
        "sec_filters":      "🔍  Filters  (populated after Load)",
        "filter_hint":      "Leave all unchecked to export everything",
        "sec_export_mode":  "💾  Export mode",
        "sec_output":       "📁  Output folder",
        "sec_log":          "📋  Log",

        # ── Buttons ───────────────────────────────────────────────────
        "btn_add":          "Add Files",
        "btn_clear":        "Clear",
        "btn_load":         "Load Files ▶",
        "btn_browse":       "Browse",
        "btn_run":          "▶   Run Extraction",
        "btn_cancel":       "⏹  Cancel",
        "btn_cancelling":   "Cancelling…",
        "btn_all":          "All",
        "btn_none":         "None",

        # ── Radio / mode ──────────────────────────────────────────────
        "mode_per_ifc":     "One file per IFC",
        "mode_merged":      "Merged (single file)",

        # ── Filter panel headers ──────────────────────────────────────
        "filter_type":      "IFC Type",
        "filter_storey":    "Storey / Level",

        # ── Module checkboxes ─────────────────────────────────────────
        "mod_metadata":     "Metadata",
        "mod_hierarchy":    "Hierarchy",
        "mod_psets":        "Psets",
        "mod_quantities":   "Quantities",

        # ── File dialogs ──────────────────────────────────────────────
        "dlg_add_title":    "Select IFC files",
        "dlg_ifc_files":    "IFC files",
        "dlg_all_files":    "All files",
        "dlg_output":       "Select output folder",

        # ── File badge  ({s} = "s" or "") ─────────────────────────────
        "badge_one":        "1 file added",
        "badge_many":       "{n} files added",

        # ── Log messages ──────────────────────────────────────────────
        "log_no_files":     "No files added — use 'Add Files' first.",
        "log_loading":      "Loading files…",
        "log_opening":      "  Opening {name}…",
        "log_hierarchy":    "  Extracting hierarchy…",
        "log_psets":        "  Extracting property sets…",
        "log_quantities":   "  Extracting quantities…",
        "log_file_ok":      "  ✓ {name} loaded.",
        "log_file_err":     "  ✗ Error loading {name}: {exc}",
        "log_cancelled":    "Cancelled — {loaded} of {total} file(s) loaded, {rows:,} hierarchy rows",
        "log_ready":        "Ready — {loaded} file(s), {rows:,} hierarchy rows",
        "log_no_loaded":    "No files loaded — click 'Load Files' first.",
        "log_exporting":    "Applying filters and exporting…",
        "log_done_per":     "✅  Done — {n} file(s) written to {folder}",
        "log_done_merged":  "✅  Done — merged file written to {path}",
        "log_export_err":   "❌  Export error: {exc}",
        "log_cancel_req":   "  ⏹  Cancel requested — stopping after current step…",
    },

    "fr": {
        # ── Section headers ───────────────────────────────────────────
        "sec_files":        "📂  Fichiers IFC",
        "sec_modules":      "⚙️  Modules",
        "sec_filters":      "🔍  Filtres  (remplis après le chargement)",
        "filter_hint":      "Tout décocher pour tout exporter",
        "sec_export_mode":  "💾  Mode d'export",
        "sec_output":       "📁  Dossier de sortie",
        "sec_log":          "📋  Journal",

        # ── Buttons ───────────────────────────────────────────────────
        "btn_add":          "Ajouter des fichiers",
        "btn_clear":        "Effacer",
        "btn_load":         "Charger ▶",
        "btn_browse":       "Parcourir",
        "btn_run":          "▶   Lancer l'extraction",
        "btn_cancel":       "⏹  Annuler",
        "btn_cancelling":   "Annulation…",
        "btn_all":          "Tout",
        "btn_none":         "Aucun",

        # ── Radio / mode ──────────────────────────────────────────────
        "mode_per_ifc":     "Un fichier par IFC",
        "mode_merged":      "Fusionné (fichier unique)",

        # ── Filter panel headers ──────────────────────────────────────
        "filter_type":      "Type IFC",
        "filter_storey":    "Niveau / Étage",

        # ── Module checkboxes ─────────────────────────────────────────
        "mod_metadata":     "Métadonnées",
        "mod_hierarchy":    "Hiérarchie",
        "mod_psets":        "Psets",
        "mod_quantities":   "Quantités",

        # ── File dialogs ──────────────────────────────────────────────
        "dlg_add_title":    "Sélectionner des fichiers IFC",
        "dlg_ifc_files":    "Fichiers IFC",
        "dlg_all_files":    "Tous les fichiers",
        "dlg_output":       "Sélectionner le dossier de sortie",

        # ── File badge ────────────────────────────────────────────────
        "badge_one":        "1 fichier ajouté",
        "badge_many":       "{n} fichiers ajoutés",

        # ── Log messages ──────────────────────────────────────────────
        "log_no_files":     "Aucun fichier ajouté — utilisez 'Ajouter des fichiers'.",
        "log_loading":      "Chargement des fichiers…",
        "log_opening":      "  Ouverture de {name}…",
        "log_hierarchy":    "  Extraction de la hiérarchie…",
        "log_psets":        "  Extraction des jeux de propriétés…",
        "log_quantities":   "  Extraction des quantités…",
        "log_file_ok":      "  ✓ {name} chargé.",
        "log_file_err":     "  ✗ Erreur lors du chargement de {name} : {exc}",
        "log_cancelled":    "Annulé — {loaded} sur {total} fichier(s) chargé(s), {rows:,} lignes de hiérarchie",
        "log_ready":        "Prêt — {loaded} fichier(s), {rows:,} lignes de hiérarchie",
        "log_no_loaded":    "Aucun fichier chargé — cliquez sur 'Charger'.",
        "log_exporting":    "Application des filtres et export en cours…",
        "log_done_per":     "✅  Terminé — {n} fichier(s) écrit(s) dans {folder}",
        "log_done_merged":  "✅  Terminé — fichier fusionné écrit : {path}",
        "log_export_err":   "❌  Erreur d'export : {exc}",
        "log_cancel_req":   "  ⏹  Annulation demandée — arrêt après l'étape en cours…",
    },
}

_FALLBACK = "en"


def t(key: str, lang: str = "en", **kwargs) -> str:
    """
    Return the translated string for *key* in *lang*.

    Any keyword arguments are substituted into the string with str.format().
    Falls back to English if the key or language is missing.
    """
    table = _STRINGS.get(lang) or _STRINGS[_FALLBACK]
    text = table.get(key) or _STRINGS[_FALLBACK].get(key, key)
    return text.format(**kwargs) if kwargs else text


def detect_lang() -> str:
    """
    Return "fr" when the OS locale is French, otherwise "en".
    """
    try:
        import locale
        loc = locale.getdefaultlocale()[0] or ""
        return "fr" if loc.lower().startswith("fr") else "en"
    except Exception:
        return "en"
