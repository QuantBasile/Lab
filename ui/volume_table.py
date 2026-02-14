"""
VolumeTable – summary pivot table of transaction volume per issuer.

What it does (current design):
- Pivot table: rows = selected group (e.g. DAY/WEEK/MONTH/UND_NAME/...), columns = ISSUER_NAME
- Modes:
    - ABSOLUT     -> sums of TXN_AMT
    - PRO_ZEILE_% -> row-normalised percentages (issuer columns in %), BUT:
         * Column ALL is ALWAYS absolute
         * Row ALL is ALWAYS absolute (issuer columns + ALL)
- Totals are ALWAYS ON (no checkbox):
    - Column "ALL" exists always
    - Row "ALL" exists always
- Buttons: only two
    - Copy Excel (blue)
    - Create HTML (light blue)
- Issuer column order: HSBC first (if present), then alphabetical
- HTML report:
    - sticky header + scroll container
    - highlights max-issuer cell per row (light green)
    - click row to highlight entire row

Notes:
- Group-by options are controlled by GROUP_BY_OPTIONS below.
- The grouping columns should exist in your incoming DataFrame and ideally be strings (DAY/WEEK/MONTH, etc.).
"""

from __future__ import annotations

import os
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

import numpy as np
import pandas as pd

from ui.table_widget import TableFrame


# =========================
# USER CONFIG
# =========================
# Choose which columns are allowed in "Gruppieren nach".
# Keep them as STRING columns if you want them treated as categorical groupings.
GROUP_BY_OPTIONS = (
    "UND_NAME",
    "CALL_OPTION",
    "UND_TYPE",
    "TYPE",
    "DAY",
    "WEEK",
    "MONTH",
    # "ISIN",  # intentionally disabled (too many groups)
)


