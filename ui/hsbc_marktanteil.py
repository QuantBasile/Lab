"""
HSBCMarketShare
----------------
This tab focuses specifically on HSBC. It displays all underlyings
in which HSBC participated, together with:

- HSBC volume for the latest month and latest week
- Market share (%) for month and week
- Change in market share vs previous period (in percentage points)
- Total market volume (latest month only)
- Sortable columns
- Copy selected rows
- Export to CSV

Public API:
    update_plot(df)
"""

from __future__ import annotations

import csv
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Dict, List, Any, Tuple

import numpy as np
import pandas as pd
from pandas.api.types import is_datetime64_any_dtype


class HSBCMarktanteil(ttk.Frame):
    """Market share breakdown per underlying, focusing on HSBC."""

    TARGET_ISSUER = "HSBC"

    # Column order / header mapping
    COLUMNS = [
        "UNDERLYING",
        "HSBC_VOL_M",
        "SHARE_M_PCT",
        "DELTA_M_PP",
        "HSBC_VOL_W",
        "SHARE_W_PCT",
        "DELTA_W_PP",
        "TOT_VOL_M",
    ]

    HEADERS = [
        "Underlying",
        "HSBC Volume (Month)",
        "Market Share Month (%)",
        "Δ Market Share Month (pp)",
        "HSBC Volume (Week)",
        "Market Share Week (%)",
        "Δ Market Share Week (pp)",
        "Total Market Volume (Month)",
    ]

    def __init__(self, master=None) -> None:
        super().__init__(master)

        self._df: Optional[pd.DataFrame] = None
        self._summary_df: Optional[pd.DataFrame] = None

        self._sort_state: Dict[str, bool] = {}  # col -> ascending

        self._build_ui()

    # ----------------------------------------------------------------------
    # --- Time column helper ------------------------------------------------
    # ----------------------------------------------------------------------
    @staticmethod
    def _ensure_time_columns(df: pd.DataFrame) -> pd.DataFrame:
        """
        Ensure WEEK and MONTH columns exist and are datetime-typed.
        """
        if df is None or df.empty:
            return df

        s = df
        if "TRANSACTION_DATE" not in s.columns:
            return s

        if not is_datetime64_any_dtype(s["TRANSACTION_DATE"]):
            s = s.copy()
            s["TRANSACTION_DATE"] = pd.to_datetime(
                s["TRANSACTION_DATE"], errors="coerce"
            )

        s = s.dropna(subset=["TRANSACTION_DATE"])

        if "WEEK" not in s.columns or "MONTH" not in s.columns:
            s = s.copy()
            if "WEEK" not in s.columns:
                s["WEEK"] = s["TRANSACTION_DATE"].dt.to_period("W-MON").dt.start_time
            if "MONTH" not in s.columns:
                s["MONTH"] = s["TRANSACTION_DATE"].dt.to_period("M").dt.start_time

        return s

    # ----------------------------------------------------------------------
    # --- UI construction ---------------------------------------------------
    # ----------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        # --- Top bar -------------------------------------------------------
        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        top.columnconfigure(0, weight=1)

        ttk.Label(
            top,
            text="HSBC Market Share by Underlying",
            font=("Segoe UI Semibold", 11),
        ).grid(row=0, column=0, sticky="w", padx=(2, 8))

        ttk.Button(top, text="Copy", command=self._copy_selection).grid(
            row=0, column=1, padx=(4, 4)
        )
        ttk.Button(top, text="Export CSV", command=self._export_csv).grid(
            row=0, column=2, padx=(0, 2)
        )

        # --- Table ---------------------------------------------------------
        table_frame = ttk.Frame(self)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 4))
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_frame, show="headings", selectmode="extended"
        )

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        # Styling
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "HSBC.Treeview",
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground="#111111",
            rowheight=24,
            font=("Segoe UI", 10),
        )
        style.configure(
            "HSBC.Treeview.Heading",
            background="#1e40af",
            foreground="#ffffff",
            font=("Segoe UI Semibold", 10),
            padding=(6, 4),
        )
        self.tree.configure(style="HSBC.Treeview")

        # Row stripes
        self.tree.tag_configure("even", background="#f9fafb")
        self.tree.tag_configure("odd", background="#ffffff")

        # ctrl+c
        self.tree.bind("<Control-c>", lambda e: self._copy_selection())

        # --- Bottom info labels -------------------------------------------
        info = ttk.Frame(self)
        info.grid(row=2, column=0, sticky="w", padx=10, pady=(2, 8))

        self.lbl_months = ttk.Label(info, text="", font=("Segoe UI", 9))
        self.lbl_weeks = ttk.Label(info, text="", font=("Segoe UI", 9))

        self.lbl_months.grid(row=0, column=0, sticky="w", padx=(0, 20))
        self.lbl_weeks.grid(row=0, column=1, sticky="w")

    # ----------------------------------------------------------------------
    # --- Public API --------------------------------------------------------
    # ----------------------------------------------------------------------
    def update_plot(self, df: pd.DataFrame) -> None:
        """Main entry point for external modules."""
        self._df = df
        self._refresh()

    # ----------------------------------------------------------------------
    # --- Refresh logic -----------------------------------------------------
    # ----------------------------------------------------------------------
    def _refresh(self) -> None:
        """Compute summary dataframe and update the Treeview."""
        self._reset_tree()

        if self._df is None or self._df.empty:
            self._show_empty()
            return

        s = self._ensure_time_columns(self._df)

        # Determine underlying column
        und_col = self._resolve_underlying_column(s)
        s["ISSUER_NAME"] = s["ISSUER_NAME"].astype(str)

        mask_hsbc = s["ISSUER_NAME"] == self.TARGET_ISSUER
        if not mask_hsbc.any():
            self._show_empty()
            return

        # Available time periods
        weeks = sorted(s["WEEK"].dropna().unique())
        months = sorted(s["MONTH"].dropna().unique())

        if not weeks or not months:
            self._show_empty()
            return

        # Last + previous week/month
        last_week, prev_week = self._last_two(weeks)
        last_month, prev_month = self._last_two(months)

        # Monthly summary
        m_last, m_prev = self._compute_monthly(s, und_col, last_month, prev_month)

        # Weekly summary
        w_last, w_prev = self._compute_weekly(s, und_col, last_week, prev_week)

        # Build combined rows
        summary = self._build_summary(m_last, m_prev, w_last, w_prev)
        if summary.empty:
            self._show_empty()
            return

        # Default sort: descending HSBC monthly volume
        summary = summary.sort_values("HSBC_VOL_M", ascending=False).reset_index(drop=True)
        self._summary_df = summary

        # Build table headers and populate tree
        self._build_tree_schema()
        self._populate_tree(summary)

        # Bottom info
        self._update_info_labels(last_month, prev_month, last_week, prev_week)

    # ----------------------------------------------------------------------
    # --- Helpers: summary-building ----------------------------------------
    # ----------------------------------------------------------------------
    def _update_info_labels(self, last_month, prev_month, last_week, prev_week) -> None:
        """Update the bottom info labels for last/previous month and week."""

        def fmt(value):
            if value is None or pd.isna(value):
                return "-"
            try:
                return pd.to_datetime(value).strftime("%Y-%m-%d")
            except Exception:
                return str(value)
    
        self.lbl_months.config(
            text=f"Latest Month: {fmt(last_month)}   ·   Previous Month: {fmt(prev_month)}"
        )
        self.lbl_weeks.config(
            text=f"Latest Week: {fmt(last_week)}   ·   Previous Week: {fmt(prev_week)}"
        )

    
    
    @staticmethod
    def _last_two(values: List[Any]) -> Tuple[Any, Optional[Any]]:
        """Return (last, second_last_or_None)."""
        if not values:
            return None, None
        if len(values) == 1:
            return values[-1], None
        return values[-1], values[-2]

    @staticmethod
    def _resolve_underlying_column(df: pd.DataFrame) -> str:
        """Determine best underlying column from available options."""
        for col in ("UND_NAME", "NAME", "UNDERLYING"):
            if col in df.columns:
                return col
        df["UNDERLYING"] = "(unknown)"
        return "UNDERLYING"

    def _compute_monthly(
        self,
        s: pd.DataFrame,
        und_col: str,
        last_m,
        prev_m,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Return (df_last_month, df_prev_month)."""
        tot = (
            s.groupby(["MONTH", und_col], observed=False)["TXN_AMT"]
            .sum()
            .rename("TOT_M")
        )
        hsbc = (
            s[s["ISSUER_NAME"] == self.TARGET_ISSUER]
            .groupby(["MONTH", und_col], observed=False)["TXN_AMT"]
            .sum()
            .rename("HSBC_M")
        )
        df = pd.concat([hsbc, tot], axis=1).reset_index()
        df["HSBC_M"] = df["HSBC_M"].fillna(0.0)
        df["TOT_M"] = df["TOT_M"].fillna(0.0)
        df["SHARE_M_PCT"] = np.where(df["TOT_M"] > 0, df["HSBC_M"] / df["TOT_M"] * 100, 0)

        df_last = df[df["MONTH"] == last_m].set_index(und_col)
        df_prev = df[df["MONTH"] == prev_m].set_index(und_col) if prev_m is not None else \
            pd.DataFrame(columns=df.columns).set_index(und_col)

        return df_last, df_prev

    def _compute_weekly(
        self,
        s: pd.DataFrame,
        und_col: str,
        last_w,
        prev_w,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Return (df_last_week, df_prev_week)."""
        tot = (
            s.groupby(["WEEK", und_col], observed=False)["TXN_AMT"]
            .sum()
            .rename("TOT_W")
        )
        hsbc = (
            s[s["ISSUER_NAME"] == self.TARGET_ISSUER]
            .groupby(["WEEK", und_col], observed=False)["TXN_AMT"]
            .sum()
            .rename("HSBC_W")
        )
        df = pd.concat([hsbc, tot], axis=1).reset_index()
        df["HSBC_W"] = df["HSBC_W"].fillna(0.0)
        df["TOT_W"] = df["TOT_W"].fillna(0.0)
        df["SHARE_W_PCT"] = np.where(df["TOT_W"] > 0, df["HSBC_W"] / df["TOT_W"] * 100, 0)

        df_last = df[df["WEEK"] == last_w].set_index(und_col)
        df_prev = df[df["WEEK"] == prev_w].set_index(und_col) if prev_w is not None else \
            pd.DataFrame(columns=df.columns).set_index(und_col)

        return df_last, df_prev

    def _build_summary(
        self,
        m_last: pd.DataFrame,
        m_prev: pd.DataFrame,
        w_last: pd.DataFrame,
        w_prev: pd.DataFrame,
    ) -> pd.DataFrame:
        """Combine monthly + weekly metrics into the final summary table."""
        rows = []

        for underlying, row_m in m_last.iterrows():
            vol_m = float(row_m.get("HSBC_M", 0.0))
            share_m = float(row_m.get("SHARE_M_PCT", 0.0))
            tot_vol_m = float(row_m.get("TOT_M", 0.0))

            # monthly delta
            prev_m_row = m_prev.loc[underlying] if underlying in m_prev.index else None
            delta_m = share_m - (float(prev_m_row.get("SHARE_M_PCT", 0.0)) if prev_m_row is not None else 0.0)

            # weekly
            if underlying in w_last.index:
                row_w = w_last.loc[underlying]
                vol_w = float(row_w.get("HSBC_W", 0.0))
                share_w = float(row_w.get("SHARE_W_PCT", 0.0))
            else:
                vol_w = 0.0
                share_w = 0.0

            # weekly delta
            prev_w_row = w_prev.loc[underlying] if underlying in w_prev.index else None
            delta_w = share_w - (float(prev_w_row.get("SHARE_W_PCT", 0.0)) if prev_w_row is not None else 0.0)

            rows.append(
                {
                    "UNDERLYING": underlying,
                    "HSBC_VOL_M": vol_m,
                    "SHARE_M_PCT": share_m,
                    "DELTA_M_PP": delta_m,
                    "HSBC_VOL_W": vol_w,
                    "SHARE_W_PCT": share_w,
                    "DELTA_W_PP": delta_w,
                    "TOT_VOL_M": tot_vol_m,
                }
            )

        return pd.DataFrame(rows)

    # ----------------------------------------------------------------------
    # --- Treeview rendering ------------------------------------------------
    # ----------------------------------------------------------------------
    def _reset_tree(self) -> None:
        """Clear Treeview and column definitions."""
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = []
        for col in self.tree["columns"]:
            self.tree.heading(col, text="")
        self._summary_df = None
        self._sort_state = {}

    def _show_empty(self) -> None:
        """Show an empty state in the table."""
        self.tree["columns"] = ("UNDERLYING",)
        self.tree.heading("UNDERLYING", text="Underlying")
        self.lbl_months.config(text="Latest Month: -   ·   Previous Month: -")
        self.lbl_weeks.config(text="Latest Week: -   ·   Previous Week: -")

    def _build_tree_schema(self) -> None:
        """Configure Treeview columns and sorting callbacks."""
        self.tree["columns"] = self.COLUMNS
        for col, header in zip(self.COLUMNS, self.HEADERS):
            anchor = "w" if col == "UNDERLYING" else "e"
            self.tree.heading(
                col,
                text=header,
                anchor=anchor,
                command=lambda c=col: self._on_sort(c),
            )
            self.tree.column(col, width=130, anchor=anchor, stretch=True)

    def _populate_tree(self, df: pd.DataFrame) -> None:
        """Fill Treeview with formatted rows."""
        self.tree.delete(*self.tree.get_children())

        for idx, row in df.iterrows():
            vals = [
                row["UNDERLYING"],
                f"{row['HSBC_VOL_M']:,.0f}".replace(",", " "),
                f"{row['SHARE_M_PCT']:.2f}",
                f"{row['DELTA_M_PP']:+.2f}",
                f"{row['HSBC_VOL_W']:,.0f}".replace(",", " "),
                f"{row['SHARE_W_PCT']:.2f}",
                f"{row['DELTA_W_PP']:+.2f}",
                f"{row['TOT_VOL_M']:,.0f}".replace(",", " "),
            ]

            tag = "even" if idx % 2 == 0 else "odd"
            self.tree.insert("", "end", values=vals, tags=(tag,))

    # ----------------------------------------------------------------------
    # --- Sorting -----------------------------------------------------------
    # ----------------------------------------------------------------------
    def _on_sort(self, col: str) -> None:
        """Sort the summary table by the given column."""
        if self._summary_df is None or self._summary_df.empty:
            return

        asc = not self._sort_state.get(col, False)
        self._sort_state = {col: asc}

        df_sorted = self._summary_df.sort_values(col, ascending=asc).reset_index(drop=True)
        self._summary_df = df_sorted

        # Update column headers to show arrow
        for c, header in zip(self.COLUMNS, self.HEADERS):
            arrow = ""
            if c == col:
                arrow = " ▲" if asc else " ▼"
            self.tree.heading(
                c,
                text=header + arrow,
                command=lambda cc=c: self._on_sort(cc),
            )

        self._populate_tree(df_sorted)

    # ----------------------------------------------------------------------
    # --- Copy / Export -----------------------------------------------------
    # ----------------------------------------------------------------------
    def _copy_selection(self) -> None:
        """Copy selected rows to clipboard as CSV text."""
        sel = self.tree.selection()
        if not sel:
            return

        lines = [",".join(self.HEADERS)]
        for iid in sel:
            vals = [str(v) for v in self.tree.item(iid, "values")]
            safe = []
            for v in vals:
                v = v.replace('"', '""')
                if any(ch in v for ch in [",", '"', "\n"]):
                    v = f'"{v}"'
                safe.append(v)
            lines.append(",".join(safe))

        text = "\n".join(lines)
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
        except Exception:
            pass  # Sometimes clipboard access is restricted (SSH, etc.)

    def _export_csv(self) -> None:
        """Export the current table to a CSV file."""
        if self._summary_df is None or self._summary_df.empty:
            messagebox.showinfo("Export", "No data to export.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export HSBC Market Share as CSV",
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.HEADERS)
                for iid in self.tree.get_children():
                    vals = self.tree.item(iid, "values")
                    writer.writerow(vals)
        except Exception as ex:
            messagebox.showerror("Export", f"Error while exporting:\n{ex}")
        else:
            messagebox.showinfo("Export", f"Successfully exported to:\n{path}")
