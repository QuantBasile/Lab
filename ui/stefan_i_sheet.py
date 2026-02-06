# ui/stefan_i_sheet.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import numpy as np
import pandas as pd

from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk


class StefanISheet(ttk.Frame):
    """
    Stefan I (CEO style):
      - Underlying selector (Top 5 by TXN_AMT).
      - Main chart: DAILY volume lines by EXPIRY, split HSBC (red) vs Market (grey).
      - Rolling toggle: optionally plot 7-day rolling mean.
      - Left panel: per-expiry block with unique marker + toggles HSBC/Market + Top3 ISIN contributions.
      - Right mini chart: horizontal bars per expiry comparing HSBC vs Market total volume.
      - Expiry normalization: invalid/NaN/empty/year>=2100 => OpenEnd.
      - Zoom/pan: NavigationToolbar.
      - Auto annotate peak day: HSBC TOTAL peak (single annotation).

    Required columns:
      - TRANSACTION_DATE
      - EXPIRY
      - ISSUER_NAME
      - TXN_AMT
      - underlying column (UND_NAME or fallbacks)

    Optional:
      - ISIN (for Top3 contribution display)
    """

    HSBC_NAME = "HSBC"
    VALUE_COL = "TXN_AMT"
    DATE_COL = "TRANSACTION_DATE"
    EXPIRY_COL = "EXPIRY"
    ISSUER_COL = "ISSUER_NAME"
    ISIN_COL = "ISIN"  # optional

    GROUP_CANDIDATES = (
        "UND_NAME",
        "NAME",
        "UNDERLYING",
        "UNDERLYING_NAME",
        "UNDERLYING_SYMBOL",
        "UND",
        "BASISWERT",
        "BASISWERT_NAME",
    )

    MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*", "<", ">", "h", "8", "p", "H",
               "+", "x", "1", "2", "3", "4", "|", "_", "d"]

    def __init__(self, master=None):
        super().__init__(master)

        self._df: pd.DataFrame | None = None
        self._group_col: str | None = None

        self._top5: list[str] = []
        self._selected_underlying = tk.StringVar(value="")

        self._rolling7 = tk.BooleanVar(value=False)

        self._days: pd.DatetimeIndex | None = None
        self._expiries: list[str] = []
        self._series_raw: dict[tuple[str, str], pd.Series] = {}
        self._expiry_marker: dict[str, str] = {}
        self._totals_by_expiry: pd.DataFrame | None = None

        self._lines: dict[tuple[str, str], any] = {}
        self._toggle_vars: dict[tuple[str, str], tk.BooleanVar] = {}

        # palette
        self.BG = "#ffffff"
        self.TEXT = "#0b1220"
        self.SUB = "#475569"
        self.HSBC_RED = "#dc2626"
        self.MKT_GREY = "#94a3b8"
        self.BORDER = "#cbd5e1"

        self._build_ui()

    # ---------------- UI ----------------
    def _build_ui(self):
        self.configure(style="CardInner.TFrame")
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # LEFT PANEL (narrower)
        left = ttk.Frame(self, style="CardInner.TFrame")
        left.grid(row=0, column=0, sticky="nsw", padx=(8, 6), pady=12)
        left.rowconfigure(6, weight=1)

        self._title_var = tk.StringVar(value="Stefan I · CEO View")
        self._sub_var = tk.StringVar(value="Load data → choose Underlying → explore expiries.")

        ttk.Label(left, textvariable=self._title_var, font=("Segoe UI Semibold", 13),
                  foreground=self.TEXT, background=self.BG).grid(row=0, column=0, sticky="w")
        ttk.Label(left, textvariable=self._sub_var, font=("Segoe UI", 10),
                  foreground=self.SUB, background=self.BG, justify="left").grid(row=1, column=0, sticky="w", pady=(4, 10))

        # Underlying selector
        sel_box = ttk.Frame(left)
        sel_box.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        sel_box.columnconfigure(1, weight=1)

        ttk.Label(sel_box, text="Underlying (Top 5):", foreground=self.SUB, background=self.BG).grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )

        self._und_combo = ttk.Combobox(sel_box, state="readonly", textvariable=self._selected_underlying, width=18)
        self._und_combo.grid(row=0, column=1, sticky="ew")
        self._und_combo.bind("<<ComboboxSelected>>", lambda e: self._recompute_for_selected_underlying())

        # Rolling toggle
        roll_box = ttk.Frame(left)
        roll_box.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        cb = tk.Checkbutton(
            roll_box,
            text="Rolling 7D (mean)",
            variable=self._rolling7,
            command=self._redraw_plots_only,
            anchor="w",
            fg=self.TEXT,
            activeforeground=self.TEXT,
            bg=self.BG,
            activebackground=self.BG,
            highlightthickness=0,
            bd=0,
            font=("Segoe UI", 10),
        )
        cb.pack(fill="x")

        # Quick filter buttons
        quick = ttk.Frame(left)
        quick.grid(row=4, column=0, sticky="ew", pady=(0, 6))
        quick.columnconfigure(0, weight=1)
        quick.columnconfigure(1, weight=1)

        ttk.Button(quick, text="Only HSBC", command=self._only_hsbc).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(quick, text="Only Market", command=self._only_market).grid(row=0, column=1, sticky="ew")

        quick2 = ttk.Frame(left)
        quick2.grid(row=5, column=0, sticky="ew", pady=(0, 10))
        quick2.columnconfigure(0, weight=1)
        quick2.columnconfigure(1, weight=1)

        ttk.Button(quick2, text="Show all", command=self._show_all).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(quick2, text="Hide all", command=self._hide_all).grid(row=0, column=1, sticky="ew")

        # Scrollable toggle panel (narrower canvas)
        panel_wrap = ttk.Frame(left)
        panel_wrap.grid(row=6, column=0, sticky="nsew")
        panel_wrap.rowconfigure(0, weight=1)
        panel_wrap.columnconfigure(0, weight=1)

        self._tog_canvas = tk.Canvas(panel_wrap, bg=self.BG, highlightthickness=0, width=235)
        self._tog_canvas.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(panel_wrap, orient="vertical", command=self._tog_canvas.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self._tog_canvas.configure(yscrollcommand=vsb.set)

        self._tog_frame = ttk.Frame(self._tog_canvas)
        self._tog_window = self._tog_canvas.create_window((0, 0), window=self._tog_frame, anchor="nw")

        self._tog_frame.bind("<Configure>", lambda e: self._tog_canvas.configure(scrollregion=self._tog_canvas.bbox("all")))
        self._tog_canvas.bind("<Configure>", lambda e: self._tog_canvas.itemconfigure(self._tog_window, width=e.width))

        # RIGHT: CHART + TOOLBAR
        right = ttk.Frame(self, style="CardInner.TFrame")
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 12), pady=12)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        tb = ttk.Frame(right)
        tb.grid(row=0, column=0, sticky="ew")
        tb.columnconfigure(0, weight=1)

        self.fig = Figure(figsize=(10, 5.0), dpi=100)
        gs = self.fig.add_gridspec(1, 2, width_ratios=[3.2, 1.2], wspace=0.18)

        self.ax_main = self.fig.add_subplot(gs[0, 0])
        self.ax_bar = self.fig.add_subplot(gs[0, 1])

        self.fig.patch.set_facecolor(self.BG)
        self.ax_main.set_facecolor(self.BG)
        self.ax_bar.set_facecolor(self.BG)

        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew")

        self.toolbar = NavigationToolbar2Tk(self.canvas, tb, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.pack(side="left", fill="x")

        self._draw_empty("No data yet")

    # ---------------- Public API ----------------
    def update_view(self, df: pd.DataFrame):
        self._df = df
        self._recompute_top5_and_select_default()

    # ---------------- Top 5 Underlyings ----------------
    def _recompute_top5_and_select_default(self):
        self._clear_all_state()

        if self._df is None or self._df.empty:
            self._title_var.set("Stefan I · CEO View")
            self._sub_var.set("No data available.")
            self._und_combo["values"] = []
            self._selected_underlying.set("")
            self._draw_empty("No data")
            return

        df = self._df

        group_col = next((c for c in self.GROUP_CANDIDATES if c in df.columns), None)
        missing = [c for c in (self.DATE_COL, self.EXPIRY_COL, self.ISSUER_COL, self.VALUE_COL) if c not in df.columns]
        if group_col is None:
            missing.append("UNDERLYING (e.g. UND_NAME)")

        if missing:
            self._sub_var.set("Missing columns:\n- " + "\n- ".join(missing))
            self._und_combo["values"] = []
            self._selected_underlying.set("")
            self._draw_empty("Missing columns")
            return

        self._group_col = group_col

        s = df[[group_col, self.VALUE_COL]].copy()
        s.rename(columns={group_col: "_UND"}, inplace=True)

        top = (
            s.groupby("_UND", observed=False)[self.VALUE_COL]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )
        self._top5 = [str(x) for x in top.index.tolist()]

        self._und_combo["values"] = self._top5
        if self._top5:
            cur = self._selected_underlying.get().strip()
            if cur not in self._top5:
                self._selected_underlying.set(self._top5[0])
            self._recompute_for_selected_underlying()
        else:
            self._selected_underlying.set("")
            self._draw_empty("No underlying")

    # ---------------- Expiry normalization ----------------
    def _normalize_expiry_series(self, exp: pd.Series) -> pd.Series:
        exp_str = exp.astype(str).str.strip()
        exp_str = exp_str.replace({"": np.nan, "NaT": np.nan, "nan": np.nan, "None": np.nan})

        dt = pd.to_datetime(exp_str, errors="coerce")
        rare = dt.isna() | (dt.dt.year >= 2100)

        out = pd.Series(index=exp.index, dtype=object)
        out[rare] = "OpenEnd"
        out[~rare] = dt[~rare].dt.strftime("%Y-%m-%d")
        return out

    @staticmethod
    def _expiry_sort_key(x: str):
        if x == "OpenEnd":
            return (9999, 99, 99)
        d = pd.to_datetime(x, errors="coerce")
        if pd.isna(d):
            return (9998, 99, 99)
        return (int(d.year), int(d.month), int(d.day))

    # ---------------- Main recompute for selection ----------------
    def _recompute_for_selected_underlying(self):
        self._series_raw.clear()
        self._expiry_marker.clear()
        self._lines.clear()
        self._toggle_vars.clear()
        self._totals_by_expiry = None
        self._clear_toggle_panel()

        if self._df is None or self._df.empty or self._group_col is None:
            self._draw_empty("No data")
            return

        und = self._selected_underlying.get().strip()
        if not und:
            self._draw_empty("Select an underlying")
            return

        df = self._df

        cols = [self._group_col, self.DATE_COL, self.EXPIRY_COL, self.ISSUER_COL, self.VALUE_COL]
        has_isin = (self.ISIN_COL in df.columns)
        if has_isin:
            cols.append(self.ISIN_COL)

        s = df[cols].copy()
        s.rename(columns={self._group_col: "_UND"}, inplace=True)

        s = s[s["_UND"].astype(str) == und]
        if s.empty:
            self._sub_var.set("No rows for selected underlying.")
            self._draw_empty("Empty")
            return

        s[self.DATE_COL] = pd.to_datetime(s[self.DATE_COL], errors="coerce")
        s = s.dropna(subset=[self.DATE_COL])
        if s.empty:
            self._sub_var.set("All rows have invalid TRANSACTION_DATE.")
            self._draw_empty("Invalid dates")
            return

        s["_EXP"] = self._normalize_expiry_series(s[self.EXPIRY_COL])
        s["_GRP"] = np.where(s[self.ISSUER_COL].astype(str) == self.HSBC_NAME, "HSBC", "Market")
        s["_DAY"] = s[self.DATE_COL].dt.floor("D")

        agg = (
            s.groupby(["_DAY", "_EXP", "_GRP"], observed=False)[self.VALUE_COL]
            .sum()
            .reset_index()
        )
        if agg.empty:
            self._sub_var.set("No aggregated data.")
            self._draw_empty("No data")
            return

        days = pd.date_range(agg["_DAY"].min(), agg["_DAY"].max(), freq="D")
        exps = sorted(agg["_EXP"].unique().tolist(), key=self._expiry_sort_key)
        grps = ["HSBC", "Market"]

        self._days = days
        self._expiries = exps

        for i, exp in enumerate(exps):
            self._expiry_marker[exp] = self.MARKERS[i % len(self.MARKERS)]

        for exp in exps:
            for grp in grps:
                sub = agg[(agg["_EXP"] == exp) & (agg["_GRP"] == grp)][["_DAY", self.VALUE_COL]]
                if sub.empty:
                    ser = pd.Series(0.0, index=days)
                else:
                    ser = sub.set_index("_DAY")[self.VALUE_COL].reindex(days, fill_value=0.0)
                self._series_raw[(exp, grp)] = ser

        tot_rows = []
        for exp in exps:
            hs = float(self._series_raw[(exp, "HSBC")].sum())
            mk = float(self._series_raw[(exp, "Market")].sum())
            tot_rows.append((exp, hs, mk))
        self._totals_by_expiry = pd.DataFrame(tot_rows, columns=["EXP", "HSBC", "Market"])

        total_vol = float(sum(float(self._series_raw[(exp, "HSBC")].sum() + self._series_raw[(exp, "Market")].sum()) for exp in exps))
        self._title_var.set("Stefan I · Expiry lines (HSBC vs Market)")
        self._sub_var.set(
            f"Underlying: {und}\n"
            f"Total volume (period): {self._fmt_big(total_vol)}\n"
            f"Markers identify expiry. HSBC=red · Market=grey."
        )

        isin_info = None
        if has_isin:
            isin_info = self._compute_top3_isin_per_expiry(s)

        self._build_toggle_panel_blocks(exps, isin_info=isin_info)
        self._redraw_plots_only()

    # ---------------- ISIN contribution blocks ----------------
    def _compute_top3_isin_per_expiry(self, s: pd.DataFrame) -> dict[str, list[tuple[str, float, float]]]:
        isin = s[self.ISIN_COL].astype(str).str.strip()
        isin = isin.replace({"": np.nan, "nan": np.nan, "None": np.nan})
        s2 = s.copy()
        s2["_ISIN"] = isin.fillna("UNKNOWN")

        exp_tot = s2.groupby("_EXP", observed=False)[self.VALUE_COL].sum()
        by = s2.groupby(["_EXP", "_ISIN"], observed=False)[self.VALUE_COL].sum()

        out: dict[str, list[tuple[str, float, float]]] = {}
        for exp in exp_tot.index.astype(str).tolist():
            tot = float(exp_tot.loc[exp]) if exp in exp_tot.index else 0.0
            if tot <= 0:
                out[exp] = []
                continue
            if exp not in by.index.get_level_values(0):
                out[exp] = []
                continue
            sub = by.loc[exp].sort_values(ascending=False).head(3)
            rows = []
            for isin_code, vol in sub.items():
                pct = 100.0 * float(vol) / tot if tot else 0.0
                rows.append((str(isin_code), float(vol), pct))
            out[exp] = rows
        return out

    # ---------------- Toggle panel blocks ----------------
    def _clear_toggle_panel(self):
        for w in self._tog_frame.winfo_children():
            w.destroy()

    def _build_toggle_panel_blocks(self, exps: list[str], isin_info: dict[str, list[tuple[str, float, float]]] | None):
        self._clear_toggle_panel()

        note = ttk.Label(
            self._tog_frame,
            text="Toggle expiries (marker + expiry)\nTop 3 ISIN shown (if available)",
            font=("Segoe UI", 9),
            foreground=self.SUB,
            justify="left",
        )
        note.grid(row=0, column=0, sticky="w", pady=(0, 10))
        r = 1

        for exp in exps:
            mk = self._expiry_marker.get(exp, "o")

            block = tk.Frame(self._tog_frame, bg=self.BG, highlightbackground=self.BORDER, highlightthickness=1)
            block.grid(row=r, column=0, sticky="ew", pady=6)
            block.columnconfigure(0, weight=1)
            r += 1

            title = tk.Label(
                block,
                text=f"{mk}  {exp}",
                bg=self.BG,
                fg=self.TEXT,
                font=("Segoe UI Semibold", 10),
                anchor="w",
                padx=8,
                pady=6,
            )
            title.grid(row=0, column=0, sticky="ew")

            togg = tk.Frame(block, bg=self.BG)
            togg.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 6))
            togg.columnconfigure(0, weight=1)
            togg.columnconfigure(1, weight=1)

            key_h = (exp, "HSBC")
            v_h = tk.BooleanVar(value=True)
            self._toggle_vars[key_h] = v_h
            tk.Checkbutton(
                togg, text="HSBC", variable=v_h, command=self._apply_toggles,
                fg=self.HSBC_RED, activeforeground=self.HSBC_RED,
                bg=self.BG, activebackground=self.BG, highlightthickness=0, bd=0,
                font=("Segoe UI", 10), anchor="w",
            ).grid(row=0, column=0, sticky="w")

            key_m = (exp, "Market")
            v_m = tk.BooleanVar(value=True)
            self._toggle_vars[key_m] = v_m
            tk.Checkbutton(
                togg, text="Market", variable=v_m, command=self._apply_toggles,
                fg=self.MKT_GREY, activeforeground=self.MKT_GREY,
                bg=self.BG, activebackground=self.BG, highlightthickness=0, bd=0,
                font=("Segoe UI", 10), anchor="w",
            ).grid(row=0, column=1, sticky="w")

            if isin_info is not None:
                rows = isin_info.get(exp, [])
                if rows:
                    lines = []
                    for (isin_code, vol, pct) in rows:
                        lines.append(f"• {isin_code}: {self._fmt_big(vol)}  ({pct:.1f}%)")
                    txt = "Top ISIN:\n" + "\n".join(lines)
                    tk.Label(
                        block, text=txt, bg=self.BG, fg=self.SUB,
                        font=("Segoe UI", 9), justify="left",
                        anchor="w", padx=10, pady=6,
                    ).grid(row=2, column=0, sticky="ew")

    # ---------------- Plotting ----------------
    def _draw_empty(self, msg: str):
        self.ax_main.clear()
        self.ax_bar.clear()
        self.ax_main.text(0.5, 0.5, msg, ha="center", va="center",
                          transform=self.ax_main.transAxes, color=self.SUB, fontsize=12)
        self.ax_main.set_xticks([])
        self.ax_main.set_yticks([])
        self.ax_bar.set_xticks([])
        self.ax_bar.set_yticks([])
        self.canvas.draw_idle()

    @staticmethod
    def _fmt_big(x: float) -> str:
        try:
            return f"{int(round(float(x))):,}"
        except Exception:
            return ""

    @staticmethod
    def _fmt_axis_km(x, _pos=None):
        try:
            v = float(x)
        except Exception:
            return ""
        av = abs(v)
        sign = "-" if v < 0 else ""
        if av >= 1_000_000:
            return f"{sign}{int(round(av / 1_000_000)):d}M"
        if av >= 1_000:
            return f"{sign}{int(round(av / 1_000)):d}k"
        return f"{sign}{int(round(av)):d}"

    def _get_series_for_plot(self, exp: str, grp: str) -> pd.Series:
        ser = self._series_raw.get((exp, grp))
        if ser is None:
            return pd.Series(dtype=float)
        if self._rolling7.get():
            return ser.rolling(7, min_periods=1).mean()
        return ser


    def _redraw_plots_only(self):
        if not self._series_raw or self._days is None:
            self._draw_empty("No data")
            return

        und = self._selected_underlying.get().strip()
        days = self._days
        exps = self._expiries

        self.ax_main.clear()
        self.ax_bar.clear()
        self._lines.clear()

        self.ax_main.yaxis.set_major_formatter(FuncFormatter(self._fmt_axis_km))
        self.ax_main.grid(True, axis="y", alpha=0.22)
        self.ax_main.margins(x=0.01)

        for exp in exps:
            mk = self._expiry_marker.get(exp, "o")

            ser_h = self._get_series_for_plot(exp, "HSBC").reindex(days, fill_value=0.0)
            line_h, = self.ax_main.plot(
                ser_h.index, ser_h.values,
                color=self.HSBC_RED, linewidth=2.4, alpha=1.0,
                marker=mk, markersize=4.6,
                markevery=max(1, int(len(ser_h) / 28)),
                label=f"HSBC · {exp}",
            )
            self._lines[(exp, "HSBC")] = line_h

            ser_m = self._get_series_for_plot(exp, "Market").reindex(days, fill_value=0.0)
            line_m, = self.ax_main.plot(
                ser_m.index, ser_m.values,
                color=self.MKT_GREY, linewidth=2.0, alpha=0.95,
                marker=mk, markersize=4.2,
                markevery=max(1, int(len(ser_m) / 28)),
                label=f"Market · {exp}",
            )
            self._lines[(exp, "Market")] = line_m

        roll_txt = "Rolling 7D" if self._rolling7.get() else "Daily"
        self.ax_main.set_title(f"{roll_txt} volume by expiry · Underlying: {und}", fontsize=12, color=self.TEXT)
        self.ax_main.set_ylabel("TXN_AMT", color=self.SUB)

        # Right mini chart: totals by expiry
        if self._totals_by_expiry is not None and not self._totals_by_expiry.empty:
            t = self._totals_by_expiry.copy()
            t["TOTAL"] = t["HSBC"] + t["Market"]
            t = t.sort_values("TOTAL", ascending=True)

            y = np.arange(len(t))
            hs = t["HSBC"].to_numpy()
            mk = t["Market"].to_numpy()

            self.ax_bar.barh(y - 0.18, mk, height=0.34, color=self.MKT_GREY, alpha=0.85, label="Market")
            self.ax_bar.barh(y + 0.18, hs, height=0.34, color=self.HSBC_RED, alpha=0.95, label="HSBC")

            labs = t["EXP"].astype(str).tolist()
            self.ax_bar.set_yticks(y)
            self.ax_bar.set_yticklabels(labs, fontsize=8)

            self.ax_bar.xaxis.set_major_formatter(FuncFormatter(self._fmt_axis_km))
            self.ax_bar.grid(True, axis="x", alpha=0.18)
            self.ax_bar.set_title("Total by expiry", fontsize=10, color=self.TEXT)
            self.ax_bar.legend(loc="lower right", fontsize=8, frameon=False)

        # apply toggles visibility
        self._apply_toggles(redraw=True)

    def _apply_toggles(self, redraw: bool = True):
        for key, line in self._lines.items():
            v = self._toggle_vars.get(key)
            visible = bool(v.get()) if v is not None else True
            line.set_visible(visible)
        if redraw:
            self.canvas.draw_idle()

    # ---------------- Quick toggles ----------------
    def _show_all(self):
        for v in self._toggle_vars.values():
            v.set(True)
        self._apply_toggles()

    def _hide_all(self):
        for v in self._toggle_vars.values():
            v.set(False)
        self._apply_toggles()

    def _only_hsbc(self):
        for (exp, grp), v in self._toggle_vars.items():
            v.set(grp == "HSBC")
        self._apply_toggles()

    def _only_market(self):
        for (exp, grp), v in self._toggle_vars.items():
            v.set(grp == "Market")
        self._apply_toggles()

    # ---------------- Utils ----------------
    def _clear_all_state(self):
        self._days = None
        self._expiries = []
        self._series_raw.clear()
        self._expiry_marker.clear()
        self._lines.clear()
        self._toggle_vars.clear()
        self._totals_by_expiry = None
        self._clear_toggle_panel()
