# ui/hsbc_comparison_sheet.py
from __future__ import annotations

import os
import re
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.font as tkfont

import numpy as np
import pandas as pd


class HSBCComparisonSheet(ttk.Frame):
    WEEK_COL = "WEEK"
    ISSUER_COL = "ISSUER_NAME"
    VALUE_COL = "TXN_AMT"
    HSBC_NAME = "HSBC"

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

    MODES = ("ABSOLUT", "PRO_ZEILE")

    # Default now 2 and 2 as requested
    DEFAULT_N_WEEKS = 2
    DEFAULT_M_WEEKS = 2

    HEADER_H = 44
    ROW_H = 32
    PAD_X = 10

    MIN_GROUP_W = 160
    MAX_GROUP_W = 520
    MIN_CELL_W = 105
    MAX_CELL_W = 360

    SPARK_W = 120

    def __init__(self, master=None):
        super().__init__(master)

        self._df: pd.DataFrame | None = None
        self._group_col: str | None = None

        self._mode = tk.StringVar(value="ABSOLUT")
        self._n_weeks = tk.IntVar(value=self.DEFAULT_N_WEEKS)
        self._m_weeks = tk.IntVar(value=self.DEFAULT_M_WEEKS)

        self._view_df: pd.DataFrame = pd.DataFrame()
        self._status_msg: str | None = None

        self._cols: list[str] = []
        self._col_widths: list[int] = []
        self._col_x: list[int] = []

        self._cell_bg: dict[tuple[int, int], str] = {}
        self._cell_arrow: dict[tuple[int, int], tuple[int, str, str]] = {}

        self._spark_weeks: list[str] = []
        self._prev_len: int = 0
        self._spark_abs: dict[str, np.ndarray] = {}
        self._spark_pct: dict[str, np.ndarray] = {}

        self._title_str = "HSBC Comparison · Ranking shift (last vs previous weeks)"
        self._subtitle_lines: list[str] = []

        self._font_body = tkfont.Font(family="Segoe UI", size=11)
        self._font_head = tkfont.Font(family="Segoe UI Semibold", size=11)
        self._font_big = tkfont.Font(family="Segoe UI Semibold", size=13)

        self._char_px = max(6, int(self._font_body.measure("0123456789") / 10))

        self._build_styles()
        self._build_ui()

    # ---------------- Styles ----------------
    def _build_styles(self):
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass

        self.WHITE = "#ffffff"
        self.TEXT = "#0b1220"
        self.SUBTEXT = "#334155"

        self.HEADER_BG = "#0b1220"
        self.HEADER_FG = "#ffffff"
        self.HEADER_ACCENT = "#2563eb"

        self.ROW_ODD = "#ffffff"
        self.ROW_EVEN = "#f7fafc"
        self.GRID = "#e2e8f0"
        self.SEP_BLACK = "#000000"

        self.HSBC_RED_BG = "#fee2e2"

        self.GROUP_GREEN = "#dcfce7"
        self.GROUP_YELLOW = "#fef9c3"
        self.GROUP_RED = "#ffe4e6"

        self.ARROW_UP = "#16a34a"
        self.ARROW_DOWN = "#dc2626"
        self.ARROW_FLAT = "#475569"

        self.SPARK_PREV = "#94a3b8"
        self.SPARK_ABS = "#111827"
        self.SPARK_PCT = "#2563eb"
        self.SPARK_GRID = "#cbd5e1"

        self.BTN_BG = "#2563eb"
        self.BTN_BG2 = "#0ea5e9"
        self.BTN_BG3 = "#111827"
        self.BTN_FG = "#ffffff"

        st.configure("Comp.TFrame", background=self.WHITE)
        st.configure("CompTop.TFrame", background=self.WHITE)
        st.configure("CompTitle.TLabel", background=self.WHITE, foreground=self.TEXT,
                     font=("Segoe UI Semibold", 16))
        st.configure("CompHint.TLabel", background=self.WHITE, foreground=self.SUBTEXT,
                     font=("Segoe UI", 10))

    # ---------------- UI ----------------
    def _build_ui(self):
        self.configure(style="Comp.TFrame")
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        top = ttk.Frame(self, style="CompTop.TFrame")
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        # Keep right controls visible: title expands, controls stay compact
        top.columnconfigure(0, weight=1)  # title area grows
        top.columnconfigure(1, weight=0)  # controls do NOT grow

        # ---- Left: title + subtitle
        title_wrap = ttk.Frame(top, style="CompTop.TFrame")
        title_wrap.grid(row=0, column=0, sticky="ew")
        title_wrap.columnconfigure(0, weight=1)

        self._title_var = tk.StringVar(value=self._title_str)
        self._subtitle_var = tk.StringVar(value="")

        ttk.Label(title_wrap, textvariable=self._title_var, style="CompTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(title_wrap, textvariable=self._subtitle_var, style="CompHint.TLabel").grid(
            row=1, column=0, sticky="w", pady=(2, 0)
        )

        # ---- Right: controls (2 rows, so buttons never go off-screen)
        ctr = ttk.Frame(top, style="CompTop.TFrame")
        ctr.grid(row=0, column=1, sticky="ne", padx=(16, 0))
        # 2 rows: inputs then buttons
        for c in range(8):
            ctr.columnconfigure(c, weight=0)

        # Row 0: inputs
        ttk.Label(ctr, text="Ansicht:", style="CompHint.TLabel").grid(row=0, column=0, padx=(0, 6), sticky="e")
        cb_mode = ttk.Combobox(ctr, values=self.MODES, textvariable=self._mode, state="readonly", width=12)
        cb_mode.grid(row=0, column=1, sticky="w")
        # NO auto-recalc on change
        cb_mode.bind("<<ComboboxSelected>>", lambda e: None)

        ttk.Label(ctr, text="Last N weeks:", style="CompHint.TLabel").grid(row=0, column=2, padx=(12, 6), sticky="e")
        sp_n = ttk.Spinbox(ctr, from_=1, to=26, increment=1, textvariable=self._n_weeks, width=4)
        sp_n.grid(row=0, column=3, sticky="w")

        ttk.Label(ctr, text="Prev M weeks:", style="CompHint.TLabel").grid(row=0, column=4, padx=(12, 6), sticky="e")
        sp_m = ttk.Spinbox(ctr, from_=1, to=52, increment=1, textvariable=self._m_weeks, width=4)
        sp_m.grid(row=0, column=5, sticky="w")

        # Row 1: buttons (fixed, always visible)
        btns = ttk.Frame(ctr, style="CompTop.TFrame")
        btns.grid(row=1, column=0, columnspan=6, sticky="e", pady=(10, 0))

        tk.Button(
            btns, text="Calculate", command=self._rebuild_and_refresh,
            bg=self.BTN_BG3, fg=self.BTN_FG, activebackground="#0b1220",
            relief="flat", padx=12, pady=6, cursor="hand2"
        ).pack(side="left", padx=(0, 8))

        # --- REMOVED Copy (Excel) button ---

        tk.Button(
            btns, text="Create HTML", command=self._create_html_report,
            bg=self.BTN_BG2, fg=self.BTN_FG, activebackground="#0284c7",
            relief="flat", padx=12, pady=6, cursor="hand2"
        ).pack(side="left")

        # ---- Body: canvas + scrollbars
        body = ttk.Frame(self, style="Comp.TFrame")
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(body, bg=self.WHITE, highlightthickness=0, bd=0)
        self._vsb = ttk.Scrollbar(body, orient="vertical", command=self._on_vscroll)
        self._hsb = ttk.Scrollbar(body, orient="horizontal", command=self._on_hscroll)
        self._canvas.configure(yscrollcommand=self._vsb.set, xscrollcommand=self._hsb.set)

        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._vsb.grid(row=0, column=1, sticky="ns")
        self._hsb.grid(row=1, column=0, sticky="ew")

        self._canvas.bind("<Configure>", lambda e: self._redraw())

        # ---------------------------
        # Mouse wheel (FIXED like MartinStyleSheet)
        # Robust: bind_all only while pointer is over the canvas
        # ---------------------------
        self._canvas.bind("<Enter>", self._mw_enter)
        self._canvas.bind("<Leave>", self._mw_leave)

        # Also bind directly to canvas (some setups deliver wheel to widget under pointer)
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)
        self._canvas.bind("<Button-4>", self._on_mousewheel)
        self._canvas.bind("<Button-5>", self._on_mousewheel)

        # Keep Ctrl+C shortcut (even if the button is removed)
        self._canvas.bind_all("<Control-c>", self._copy_excel_ready)
        self._canvas.bind_all("<Command-c>", self._copy_excel_ready)

    # ---------------- Mouse wheel scoped binding ----------------
    def _mw_enter(self, event=None):
        top = self.winfo_toplevel()
        top.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        top.bind_all("<Shift-MouseWheel>", self._on_shift_mousewheel, add="+")
        top.bind_all("<Button-4>", self._on_mousewheel, add="+")
        top.bind_all("<Button-5>", self._on_mousewheel, add="+")
        return None

    def _mw_leave(self, event=None):
        top = self.winfo_toplevel()
        try:
            top.unbind_all("<MouseWheel>")
            top.unbind_all("<Shift-MouseWheel>")
            top.unbind_all("<Button-4>")
            top.unbind_all("<Button-5>")
        except Exception:
            pass
        return None

    # ---------------- Public API ----------------
    def update_view(self, df: pd.DataFrame):
        self._df = df
        # Do NOT auto-recalc heavy view: let user press Calculate
        self._status_msg = "Ready.\nAdjust N/M/Ansicht and press Calculate."
        self._cols = []
        self._view_df = pd.DataFrame()
        self._subtitle_var.set("Adjust N/M/Ansicht on the right → press Calculate.")
        self._canvas.configure(scrollregion=(0, 0, 1, 1))
        self._redraw()

    # ---------------- WEEK normalization ----------------
    @staticmethod
    def _week_key(w: str):
        w = str(w).strip()
        if w.isdigit():
            return int(w)
        m = re.match(r"^\s*(\d{4})\s*[-_ ]?W?\s*(\d{1,2})\s*$", w, re.IGNORECASE)
        if m:
            y = int(m.group(1))
            ww = int(m.group(2))
            return y * 100 + ww
        return w

    def _select_weeks(self, df: pd.DataFrame):
        week_raw = df[self.WEEK_COL].dropna().astype(str).str.strip()
        if week_raw.empty:
            return None, None, None

        keys = week_raw.map(self._week_key)
        df_weeks = pd.DataFrame({"week_str": week_raw, "key": keys})
        df_weeks = df_weeks.drop_duplicates(subset=["key"], keep="first")
        df_weeks = df_weeks.sort_values("key", kind="mergesort")

        weeks_sorted_str = df_weeks["week_str"].to_list()

        n = int(self._n_weeks.get())
        m = int(self._m_weeks.get())

        if len(weeks_sorted_str) < n + m:
            self._status_msg = f"Not enough weeks in data.\nNeed {n+m} unique WEEK values, got {len(weeks_sorted_str)}."
            return None, None, None

        curr = weeks_sorted_str[-n:]
        prev = weeks_sorted_str[-(n + m):-n]
        window = prev + curr
        return window, prev, curr

    # ---------------- Formatting ----------------
    @staticmethod
    def _fmt_int_commas(n: int) -> str:
        return f"{n:,}"

    def _fmt_abs_compact_int_commas(self, x: float) -> str:
        try:
            v = float(x)
        except Exception:
            return ""
        sign = "-" if v < 0 else ""
        v = abs(v)
        if v >= 1_000_000:
            m = int(round(v / 1_000_000))
            return f"{sign}{self._fmt_int_commas(m)}M"
        if v >= 1_000:
            k = int(round(v / 1_000))
            return f"{sign}{self._fmt_int_commas(k)}k"
        return f"{sign}{self._fmt_int_commas(int(round(v)))}"

    @staticmethod
    def _fmt_pct_1d(x: float) -> str:
        try:
            return f"{float(x):.1f}%"
        except Exception:
            return ""

    # ---------------- Build table ----------------
    def _rebuild_and_refresh(self):
        self._build_table()
        if self._status_msg is None:
            self._compute_auto_widths_fast()
            self._update_scrollregion()
        else:
            if self._cols:
                self._update_scrollregion()
            else:
                self._canvas.configure(scrollregion=(0, 0, 1, 1))
        self._redraw()

    def _build_table(self):
        self._status_msg = None
        self._view_df = pd.DataFrame()
        self._cell_bg.clear()
        self._cell_arrow.clear()
        self._spark_weeks = []
        self._prev_len = 0
        self._spark_abs.clear()
        self._spark_pct.clear()
        self._subtitle_lines = []

        if self._df is None or self._df.empty:
            self._status_msg = "No data available.\nLoad data first (Generate / Apply filters)."
            return

        df = self._df

        req_missing = [c for c in (self.WEEK_COL, self.ISSUER_COL, self.VALUE_COL) if c not in df.columns]
        if req_missing:
            self._status_msg = f"Cannot build comparison.\nMissing columns: {', '.join(req_missing)}"
            return

        group_col = next((c for c in self.GROUP_CANDIDATES if c in df.columns), None)
        if group_col is None:
            self._status_msg = f"Cannot build comparison.\nMissing underlying column (tried {', '.join(self.GROUP_CANDIDATES)})"
            return
        self._group_col = group_col

        weeks_window, prev_weeks, curr_weeks = self._select_weeks(df)
        if weeks_window is None:
            if self._status_msg is None:
                self._status_msg = "Cannot build comparison.\nWEEK parsing failed."
            return

        self._spark_weeks = weeks_window
        self._prev_len = len(prev_weeks)

        def chips(label: str, xs: list[str]) -> str:
            return f"{label}: " + " ".join([f"[{x}]" for x in xs])

        self._subtitle_lines = [
            f"{chips('PREV', prev_weeks)}   |   {chips('CURR', curr_weeks)}",
            "Red cell = HSBC.",
            "(#p ↑/↓/—) in HSBC cell = previous rank (#p) and change vs current position.",
            "Sparklines: grey=PREV, color=CURR (HSBC volume and HSBC share).",
            "Semaforo (GROUP): 🟢 #1 · 🟡 #2–#5 · 🔴 >#5 (HSBC current rank).",
        ]
        self._subtitle_var.set("\n".join(self._subtitle_lines))

        slim_cols = [group_col, self.WEEK_COL, self.ISSUER_COL, self.VALUE_COL]
        s = df[slim_cols].copy()
        s.rename(columns={group_col: "_GROUP"}, inplace=True)
        week_norm = s[self.WEEK_COL].astype(str).str.strip()

        s_curr = s[week_norm.isin(set(curr_weeks))]
        s_prev = s[week_norm.isin(set(prev_weeks))]
        s_win = s[week_norm.isin(set(weeks_window))]

        if s_curr.empty or s_prev.empty:
            self._status_msg = "Empty period after filtering.\nCheck WEEK values or filters."
            return

        mode = self._mode.get()
        is_pro = (mode == "PRO_ZEILE")

        pv_curr = pd.pivot_table(
            s_curr, index="_GROUP", columns=self.ISSUER_COL, values=self.VALUE_COL,
            aggfunc="sum", fill_value=0.0, observed=False
        )
        pv_prev = pd.pivot_table(
            s_prev, index="_GROUP", columns=self.ISSUER_COL, values=self.VALUE_COL,
            aggfunc="sum", fill_value=0.0, observed=False
        )
        pv_curr.columns.name = None
        pv_prev.columns.name = None

        issuers = sorted(set(pv_curr.columns).union(set(pv_prev.columns)))
        pv_curr = pv_curr.reindex(columns=issuers, fill_value=0.0)
        pv_prev = pv_prev.reindex(columns=issuers, fill_value=0.0)

        if self.HSBC_NAME not in issuers:
            self._status_msg = "HSBC not found in ISSUER_NAME.\nNo HSBC comparison possible."
            return
        hsbc_idx = issuers.index(self.HSBC_NAME)

        all_curr = pv_curr.sum(axis=1).astype(float)
        pv_curr = pv_curr.loc[all_curr.sort_values(ascending=False).index]
        pv_prev = pv_prev.reindex(index=pv_curr.index, fill_value=0.0)
        all_curr = pv_curr.sum(axis=1).astype(float)

        if is_pro:
            denom = all_curr.replace(0.0, np.nan)
            pv_curr_pct = pv_curr.div(denom, axis=0).fillna(0.0) * 100.0
        else:
            pv_curr_pct = None

        # Sparklines
        s_hsbc = s_win[s_win[self.ISSUER_COL] == self.HSBC_NAME].copy()
        s_tot = s_win.copy()

        hsbc_by = (
            s_hsbc.assign(_W=week_norm[s_hsbc.index].astype(str).str.strip())
            .groupby(["_GROUP", "_W"], observed=False)[self.VALUE_COL].sum()
        )
        tot_by = (
            s_tot.assign(_W=week_norm[s_tot.index].astype(str).str.strip())
            .groupby(["_GROUP", "_W"], observed=False)[self.VALUE_COL].sum()
        )

        win_weeks = weeks_window
        for g in pv_curr.index.astype(str).tolist():
            abs_arr = np.zeros(len(win_weeks), dtype=float)
            pct_arr = np.zeros(len(win_weeks), dtype=float)
            for i, w in enumerate(win_weeks):
                hv = float(hsbc_by.get((g, w), 0.0)) if isinstance(hsbc_by, pd.Series) else 0.0
                tv = float(tot_by.get((g, w), 0.0)) if isinstance(tot_by, pd.Series) else 0.0
                abs_arr[i] = hv
                pct_arr[i] = (100.0 * hv / tv) if tv != 0 else 0.0
            self._spark_abs[g] = abs_arr
            self._spark_pct[g] = pct_arr

        n_iss = len(issuers)
        rank_cols = [f"{i}°" for i in range(1, n_iss + 1)]
        self._cols = ["GROUP", "HSBC VOL", "HSBC %"] + rank_cols + ["ALL"]

        curr_np = pv_curr.to_numpy(dtype=float, copy=False)
        prev_np = pv_prev.to_numpy(dtype=float, copy=False)

        view_rows: list[list[str]] = []

        for r_i, g in enumerate(pv_curr.index.astype(str).tolist()):
            vals_c = curr_np[r_i]
            vals_p = prev_np[r_i]

            order_c = np.argsort(-vals_c)
            order_p = np.argsort(-vals_p)

            prev_pos = np.empty(n_iss, dtype=int)
            prev_pos[order_p] = np.arange(1, n_iss + 1)

            hsbc_curr_pos = int(np.where(order_c == hsbc_idx)[0][0]) + 1
            hsbc_prev_pos = int(prev_pos[hsbc_idx])

            group_label = g
            if hsbc_curr_pos == 1:
                self._cell_bg[(r_i, 0)] = self.GROUP_GREEN
                group_label = "🟢 " + g
            elif 2 <= hsbc_curr_pos <= 5:
                self._cell_bg[(r_i, 0)] = self.GROUP_YELLOW
                group_label = "🟡 " + g
            else:
                self._cell_bg[(r_i, 0)] = self.GROUP_RED
                group_label = "🔴 " + g

            row_cells = [""] * n_iss

            for kpos in range(n_iss):
                idx = int(order_c[kpos])
                name = issuers[idx]

                if not is_pro:
                    v_str = self._fmt_abs_compact_int_commas(float(vals_c[idx]))
                else:
                    v_str = self._fmt_pct_1d(float(pv_curr_pct.iat[r_i, idx]))  # type: ignore[union-attr]

                if name != self.HSBC_NAME:
                    row_cells[kpos] = f"{name}: {v_str}"
                else:
                    ppos = hsbc_prev_pos
                    if (kpos + 1) < ppos:
                        delta = f"↑{ppos - (kpos + 1)}"
                        arrow_color = self.ARROW_UP
                    elif (kpos + 1) > ppos:
                        delta = f"↓{(kpos + 1) - ppos}"
                        arrow_color = self.ARROW_DOWN
                    else:
                        delta = "—"
                        arrow_color = self.ARROW_FLAT

                    txt = f"{v_str} (#{ppos} {delta})"
                    row_cells[kpos] = txt

                    col_view = 3 + kpos
                    self._cell_bg[(r_i, col_view)] = self.HSBC_RED_BG

                    arrow_char = delta[0]
                    arrow_idx = txt.find(arrow_char)
                    if arrow_idx >= 0 and arrow_char in ("↑", "↓", "—"):
                        self._cell_arrow[(r_i, col_view)] = (arrow_idx, arrow_char, arrow_color)

            all_str = self._fmt_abs_compact_int_commas(float(all_curr.loc[g]))
            view_rows.append([group_label, "", ""] + row_cells + [all_str])

        self._view_df = pd.DataFrame(view_rows, columns=self._cols)

    # ---------------- Auto-width ----------------
    def _compute_auto_widths_fast(self):
        if self._view_df.empty:
            return

        g = self._view_df["GROUP"].astype(str)
        g = g.str.replace("🟢 ", "", regex=False).str.replace("🟡 ", "", regex=False).str.replace("🔴 ", "", regex=False)
        max_g = int(g.str.len().max() or 0)
        group_w = max_g * self._char_px + (self.PAD_X * 2) + 24
        group_w = int(min(self.MAX_GROUP_W, max(self.MIN_GROUP_W, group_w)))

        widths = [group_w, self.SPARK_W, self.SPARK_W]
        for c in self._cols[3:]:
            s = self._view_df[c].astype(str)
            max_len = int(s.str.len().max() or 0)
            w = max_len * self._char_px + (self.PAD_X * 2) + 24
            w = int(min(self.MAX_CELL_W, max(self.MIN_CELL_W, w)))
            widths.append(w)

        self._col_widths = widths
        self._col_x = self._compute_col_x(widths)

    @staticmethod
    def _compute_col_x(widths: list[int]) -> list[int]:
        x = [0]
        s = 0
        for w in widths:
            s += int(w)
            x.append(s)
        return x

    # ---------------- Virtual rendering helpers ----------------
    def _on_vscroll(self, *args):
        self._canvas.yview(*args)
        self._redraw()

    def _on_hscroll(self, *args):
        self._canvas.xview(*args)
        self._redraw()

    def _update_scrollregion(self):
        if not self._cols:
            self._canvas.configure(scrollregion=(0, 0, 1, 1))
            return
        total_w = self._col_x[-1]
        total_h = self.HEADER_H + (len(self._view_df) * self.ROW_H)
        self._canvas.configure(scrollregion=(0, 0, total_w, total_h))

    def _visible_row_range(self):
        h = max(1, int(self._canvas.winfo_height() or 1))
        y0 = self._canvas.canvasy(0)
        y1 = y0 + h
        first = max(0, int((y0 - self.HEADER_H) // self.ROW_H))
        last = min(len(self._view_df) - 1, int((y1 - self.HEADER_H) // self.ROW_H) + 1)
        return first, last

    def _visible_col_range(self):
        w = max(1, int(self._canvas.winfo_width() or 1))
        x0 = self._canvas.canvasx(0)
        x1 = x0 + w
        xs = self._col_x

        c0 = 0
        for i in range(len(xs) - 1):
            if xs[i + 1] > x0:
                c0 = i
                break

        c1 = len(xs) - 2
        for i in range(c0, len(xs) - 1):
            if xs[i] >= x1:
                c1 = max(c0, i - 1)
                break
        return c0, c1

    # ---------------- Sparklines drawing ----------------
    def _draw_sparkline_split(self, x0: float, y0: float, x1: float, y1: float, series: np.ndarray, curr_color: str):
        if series is None or len(series) < 2:
            return

        pad = 6
        sx0, sy0 = x0 + pad, y0 + pad
        sx1, sy1 = x1 - pad, y1 - pad
        if sx1 <= sx0 or sy1 <= sy0:
            return

        vmin = float(np.min(series))
        vmax = float(np.max(series))

        midy = (sy0 + sy1) / 2
        self._canvas.create_line(sx0, midy, sx1, midy, fill=self.SPARK_GRID, width=1)

        xs = np.linspace(sx0, sx1, len(series))
        split = max(1, min(self._prev_len, len(series) - 1))

        if vmax - vmin < 1e-12:
            yy = (sy0 + sy1) / 2
            self._canvas.create_line(xs[0], yy, xs[split - 1], yy, fill=self.SPARK_PREV, width=2)
            self._canvas.create_line(xs[split - 1], yy, xs[-1], yy, fill=curr_color, width=2)
            return

        ys = sy1 - (series - vmin) / (vmax - vmin) * (sy1 - sy0)

        pts_prev = []
        for i in range(0, split):
            pts_prev.extend([float(xs[i]), float(ys[i])])
        if len(pts_prev) >= 4:
            self._canvas.create_line(*pts_prev, fill=self.SPARK_PREV, width=2)

        pts_curr = []
        for i in range(split - 1, len(series)):
            pts_curr.extend([float(xs[i]), float(ys[i])])
        if len(pts_curr) >= 4:
            self._canvas.create_line(*pts_curr, fill=curr_color, width=2)

    # ---------------- Redraw ----------------
    def _redraw(self):
        self._canvas.delete("all")

        if self._status_msg is not None and (self._view_df.empty or not self._cols):
            w = max(400, int(self._canvas.winfo_width() or 800))
            h = max(200, int(self._canvas.winfo_height() or 400))
            self._canvas.create_text(
                w / 2, h / 2,
                text=self._status_msg,
                fill=self.SUBTEXT,
                font=self._font_big,
                justify="center",
                anchor="center"
            )
            self._canvas.configure(scrollregion=(0, 0, w, h))
            return

        if self._view_df.empty or not self._cols:
            return

        total_h = self.HEADER_H + len(self._view_df) * self.ROW_H
        r0, r1 = self._visible_row_range()
        c0, c1 = self._visible_col_range()

        vx0 = self._col_x[c0]
        vx1 = self._col_x[c1 + 1]

        # Header
        self._canvas.create_rectangle(vx0, 0, vx1, self.HEADER_H, fill=self.HEADER_BG, outline=self.HEADER_BG)
        self._canvas.create_rectangle(vx0, self.HEADER_H - 3, vx1, self.HEADER_H,
                                      fill=self.HEADER_ACCENT, outline=self.HEADER_ACCENT)

        for ci in range(c0, c1 + 1):
            col = self._cols[ci]
            x_left = self._col_x[ci]
            x_right = self._col_x[ci + 1]
            cw = x_right - x_left

            if col == "GROUP":
                anchor = "w"
                tx = x_left + self.PAD_X
            else:
                anchor = "center"
                tx = x_left + cw / 2

            self._canvas.create_text(tx, self.HEADER_H / 2 - 1, text=col,
                                     fill=self.HEADER_FG, font=self._font_head, anchor=anchor)
            self._canvas.create_line(x_right, 0, x_right, self.HEADER_H, fill="#111827", width=1)

        # Body
        for ri in range(r0, r1 + 1):
            y0 = self.HEADER_H + ri * self.ROW_H
            y1 = y0 + self.ROW_H
            base_bg = self.ROW_EVEN if (ri % 2 == 0) else self.ROW_ODD

            g_text = str(self._view_df.iat[ri, 0])
            g_key = g_text.replace("🟢 ", "").replace("🟡 ", "").replace("🔴 ", "")

            for ci in range(c0, c1 + 1):
                x_left = self._col_x[ci]
                x_right = self._col_x[ci + 1]
                cw = x_right - x_left

                bg = self._cell_bg.get((ri, ci), base_bg)
                self._canvas.create_rectangle(x_left, y0, x_right, y1, fill=bg, outline=self.GRID)

                col_name = self._cols[ci]

                if col_name == "HSBC VOL":
                    series = self._spark_abs.get(g_key)
                    if series is not None:
                        self._draw_sparkline_split(x_left, y0, x_right, y1, series, self.SPARK_ABS)
                    continue

                if col_name == "HSBC %":
                    series = self._spark_pct.get(g_key)
                    if series is not None:
                        self._draw_sparkline_split(x_left, y0, x_right, y1, series, self.SPARK_PCT)
                    continue

                val = str(self._view_df.iat[ri, ci])

                if col_name == "GROUP":
                    self._canvas.create_text(x_left + self.PAD_X, (y0 + y1) / 2, text=val,
                                             fill=self.TEXT, font=self._font_body, anchor="w")
                    continue

                cx = x_left + cw / 2
                cy = (y0 + y1) / 2

                key = (ri, ci)
                if key in self._cell_arrow:
                    arrow_idx, arrow_char, arrow_color = self._cell_arrow[key]
                    self._canvas.create_text(cx, cy, text=val, fill=self.TEXT, font=self._font_body, anchor="center")

                    total_w = self._font_body.measure(val)
                    prefix_w = self._font_body.measure(val[:arrow_idx])
                    arrow_w = self._font_body.measure(arrow_char)

                    left_x = cx - total_w / 2
                    arrow_x = left_x + prefix_w + arrow_w / 2
                    self._canvas.create_text(arrow_x, cy, text=arrow_char, fill=arrow_color,
                                             font=self._font_body, anchor="center")
                else:
                    self._canvas.create_text(cx, cy, text=val, fill=self.TEXT, font=self._font_body, anchor="center")

        # Separator after HSBC % (spark columns)
        try:
            sep_col = self._cols.index("HSBC %")
            xx = self._col_x[sep_col + 1]
            self._canvas.create_line(xx, 0, xx, total_h, fill=self.SEP_BLACK, width=2)
        except ValueError:
            pass

        # Vertical black separators: between 1° and 2°, and between 5° and 6°
        for rank_name in ("1°", "5°"):
            try:
                idx = self._cols.index(rank_name)
                xx = self._col_x[idx + 1]
                self._canvas.create_line(xx, 0, xx, total_h, fill=self.SEP_BLACK, width=2)
            except ValueError:
                pass

        self._canvas.configure(scrollregion=(0, 0, self._col_x[-1], total_h))

    # ---------------- Mouse wheel ----------------
    def _on_mousewheel(self, event):
        if getattr(event, "delta", 0) != 0:
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        else:
            if event.num == 5:
                self._canvas.yview_scroll(1, "units")
            elif event.num == 4:
                self._canvas.yview_scroll(-1, "units")
        self._redraw()
        return "break"

    def _on_shift_mousewheel(self, event):
        if getattr(event, "delta", 0) != 0:
            self._canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
        else:
            if event.num == 5:
                self._canvas.xview_scroll(1, "units")
            elif event.num == 4:
                self._canvas.xview_scroll(-1, "units")
        self._redraw()
        return "break"

    # ---------------- Copy Excel-ready (kept: Ctrl+C shortcut) ----------------
    def _copy_excel_ready(self, event=None):
        if self._view_df.empty:
            if event is None:
                try:
                    messagebox.showinfo("Copy", "No data to copy.")
                except Exception:
                    pass
            return "break"

        lines = ["\t".join(self._cols)]
        for r in range(len(self._view_df)):
            row = [str(self._view_df.iat[r, c]) for c in range(len(self._cols))]
            lines.append("\t".join(row))
        txt = "\n".join(lines)

        try:
            self.clipboard_clear()
            self.clipboard_append(txt)
            self.update()
            if event is None:
                messagebox.showinfo("Copy (Excel)", "Copied to clipboard (Excel-ready).")
        except Exception:
            pass
        return "break"

    # ---------------- HTML report (multiline subtitle + separators) ----------------
    def _spark_svg_split(self, series: np.ndarray, curr_stroke: str) -> str:
        if series is None or len(series) < 2:
            return ""
        vmin = float(np.min(series))
        vmax = float(np.max(series))
        w, h = 110, 22
        pad = 2

        split = max(1, min(self._prev_len, len(series) - 1))

        def poly(points, stroke):
            return f"<polyline points='{points}' fill='none' stroke='{stroke}' stroke-width='2'/>"

        mid = h / 2
        grid = f"<line x1='{pad}' y1='{mid:.1f}' x2='{w-pad}' y2='{mid:.1f}' stroke='{self.SPARK_GRID}' stroke-width='1'/>"

        if vmax - vmin < 1e-12:
            y = h / 2
            x0 = pad
            x_split = pad + (w - 2 * pad) * (split - 1) / (len(series) - 1)
            x1 = w - pad
            return (
                f"<svg width='{w}' height='{h}' viewBox='0 0 {w} {h}'>"
                f"{grid}"
                f"<line x1='{x0}' y1='{y}' x2='{x_split}' y2='{y}' stroke='{self.SPARK_PREV}' stroke-width='2'/>"
                f"<line x1='{x_split}' y1='{y}' x2='{x1}' y2='{y}' stroke='{curr_stroke}' stroke-width='2'/>"
                f"</svg>"
            )

        xs = np.linspace(pad, w - pad, len(series))
        ys = (h - pad) - (series - vmin) / (vmax - vmin) * (h - 2 * pad)

        pts_prev = " ".join([f"{xs[i]:.2f},{ys[i]:.2f}" for i in range(0, split)])
        pts_curr = " ".join([f"{xs[i]:.2f},{ys[i]:.2f}" for i in range(split - 1, len(series))])

        return (
            f"<svg width='{w}' height='{h}' viewBox='0 0 {w} {h}'>"
            f"{grid}"
            f"{poly(pts_prev, self.SPARK_PREV)}"
            f"{poly(pts_curr, curr_stroke)}"
            f"</svg>"
        )

    def _create_html_report(self):
        if self._view_df.empty:
            messagebox.showinfo("Create HTML", "No data for report.")
            return

        try:
            reports_dir = os.path.abspath(os.path.join(os.getcwd(), "reports"))
            os.makedirs(reports_dir, exist_ok=True)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"hsbc_comparison_{ts}.html"
            fpath = os.path.join(reports_dir, fname)

            title = self._title_str
            subtitle_lines = self._subtitle_lines[:] if self._subtitle_lines else []

            df = self._view_df
            cols = self._cols

            def bg_for_cell(r, c):
                bg = self._cell_bg.get((r, c))
                if bg:
                    return bg
                return "#f7fafc" if (r % 2 == 0) else "#ffffff"

            sep_after_cols = set()
            for nm in ("1°", "5°", "HSBC %"):
                if nm in cols:
                    sep_after_cols.add(cols.index(nm))

            head_html = ""
            for i, c in enumerate(cols):
                cls = "sep-right" if i in sep_after_cols else ""
                head_html += f"<th class='{cls}'>{c}</th>"

            body_rows = []
            for r in range(len(df)):
                g_text = str(df.iat[r, 0]).replace("🟢 ", "").replace("🟡 ", "").replace("🔴 ", "")
                tds = []
                for c_i, c in enumerate(cols):
                    bg = bg_for_cell(r, c_i)
                    align = "left" if c == "GROUP" else "center"
                    cls = "sep-right" if c_i in sep_after_cols else ""

                    if c == "HSBC VOL":
                        svg = self._spark_svg_split(self._spark_abs.get(g_text), self.SPARK_ABS)
                        tds.append(f"<td class='{cls}' style='background:{bg}; text-align:{align};'>{svg}</td>")
                        continue

                    if c == "HSBC %":
                        svg = self._spark_svg_split(self._spark_pct.get(g_text), self.SPARK_PCT)
                        tds.append(f"<td class='{cls}' style='background:{bg}; text-align:{align};'>{svg}</td>")
                        continue

                    val = str(df.iat[r, c_i])

                    if (r, c_i) in self._cell_arrow:
                        arrow_idx, arrow_char, arrow_color = self._cell_arrow[(r, c_i)]
                        pre = val[:arrow_idx]
                        post = val[arrow_idx + 1:]
                        val_html = f"{pre}<span style='color:{arrow_color}; font-weight:800;'>{arrow_char}</span>{post}"
                    else:
                        val_html = val

                    tds.append(
                        f"<td class='{cls}' style='background:{bg}; color:{self.TEXT}; text-align:{align};'>{val_html}</td>"
                    )

                body_rows.append("<tr>" + "".join(tds) + "</tr>")

            body_html = "\n".join(body_rows)

            def render_week_chips(line: str) -> str:
                parts = line.split("|")
                out = []
                for p in parts:
                    p = p.strip()
                    if ":" not in p:
                        continue
                    label, rest = p.split(":", 1)
                    items = [x.strip("[] ") for x in rest.strip().split() if x.strip()]
                    chips = " ".join([f"<span class='chip'>{x}</span>" for x in items])
                    out.append(f"<div class='line'><span class='lab'>{label.strip()}</span>{chips}</div>")
                return "".join(out)

            week_block = render_week_chips(subtitle_lines[0]) if subtitle_lines else ""
            other_lines_html = "".join([f"<div class='explain-line'>{line}</div>" for line in subtitle_lines[1:]])

            # ---- HTML (changes requested): 90vh wrapper + row selection highlight ----
            html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HSBC Comparison</title>
<style>
  body {{
    font-family: Segoe UI, Arial, sans-serif;
    margin: 18px;
    color: #0b1220;
    background: #ffffff;
  }}
  h1 {{
    margin: 0 0 10px 0;
    font-size: 20px;
  }}
  .weeks {{
    margin: 0 0 8px 0;
    color:#475569;
    font-size: 12px;
    display:flex;
    gap: 14px;
    flex-wrap: wrap;
  }}
  .line {{
    display:flex;
    align-items:center;
    gap: 8px;
  }}
  .lab {{
    font-weight: 800;
    color:#0b1220;
  }}
  .chip {{
    display:inline-block;
    padding: 3px 8px;
    border-radius: 999px;
    background: #0b1220;
    color: white;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: .2px;
  }}
  .explain {{
    color:#475569;
    font-size: 12px;
    margin: 0 0 12px 0;
    display:flex;
    flex-direction: column;
    gap: 4px;
  }}
  .explain-line {{
    line-height: 1.25;
  }}

  .table-wrap {{
    height: 90vh;                 /* NEW */
    overflow: auto;               /* NEW: vertical + horizontal */
    -webkit-overflow-scrolling: touch;
    border-radius: 14px;
    box-shadow: 0 10px 28px rgba(2,6,23,0.10);
  }}
  table {{
    width: max-content;
    border-collapse: collapse;
    background: white;
    white-space: nowrap;
    min-width: 100%;
  }}
  thead th {{
    background: #0b1220;
    color: white;
    text-align: center;
    padding: 12px 10px;
    font-weight: 800;
    font-size: 13px;
    border-right: 1px solid #111827;
    position: sticky;             /* keep sticky header */
    top: 0;
    z-index: 2;
  }}
  thead th:first-child {{ text-align:left; }}
  thead tr {{ border-bottom: 3px solid #2563eb; }}
  tbody td {{
    border: 1px solid #e2e8f0;
    padding: 8px 10px;
    font-size: 13px;
  }}
  svg {{ display:block; margin: 0 auto; }}

  .sep-right {{
    border-right: 2px solid #000000 !important;
  }}

  /* NEW: Row selection */
  tbody tr.selected td {{
    background: #cfe8ff !important;
  }}
</style>
</head>
<body>
  <h1>{title}</h1>

  <div class="weeks">{week_block}</div>
  <div class="explain">{other_lines_html}</div>

  <div class="table-wrap">
    <table id="comp-table">
      <thead><tr>{head_html}</tr></thead>
      <tbody>
        {body_html}
      </tbody>
    </table>
  </div>

  <script>
    // NEW: Click row to highlight selection
    document.querySelectorAll("#comp-table tbody tr").forEach(tr => {{
      tr.addEventListener("click", () => {{
        document.querySelectorAll("#comp-table tbody tr.selected")
          .forEach(x => x.classList.remove("selected"));
        tr.classList.add("selected");
      }});
    }});
  </script>

</body>
</html>
"""
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(html)

            url = "file://" + fpath.replace("\\", "/")
            self.clipboard_clear()
            self.clipboard_append(url)
            self.update()
            messagebox.showinfo("Create HTML", f"HTML created. URL copied:\n{url}")
        except Exception as ex:
            messagebox.showerror("Create HTML", f"Failed:\n{ex}")
