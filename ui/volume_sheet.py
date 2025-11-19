# ui/volume_sheet.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import matplotlib.ticker as mticker

from utils.issuer_colors import get_issuer_color


class VolumeSheet(ttk.Frame):
    """
    Volume dashboard (2x2):

      [0,0] Daily lines (Σ TXN_AMT) per issuer
      [0,1] 7-day rolling mean per issuer
      [1,0] Weekly grouped bars (Σ TXN_AMT) per issuer
      [1,1] Monthly grouped bars (Σ TXN_AMT) per issuer

    Expected columns in the input DataFrame:
      - DAY   : normalized day (datetime64)
      - WEEK  : week start (datetime64)
      - MONTH : month start (datetime64)
      - ISSUER_NAME, TXN_AMT
    """

    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master)

        self._df: Optional[pd.DataFrame] = None

        # Artists per issuer
        self._lines_day: Dict[str, object] = {}     # issuer -> Line2D
        self._lines_roll: Dict[str, object] = {}    # issuer -> Line2D (7d)
        self._bars_week: Dict[str, List[object]] = {}   # issuer -> [Rectangles]
        self._bars_month: Dict[str, List[object]] = {}  # issuer -> [Rectangles]

        # Sidebar state
        self._issuer_vars: Dict[str, tk.BooleanVar] = {}
        self._issuer_checkwidgets: Dict[str, tk.Checkbutton] = {}

        # Base series for daily / rolling
        self._issuers: List[str] = []
        self._full_range: Optional[pd.DatetimeIndex] = None
        self._daily_series_per_issuer: Dict[str, pd.Series] = {}

        # UI containers
        self._issuer_checks_parent: tk.Widget | None = None
        self._issuer_canvas: tk.Canvas | None = None
        self._issuer_inner: tk.Frame | None = None

        # Matplotlib objects
        self.fig: Figure
        self.ax_day: object
        self.ax_roll: object
        self.ax_week: object
        self.ax_month: object
        self.canvas: FigureCanvasTkAgg
        self.canvas_widget: tk.Widget
        self.toolbar: NavigationToolbar2Tk

        self._build()

    # ------------------------------------------------------------------
    # UI BUILD
    # ------------------------------------------------------------------
    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        # Sidebar
        sidebar = tk.Frame(self, bg="#FFF4E5", bd=0, highlightthickness=0, width=140)
        sidebar.grid(row=1, column=0, sticky="nsw", padx=(6, 8), pady=(4, 6))
        sidebar.grid_propagate(False)
        self.sidebar = sidebar  # keep reference
        self._build_sidebar()

        # Right plot area
        right = tk.Frame(self, bg="white", bd=0, highlightthickness=0)
        right.grid(row=1, column=1, sticky="nsew", padx=(0, 6), pady=(4, 6))
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        # Figure with 4 subplots (2x2)
        self.fig = Figure(figsize=(12, 6.6), dpi=100)
        gs = self.fig.add_gridspec(2, 2, height_ratios=[1, 1])

        self.ax_day = self.fig.add_subplot(gs[0, 0])   # top-left: daily
        self.ax_roll = self.fig.add_subplot(gs[0, 1])  # top-right: rolling 7d
        self.ax_week = self.fig.add_subplot(gs[1, 0])  # bottom-left: weekly
        self.ax_month = self.fig.add_subplot(gs[1, 1]) # bottom-right: monthly

        self.fig.subplots_adjust(
            left=0.07,
            right=0.98,
            wspace=0.32,
            hspace=0.32,
            bottom=0.12,
            top=0.94,
        )

        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.configure(bg="white", highlightthickness=0)
        self.canvas_widget.grid(row=1, column=0, sticky="nsew")

        # Toolbar
        self.toolbar = NavigationToolbar2Tk(self.canvas, right, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.grid(row=0, column=0, sticky="w", pady=(0, 6))
        try:
            self.toolbar.configure(background="white")
            for w in self.toolbar.winfo_children():
                try:
                    w.configure(background="white")
                except Exception:
                    pass
        except Exception:
            pass

    def _build_sidebar(self) -> None:
        title = tk.Label(
            self.sidebar,
            text="Emittenten",
            bg="#FFF4E5",
            fg="#7A3E00",
            font=("Segoe UI Semibold", 10),
        )
        title.pack(anchor="w", padx=4, pady=(4, 2))

        # Global buttons (all on/off)
        btns = tk.Frame(self.sidebar, bg="#FFF4E5")
        btns.pack(fill="x", padx=4, pady=(0, 4))

        for text, cmd in (("Alle AN", self._all_on), ("Alle AUS", self._all_off)):
            tk.Button(
                btns,
                text=text,
                command=cmd,
                bg="white",
                relief="solid",
                bd=1,
                padx=4,
                pady=1,
                cursor="hand2",
            ).pack(fill="x", pady=(0, 6))

        # Scrollable issuer list
        list_container = tk.Frame(self.sidebar, bg="#FFF4E5")
        list_container.pack(fill="both", expand=True, padx=4, pady=(2, 6))

        self._issuer_canvas = tk.Canvas(
            list_container,
            borderwidth=0,
            highlightthickness=0,
            bg="#FFF4E5",
            width=128,
        )
        vsb = ttk.Scrollbar(list_container, orient="vertical", command=self._issuer_canvas.yview)
        self._issuer_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        self._issuer_inner = tk.Frame(self._issuer_canvas, bg="#FFF4E5")
        self._issuer_canvas.create_window((0, 0), window=self._issuer_inner, anchor="nw")
        self._issuer_inner.bind(
            "<Configure>",
            lambda e: self._issuer_canvas.configure(scrollregion=self._issuer_canvas.bbox("all")),
        )
        self._issuer_canvas.pack(side="left", fill="both", expand=True)

        self._issuer_checks_parent = self._issuer_inner

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------
    def update_plot(self, df: pd.DataFrame) -> None:
        """
        Receive the filtered DataFrame (already containing DAY/WEEK/MONTH)
        and redraw all plots.
        """
        self._df = df
        self._draw_all()

    # ------------------------------------------------------------------
    # DRAWING
    # ------------------------------------------------------------------
    def _draw_all(self) -> None:
        # Clear axes and state
        for ax in (self.ax_day, self.ax_roll, self.ax_week, self.ax_month):
            ax.clear()

        self._lines_day.clear()
        self._lines_roll.clear()
        self._bars_week.clear()
        self._bars_month.clear()
        self._daily_series_per_issuer.clear()
        self._issuer_checkwidgets.clear()
        self._issuers = []
        self._full_range = None

        if self._df is None or self._df.empty:
            for ax in (self.ax_day, self.ax_roll, self.ax_week, self.ax_month):
                ax.text(
                    0.5,
                    0.5,
                    "Keine Daten",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                )
            self.canvas.draw_idle()
            return

        s = self._df.copy()

        if "ISSUER_NAME" in s.columns:
            s["ISSUER_NAME"] = s["ISSUER_NAME"].astype("category")

        # ---- issuer list and full day range ----
        self._issuers = sorted(s["ISSUER_NAME"].unique())
        self._full_range = pd.date_range(s["DAY"].min(), s["DAY"].max(), freq="D")

        # Daily series per issuer (for rolling 7d)
        for issuer in self._issuers:
            si = s[s["ISSUER_NAME"] == issuer]
            daily = (
                si.groupby("DAY")["TXN_AMT"]
                .sum()
                .reindex(self._full_range)
                .fillna(0.0)
            )
            self._daily_series_per_issuer[issuer] = daily

        # ---- sidebar toggles (all OFF) ----
        parent = self._issuer_checks_parent
        if parent is not None:
            for w in parent.winfo_children():
                w.destroy()
        self._issuer_vars.clear()

        for issuer in self._issuers:
            var = tk.BooleanVar(value=False)
            cb = tk.Checkbutton(
                parent,
                text=issuer,
                variable=var,
                bg="#FFF4E5",
                activebackground="#FFF4E5",
                anchor="w",
                padx=4,
                pady=1,
                relief="flat",
                command=lambda i=issuer: self._toggle_issuer(i),
            )
            cb.pack(fill="x", padx=0, pady=1)
            self._issuer_vars[issuer] = var
            self._issuer_checkwidgets[issuer] = cb

        # ---- [0,0] Daily lines ----
        grouped_day = (
            s.groupby(["DAY", "ISSUER_NAME"], observed=False)["TXN_AMT"]
            .sum()
            .reset_index()
            .sort_values(by="DAY")
        )
        for issuer in self._issuers:
            sub = grouped_day[grouped_day["ISSUER_NAME"] == issuer]
            color = get_issuer_color(issuer)
            line, = self.ax_day.plot(
                sub["DAY"],
                sub["TXN_AMT"],
                marker="o",
                linewidth=1.3,
                label=issuer,
                color=color if color is not None else None,
            )
            line.set_visible(False)
            self._lines_day[issuer] = line

        self._format_date_axis(self.ax_day, "Volumen pro Tag (Σ TXN_AMT)")

        # ---- [0,1] 7-day rolling mean ----
        for issuer in self._issuers:
            daily = self._daily_series_per_issuer[issuer]
            roll = daily.rolling(window=7, min_periods=1).mean()
            color = get_issuer_color(issuer)

            line, = self.ax_roll.plot(
                self._full_range,
                roll.values,
                linewidth=1.6,
                label=issuer,
                color=color if color is not None else None,
            )
            line.set_visible(False)
            self._lines_roll[issuer] = line

        # Apply issuer color to sidebar checkbuttons
        for issuer, line in self._lines_roll.items():
            color = get_issuer_color(issuer, fallback=line.get_color())
            cb = self._issuer_checkwidgets.get(issuer)
            if cb and color:
                try:
                    cb.configure(
                        fg=color,
                        activeforeground=color,
                        selectcolor="#FFF4E5",
                    )
                except Exception:
                    pass

        self._format_date_axis(self.ax_roll, "7-Tage-Gleitmittel (Σ TXN_AMT)")

        # ---- [1,0] Weekly bars ----
        grouped_week = (
            s.groupby(["WEEK", "ISSUER_NAME"], sort=False, observed=False)["TXN_AMT"]
            .sum()
            .reset_index()
            .sort_values("WEEK")
        )
        pivot_w = (
            grouped_week.pivot(index="WEEK", columns="ISSUER_NAME", values="TXN_AMT")
            .fillna(0.0)
            .sort_index()
        )
        self._build_grouped_bars(
            ax=self.ax_week,
            pivot=pivot_w,
            issuers=self._issuers,
            store_dict=self._bars_week,
            title="Volumen pro Woche (Σ TXN_AMT)",
            xlabels_func=lambda dates: [
                f"{d.isocalendar().year}-W{d.isocalendar().week:02d}" for d in dates
            ],
        )

        # ---- [1,1] Monthly bars ----
        grouped_month = (
            s.groupby(["MONTH", "ISSUER_NAME"], sort=False, observed=False)["TXN_AMT"]
            .sum()
            .reset_index()
            .sort_values("MONTH")
        )
        pivot_m = (
            grouped_month.pivot(index="MONTH", columns="ISSUER_NAME", values="TXN_AMT")
            .fillna(0.0)
            .sort_index()
        )
        self._build_grouped_bars(
            ax=self.ax_month,
            pivot=pivot_m,
            issuers=self._issuers,
            store_dict=self._bars_month,
            title="Volumen pro Monat (Σ TXN_AMT)",
            xlabels_func=lambda dates: [d.strftime("%Y-%m") for d in dates],
        )

        self.canvas.draw_idle()

    # ------------------------------------------------------------------
    # INTERNAL HELPERS
    # ------------------------------------------------------------------
    def _build_grouped_bars(
        self,
        ax,
        pivot: pd.DataFrame,
        issuers: List[str],
        store_dict: Dict[str, List[object]],
        title: str,
        xlabels_func,
    ) -> None:
        """
        Build grouped bar charts (weekly / monthly) in a compact way.

        Parameters
        ----------
        ax : matplotlib.axes.Axes
            Axis to draw on.
        pivot : DataFrame
            Index = datetime, columns = issuer, values = volume.
        issuers : list[str]
            Ordered list of issuers.
        store_dict : dict[str, list[Rectangle]]
            Dict to store created bar artists per issuer.
        title : str
            Plot title.
        xlabels_func : callable
            Function that receives list of datetime objects and returns
            list of string labels for x-axis.
        """
        if pivot.empty:
            return

        dates = pivot.index.to_pydatetime()
        n_groups = len(dates)
        n_iss = len(issuers)

        group_width = 0.85
        bar_width = group_width / max(n_iss, 1)

        x = np.arange(n_groups)

        for idx, issuer in enumerate(issuers):
            offs = (idx - (n_iss - 1) / 2.0) * bar_width
            series = pivot.get(issuer)
            vals = series.values if series is not None else np.zeros(n_groups)

            bars = ax.bar(x + offs, vals, width=bar_width, label=issuer)

            color = get_issuer_color(
                issuer,
                fallback=(
                    self._lines_roll.get(issuer).get_color()
                    if issuer in self._lines_roll
                    else None
                ),
            )

            if color:
                for b in bars:
                    b.set_color(color)
                    b.set_alpha(0.85)

            for b in bars:
                b.set_visible(False)

            store_dict[issuer] = list(bars)

        ax.set_xticks(x)
        ax.set_xticklabels(xlabels_func(dates), rotation=20, ha="right")
        self._format_value_axis(ax, title)

    # ---------- formatting helpers ----------
    def _format_volume_tick(self, x, pos) -> str:
        """
        Y-axis formatting:
          - < 1M   -> normal with thousands: 12,345
          - >= 1M  -> abbreviated as M (1.1M, 2M, 10M, ...)
        """
        abs_x = abs(x)
        if abs_x >= 1_000_000:
            value = x / 1_000_000.0
            if abs_x >= 10_000_000:
                return f"{value:,.0f}M"
            return f"{value:,.1f}M"
        return f"{x:,.0f}"

    def _format_date_axis(self, ax, title: str) -> None:
        locator = mdates.AutoDateLocator()
        formatter = mdates.AutoDateFormatter(locator)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(self._format_volume_tick))
        ax.grid(True, alpha=0.3)
        ax.set_title(title)
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.tick_params(axis="x", rotation=20)

    def _format_value_axis(self, ax, title: str) -> None:
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(self._format_volume_tick))
        ax.grid(True, axis="y", alpha=0.3)
        ax.set_title(title)
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.tick_params(axis="x", rotation=20)

    # ------------------------------------------------------------------
    # SIDEBAR ACTIONS
    # ------------------------------------------------------------------
    def _toggle_issuer(self, issuer: str) -> None:
        """Show/hide a given issuer across all four plots according to its checkbox."""
        on = bool(self._issuer_vars[issuer].get())

        line_day = self._lines_day.get(issuer)
        if line_day is not None:
            line_day.set_visible(on)

        line_roll = self._lines_roll.get(issuer)
        if line_roll is not None:
            line_roll.set_visible(on)

        for b in self._bars_week.get(issuer, []):
            b.set_visible(on)
        for b in self._bars_month.get(issuer, []):
            b.set_visible(on)

        self.canvas.draw_idle()

    def _all_on(self) -> None:
        for issuer, var in self._issuer_vars.items():
            if not var.get():
                var.set(True)
                self._toggle_issuer(issuer)

    def _all_off(self) -> None:
        for issuer, var in self._issuer_vars.items():
            if var.get():
                var.set(False)
                self._toggle_issuer(issuer)

    # (kept for backward-compatibility if you ever used it externally)
    def get_issuer_color(self, issuer: str):
        line = self._lines_roll.get(issuer) or self._lines_day.get(issuer)
        return line.get_color() if line else None
