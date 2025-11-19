"""
VolumeSummary – Zwei Histogramme:

[0,0] Stacked volume per issuer (Σ TXN_AMT), optionally broken down by UND_TYPE.
       - Each stacked segment labelled with % contribution.
       - Top of each bar labelled with total volume.

[0,1] Market share histogram (% of total volume per issuer).

Public API:
    update_view(df)

This module expects at minimum:
    - ISSUER_NAME
    - TXN_AMT
    - (optional) UND_TYPE
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional, Iterable

import numpy as np
import pandas as pd
import matplotlib.ticker as mticker
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from utils.issuer_colors import get_issuer_color


class VolumeSummary(ttk.Frame):
    """Summary view: stacked volume + market share (per issuer)."""

    def __init__(self, master=None) -> None:
        super().__init__(master)
        self._df: Optional[pd.DataFrame] = None
        self._build_ui()

    # ----------------------------------------------------------------------
    # --- UI Construction ---------------------------------------------------
    # ----------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        # ------ LEFT PANEL ------ (stacked histogram)
        left = tk.Frame(self, bg="white", bd=0, highlightthickness=0)
        left.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=10)
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        self.fig_left = Figure(figsize=(6, 4.2), dpi=100)
        self.ax_left = self.fig_left.add_subplot(111)
        self.fig_left.subplots_adjust(left=0.08, right=0.98, top=0.9, bottom=0.30)

        self.canvas_left = FigureCanvasTkAgg(self.fig_left, master=left)
        self.canvas_left.get_tk_widget().configure(bg="white", highlightthickness=0)
        self.canvas_left.get_tk_widget().grid(row=1, column=0, sticky="nsew")

        tb_left = NavigationToolbar2Tk(self.canvas_left, left, pack_toolbar=False)
        tb_left.grid(row=0, column=0, sticky="w", pady=(0, 6))
        self._set_toolbar_background(tb_left)

        # ------ RIGHT PANEL ------ (market share)
        right = tk.Frame(self, bg="white", bd=0, highlightthickness=0)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 10), pady=10)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        self.fig_right = Figure(figsize=(6, 4.2), dpi=100)
        self.ax_right = self.fig_right.add_subplot(111)
        self.fig_right.subplots_adjust(left=0.08, right=0.98, top=0.9, bottom=0.30)

        self.canvas_right = FigureCanvasTkAgg(self.fig_right, master=right)
        self.canvas_right.get_tk_widget().configure(bg="white", highlightthickness=0)
        self.canvas_right.get_tk_widget().grid(row=1, column=0, sticky="nsew")

        tb_right = NavigationToolbar2Tk(self.canvas_right, right, pack_toolbar=False)
        tb_right.grid(row=0, column=0, sticky="w", pady=(0, 6))
        self._set_toolbar_background(tb_right)

    @staticmethod
    def _set_toolbar_background(toolbar: NavigationToolbar2Tk) -> None:
        """Safely set all toolbar backgrounds to white."""
        try:
            toolbar.configure(background="white")
            for w in toolbar.winfo_children():
                try:
                    w.configure(background="white")
                except Exception:
                    pass
        except Exception:
            pass

    # ----------------------------------------------------------------------
    # --- Public API --------------------------------------------------------
    # ----------------------------------------------------------------------
    def update_view(self, df: pd.DataFrame) -> None:
        """Receive filtered DataFrame and redraw both summary plots."""
        self._df = df
        self._draw()

    # ----------------------------------------------------------------------
    # --- Formatting Helpers ------------------------------------------------
    # ----------------------------------------------------------------------
    @staticmethod
    def _format_volume_tick(x, pos) -> str:
        """Human-readable volume: 12,345 or 1.2M, 10M, etc."""
        abs_x = abs(x)
        if abs_x >= 1_000_000:
            v = x / 1_000_000
            return f"{v:,.0f}M" if abs_x >= 10_000_000 else f"{v:,.1f}M"
        return f"{x:,.0f}"

    @staticmethod
    def _format_pct_tick(x, pos) -> str:
        """Percentage ticks."""
        return f"{x:.0f} %"

    # ----------------------------------------------------------------------
    # --- Drawing / Main Logic ---------------------------------------------
    # ----------------------------------------------------------------------
    def _draw(self) -> None:
        self.ax_left.clear()
        self.ax_right.clear()

        if self._df is None or self._df.empty:
            self._draw_empty()
            return

        df = self._df

        if "ISSUER_NAME" not in df or "TXN_AMT" not in df:
            self._draw_empty("Spalten fehlen")
            return

        # Order emitters by volume descending
        totals_by_issuer = (
            df.groupby("ISSUER_NAME", dropna=False, observed=False)["TXN_AMT"]
            .sum()
            .sort_values(ascending=False)
        )
        emitters = totals_by_issuer.index.tolist()
        totals = totals_by_issuer.values.astype(float)

        total_all = totals.sum()
        total_all_safe = total_all if total_all > 0 else 1.0

        x = np.arange(len(emitters))

        # ---------------------------------------------------------------
        # LEFT: STACKED HISTOGRAM (WITH OPTIONAL UND_TYPE)
        # ---------------------------------------------------------------
        if "UND_TYPE" in df:
            self._draw_stacked_by_undtype(df, emitters, x)
        else:
            self._draw_simple_bars(df, emitters, totals, x)

        # ---------------------------------------------------------------
        # RIGHT: MARKET SHARE
        # ---------------------------------------------------------------
        market_share = (totals / total_all_safe) * 100
        self._draw_market_share(emitters, x, market_share)

        self.canvas_left.draw_idle()
        self.canvas_right.draw_idle()

    # ----------------------------------------------------------------------
    # --- Left Panel Construction ------------------------------------------
    # ----------------------------------------------------------------------
    def _draw_stacked_by_undtype(
        self, df: pd.DataFrame, emitters: Iterable[str], x: np.ndarray
    ) -> None:
        """Draw left histogram as stacked volume per UND_TYPE."""
        pivot = (
            df.groupby(["ISSUER_NAME", "UND_TYPE"], dropna=False, observed=False)["TXN_AMT"]
            .sum()
            .unstack(fill_value=0.0)
            .reindex(emitters)
        )

        und_types = list(pivot.columns)
        bottom = np.zeros(len(emitters), float)

        # Simple palette
        base_colors = ["#2563eb", "#059669", "#f97316", "#7c3aed", "#e11d48"]
        colors = {ut: base_colors[i % len(base_colors)] for i, ut in enumerate(und_types)}

        totals_per_issuer = pivot.sum(axis=1).values

        for ut in und_types:
            vals = pivot[ut].values.astype(float)
            bars = self.ax_left.bar(
                x, vals, bottom=bottom, label=str(ut), color=colors[ut], alpha=0.9
            )

            # % label inside each bar segment
            for i, b in enumerate(bars):
                h = b.get_height()
                tot = totals_per_issuer[i]
                if h > 0 and tot > 0:
                    pct = (h / tot) * 100
                    bx = b.get_x() + b.get_width() / 2
                    by = b.get_y() + h / 2
                    self.ax_left.text(
                        bx,
                        by,
                        f"{pct:.1f}%",
                        ha="center",
                        va="center",
                        fontsize=8,
                        color="white" if pct > 10 else "black",
                    )

            bottom += vals

        self.ax_left.legend(title="UND_TYPE", fontsize=8, title_fontsize=9)

        # Total on top
        for i, vol in enumerate(bottom):
            if vol > 0:
                self.ax_left.text(
                    x[i],
                    vol,
                    self._format_volume_tick(vol, None),
                    ha="center",
                    va="bottom",
                    fontsize=9,
                )

        self._format_left_axis(emitters, bottom.max() if bottom.size else 0)

    def _draw_simple_bars(
        self, df: pd.DataFrame, emitters: Iterable[str], totals: np.ndarray, x: np.ndarray
    ) -> None:
        """Fallback: no UND_TYPE column → simple bars colored per issuer."""
        bars = self.ax_left.bar(x, totals)

        for i, iss in enumerate(emitters):
            col = get_issuer_color(iss)
            if col:
                bars[i].set_color(col)
                bars[i].set_alpha(0.9)

        for i, vol in enumerate(totals):
            if vol > 0:
                self.ax_left.text(
                    x[i],
                    vol,
                    self._format_volume_tick(vol, None),
                    ha="center",
                    va="bottom",
                    fontsize=9,
                )

        self._format_left_axis(emitters, totals.max() if totals.size else 0)

    # ----------------------------------------------------------------------
    # --- Left Axis Formatting ----------------------------------------------
    # ----------------------------------------------------------------------
    def _format_left_axis(self, emitters: Iterable[str], ymax: float) -> None:
        self.ax_left.set_xticks(np.arange(len(emitters)))
        self.ax_left.set_xticklabels(emitters, rotation=20, ha="right")
        self.ax_left.yaxis.set_major_formatter(mticker.FuncFormatter(self._format_volume_tick))
        self.ax_left.grid(True, axis="y", alpha=0.3)
        self.ax_left.set_xlabel("")
        self.ax_left.set_ylabel("")
        self.ax_left.set_title("Volumen nach Emittent (Σ TXN_AMT)")
        if ymax > 0:
            self.ax_left.set_ylim(0, ymax * 1.12)

    # ----------------------------------------------------------------------
    # --- Right Panel Construction ------------------------------------------
    # ----------------------------------------------------------------------
    def _draw_market_share(
        self, emitters: Iterable[str], x: np.ndarray, market_share: np.ndarray
    ) -> None:
        bars = self.ax_right.bar(x, market_share)

        for i, iss in enumerate(emitters):
            col = get_issuer_color(iss)
            if col:
                bars[i].set_color(col)
                bars[i].set_alpha(0.9)

        ymax = 0
        for b, pct in zip(bars, market_share):
            h = b.get_height()
            ymax = max(ymax, h)
            if h > 0:
                bx = b.get_x() + b.get_width() / 2
                self.ax_right.text(
                    bx,
                    h,
                    f"{pct:.1f}%",
                    ha="center",
                    va="bottom",
                    fontsize=9,
                )

        self.ax_right.set_xticks(x)
        self.ax_right.set_xticklabels(emitters, rotation=20, ha="right")
        self.ax_right.yaxis.set_major_formatter(mticker.FuncFormatter(self._format_pct_tick))
        self.ax_right.grid(True, axis="y", alpha=0.3)
        self.ax_right.set_xlabel("")
        self.ax_right.set_ylabel("")
        self.ax_right.set_title("Marktanteil nach Emittent (Volumen %)")

        if ymax > 0:
            self.ax_right.set_ylim(0, ymax * 1.12)

    # ----------------------------------------------------------------------
    # --- Empty State --------------------------------------------------------
    # ----------------------------------------------------------------------
    def _draw_empty(self, msg: str = "Keine Daten") -> None:
        """Render both axes with a centered message."""
        for ax in (self.ax_left, self.ax_right):
            ax.clear()
            ax.text(0.5, 0.5, msg, ha="center", va="center", transform=ax.transAxes)
        self.canvas_left.draw()
        self.canvas_right.draw()
