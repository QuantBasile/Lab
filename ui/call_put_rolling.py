# ui/call_put_rolling.py

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Dict, Tuple, Optional

import numpy as np
import pandas as pd
from pandas.api.types import is_datetime64_any_dtype

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
from matplotlib.lines import Line2D

from utils.issuer_colors import get_issuer_color


class CallPutRolling(ttk.Frame):
    """
    Tab: 7-day rolling volume per issuer, split by CALL / PUT.

    Layout:
      - Left sidebar: issuer list with checkboxes (All ON / OFF)
      - Center: one figure with a single plot:
          * 7-day rolling TXN_AMT for each issuer and CALL/PUT
          * Color = issuer (global palette from JSON)
          * Line style = option type (CALL / PUT / other)
    """

    def __init__(self, master: Optional[tk.Misc] = None) -> None:
        super().__init__(master)
        self._df: Optional[pd.DataFrame] = None

        self._issuers: list[str] = []
        self._issuer_vars: Dict[str, tk.BooleanVar] = {}     # issuer -> BooleanVar
        self._issuer_checks: Dict[str, tk.Checkbutton] = {}  # issuer -> Checkbutton
        self._issuer_colors: Dict[str, str] = {}             # issuer -> color

        self._full_range: Optional[pd.DatetimeIndex] = None  # daily range
        self._lines_vol: Dict[Tuple[str, str], Line2D] = {}  # (issuer, call/put) -> Line2D

        self._build()

    # ------------------------------------------------------------------
    # Time-column helper
    # ------------------------------------------------------------------
    def _ensure_time_cols(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ensure DAY is derived from TRANSACTION_DATE.

        Optimised:
        - No unnecessary copies.
        - Convert to datetime only if needed.
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

        # Build DAY only if it does not exist
        if "DAY" not in s.columns:
            if not s._is_copy:
                s = s.copy()
            s["DAY"] = s["TRANSACTION_DATE"].dt.normalize()

        return s

    # ------------------------------------------------------------------
    # UI build
    # ------------------------------------------------------------------
    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        # Issuer sidebar
        self.sidebar = tk.Frame(
            self,
            bg="#FFF4E5",
            bd=0,
            highlightthickness=0,
            width=140,
        )
        self.sidebar.grid(row=1, column=0, sticky="nsw", padx=(6, 8), pady=(4, 6))
        self.sidebar.grid_propagate(False)
        self._build_sidebar()

        # Plot area
        center = tk.Frame(self, bg="white", bd=0, highlightthickness=0)
        center.grid(row=1, column=1, sticky="nsew", padx=(0, 6), pady=(4, 6))
        center.rowconfigure(1, weight=1)
        center.columnconfigure(0, weight=1)

        # Single figure / axis
        self.fig = Figure(figsize=(12, 5.8), dpi=100)
        self.ax_vol = self.fig.add_subplot(1, 1, 1)
        self.fig.subplots_adjust(
            left=0.06,
            right=0.98,
            bottom=0.14,
            top=0.90,
        )

        self.canvas = FigureCanvasTkAgg(self.fig, master=center)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.configure(bg="white", highlightthickness=0)
        self.canvas_widget.grid(row=1, column=0, sticky="nsew")

        # Toolbar
        self.toolbar = NavigationToolbar2Tk(self.canvas, center, pack_toolbar=False)
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
        tk.Label(
            self.sidebar,
            text="Issuers",
            bg="#FFF4E5",
            fg="#7A3E00",
            font=("Segoe UI Semibold", 10),
        ).pack(anchor="w", padx=4, pady=(4, 2))

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
        ).pack(fill="x", pady=(0, 4))

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
        ).pack(fill="x", pady=(0, 4))

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
        vsb = ttk.Scrollbar(
            list_container,
            orient="vertical",
            command=self._issuer_canvas.yview,
        )
        self._issuer_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        self._issuer_inner = tk.Frame(self._issuer_canvas, bg="#FFF4E5")
        self._issuer_canvas.create_window(
            (0, 0),
            window=self._issuer_inner,
            anchor="nw",
        )
        self._issuer_inner.bind(
            "<Configure>",
            lambda e: self._issuer_canvas.configure(
                scrollregion=self._issuer_canvas.bbox("all")
            ),
        )
        self._issuer_canvas.pack(side="left", fill="both", expand=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def update_plot(self, df: pd.DataFrame) -> None:
        """Receive filtered DataFrame and redraw the sheet."""
        self._df = df
        self._draw_all()

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------
    def _format_volume_tick(self, x, pos) -> str:
        """
        Format for volume axis:
          - < 1M : standard with thousands separators (12,345)
          - >= 1M: in millions, e.g. 1M, 1.1M, 10M
        """
        abs_x = abs(x)
        if abs_x >= 1_000_000:
            value = x / 1_000_000.0
            if abs_x >= 10_000_000:
                return f"{value:,.0f}M"
            return f"{value:,.1f}M"
        return f"{x:,.0f}"

    def _set_dynamic_ylim(self) -> None:
        """Adjust Y-axis limits based on currently visible lines."""
        vals = []
        for ln in self._lines_vol.values():
            y = ln.get_ydata()
            if y is None:
                continue
            arr = np.asarray(y, dtype=float)
            arr = arr[~np.isnan(arr)]
            if arr.size:
                vals.append(arr.max())
        if not vals:
            return
        ymax = max(vals)
        if ymax <= 0:
            ymax = 1.0
        self.ax_vol.set_ylim(0, ymax * 1.1)

    # ------------------------------------------------------------------
    # Main drawing
    # ------------------------------------------------------------------
    def _draw_all(self) -> None:
        # Clear axis and state
        self.ax_vol.clear()
        self._issuer_vars.clear()
        self._issuer_checks.clear()
        self._issuer_colors.clear()
        self._lines_vol.clear()
        self._full_range = None
        self._issuers = []

        for w in self._issuer_inner.winfo_children():
            w.destroy()

        if self._df is None or self._df.empty:
            self.ax_vol.text(
                0.5,
                0.5,
                "No data",
                ha="center",
                va="center",
                transform=self.ax_vol.transAxes,
            )
            self.canvas.draw_idle()
            return

        s = self._ensure_time_cols(self._df)

        required = {"TRANSACTION_DATE", "TXN_AMT", "CALL_OPTION", "ISSUER_NAME"}
        if not required.issubset(s.columns):
            msg = "Missing columns: " + ", ".join(sorted(required - set(s.columns)))
            self.ax_vol.text(
                0.5,
                0.5,
                msg,
                ha="center",
                va="center",
                transform=self.ax_vol.transAxes,
            )
            self.canvas.draw_idle()
            return

        s["CALL_OPTION"] = s["CALL_OPTION"].astype(str)
        s["ISSUER_NAME"] = s["ISSUER_NAME"].astype(str)

        # Issuers & continuous date range
        self._issuers = sorted(s["ISSUER_NAME"].unique())
        self._full_range = pd.date_range(s["DAY"].min(), s["DAY"].max(), freq="D")

        # Sidebar issuers
        for iss in self._issuers:
            var = tk.BooleanVar(value=False)
            cb = tk.Checkbutton(
                self._issuer_inner,
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
            self._issuer_checks[iss] = cb

        # CALL/PUT values (as strings)
        callput_values = sorted(s["CALL_OPTION"].unique())

        # Build rolling lines
        for iss in self._issuers:
            color = get_issuer_color(iss)
            if color is None:
                # Fallback if issuer is not present in JSON
                color = self.ax_vol._get_lines.get_next_color()
            self._issuer_colors[iss] = color

            for cp in callput_values:
                mask = (s["ISSUER_NAME"] == iss) & (s["CALL_OPTION"] == cp)
                if not mask.any():
                    continue

                daily = (
                    s.loc[mask]
                    .groupby("DAY", sort=False)["TXN_AMT"]
                    .sum()
                    .reindex(self._full_range)
                    .fillna(0.0)
                )

                # 7-day rolling mean
                roll_vol = (
                    pd.Series(daily.values, index=self._full_range)
                    .rolling(window=7, min_periods=1)
                    .mean()
                )

                color_line = self._issuer_colors[iss]
                ls = self._linestyle_for_callput(cp)

                (ln_v,) = self.ax_vol.plot(
                    self._full_range,
                    roll_vol.values,
                    linewidth=1.4,
                    color=color_line,
                    linestyle=ls,
                    label=f"{iss} {cp}",
                )
                ln_v.set_visible(False)
                self._lines_vol[(iss, cp)] = ln_v

        # Color sidebar checkbuttons according to issuer color
        for iss, cb in self._issuer_checks.items():
            color = get_issuer_color(iss, fallback=self._issuer_colors.get(iss))
            if color:
                try:
                    cb.configure(
                        fg=color,
                        activeforeground=color,
                        selectcolor="#FFF4E5",
                    )
                except Exception:
                    pass

        # Axis format
        self._format_vol_axis()

        # Dynamic Y-axis
        self._set_dynamic_ylim()

        # Legends: issuers (colors) and types (line styles)
        self._build_legends(callput_values)

        self.canvas.draw_idle()

    # ------------------------------------------------------------------
    # Axis formatting
    # ------------------------------------------------------------------
    def _format_vol_axis(self) -> None:
        locator = mdates.AutoDateLocator()
        formatter = mdates.AutoDateFormatter(locator)
        self.ax_vol.xaxis.set_major_locator(locator)
        self.ax_vol.xaxis.set_major_formatter(formatter)
        self.ax_vol.yaxis.set_major_formatter(
            mticker.FuncFormatter(self._format_volume_tick)
        )
        self.ax_vol.grid(True, alpha=0.3)
        self.ax_vol.set_title("7-Day Rolling Volume by Issuer and CALL/PUT")
        self.ax_vol.set_xlabel("")
        self.ax_vol.set_ylabel("")
        self.ax_vol.tick_params(axis="x", rotation=20)
        self.ax_vol.tick_params(axis="y", rotation=0)

        # Full x-range
        if self._full_range is not None and len(self._full_range) > 0:
            self.ax_vol.set_xlim(self._full_range.min(), self._full_range.max())

    # ------------------------------------------------------------------
    # Line styles for call/put
    # ------------------------------------------------------------------
    @staticmethod
    def _linestyle_for_callput(cp_value: str) -> str:
        key = str(cp_value).upper()
        if key in ("CALL", "C"):
            return "-"
        if key in ("PUT", "P"):
            return "--"
        return ":"  # other types

    # ------------------------------------------------------------------
    # Legends
    # ------------------------------------------------------------------
    def _build_legends(self, callput_values) -> None:
        # Issuer legend (colors)
        issuer_handles = []
        issuer_labels = []
        for iss in self._issuers:
            color = self._issuer_colors.get(iss)
            if not color:
                continue
            h = Line2D([0], [0], color=color, linewidth=2.0)
            issuer_handles.append(h)
            issuer_labels.append(iss)

        # Type legend (line styles)
        style_handles = []
        style_labels = []
        types_seen = set()

        for cp in callput_values:
            key = str(cp).upper()
            if key in ("CALL", "C"):
                normalized = "CALL"
            elif key in ("PUT", "P"):
                normalized = "PUT"
            else:
                normalized = cp

            if normalized in types_seen:
                continue
            types_seen.add(normalized)

            ls = self._linestyle_for_callput(cp)
            h = Line2D([0], [0], color="black", linestyle=ls, linewidth=2.0)
            style_handles.append(h)
            style_labels.append(normalized)

        # Two legends: left = issuers, right = types
        if issuer_handles:
            leg1 = self.ax_vol.legend(
                issuer_handles,
                issuer_labels,
                title="Issuers",
                loc="upper left",
                fontsize=8,
            )
            self.ax_vol.add_artist(leg1)

        if style_handles:
            self.ax_vol.legend(
                style_handles,
                style_labels,
                title="Type",
                loc="upper right",
                fontsize=8,
            )

    # ------------------------------------------------------------------
    # Toggles
    # ------------------------------------------------------------------
    def _toggle_issuer(self, issuer: str) -> None:
        on = bool(self._issuer_vars[issuer].get())
        for (iss, cp), ln in list(self._lines_vol.items()):
            if iss == issuer:
                ln.set_visible(on)
        # Update Y-limits after visibility change
        self._set_dynamic_ylim()
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
