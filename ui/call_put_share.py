# ui/call_put_share.py
# ---------------------------------------------------------------------
# CALL vs PUT Share Dashboard
#
# Layout (2x2 figure):
#   [0,0] Daily 100% stacked bars: CALL vs PUT % of daily volume.
#   [0,1] Weekly 100% stacked bars: CALL vs PUT % of weekly volume.
#   [1,0] Per-issuer 100% stacked bars: CALL vs PUT % of issuer volume.
#   [1,1] Global pie: CALL vs PUT % of total volume.
#
# Public API:
#     update_plot(df)
#
# Required columns:
#     TRANSACTION_DATE, TXN_AMT, CALL_OPTION, ISSUER_NAME
# ---------------------------------------------------------------------

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional, List

import numpy as np
import pandas as pd
from pandas.api.types import is_datetime64_any_dtype

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.ticker as mticker


class CallPutShare(ttk.Frame):
    """2×2 dashboard visualizing CALL vs PUT share percentages."""

    def __init__(self, master: Optional[tk.Misc] = None) -> None:
        super().__init__(master)
        self._df: Optional[pd.DataFrame] = None
        self._build()

    # ------------------------------------------------------------------
    # Time-column helper
    # ------------------------------------------------------------------
    def _ensure_time_cols(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ensures DAY and WEEK columns exist.
        Optimized: avoids unnecessary copies & conversions.
        """
        if df is None or df.empty:
            return df

        s = df

        if "TRANSACTION_DATE" not in s.columns:
            return s

        # Convert to datetime only if needed
        if not is_datetime64_any_dtype(s["TRANSACTION_DATE"]):
            s = s.copy()
            s["TRANSACTION_DATE"] = pd.to_datetime(
                s["TRANSACTION_DATE"], errors="coerce"
            )

        s = s.dropna(subset=["TRANSACTION_DATE"])

        need_copy = "DAY" not in s.columns or "WEEK" not in s.columns
        if need_copy:
            s = s.copy()
            if "DAY" not in s.columns:
                s["DAY"] = s["TRANSACTION_DATE"].dt.normalize()
            if "WEEK" not in s.columns:
                s["WEEK"] = (
                    s["TRANSACTION_DATE"]
                    .dt.to_period("W-MON")
                    .dt.start_time
                )

        return s

    # ------------------------------------------------------------------
    # UI build
    # ------------------------------------------------------------------
    def _build(self) -> None:
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        container = tk.Frame(self, bg="white")
        container.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        container.rowconfigure(1, weight=1)
        container.columnconfigure(0, weight=1)

        # ---- Figure with 4 panels ----
        self.fig = Figure(figsize=(12, 6.8), dpi=100)
        gs = self.fig.add_gridspec(2, 2, hspace=0.35, wspace=0.30)

        self.ax_day = self.fig.add_subplot(gs[0, 0])
        self.ax_week = self.fig.add_subplot(gs[0, 1])
        self.ax_issuer = self.fig.add_subplot(gs[1, 0])
        self.ax_pie = self.fig.add_subplot(gs[1, 1])

        self.fig.subplots_adjust(
            left=0.06,
            right=0.98,
            bottom=0.10,
            top=0.94,
        )

        self.canvas = FigureCanvasTkAgg(self.fig, master=container)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.configure(bg="white")
        self.canvas_widget.grid(row=1, column=0, sticky="nsew")

        # Toolbar
        tb = NavigationToolbar2Tk(self.canvas, container, pack_toolbar=False)
        tb.grid(row=0, column=0, sticky="w", pady=(0, 6))
        try:
            tb.configure(background="white")
            for w in tb.winfo_children():
                w.configure(background="white")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def update_plot(self, df: pd.DataFrame) -> None:
        """Receives filtered DataFrame and redraws all four panels."""
        self._df = df
        self._draw_all()

    # ------------------------------------------------------------------
    # Main drawing routine
    # ------------------------------------------------------------------
    def _draw_all(self) -> None:
        # Clear all axes
        for ax in (self.ax_day, self.ax_week, self.ax_issuer, self.ax_pie):
            ax.clear()

        if self._df is None or self._df.empty:
            self._draw_empty("No data")
            return

        s = self._ensure_time_cols(self._df)

        required = {"TRANSACTION_DATE", "TXN_AMT", "CALL_OPTION", "ISSUER_NAME"}
        if not required.issubset(s.columns):
            missing = ", ".join(sorted(required - set(s.columns)))
            self._draw_empty(f"Missing columns: {missing}")
            return

        s["CALL_OPTION"] = s["CALL_OPTION"].astype(str)
        s["ISSUER_NAME"] = s["ISSUER_NAME"].astype(str)

        categories = sorted(s["CALL_OPTION"].unique())
        colors = self._get_callput_colors(categories)

        # Draw panels
        self._draw_daily(s, categories, colors)
        self._draw_weekly(s, categories, colors)
        self._draw_issuer(s, categories, colors)
        self._draw_pie(s, categories, colors)

        self.canvas.draw_idle()

    # ------------------------------------------------------------------
    # Empty state
    # ------------------------------------------------------------------
    def _draw_empty(self, msg: str) -> None:
        for ax in (self.ax_day, self.ax_week, self.ax_issuer, self.ax_pie):
            ax.text(
                0.5,
                0.5,
                msg,
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
        self.canvas.draw_idle()

    # ------------------------------------------------------------------
    # Daily CALL/PUT share (100% bars)
    # ------------------------------------------------------------------
    def _draw_daily(self, s: pd.DataFrame, cats: List[str], colors: List[str]) -> None:
        grp = (
            s.groupby(["DAY", "CALL_OPTION"], sort=False)["TXN_AMT"]
            .sum()
            .reset_index()
            .sort_values("DAY")
        )

        if grp.empty:
            self.ax_day.text(0.5, 0.5, "No daily data", ha="center", va="center")
            return

        pivot = grp.pivot(index="DAY", columns="CALL_OPTION", values="TXN_AMT").fillna(0.0)
        pivot = pivot.reindex(columns=cats)

        total = pivot.sum(axis=1)
        pct = (pivot.div(total.replace(0, np.nan), axis=0) * 100).fillna(0)

        days = list(pct.index)
        n = len(days)
        x = np.arange(n)

        bottom = np.zeros(n)
        for i, cat in enumerate(cats):
            vals = pct[cat].values
            self.ax_day.bar(x, vals, bottom=bottom, color=colors[i], alpha=0.9, label=cat)
            bottom += vals

        # Max 10 ticks
        max_ticks = 10
        if n <= max_ticks:
            idx = np.arange(n)
        else:
            idx = np.linspace(0, n - 1, max_ticks, dtype=int)

        labels = [days[i].strftime("%Y-%m-%d") for i in idx]
        self.ax_day.set_xticks(idx)
        self.ax_day.set_xticklabels(labels, rotation=20, ha="right")

        self.ax_day.set_ylim(0, 100)
        self.ax_day.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:.0f}%"))
        self.ax_day.grid(True, axis="y", alpha=0.3)
        self.ax_day.set_title("Daily CALL vs PUT Share (%)")
        self.ax_day.legend(loc="upper right", fontsize=8)

    # ------------------------------------------------------------------
    # Weekly CALL/PUT share
    # ------------------------------------------------------------------
    def _draw_weekly(self, s: pd.DataFrame, cats: List[str], colors: List[str]) -> None:
        grp = (
            s.groupby(["WEEK", "CALL_OPTION"], sort=False)["TXN_AMT"]
            .sum()
            .reset_index()
            .sort_values("WEEK")
        )

        if grp.empty:
            self.ax_week.text(0.5, 0.5, "No weekly data", ha="center", va="center")
            return

        pivot = grp.pivot(index="WEEK", columns="CALL_OPTION", values="TXN_AMT").fillna(0.0)
        pivot = pivot.reindex(columns=cats)

        total = pivot.sum(axis=1)
        pct = (pivot.div(total.replace(0, np.nan), axis=0) * 100).fillna(0)

        weeks = list(pct.index)
        n = len(weeks)
        x = np.arange(n)

        bottom = np.zeros(n)
        for i, cat in enumerate(cats):
            vals = pct[cat].values
            self.ax_week.bar(x, vals, bottom=bottom, color=colors[i], alpha=0.9, label=cat)
            bottom += vals

        max_ticks = 10
        if n <= max_ticks:
            idx = np.arange(n)
        else:
            idx = np.linspace(0, n - 1, max_ticks, dtype=int)

        labels = [
            f"{weeks[i].isocalendar().year}-W{weeks[i].isocalendar().week:02d}"
            for i in idx
        ]

        self.ax_week.set_xticks(idx)
        self.ax_week.set_xticklabels(labels, rotation=20, ha="right")

        self.ax_week.set_ylim(0, 100)
        self.ax_week.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:.0f}%"))
        self.ax_week.grid(True, axis="y", alpha=0.3)
        self.ax_week.set_title("Weekly CALL vs PUT Share (%)")
        self.ax_week.legend(loc="upper right", fontsize=8)

    # ------------------------------------------------------------------
    # Per-issuer CALL/PUT share
    # ------------------------------------------------------------------
    def _draw_issuer(self, s: pd.DataFrame, cats: List[str], colors: List[str]) -> None:
        grp = (
            s.groupby(["ISSUER_NAME", "CALL_OPTION"], sort=False)["TXN_AMT"]
            .sum()
            .reset_index()
        )

        if grp.empty:
            self.ax_issuer.text(0.5, 0.5, "No issuer data", ha="center", va="center")
            return

        pivot = grp.pivot(index="ISSUER_NAME", columns="CALL_OPTION", values="TXN_AMT").fillna(0)
        pivot = pivot.reindex(columns=cats)
        pivot = pivot.sort_index()

        total = pivot.sum(axis=1)
        pct = (pivot.div(total.replace(0, np.nan), axis=0) * 100).fillna(0)

        issuers = list(pct.index)
        x = np.arange(len(issuers))

        bottom = np.zeros(len(issuers))
        for i, cat in enumerate(cats):
            vals = pct[cat].values
            self.ax_issuer.bar(x, vals, bottom=bottom, color=colors[i], alpha=0.9, label=cat)
            bottom += vals

        self.ax_issuer.set_xticks(x)
        self.ax_issuer.set_xticklabels(issuers, rotation=20, ha="right")
        self.ax_issuer.set_ylim(0, 100)
        self.ax_issuer.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:.0f}%"))
        self.ax_issuer.grid(True, axis="y", alpha=0.3)
        self.ax_issuer.set_title("CALL vs PUT Share by Issuer (%)")
        self.ax_issuer.legend(loc="upper right", fontsize=8)

    # ------------------------------------------------------------------
    # Global CALL/PUT pie chart
    # ------------------------------------------------------------------
    def _draw_pie(self, s: pd.DataFrame, cats: List[str], colors: List[str]) -> None:
        grp = s.groupby("CALL_OPTION")["TXN_AMT"].sum()
        vals = [grp.get(c, 0.0) for c in cats]

        if sum(vals) == 0:
            self.ax_pie.text(0.5, 0.5, "No volume", ha="center", va="center")
            return

        self.ax_pie.pie(
            vals,
            labels=cats,
            autopct=lambda p: f"{p:.1f}%",
            colors=colors,
            startangle=90,
        )
        self.ax_pie.set_title("Global CALL vs PUT Share")
        self.ax_pie.axis("equal")

    # ------------------------------------------------------------------
    # Color selection for CALL/PUT
    # ------------------------------------------------------------------
    def _get_callput_colors(self, cats: List[str]) -> List[str]:
        """
        Assign stable colors:
          CALL → blue
          PUT  → orange
          others → fallback palette
        """
        palette = ["#2563eb", "#f97316", "#16a34a", "#9333ea"]
        out = []
        for i, c in enumerate(cats):
            key = c.upper()
            if key in ("CALL", "C"):
                out.append("#2563eb")  # blue
            elif key in ("PUT", "P"):
                out.append("#f97316")  # orange
            else:
                out.append(palette[i % len(palette)])
        return out
