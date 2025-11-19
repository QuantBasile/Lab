"""
VolumeTable – summary pivot table of transaction volume per issuer.

Features:
- Group by: UND_NAME / CALL_OPTION / UND_TYPE / TYPE
- Modes: ABSOLUT (sum of TXN_AMT) or PRO_ZEILE_% (row-normalised %)
- Optional totals (row "ALL" and column "ALL")
- Copy to clipboard (TSV)
- Export to CSV
- Status bar showing visible table dimensions
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Tuple

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
        for c in range(10):
            top.columnconfigure(c, weight=0)
        top.columnconfigure(9, weight=1)

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
        ttk.Button(top, text="Kopieren", command=self._copy_to_clipboard).grid(
            row=0, column=5, padx=(12, 4)
        )
        ttk.Button(top, text="Als CSV exportieren", command=self._export_csv).grid(
            row=0, column=6, padx=(4, 0)
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

        # Best guess for UND_NAME based on your dataset
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
            out = (pv.div(sums, axis=0).fillna(0) * 100.0)

        if self._with_totals.get():
            out = self._append_totals(out, mode)

        return out

    def _append_totals(self, df: pd.DataFrame, mode: str) -> pd.DataFrame:
        """Append totals row/column depending on mode."""
        df = df.copy()
        if df.empty:
            return df

        if mode == "ABSOLUT":
            # Add row totals, column totals, and grand total
            row_totals = df.sum(axis=1)
            col_totals = df.sum(axis=0)
            grand = row_totals.sum()

            df["ALL"] = row_totals
            df.loc["ALL"] = list(col_totals.values) + [grand]

        else:  # PRO_ZEILE_%
            df["ALL"] = 100.0
            col_avg = df.drop(columns=["ALL"], errors="ignore").mean(axis=0)
            df.loc["ALL"] = list(col_avg.values) + [100.0]

        return df

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
                self._pivot_view
                .reset_index()
                .rename(columns={self._index_name: "GROUP"})
            )

            self.table.show_dataframe(df_show)
            self._force_right_alignment()

            rows, cols = df_show.shape
            self._update_shape_label(rows, cols)

        except Exception as ex:
            messagebox.showerror(
                "Fehler",
                f"Tabelle konnte nicht aktualisiert werden:\n{ex}",
            )

    def _force_right_alignment(self) -> None:
        """Align all Treeview columns to the right."""
        tree = self.table._tree
        for col in tree["columns"]:
            tree.column(col, anchor="e")

    # ----------------------------------------------------------------------
    # EXPORT & CLIPBOARD
    # ----------------------------------------------------------------------
    def _export_csv(self) -> None:
        if self._pivot_view.empty:
            messagebox.showinfo("Exportieren", "Keine Daten zum Exportieren.")
            return

        df_out = self._pivot_view.reset_index().rename(columns={self._index_name: "GROUP"})
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        try:
            df_out.to_csv(path, index=False)
            messagebox.showinfo("Exportieren", f"Erfolgreich exportiert:\n{path}")
        except Exception as ex:
            messagebox.showerror("Exportieren", f"Export fehlgeschlagen:\n{ex}")

    def _copy_to_clipboard(self) -> None:
        """Copy current table view to clipboard (TSV)."""
        if self._pivot_view.empty:
            messagebox.showinfo("Kopieren", "Keine Daten zum Kopieren.")
            return

        df_out = self._pivot_view.reset_index().rename(columns={self._index_name: "GROUP"})
        try:
            tsv = df_out.to_csv(sep="\t", index=False)
            self.clipboard_clear()
            self.clipboard_append(tsv)
            self.update()
            messagebox.showinfo("Kopieren", "Tabelle in die Zwischenablage kopiert.")
        except Exception as ex:
            messagebox.showerror("Kopieren", f"Konnte nicht kopiert werden:\n{ex}")

    # ----------------------------------------------------------------------
    # HELPER
    # ----------------------------------------------------------------------
    def _update_shape_label(self, rows: int, cols: int) -> None:
        self._shape_var.set(f"Dimensionen: {rows} × {cols}")