class VolumeTable(ttk.Frame):
    """Pivot-style summary of volume per issuer."""

    GROUP_FIELDS = GROUP_BY_OPTIONS
    MODES = ("ABSOLUT", "PRO_ZEILE_%")

    def __init__(self, master=None) -> None:
        super().__init__(master)

        # Input data
        self._df: Optional[pd.DataFrame] = None

        # Pivot storage
        self._pivot_abs: pd.DataFrame = pd.DataFrame()
        self._pivot_view: pd.DataFrame = pd.DataFrame()

        # UI state
        self._group_by = tk.StringVar(value=self.GROUP_FIELDS[0] if self.GROUP_FIELDS else "UND_NAME")
        self._mode = tk.StringVar(value="ABSOLUT")
        self._index_name = "UND_NAME"

        self._shape_var = tk.StringVar(value="Dimensionen: 0 × 0")

        self._configure_styles()
        self._build_ui()

    # ----------------------------------------------------------------------
    # STYLES
    # ----------------------------------------------------------------------
    def _configure_styles(self) -> None:
        """Apply lightweight green background styling + button colors."""
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        self.LIGHT_GREEN = "#e6f7ec"
        style.configure("VolumeTable.TFrame", background=self.LIGHT_GREEN)
        self.configure(style="VolumeTable.TFrame")

        # Buttons
        style.configure(
            "CopyExcel.TButton",
            background="#1e40af",
            foreground="white",
            padding=(10, 6),
        )
        style.map("CopyExcel.TButton", background=[("active", "#1d4ed8")])

        style.configure(
            "CreateHtml.TButton",
            background="#38bdf8",
            foreground="#0b1220",
            padding=(10, 6),
        )
        style.map("CreateHtml.TButton", background=[("active", "#7dd3fc")])

    # ----------------------------------------------------------------------
    # UI BUILD
    # ----------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        # ----- Top controls -----
        top = ttk.Frame(self, style="VolumeTable.TFrame")
        top.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        for c in range(20):
            top.columnconfigure(c, weight=0)
        top.columnconfigure(19, weight=1)

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

        # Only two buttons (as requested)
        ttk.Button(
            top,
            text="Copy Excel",
            style="CopyExcel.TButton",
            command=self._copy_to_clipboard_excel,
        ).grid(row=0, column=4, padx=(16, 6))

        ttk.Button(
            top,
            text="Create HTML",
            style="CreateHtml.TButton",
            command=self._create_html_report,
        ).grid(row=0, column=5, padx=(6, 0))

        #only hsbc
        self._only_zero_hsbc = tk.BooleanVar(value=False)
        
        right = ttk.Frame(top)
        right.grid(row=0, column=99, sticky="e")   # top sigue con grid
        
        ttk.Checkbutton(
            right,
            text="Hide zero HSBC",
            variable=self._only_zero_hsbc,
            command=self._refresh_table
        ).pack(side="left", padx=5)


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

        # Issuer column order: HSBC first (if present), then alphabetical
        cols = list(pv.columns)
        hsbc = [c for c in cols if "HSBC" in str(c).upper()]
        rest = [c for c in cols if c not in hsbc]
        rest = sorted(rest)
        pv = pv.reindex(hsbc + rest, axis=1)

        # Sort rows descending by total
        pv = pv.loc[pv.sum(axis=1).sort_values(ascending=False).index]

        self._pivot_abs = pv.rename_axis(index=self._index_name, columns="ISSUER_NAME")
        self._pivot_abs.columns.name = None  # remove phantom header

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
        """
        Compute the view pivot, applying % mode.

        Totals are ALWAYS appended.
        """
        pv = self._pivot_abs.copy()
        if pv.empty:
            return pv

        mode = self._mode.get()

        if mode == "ABSOLUT":
            out = pv
        else:  # PRO_ZEILE_%
            sums = pv.sum(axis=1).replace(0, np.nan)
            out = (pv.div(sums, axis=0).fillna(0.0) * 100.0)

        # ALWAYS append totals
        out = self._append_totals(out, mode)
        return out

    def _append_totals(self, df: pd.DataFrame, mode: str) -> pd.DataFrame:
        """
        Append totals row/column.
    
        Rules:
          - Column ALL is ALWAYS absolute.
          - Row ALL:
              * ABSOLUT     -> absolute totals
              * PRO_ZEILE_% -> percentages by issuer (sum to 100),
                              BUT column ALL stays absolute
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
    
        issuer_cols = [c for c in df.columns if c != "ALL"]
    
        if mode == "ABSOLUT":
            # Row ALL: absolute
            df.loc["ALL", issuer_cols] = abs_col_totals.reindex(issuer_cols).fillna(0.0).values
            df.loc["ALL", "ALL"] = abs_grand_total
            return df
    
        # mode == PRO_ZEILE_%
        # Row ALL: percentages across issuers (share of grand total)
        if abs_grand_total > 0:
            pct = (abs_col_totals.reindex(issuer_cols).fillna(0.0) / abs_grand_total) * 100.0
        else:
            pct = pd.Series(0.0, index=issuer_cols)
    
        df.loc["ALL", issuer_cols] = pct.values
        df.loc["ALL", "ALL"] = abs_grand_total  # keep absolute
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

            df_show = self._pivot_view.reset_index().rename(columns={self._index_name: "GROUP"})
            # --- FILTER: hide rows where HSBC volume == 0 (numeric) ---
            if self._only_zero_hsbc.get():
                hsbc_cols = [c for c in self._pivot_view.columns if "HSBC" in str(c).upper()]
                if hsbc_cols:
                    hsbc_col = hsbc_cols[0]  # normalmente solo hay una
                    # ojo: NO elimines la fila ALL
                    mask = (self._pivot_view[hsbc_col] != 0)
                    if "ALL" in self._pivot_view.index:
                        mask.loc["ALL"] = True
                    df_show = df_show[mask.reindex(self._pivot_view.index, fill_value=True).values]

            
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
    # CLIPBOARD, HTML
    # ----------------------------------------------------------------------
    def _excel_copy_df(self) -> pd.DataFrame:
        """Return an Excel-friendly (numeric) DataFrame matching the current view requirements."""
        if self._pivot_view.empty:
            return pd.DataFrame()

        mode = self._mode.get()
        df_out = self._pivot_view.copy()

        if mode == "ABSOLUT":
            for c in df_out.columns:
                df_out[c] = pd.to_numeric(df_out[c], errors="coerce").fillna(0.0).round(0).astype(int)
        else:
            for c in df_out.columns:
                if c == "ALL":
                    df_out[c] = pd.to_numeric(df_out[c], errors="coerce").fillna(0.0).round(0).astype(int)
                else:
                    df_out[c] = pd.to_numeric(df_out[c], errors="coerce").fillna(0.0).round(1)

            # Row ALL must be absolute in issuer columns too (integers)
            if "ALL" in df_out.index:
                issuer_cols = [c for c in df_out.columns if c != "ALL"]
                df_out.loc["ALL", issuer_cols] = (
                    pd.to_numeric(df_out.loc["ALL", issuer_cols], errors="coerce")
                    .fillna(0.0)
                    .round(0)
                    .astype(int)
                    .values
                )

        df_out = df_out.reset_index().rename(columns={self._index_name: "GROUP"})
        df_out.columns.name = None
        return df_out

    def _copy_to_clipboard_excel(self) -> None:
        """Copy current view to clipboard as TSV (paste straight into Excel)."""
        if self._pivot_view.empty:
            messagebox.showinfo("Copy Excel", "Keine Daten zum Kopieren.")
            return

        try:
            df_out = self._excel_copy_df()
            tsv = df_out.to_csv(sep="\t", index=False, lineterminator="\n")
            self.clipboard_clear()
            self.clipboard_append(tsv)
            self.update()
            messagebox.showinfo("Copy Excel", "Tabelle in die Zwischenablage kopiert (Excel-ready).")
        except Exception as ex:
            messagebox.showerror("Copy Excel", f"Konnte nicht kopiert werden:\n{ex}")

    def _create_html_report(self) -> None:
        """Create an HTML report and copy its path to the clipboard."""
        if self._pivot_view.empty:
            messagebox.showinfo("Create HTML", "Keine Daten für den Report.")
            return

        try:
            # DISPLAY formatting for HTML
            df_disp = self._pivot_view.reset_index().rename(columns={self._index_name: "GROUP"})
            df_disp = self._format_df_for_display(df_disp, self._mode.get())

            # winners (max issuer per row) computed from numeric pivot_view
            numeric = self._pivot_view.copy()
            issuer_cols = [c for c in numeric.columns if c != "ALL"]

            winners = {}
            for idx in numeric.index:
                g = str(idx)
                if g == "ALL":
                    continue
                row = numeric.loc[idx, issuer_cols]
                if row.empty:
                    continue
                # idxmax on numeric row
                winners[g] = str(row.idxmax())

            # manual html table (for cell classes)
            cols = list(df_disp.columns)
            thead = "<thead><tr>" + "".join([f"<th>{c}</th>" for c in cols]) + "</tr></thead>"

            rows_html = []
            for _, r in df_disp.iterrows():
                g = str(r["GROUP"])
                tds = []
                for c in cols:
                    val = r[c]
                    cls = ""
                    if c != "GROUP" and g in winners and winners[g] == c:
                        cls = ' class="maxcell"'
                    if c == "GROUP":
                        tds.append(f"<td>{val}</td>")
                    else:
                        tds.append(f"<td{cls}>{val}</td>")
                rows_html.append("<tr>" + "".join(tds) + "</tr>")

            tbody = "<tbody>" + "".join(rows_html) + "</tbody>"
            html_table = f'<div class="table-wrap"><table id="vol-table">{thead}{tbody}</table></div>'

            reports_dir = os.path.abspath(os.path.join(os.getcwd(), "reports"))
            os.makedirs(reports_dir, exist_ok=True)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"volume_table_{self._group_by.get()}_{self._mode.get()}_{ts}.html"
            fpath = os.path.join(reports_dir, fname)

            title = f"VolumeTable – {self._group_by.get()} – {self._mode.get()} – {ts}"

            html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 18px; }}
    h2 {{ margin: 0 0 12px 0; }}
    .table-wrap {{ max-height: 95vh; overflow: auto; border: 1px solid #d1d5db; border-radius: 10px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #d1d5db; padding: 6px 8px; text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{ background: #e6f7ec; font-weight: 600; position: sticky; top: 0; z-index: 2; }}
    tr:nth-child(even) td {{ background: #fbfffc; }}
    .maxcell {{ background: #e6f7ec !important; }}
    tr.selected td {{ background: #cfe8ff !important; }}
  </style>
</head>
<body>
  <h2>{title}</h2>
  {html_table}
  <script>
    document.querySelectorAll("#vol-table tbody tr").forEach(tr => {{
      tr.addEventListener("click", () => {{
        document.querySelectorAll("#vol-table tbody tr.selected")
          .forEach(x => x.classList.remove("selected"));
        tr.classList.add("selected");
      }});
    }});
  </script>
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
