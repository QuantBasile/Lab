"""
VolumeTable – summary pivot table of transaction volume per issuer.

Features:
- Group by: UND_NAME / CALL_OPTION / UND_TYPE / TYPE
- Modes: ABSOLUT (sum of TXN_AMT) or PRO_ZEILE_% (row-normalised %)
- Optional totals (row "ALL" and column "ALL")
- Copy to clipboard (Excel-ready TSV)
- Export to CSV
- Create HTML report (stores in ./reports and copies path to clipboard)
- Status bar showing visible table dimensions
"""

from __future__ import annotations

import os
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional

import numpy as np
import pandas as pd

from ui.table_widget import TableFrame


class VolumeTable(ttk.Frame):
    """Pivot-style summary of volume per issuer."""

    GROUP_FIELDS = ("UND_NAME", "CALL_OPTION", "UND_TYPE", "TYPE")
    MODES = ("ABSOLUT", "PRO_ZEILE_%")

    def __init__(self, master=None) -> None:
        super().__init__(master)

        # Input data
        self._df: Optional[pd.DataFrame] = None

        # Pivot storage
        self._pivot_abs: pd.DataFrame = pd.DataFrame()
        self._pivot_view: pd.DataFrame = pd.DataFrame()

        # UI state
        self._group_by = tk.StringVar(value="UND_NAME")
        self._mode = tk.StringVar(value="ABSOLUT")
        self._with_totals = tk.BooleanVar(value=True)
        self._index_name = "UND_NAME"

        self._shape_var = tk.StringVar(value="Dimensionen: 0 × 0")

        self._configure_styles()
        self._build_ui()

    # ----------------------------------------------------------------------
    # STYLES
    # ----------------------------------------------------------------------
    def _configure_styles(self) -> None:
        """Apply lightweight green background styling."""
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        self.LIGHT_GREEN = "#e6f7ec"
        style.configure("VolumeTable.TFrame", background=self.LIGHT_GREEN)
        self.configure(style="VolumeTable.TFrame")

    # ----------------------------------------------------------------------
    # UI BUILD
    # ----------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        # ----- Top controls -----
        top = ttk.Frame(self, style="VolumeTable.TFrame")
        top.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        for c in range(12):
            top.columnconfigure(c, weight=0)
        top.columnconfigure(11, weight=1)

        ttk.Label(top, text="Gruppieren nach:").grid(row=0, column=0, padx=(0, 6))
        group_combo = ttk.Combobox(
            top,
            values=self.GROUP_FIELDS,
            textvariable=self._group_by,
            width=14,
            state="readonly",
        )
        group_combo.grid(row=0, column=1)
        group_combo.bind("<<ComboboxSelected>>", lambda e: self._rebuild_and_refresh())

        ttk.Label(top, text="Ansicht:").grid(row=0, column=2, padx=(12, 6))
        mode_combo = ttk.Combobox(
            top,
            values=self.MODES,
            textvariable=self._mode,
            width=12,
            state="readonly",
        )
        mode_combo.grid(row=0, column=3)
        mode_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_table())

        chk_totals = ttk.Checkbutton(
            top,
            text="Summen einblenden",
            variable=self._with_totals,
            command=self._refresh_table,
        )
        chk_totals.grid(row=0, column=4, padx=(12, 0))

        # Copy & export buttons
        ttk.Button(top, text="Kopieren", command=self._copy_to_clipboard_excel).grid(
            row=0, column=5, padx=(12, 4)
        )
        ttk.Button(top, text="Als CSV exportieren", command=self._export_csv).grid(
            row=0, column=6, padx=(4, 4)
        )
        ttk.Button(top, text="Create HTML", command=self._create_html_report).grid(
            row=0, column=7, padx=(4, 0)
        )

        # ----- Table -----
        body = ttk.Frame(self, style="VolumeTable.TFrame")
        body.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 4))
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        self.table = TableFrame(body)
        self.table.grid(row=0, column=0, sticky="nsew")

        # ----- Status bar -----
        status = ttk.Frame(self, style="VolumeTable.TFrame")
        status.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        status.columnconfigure(0, weight=1)

        ttk.Label(status, textvariable=self._shape_var, anchor="e").grid(
            row=0, column=0, sticky="e"
        )

    # ----------------------------------------------------------------------
    # PUBLIC API
    # ----------------------------------------------------------------------
    def update_view(self, df: pd.DataFrame) -> None:
        """Receive filtered DataFrame and refresh the table."""
        self._df = df
        self._rebuild_and_refresh()

    # ----------------------------------------------------------------------
    # TABLE REBUILD & REFRESH LOGIC
    # ----------------------------------------------------------------------
    def _rebuild_and_refresh(self) -> None:
        self._prepare_pivot_abs()
        self._refresh_table()

    def _prepare_pivot_abs(self) -> None:
        """Compute the base absolute-value pivot table."""
        self._pivot_abs = pd.DataFrame()
        self._pivot_view = pd.DataFrame()

        if self._df is None or self._df.empty:
            return

        s = self._df.copy()
        grp_field = self._group_by.get()

        idx_col = self._resolve_index_column(s, grp_field)
        self._index_name = grp_field if grp_field != "UND_NAME" else "UND_NAME"

        if "ISSUER_NAME" not in s or "TXN_AMT" not in s:
            return

        pv = pd.pivot_table(
            s,
            index=idx_col,
            columns="ISSUER_NAME",
            values="TXN_AMT",
            aggfunc="sum",
            fill_value=0.0,
            observed=False,
        )

        pv = pv.reindex(sorted(pv.columns), axis=1)

        # Sort rows descending by total
        pv = pv.loc[pv.sum(axis=1).sort_values(ascending=False).index]

        self._pivot_abs = pv.rename_axis(index=self._index_name, columns="ISSUER_NAME")
        self._pivot_abs.columns.name = None   # <- quita el header fantasma "ISSUER_NAME"

    def _resolve_index_column(self, df: pd.DataFrame, grp: str) -> str:
        """Determine the internal index column to use for pivot."""
        if grp != "UND_NAME":
            if grp not in df.columns:
                df[grp] = f"({grp} fehlt)"
            return grp

        # UND_NAME → prefer existing column
        if "UND_NAME" in df.columns:
            return "UND_NAME"
        if "NAME" in df.columns:
            df["UND_NAME_FALLBACK"] = df["NAME"]
            return "UND_NAME_FALLBACK"

        df["UND_NAME_SYN"] = "(UND_NAME fehlt)"
        return "UND_NAME_SYN"

    # ----------------------------------------------------------------------
    # VIEW MODE COMPUTATION
    # ----------------------------------------------------------------------
    def _compute_view(self) -> pd.DataFrame:
        """Compute the view pivot, applying % mode and totals if selected."""
        pv = self._pivot_abs.copy()
        if pv.empty:
            return pv

        mode = self._mode.get()

        if mode == "ABSOLUT":
            out = pv
        else:  # PRO_ZEILE_%
            sums = pv.sum(axis=1).replace(0, np.nan)
            out = (pv.div(sums, axis=0).fillna(0.0) * 100.0)

        if self._with_totals.get():
            out = self._append_totals(out, mode)

        return out

    def _append_totals(self, df: pd.DataFrame, mode: str) -> pd.DataFrame:
        """Append totals row/column.

        Requirement:
          - Column ALL is ALWAYS absolute, regardless of mode.
          - In PRO_ZEILE_%, issuer columns stay in %; ALL stays absolute.
        """
        df = df.copy()
        if df.empty:
            return df

        # Absolute totals source (always)
        abs_row_totals = self._pivot_abs.sum(axis=1)
        abs_col_totals = self._pivot_abs.sum(axis=0)
        abs_grand_total = float(abs_row_totals.sum())

        # Column ALL: always absolute row totals
        df["ALL"] = abs_row_totals.reindex(df.index).fillna(0.0)

        # Row ALL
        if mode == "ABSOLUT":
            issuer_cols = [c for c in df.columns if c != "ALL"]
            df.loc["ALL", issuer_cols] = abs_col_totals.reindex(issuer_cols).fillna(0.0).values
            df.loc["ALL", "ALL"] = abs_grand_total
        else:
            issuer_cols = [c for c in df.columns if c != "ALL"]
            base_idx = [i for i in df.index if i != "ALL"]
            df.loc["ALL", issuer_cols] = df.loc[base_idx, issuer_cols].mean(axis=0).values
            df.loc["ALL", "ALL"] = abs_grand_total

        return df

    # ----------------------------------------------------------------------
    # DISPLAY FORMATTING
    # ----------------------------------------------------------------------
    @staticmethod
    def _fmt_abs(x) -> str:
        """Absolute formatting: integer with thousands commas."""
        try:
            return f"{int(round(float(x))):,}"
        except Exception:
            return ""

    @staticmethod
    def _fmt_pct_1d(x) -> str:
        """Percentage formatting: 1 decimal, dot as decimal separator."""
        try:
            return f"{float(x):.1f}"
        except Exception:
            return ""

    def _format_df_for_display(self, df: pd.DataFrame, mode: str) -> pd.DataFrame:
        """Format values for the Treeview display."""
        out = df.copy()
        for c in out.columns:
            if c == "GROUP":
                continue
            if mode == "ABSOLUT":
                out[c] = out[c].map(self._fmt_abs)
            else:  # PRO_ZEILE_%
                if c == "ALL":
                    out[c] = out[c].map(self._fmt_abs)
                else:
                    out[c] = out[c].map(self._fmt_pct_1d)
        return out

    # ----------------------------------------------------------------------
    # TABLE UPDATE
    # ----------------------------------------------------------------------
    def _refresh_table(self) -> None:
        """Update the Treeview from the current pivot view."""
        try:
            self._pivot_view = self._compute_view()

            if self._pivot_view.empty:
                self.table.show_dataframe(pd.DataFrame(columns=[self._index_name]))
                self._force_right_alignment()
                self._update_shape_label(0, 0)
                return

            # Move ALL row to bottom
            if "ALL" in self._pivot_view.index:
                idx = [i for i in self._pivot_view.index if i != "ALL"] + ["ALL"]
                self._pivot_view = self._pivot_view.loc[idx]

            df_show = (
                self._pivot_view.reset_index().rename(columns={self._index_name: "GROUP"})
            )

            # Format for UI
            df_show = self._format_df_for_display(df_show, self._mode.get())

            self.table.show_dataframe(df_show)
            self._force_right_alignment()

            rows, cols = df_show.shape
            self._update_shape_label(rows, cols)

        except Exception as ex:
            messagebox.showerror("Fehler", f"Tabelle konnte nicht aktualisiert werden:\n{ex}")

    def _force_right_alignment(self) -> None:
        """Align all Treeview columns to the right."""
        tree = self.table._tree
        for col in tree["columns"]:
            tree.column(col, anchor="e")

    # ----------------------------------------------------------------------
    # EXPORT, CLIPBOARD, HTML
    # ----------------------------------------------------------------------
    def _export_csv(self) -> None:
        """Export numeric table (not formatted strings)."""
        if self._pivot_view.empty:
            messagebox.showinfo("Exportieren", "Keine Daten zum Exportieren.")
            return

        df_out = self._pivot_view.reset_index().rename(columns={self._index_name: "GROUP"})
        df_out.columns.name = None
        fpath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not fpath:
            return
        try:
            df_out.to_csv(fpath, index=False)
            messagebox.showinfo("Exportieren", f"Erfolgreich exportiert:\n{fpath}")
        except Exception as ex:
            messagebox.showerror("Exportieren", f"Export fehlgeschlagen:\n{ex}")

    def _excel_copy_df(self) -> pd.DataFrame:
        """Return an Excel-friendly (numeric) DataFrame matching the current view requirements."""
        if self._pivot_view.empty:
            return pd.DataFrame()

        mode = self._mode.get()

        # Start from the computed numeric view (already has ALL absolute if totals enabled)
        df_out = self._pivot_view.copy()

        # Enforce numeric shapes for Excel:
        # - ABSOLUT: integers
        # - PRO_ZEILE_%: issuer columns 1 decimal, ALL absolute integers
        if mode == "ABSOLUT":
            for c in df_out.columns:
                df_out[c] = pd.to_numeric(df_out[c], errors="coerce").fillna(0.0).round(0).astype(int)
        else:
            for c in df_out.columns:
                if c == "ALL":
                    df_out[c] = pd.to_numeric(df_out[c], errors="coerce").fillna(0.0).round(0).astype(int)
                else:
                    df_out[c] = pd.to_numeric(df_out[c], errors="coerce").fillna(0.0).round(1)

        df_out = df_out.reset_index().rename(columns={self._index_name: "GROUP"})
        df_out.columns.name = None
        return df_out

    def _copy_to_clipboard_excel(self) -> None:
        """Copy current view to clipboard as TSV (paste straight into Excel)."""
        if self._pivot_view.empty:
            messagebox.showinfo("Kopieren", "Keine Daten zum Kopieren.")
            return

        try:
            df_out = self._excel_copy_df()
            # Excel paste: tabs + newlines
            tsv = df_out.to_csv(sep="\t", index=False, lineterminator="\n")
            self.clipboard_clear()
            self.clipboard_append(tsv)
            self.update()
            messagebox.showinfo("Kopieren", "Tabelle in die Zwischenablage kopiert (Excel-ready).")
        except Exception as ex:
            messagebox.showerror("Kopieren", f"Konnte nicht kopiert werden:\n{ex}")

    def _create_html_report(self) -> None:
        """Create an HTML report and copy its path to the clipboard."""
        if self._pivot_view.empty:
            messagebox.showinfo("Create HTML", "Keine Daten für den Report.")
            return

        try:
            # Use the DISPLAY formatting for the HTML (human-friendly)
            df_show = self._pivot_view.reset_index().rename(columns={self._index_name: "GROUP"})
            df_show = self._format_df_for_display(df_show, self._mode.get())

            reports_dir = os.path.abspath(os.path.join(os.getcwd(), "reports"))
            os.makedirs(reports_dir, exist_ok=True)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"volume_table_{self._group_by.get()}_{self._mode.get()}_{ts}.html"
            fpath = os.path.join(reports_dir, fname)

            title = f"VolumeTable – {self._group_by.get()} – {self._mode.get()} – {ts}"

            html_table = df_show.to_html(index=False, escape=False)
            html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 18px; }}
    h2 {{ margin: 0 0 12px 0; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #d1d5db; padding: 6px 8px; text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{ background: #e6f7ec; font-weight: 600; }}
    tr:nth-child(even) td {{ background: #fbfffc; }}
  </style>
</head>
<body>
  <h2>{title}</h2>
  {html_table}
</body>
</html>"""

            with open(fpath, "w", encoding="utf-8") as f:
                f.write(html)

            # Copy path (as file:// URL) to clipboard
            url = "file://" + fpath.replace("\\", "/")
            self.clipboard_clear()
            self.clipboard_append(url)
            self.update()

            messagebox.showinfo("Create HTML", f"HTML erstellt. Pfad (URL) kopiert:\n{url}")
        except Exception as ex:
            messagebox.showerror("Create HTML", f"Konnte HTML nicht erstellen:\n{ex}")

    # ----------------------------------------------------------------------
    # HELPER
    # ----------------------------------------------------------------------
    def _update_shape_label(self, rows: int, cols: int) -> None:
        self._shape_var.set(f"Dimensionen: {rows} × {cols}")
