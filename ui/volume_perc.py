# ui/volume_percentage.py
# ---------------------------------------------------------------------
# Volume Percentage Dashboard (2×2 grid)
#
# [0,0] Daily % share per issuer (line)
# [0,1] 7-Day rolling % share per issuer (line)
# [1,0] Weekly % share per issuer (grouped bars)
# [1,1] Monthly % share per issuer (grouped bars)
#
# Requirements:
#    DataFrame must contain DAY, WEEK, MONTH, ISSUER_NAME, TXN_AMT.
#
# Public API:
#    update_plot(df)
# ---------------------------------------------------------------------

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, List

import numpy as np
import pandas as pd
import matplotlib.ticker as mticker
import matplotlib.dates as mdates

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from utils.issuer_colors import get_issuer_color


class VolumePercentage(ttk.Frame):
    """Four-panel dashboard showing % volume share per issuer."""

    def __init__(self, master=None):
        super().__init__(master)
        self._df: Optional[pd.DataFrame] = None

        # Internal state / artists
        self._issuers: List[str] = []
        self._full_range: Optional[pd.DatetimeIndex] = None

        self._daily_pct_per_issuer: Dict[str, pd.Series] = {}
        self._lines_day: Dict[str, object] = {}
        self._lines_roll: Dict[str, object] = {}
        self._bars_week: Dict[str, List[object]] = {}
        self._bars_month: Dict[str, List[object]] = {}

        self._issuer_vars: Dict[str, tk.BooleanVar] = {}
        self._issuer_checkwidgets: Dict[str, tk.Checkbutton] = {}

        self._build()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        # Sidebar
        self.sidebar = tk.Frame(
            self, bg="#FFF4E5", bd=0, highlightthickness=0, width=140
        )
        self.sidebar.grid(row=1, column=0, sticky="nsw", padx=(6, 8), pady=(4, 6))
        self.sidebar.grid_propagate(False)
        self._build_sidebar()

        # Plot area
        right = tk.Frame(self, bg="white", bd=0, highlightthickness=0)
        right.grid(row=1, column=1, sticky="nsew", padx=(0, 6), pady=(4, 6))
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        # Figure with 4 subplots
        self.fig = Figure(figsize=(12, 6.6), dpi=100)
        gs = self.fig.add_gridspec(2, 2, height_ratios=[1, 1])

        self.ax_day = self.fig.add_subplot(gs[0, 0])
        self.ax_roll = self.fig.add_subplot(gs[0, 1])
        self.ax_week = self.fig.add_subplot(gs[1, 0])
        self.ax_month = self.fig.add_subplot(gs[1, 1])

        self.fig.subplots_adjust(
            left=0.07,
            right=0.98,
            wspace=0.32,
            hspace=0.32,
            bottom=0.12,
            top=0.94,
        )

        # Canvas
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        widget = self.canvas.get_tk_widget()
        widget.configure(bg="white", highlightthickness=0)
        widget.grid(row=1, column=0, sticky="nsew")

        # Toolbar
        self.toolbar = NavigationToolbar2Tk(self.canvas, right, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.grid(row=0, column=0, sticky="w")
        try:
            self.toolbar.configure(background="white")
            for w in self.toolbar.winfo_children():
                w.configure(background="white")
        except Exception:
            pass

    def _build_sidebar(self) -> None:
        tk.Label(
            self.sidebar,
            text="Issuers",
            bg="#FFF4E5",
            fg="#7A3E00",
            font=("Segoe UI Semibold", 10),
        ).pack(anchor="w", padx=4, pady=(4, 2))

        # Global ON/OFF buttons
        btns = tk.Frame(self.sidebar, bg="#FFF4E5")
        btns.pack(fill="x", padx=4, pady=(0, 4))

        tk.Button(
            btns,
            text="All ON",
            command=self._all_on,
            bg="white",
            relief="solid",
            bd=1,
            padx=4,
            pady=1,
            cursor="hand2",
        ).pack(fill="x", pady=(0, 6))

        tk.Button(
            btns,
            text="All OFF",
            command=self._all_off,
            bg="white",
            relief="solid",
            bd=1,
            padx=4,
            pady=1,
            cursor="hand2",
        ).pack(fill="x", pady=(0, 6))

        # Scrollable issuer list container
        list_container = tk.Frame(self.sidebar, bg="#FFF4E5")
        list_container.pack(fill="both", expand=True, padx=4, pady=(2, 6))

        self._issuer_canvas = tk.Canvas(
            list_container,
            borderwidth=0,
            highlightthickness=0,
            bg="#FFF4E5",
            width=128,
        )
        vsb = ttk.Scrollbar(
            list_container, orient="vertical", command=self._issuer_canvas.yview
        )
        self._issuer_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        self._issuer_inner = tk.Frame(self._issuer_canvas, bg="#FFF4E5")
        self._issuer_canvas.create_window(
            (0, 0), window=self._issuer_inner, anchor="nw"
        )
        self._issuer_inner.bind(
            "<Configure>",
            lambda e: self._issuer_canvas.configure(
                scrollregion=self._issuer_canvas.bbox("all")
            ),
        )
        self._issuer_canvas.pack(side="left", fill="both", expand=True)

        self._issuer_checks_parent = self._issuer_inner

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def update_plot(self, df: pd.DataFrame) -> None:
        """Receive filtered DataFrame (with DAY/WEEK/MONTH) and redraw all plots."""
        self._df = df
        self._draw_all()

    # ------------------------------------------------------------------
    # Main drawing
    # ------------------------------------------------------------------
    def _draw_all(self) -> None:

        # Reset axes and state
        for ax in (self.ax_day, self.ax_roll, self.ax_week, self.ax_month):
            ax.clear()

        self._lines_day.clear()
        self._lines_roll.clear()
        self._bars_week.clear()
        self._bars_month.clear()
        self._daily_pct_per_issuer.clear()
        self._issuer_vars.clear()
        self._issuer_checkwidgets.clear()
        self._issuers = []
        self._full_range = None

        # If no data
        if self._df is None or self._df.empty:
            for ax in (self.ax_day, self.ax_roll, self.ax_week, self.ax_month):
                ax.text(
                    0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes
                )
            self.canvas.draw_idle()
            return

        s = self._df.copy()

        # Ensure category type for issuers
        if "ISSUER_NAME" in s.columns:
            s["ISSUER_NAME"] = s["ISSUER_NAME"].astype("category")

        # Issuer list & continuous daily range
        self._issuers = sorted(s["ISSUER_NAME"].unique())
        self._full_range = pd.date_range(
            s["DAY"].min(), s["DAY"].max(), freq="D"
        )

        # ----------------------------------------------------------
        # DAILY PERCENTAGES (base for rolling)
        # ----------------------------------------------------------

        # Daily total volume (all issuers)
        tot_day = (
            s.groupby("DAY", sort=False)["TXN_AMT"]
            .sum()
            .reindex(self._full_range)
        )
        tot_vals = tot_day.values.astype(float)

        # mask: only days with >0 total allow percentages
        valid_mask = tot_vals > 0.0

        # Build daily percentages per issuer
        for iss in self._issuers:
            si = s[s["ISSUER_NAME"] == iss]
            daily = (
                si.groupby("DAY", sort=False)["TXN_AMT"]
                .sum()
                .reindex(self._full_range)
            )

            vals = daily.values.astype(float)
            nonan = np.where(np.isnan(vals), 0.0, vals)

            pct = np.full_like(tot_vals, np.nan, dtype=float)
            pct[valid_mask] = (nonan[valid_mask] / tot_vals[valid_mask]) * 100.0

            self._daily_pct_per_issuer[iss] = pd.Series(
                pct, index=self._full_range
            )

        # ----------------------------------------------------------
        # Sidebar toggle construction (all OFF initially)
        # ----------------------------------------------------------
        for w in self._issuer_checks_parent.winfo_children():
            w.destroy()

        for iss in self._issuers:
            var = tk.BooleanVar(value=False)
            cb = tk.Checkbutton(
                self._issuer_checks_parent,
                text=iss,
                variable=var,
                bg="#FFF4E5",
                activebackground="#FFF4E5",
                anchor="w",
                padx=4,
                pady=1,
                relief="flat",
                command=lambda i=iss: self._toggle_issuer(i),
            )
            cb.pack(fill="x", padx=0, pady=1)
            self._issuer_vars[iss] = var
            self._issuer_checkwidgets[iss] = cb

        # ----------------------------------------------------------
        # [0,0] Daily % lines
        # ----------------------------------------------------------
        for iss in self._issuers:
            series = self._daily_pct_per_issuer[iss]
            color = get_issuer_color(iss)
            (ln,) = self.ax_day.plot(
                self._full_range,
                series.values,
                linewidth=1.3,
                label=iss,
                color=color if color else None,
            )
            ln.set_visible(False)
            self._lines_day[iss] = ln

        self._format_date_axis_pct(
            self.ax_day,
            "Daily % Share per Issuer (of total daily volume)",
        )

        # ----------------------------------------------------------
        # [0,1] 7-Day Rolling % lines
        # ----------------------------------------------------------
        for iss in self._issuers:
            daily_pct = self._daily_pct_per_issuer[iss]
            roll = (
                pd.Series(daily_pct.values, index=self._full_range)
                .rolling(window=7, min_periods=1)
                .mean()
            )
            color = get_issuer_color(iss)
            (ln,) = self.ax_roll.plot(
                self._full_range,
                roll.values,
                linewidth=1.6,
                label=iss,
                color=color if color else None,
            )
            ln.set_visible(False)
            self._lines_roll[iss] = ln

        self._format_date_axis_pct(
            self.ax_roll,
            "7-Day Rolling % Share per Issuer",
        )

        # Colorize sidebar entries
        for iss, ln in self._lines_roll.items():
            color = get_issuer_color(iss, fallback=ln.get_color())
            if iss in self._issuer_checkwidgets:
                try:
                    self._issuer_checkwidgets[iss].configure(
                        fg=color,
                        activeforeground=color,
                        selectcolor="#FFF4E5",
                    )
                except Exception:
                    pass

        # ----------------------------------------------------------
        # [1,0] Weekly % share (grouped bars)
        # ----------------------------------------------------------
        self._draw_weekly_bars(s)

        # ----------------------------------------------------------
        # [1,1] Monthly % share (grouped bars)
        # ----------------------------------------------------------
        self._draw_monthly_bars(s)

        self.canvas.draw_idle()

    # --------------------------------------------------------------
    # Weekly bars
    # --------------------------------------------------------------
    def _draw_weekly_bars(self, s: pd.DataFrame) -> None:
        grouped = (
            s.groupby(["WEEK", "ISSUER_NAME"], sort=False, observed=False)["TXN_AMT"]
            .sum()
            .reset_index()
            .sort_values("WEEK")
        )
        pivot = (
            grouped.pivot(index="WEEK", columns="ISSUER_NAME", values="TXN_AMT")
            .fillna(0.0)
            .sort_index()
        )

        if pivot.empty:
            self.ax_week.text(0.5, 0.5, "No weekly data", ha="center", va="center")
            return

        row_sums = pivot.sum(axis=1).values.astype(float)
        mask_row = row_sums > 0.0

        pct = pivot.copy().astype(float)
        pct.loc[:, :] = np.nan
        pct[mask_row] = (
            pivot[mask_row].div(row_sums[mask_row], axis=0) * 100.0
        )

        weeks = pct.index.to_pydatetime()
        n_w = len(weeks)
        n_iss = len(self._issuers)
        x = np.arange(n_w)

        group_width = 0.85
        bar_width = group_width / max(n_iss, 1)

        for i, iss in enumerate(self._issuers):
            offs = (i - (n_iss - 1) / 2.0) * bar_width
            col = pct.get(iss)
            vals = col.values if col is not None else np.zeros(n_w)
            vals_plot = np.where(np.isnan(vals), 0.0, vals)

            bars = self.ax_week.bar(x + offs, vals_plot, width=bar_width)
            color = get_issuer_color(
                iss,
                fallback=(self._lines_roll.get(iss).get_color()
                          if iss in self._lines_roll else None),
            )
            if color:
                for b in bars:
                    b.set_color(color)
                    b.set_alpha(0.85)

            # Visibility depends on toggle
            for idx, b in enumerate(bars):
                if np.isnan(vals[idx]):
                    b.set_visible(False)
                else:
                    b.set_visible(False)
            self._bars_week[iss] = list(bars)

        labels = [
            f"{d.isocalendar().year}-W{d.isocalendar().week:02d}" for d in weeks
        ]
        self.ax_week.set_xticks(x)
        self.ax_week.set_xticklabels(labels, rotation=45, ha="right")

        self._format_pct_axis(
            self.ax_week,
            "Weekly % Share per Issuer",
        )

    # --------------------------------------------------------------
    # Monthly bars
    # --------------------------------------------------------------
    def _draw_monthly_bars(self, s: pd.DataFrame) -> None:
        grouped = (
            s.groupby(["MONTH", "ISSUER_NAME"], sort=False, observed=False)["TXN_AMT"]
            .sum()
            .reset_index()
            .sort_values("MONTH")
        )
        pivot = (
            grouped.pivot(index="MONTH", columns="ISSUER_NAME", values="TXN_AMT")
            .fillna(0.0)
            .sort_index()
        )

        if pivot.empty:
            self.ax_month.text(0.5, 0.5, "No monthly data", ha="center", va="center")
            return

        row_sums = pivot.sum(axis=1).values.astype(float)
        mask_row = row_sums > 0.0

        pct = pivot.copy().astype(float)
        pct.loc[:, :] = np.nan
        pct[mask_row] = (
            pivot[mask_row].div(row_sums[mask_row], axis=0) * 100.0
        )

        months = pct.index.to_pydatetime()
        n_m = len(months)
        n_iss = len(self._issuers)
        x = np.arange(n_m)

        group_width = 0.85
        bar_width = group_width / max(n_iss, 1)

        for i, iss in enumerate(self._issuers):
            offs = (i - (n_iss - 1) / 2.0) * bar_width
            col = pct.get(iss)
            vals = col.values if col is not None else np.zeros(n_m)
            vals_plot = np.where(np.isnan(vals), 0.0, vals)

            bars = self.ax_month.bar(x + offs, vals_plot, width=bar_width)
            color = get_issuer_color(
                iss,
                fallback=(self._lines_roll.get(iss).get_color()
                          if iss in self._lines_roll else None),
            )
            if color:
                for b in bars:
                    b.set_color(color)
                    b.set_alpha(0.85)

            for idx, b in enumerate(bars):
                if np.isnan(vals[idx]):
                    b.set_visible(False)
                else:
                    b.set_visible(False)

            self._bars_month[iss] = list(bars)

        self.ax_month.set_xticks(x)
        self.ax_month.set_xticklabels(
            [dt.strftime("%Y-%m") for dt in months],
            rotation=45,
            ha="right",
        )

        self._format_pct_axis(
            self.ax_month,
            "Monthly % Share per Issuer",
        )

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------
    def _format_date_axis_pct(self, ax, title: str) -> None:
        locator = mdates.AutoDateLocator()
        formatter = mdates.AutoDateFormatter(locator)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)

        ax.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:.0f}%"))
        ax.grid(True, alpha=0.3)
        ax.set_title(title)
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.tick_params(axis="x", rotation=45)

    def _format_pct_axis(self, ax, title: str) -> None:
        ax.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:.0f}%"))
        ax.grid(True, axis="y", alpha=0.3)
        ax.set_title(title)
        ax.set_xlabel("")
        ax.set_ylabel("")

    # ------------------------------------------------------------------
    # Sidebar → toggles
    # ------------------------------------------------------------------
    def _toggle_issuer(self, issuer: str) -> None:
        """Toggle visibility of all plots for a given issuer."""
        on = bool(self._issuer_vars[issuer].get())

        # Daily lines
        ln_d = self._lines_day.get(issuer)
        if ln_d is not None:
            ln_d.set_visible(on)

        # Rolling lines
        ln_r = self._lines_roll.get(issuer)
        if ln_r is not None:
            ln_r.set_visible(on)

        # Weekly bars
        for b in self._bars_week.get(issuer, []):
            b.set_visible(on)

        # Monthly bars
        for b in self._bars_month.get(issuer, []):
            b.set_visible(on)

        self.canvas.draw_idle()

    def _all_on(self) -> None:
        for iss, var in self._issuer_vars.items():
            if not var.get():
                var.set(True)
                self._toggle_issuer(iss)

    def _all_off(self) -> None:
        for iss, var in self._issuer_vars.items():
            if var.get():
                var.set(False)
                self._toggle_issuer(iss)
