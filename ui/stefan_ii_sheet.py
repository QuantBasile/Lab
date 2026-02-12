# ui/stefan_ii_sheet.py
from __future__ import annotations

import os
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.font as tkfont

import numpy as np
import pandas as pd


class StefanIISheet(ttk.Frame):
    """
    Stefan II (CEO table, HTML/email-ready) - OOM-safe.

    Rows:
      - (Underlying, Side) with Side = CALL/PUT

    Columns:
      - Underlying
      - Side
      - One column per EXPIRY MONTH (HSBC ONLY) [capped, rest -> "Other"]
      - HSBC Total
      - Market Total (= ALL - HSBC)
      - Market Most Volume expiry (true max expiry in Market, not bucketed)
      - Top 3 ISINs HSBC (if ISIN exists)
      - Top 3 ISINs Market (if ISIN exists)
      - 🏁 ALL (Total volume)

    Styling:
      - HSBC Total column light red
      - HSBC expiry month cells: row-wise gradient heatmap (more colorful than max-only)
        (stronger color = bigger HSBC volume for that expiry-month in that row)
    """

    HSBC_NAME = "HSBC"

    VALUE_COL = "TXN_AMT"
    EXPIRY_COL = "EXPIRY"
    ISSUER_COL = "ISSUER_NAME"
    SIDE_COL = "CALL_OPTION"
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
        "UND_ISIN",
    )

    # IMPORTANT: prevents OOM when real data has hundreds of expiries
    MAX_EXPIRY_COLS = 12
    INCLUDE_OPENEND_ALWAYS = True
    OTHER_BUCKET_LABEL = "Other"

    HEADER_H = 46
    ROW_H = 34
    PAD_X = 10

    MIN_W = 90
    MAX_W = 860

    def __init__(self, master=None):
        super().__init__(master)

        self._df: pd.DataFrame | None = None
        self._group_col: str | None = None

        self._view_df: pd.DataFrame = pd.DataFrame()
        self._cols: list[str] = []
        self._col_widths: list[int] = []
        self._col_x: list[int] = []
        self._status_msg: str | None = None

        # (row_idx, col_idx) -> bg color
        self._cell_bg: dict[tuple[int, int], str] = {}

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
        self.SUB = "#475569"

        self.HEADER_BG = "#0b1220"
        self.HEADER_FG = "#ffffff"
        self.HEADER_ACCENT = "#2563eb"

        self.ROW_ODD = "#ffffff"
        self.ROW_EVEN = "#f7fafc"
        self.GRID = "#e2e8f0"

        # Totals
        self.HSBC_BG = "#fee2e2"  # light red

        # Heatmap colors for HSBC expiry cells
        # (low -> high)
        self.HEAT_LOW = "#ecfeff"     # very light cyan
        self.HEAT_HIGH = "#22c55e"    # strong green

        self.BTN_BG2 = "#0ea5e9"
        self.BTN_FG = "#ffffff"

        st.configure("S2.TFrame", background=self.WHITE)
        st.configure("S2Top.TFrame", background=self.WHITE)
        st.configure(
            "S2Title.TLabel",
            background=self.WHITE,
            foreground=self.TEXT,
            font=("Segoe UI Semibold", 16),
        )
        st.configure(
            "S2Hint.TLabel",
            background=self.WHITE,
            foreground=self.SUB,
            font=("Segoe UI", 10),
        )

    # ---------------- UI ----------------
    def _build_ui(self):
        self.configure(style="S2.TFrame")
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        top = ttk.Frame(self, style="S2Top.TFrame")
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        top.columnconfigure(0, weight=1)

        self._title_var = tk.StringVar(value="Stefan II · Expiry table (HSBC columns)")
        self._subtitle_var = tk.StringVar(value="")

        title_wrap = ttk.Frame(top, style="S2Top.TFrame")
        title_wrap.grid(row=0, column=0, sticky="w")
        ttk.Label(title_wrap, textvariable=self._title_var, style="S2Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(title_wrap, textvariable=self._subtitle_var, style="S2Hint.TLabel").grid(
            row=1, column=0, sticky="w", pady=(2, 0)
        )

        btns = ttk.Frame(top, style="S2Top.TFrame")
        btns.grid(row=0, column=1, sticky="e")

        # Removed Copy (Excel) button (per request)
        tk.Button(
            btns,
            text="Create HTML",
            command=self._create_html_report,
            bg=self.BTN_BG2,
            fg=self.BTN_FG,
            activebackground="#0284c7",
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
        ).pack(side="left")

        body = ttk.Frame(self, style="S2.TFrame")
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
        # Mouse wheel scrolling (FIX)
        # Robust: bind_all only while pointer is over canvas
        # ---------------------------
        self._canvas.bind("<Enter>", self._mw_enter)
        self._canvas.bind("<Leave>", self._mw_leave)

        # Also bind directly to canvas (some setups deliver wheel directly to widget)
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)
        self._canvas.bind("<Button-4>", self._on_mousewheel)  # Linux
        self._canvas.bind("<Button-5>", self._on_mousewheel)

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
        self._rebuild_and_refresh()

    # ---------------- Build table ----------------
    def _rebuild_and_refresh(self):
        self._build_table()
        if self._status_msg is None and not self._view_df.empty:
            self._compute_auto_widths_fast()
            self._update_scrollregion()
        else:
            self._canvas.configure(scrollregion=(0, 0, 1, 1))
        self._redraw()

    def _build_table(self):
        self._status_msg = None
        self._view_df = pd.DataFrame()
        self._cols = []
        self._cell_bg.clear()

        if self._df is None or self._df.empty:
            self._status_msg = "No data available."
            return

        df = self._df
        group_col = next((c for c in self.GROUP_CANDIDATES if c in df.columns), None)
        if group_col is None:
            self._status_msg = "Missing underlying column (UND_NAME/NAME/UND_ISIN...)."
            return
        self._group_col = group_col

        req = [self.EXPIRY_COL, self.ISSUER_COL, self.VALUE_COL, self.SIDE_COL]
        miss = [c for c in req if c not in df.columns]
        if miss:
            self._status_msg = "Missing columns: " + ", ".join(miss)
            return

        cols = [group_col, self.EXPIRY_COL, self.ISSUER_COL, self.VALUE_COL, self.SIDE_COL]
        has_isin = (self.ISIN_COL in df.columns)
        if has_isin:
            cols.append(self.ISIN_COL)

        s = df[cols].copy()
        s.rename(columns={group_col: "_UND"}, inplace=True)

        # normalize side
        side = s[self.SIDE_COL].astype(str).str.upper().str.strip()
        side = side.replace({"C": "CALL", "P": "PUT"})
        s["_SIDE"] = np.where(side.isin(["CALL", "PUT"]), side, side)

        # expiry normalized -> MONTH LABEL like "Jan-26" (plus OpenEnd)
        s["_EXP_RAW"] = self._normalize_expiry_month(s[self.EXPIRY_COL]).astype(str)

        # issuer group
        issuer = s[self.ISSUER_COL].astype(str)
        s["_IS_HSBC"] = (issuer == self.HSBC_NAME)

        # optional ISIN
        if has_isin:
            isin = s[self.ISIN_COL].astype(str).str.strip()
            isin = isin.replace({"": np.nan, "nan": np.nan, "None": np.nan}).fillna("UNKNOWN")
            s["_ISIN"] = isin

        # ---- Choose expiry columns safely (cap) ----
        # Use TOTAL volume by expiry month (ALL issuers) to select top months
        exp_tot = s.groupby("_EXP_RAW", observed=True)[self.VALUE_COL].sum().sort_values(ascending=False)

        expiries = exp_tot.index.tolist()
        selected = []

        if self.INCLUDE_OPENEND_ALWAYS and "OpenEnd" in expiries:
            selected.append("OpenEnd")

        for e in expiries:
            if e == "OpenEnd":
                continue
            selected.append(e)
            if len(selected) >= self.MAX_EXPIRY_COLS:
                break

        selected_set = set(selected)
        # bucket the rest into Other (only affects HSBC expiry columns)
        s["_EXP"] = np.where(s["_EXP_RAW"].isin(selected_set), s["_EXP_RAW"], self.OTHER_BUCKET_LABEL)

        exp_cols = selected.copy()
        # include "Other" if it exists
        if (s["_EXP"] == self.OTHER_BUCKET_LABEL).any():
            exp_cols.append(self.OTHER_BUCKET_LABEL)

        # Keep stable ordering: OpenEnd first if included, then months, then Other
        exp_cols_sorted = []
        if "OpenEnd" in exp_cols:
            exp_cols_sorted.append("OpenEnd")
        months = [e for e in exp_cols if e not in ("OpenEnd", self.OTHER_BUCKET_LABEL)]
        months = sorted(months, key=self._month_sort_key)
        exp_cols_sorted += months
        if self.OTHER_BUCKET_LABEL in exp_cols:
            exp_cols_sorted.append(self.OTHER_BUCKET_LABEL)
        exp_cols = exp_cols_sorted

        # ---- HSBC per expiry (month) wide table (SAFE) ----
        s_h = s[s["_IS_HSBC"]].copy()
        # if HSBC empty, we still show totals; expiry cols will be zeros

        hs_exp_wide = pd.pivot_table(
            s_h,
            values=self.VALUE_COL,
            index=["_UND", "_SIDE"],
            columns="_EXP",
            aggfunc="sum",
            fill_value=0.0,
            observed=True
        ) if not s_h.empty else pd.DataFrame(index=pd.MultiIndex.from_tuples([], names=["_UND", "_SIDE"]))

        # ensure all expiry columns exist
        for e in exp_cols:
            if e not in hs_exp_wide.columns:
                hs_exp_wide[e] = 0.0
        if not hs_exp_wide.empty:
            hs_exp_wide = hs_exp_wide[exp_cols]

        # ---- Totals (ALL & HSBC) ----
        all_total = s.groupby(["_UND", "_SIDE"], observed=True)[self.VALUE_COL].sum()
        hs_total = (
            s_h.groupby(["_UND", "_SIDE"], observed=True)[self.VALUE_COL].sum()
            if not s_h.empty else all_total * 0.0
        )
        hs_total = hs_total.reindex(all_total.index, fill_value=0.0)
        mk_total = (all_total - hs_total).clip(lower=0.0)

        # ---- Underlying total for sorting (CALL+PUT together) ----
        und_total = all_total.groupby(level=0, observed=True).sum().sort_values(ascending=False)

        # ---- Market Most Volume expiry (true raw expiry from original, NOT month-bucketed) ----
        # We compute from original EXPIRY column for market only
        s_m = s[~s["_IS_HSBC"]].copy()
        if not s_m.empty:
            # use original expiry normalized to date string (for "true" most volume expiry)
            s_m["_EXP_TRUE"] = self._normalize_expiry_date(df.loc[s_m.index, self.EXPIRY_COL])
            mk_exp = s_m.groupby(["_UND", "_SIDE", "_EXP_TRUE"], observed=True)[self.VALUE_COL].sum()
            mk_max_exp = mk_exp.groupby(level=[0, 1], observed=True).idxmax()
            mk_max_exp = mk_max_exp.map(lambda t: t[2] if isinstance(t, tuple) and len(t) == 3 else "")
        else:
            mk_max_exp = pd.Series("", index=all_total.index)

        # ---- Top 3 ISINs per (UND,SIDE) for HSBC and Market ----
        def top3_isin_text(sub_df: pd.DataFrame) -> pd.Series:
            if not has_isin or sub_df.empty:
                return pd.Series("", index=all_total.index)
            agg = sub_df.groupby(["_UND", "_SIDE", "_ISIN"], observed=True)[self.VALUE_COL].sum()
            out = {}
            for (und, side2), grp in agg.groupby(level=[0, 1], observed=True):
                g = grp.droplevel([0, 1]).sort_values(ascending=False)
                tot = float(g.sum())
                top = g.head(3)
                parts = []
                for isin_code, vol in top.items():
                    pct = (100.0 * float(vol) / tot) if tot else 0.0
                    parts.append(f"{isin_code}: {self._fmt_compact(float(vol))} ({pct:.0f}%)")
                out[(und, side2)] = " · ".join(parts)
            ser = pd.Series(out)
            return ser.reindex(all_total.index, fill_value="")

        top_isin_h = top3_isin_text(s_h) if has_isin else pd.Series("", index=all_total.index)
        top_isin_m = top3_isin_text(s_m) if has_isin else pd.Series("", index=all_total.index)

        # ---- Build output table ----
        self._cols = (
            ["Underlying", "Side"]
            + exp_cols
            + ["HSBC Total", "Market Total", "Market Most Volume expiry", "Top 3 ISINs HSBC", "Top 3 ISINs Market", "🏁 ALL"]
        )

        rows = []
        sides_order = ["CALL", "PUT"]

        for und in und_total.index.tolist():
            for side2 in sides_order:
                key = (und, side2)
                if key not in all_total.index:
                    continue

                # HSBC expiry values
                if (not hs_exp_wide.empty) and (key in hs_exp_wide.index):
                    exp_vals_num = hs_exp_wide.loc[key].to_numpy(dtype=float)
                else:
                    exp_vals_num = np.zeros(len(exp_cols), dtype=float)

                exp_vals = [self._fmt_compact(v) for v in exp_vals_num]

                hs_t = float(hs_total.loc[key])
                mk_t = float(mk_total.loc[key])
                all_t = float(all_total.loc[key])
                mk_max = str(mk_max_exp.get(key, ""))

                row = (
                    [str(und), str(side2)]
                    + exp_vals
                    + [
                        self._fmt_compact(hs_t),
                        self._fmt_compact(mk_t),
                        mk_max,
                        str(top_isin_h.get(key, "")),
                        str(top_isin_m.get(key, "")),
                        self._fmt_compact(all_t),
                    ]
                )
                r_i = len(rows)
                rows.append(row)

                # HSBC Total bg
                idx_hs_total = 2 + len(exp_cols)
                self._cell_bg[(r_i, idx_hs_total)] = self.HSBC_BG

                # Heatmap across HSBC expiry cells (columns 2 .. 2+len(exp_cols)-1)
                self._apply_row_heatmap_expiries(r_i, exp_vals_num, base_bg=None)

        self._view_df = pd.DataFrame(rows, columns=self._cols)

        self._subtitle_var.set(
            f"HSBC expiry MONTH columns capped at {self.MAX_EXPIRY_COLS} (rest → '{self.OTHER_BUCKET_LABEL}'). "
            f"Market = ALL − HSBC. Heatmap shows HSBC volume intensity across expiries."
        )

    # ---------------- Helpers ----------------
    @staticmethod
    def _blend_hex(c1: str, c2: str, t: float) -> str:
        """Blend two hex colors (0..1)."""
        t = float(np.clip(t, 0.0, 1.0))
        c1 = c1.lstrip("#")
        c2 = c2.lstrip("#")
        r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
        r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)
        r = int(round(r1 + (r2 - r1) * t))
        g = int(round(g1 + (g2 - g1) * t))
        b = int(round(b1 + (b2 - b1) * t))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _apply_row_heatmap_expiries(self, r_i: int, exp_vals_num: np.ndarray, base_bg: str | None):
        """
        Apply heatmap backgrounds to the HSBC expiry columns for a given row.

        exp_vals_num corresponds to exp_cols order.
        """
        if exp_vals_num is None or len(exp_vals_num) == 0:
            return

        vmax = float(np.max(exp_vals_num)) if float(np.max(exp_vals_num)) > 0 else 0.0
        if vmax <= 0:
            return

        # expiry columns start at index 2
        for j, v in enumerate(exp_vals_num):
            vv = float(v)
            if vv <= 0:
                continue
            t = vv / vmax  # 0..1 in row
            # boost contrast a bit (gamma)
            t = t ** 0.65
            col = self._blend_hex(self.HEAT_LOW, self.HEAT_HIGH, t)
            self._cell_bg[(r_i, 2 + j)] = col

    def _normalize_expiry_month(self, exp: pd.Series) -> pd.Series:
        """
        Normalize expiry to:
          - "OpenEnd" for NaT / blank / year>=2100
          - else month label like "Jan-26" (English months)
        """
        exp_str = exp.astype(str).str.strip()
        exp_str = exp_str.replace({"": np.nan, "NaT": np.nan, "nan": np.nan, "None": np.nan})
        dt = pd.to_datetime(exp_str, errors="coerce")

        rare = dt.isna() | (dt.dt.year >= 2100)

        out = pd.Series(index=exp.index, dtype=object)
        out[rare] = "OpenEnd"

        # month label for non-rare
        months = np.array(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], dtype=object)
        m = dt[~rare].dt.month.astype(int).to_numpy() - 1
        y = dt[~rare].dt.year.astype(int).to_numpy() % 100
        lab = pd.Series(months[m], index=dt[~rare].index).astype(str) + "-" + pd.Series(y, index=dt[~rare].index).map(lambda x: f"{int(x):02d}")
        out[~rare] = lab
        return out

    def _normalize_expiry_date(self, exp: pd.Series) -> pd.Series:
        """
        Normalize expiry to a date string for "true expiry" display:
          - "OpenEnd" for NaT / blank / year>=2100
          - else "YYYY-MM-DD"
        """
        exp_str = exp.astype(str).str.strip()
        exp_str = exp_str.replace({"": np.nan, "NaT": np.nan, "nan": np.nan, "None": np.nan})
        dt = pd.to_datetime(exp_str, errors="coerce")
        rare = dt.isna() | (dt.dt.year >= 2100)
        out = pd.Series(index=exp.index, dtype=object)
        out[rare] = "OpenEnd"
        out[~rare] = dt[~rare].dt.strftime("%Y-%m-%d")
        return out

    @staticmethod
    def _month_sort_key(x: str):
        """Sort key for month labels like 'Jan-26'. 'OpenEnd' first, 'Other' last."""
        if x == "OpenEnd":
            return (0, 0)
        if x == StefanIISheet.OTHER_BUCKET_LABEL:
            return (9999, 99)
        # parse 'Mon-YY'
        try:
            mon_map = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
                       "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
            mon = x[:3]
            yy = int(x[-2:])
            year = 2000 + yy
            mm = mon_map.get(mon, 99)
            return (year, mm)
        except Exception:
            return (9998, 99)

    @staticmethod
    def _fmt_compact(x: float) -> str:
        try:
            v = float(x)
        except Exception:
            return ""
        sign = "-" if v < 0 else ""
        v = abs(v)
        if v >= 1_000_000:
            m = int(round(v / 1_000_000))
            return f"{sign}{m:,}M"
        if v >= 1_000:
            k = int(round(v / 1_000))
            return f"{sign}{k:,}k"
        return f"{sign}{int(round(v)):,}"

    # ---------------- Auto-width + scrolling ----------------
    def _compute_auto_widths_fast(self):
        if self._view_df.empty:
            return
        widths = []
        for c in self._cols:
            s = self._view_df[c].astype(str)
            max_len = int(s.str.len().max() or 0)
            w = max_len * self._char_px + (self.PAD_X * 2) + 20
            w = int(min(self.MAX_W, max(self.MIN_W, w)))

            # Keep your "wide text columns" behavior
            if c in ("Underlying", "Top 3 ISINs HSBC", "Top 3 ISINs Market"):
                w = min(self.MAX_W, max(w, 1800))
            if c == "Market Most Volume expiry":
                w = min(self.MAX_W, max(w, 1000))

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

    def _update_scrollregion(self):
        total_w = self._col_x[-1] if self._col_x else 1
        total_h = self.HEADER_H + len(self._view_df) * self.ROW_H
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

    # ---------------- Render ----------------
    def _redraw(self):
        self._canvas.delete("all")

        if self._status_msg is not None:
            w = max(400, int(self._canvas.winfo_width() or 800))
            h = max(200, int(self._canvas.winfo_height() or 400))
            self._canvas.create_text(
                w / 2,
                h / 2,
                text=self._status_msg,
                fill=self.SUB,
                font=self._font_big,
                justify="center",
                anchor="center",
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

        # header bg
        self._canvas.create_rectangle(vx0, 0, vx1, self.HEADER_H, fill=self.HEADER_BG, outline=self.HEADER_BG)
        self._canvas.create_rectangle(
            vx0, self.HEADER_H - 3, vx1, self.HEADER_H, fill=self.HEADER_ACCENT, outline=self.HEADER_ACCENT
        )

        for ci in range(c0, c1 + 1):
            col = self._cols[ci]
            x_left = self._col_x[ci]
            x_right = self._col_x[ci + 1]
            cw = x_right - x_left

            anchor = "w" if ci == 0 else "center"
            tx = x_left + self.PAD_X if anchor == "w" else x_left + cw / 2

            self._canvas.create_text(
                tx, self.HEADER_H / 2 - 1, text=col, fill=self.HEADER_FG, font=self._font_head, anchor=anchor
            )
            self._canvas.create_line(x_right, 0, x_right, self.HEADER_H, fill="#111827", width=1)

        for ri in range(r0, r1 + 1):
            y0 = self.HEADER_H + ri * self.ROW_H
            y1 = y0 + self.ROW_H
            base_bg = self.ROW_EVEN if (ri % 2 == 0) else self.ROW_ODD

            for ci in range(c0, c1 + 1):
                x_left = self._col_x[ci]
                x_right = self._col_x[ci + 1]
                cw = x_right - x_left

                bg = self._cell_bg.get((ri, ci), base_bg)
                self._canvas.create_rectangle(x_left, y0, x_right, y1, fill=bg, outline=self.GRID)

                val = str(self._view_df.iat[ri, ci])

                anchor = "w" if ci == 0 else "center"
                tx = x_left + self.PAD_X if anchor == "w" else x_left + cw / 2
                ty = (y0 + y1) / 2

                self._canvas.create_text(tx, ty, text=val, fill=self.TEXT, font=self._font_body, anchor=anchor)

        self._canvas.configure(scrollregion=(0, 0, self._col_x[-1], total_h))

    # ---------------- Scroll events ----------------
    def _on_vscroll(self, *args):
        self._canvas.yview(*args)
        self._redraw()

    def _on_hscroll(self, *args):
        self._canvas.xview(*args)
        self._redraw()

    # ---------------- Mouse wheel handlers ----------------
    def _on_mousewheel(self, event):
        if getattr(event, "delta", 0) != 0:
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        else:
            # Linux
            if getattr(event, "num", None) == 5:
                self._canvas.yview_scroll(1, "units")
            elif getattr(event, "num", None) == 4:
                self._canvas.yview_scroll(-1, "units")
        self._redraw()
        return "break"

    def _on_shift_mousewheel(self, event):
        if getattr(event, "delta", 0) != 0:
            self._canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
        else:
            if getattr(event, "num", None) == 5:
                self._canvas.xview_scroll(1, "units")
            elif getattr(event, "num", None) == 4:
                self._canvas.xview_scroll(-1, "units")
        self._redraw()
        return "break"

    # ---------------- HTML Report ----------------
    def _create_html_report(self):
        if self._view_df.empty:
            messagebox.showinfo("Create HTML", "No data for report.")
            return

        try:
            # NOTE: if you later distribute, consider writing to a user-writable folder
            reports_dir = os.path.abspath(os.path.join(os.getcwd(), "reports"))
            os.makedirs(reports_dir, exist_ok=True)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"stefan_ii_{ts}.html"
            fpath = os.path.join(reports_dir, fname)

            title = "Stefan II · Expiry table"
            subtitle = self._subtitle_var.get()

            cols = self._cols
            df = self._view_df

            head_html = "".join(f"<th>{c}</th>" for c in cols)

            body_rows = []
            for r in range(len(df)):
                tds = []
                for c_i, c in enumerate(cols):
                    val = str(df.iat[r, c_i])
                    base_bg = "#f7fafc" if (r % 2 == 0) else "#ffffff"
                    bg = self._cell_bg.get((r, c_i), base_bg)
                    align = "left" if c_i == 0 else "center"
                    tds.append(f"<td style='background:{bg}; text-align:{align};'>{val}</td>")
                body_rows.append("<tr>" + "".join(tds) + "</tr>")
            body_html = "\n".join(body_rows)

            html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Stefan II</title>
<style>
  body {{
    font-family: Segoe UI, Arial, sans-serif;
    margin: 18px;
    color: #0b1220;
    background: #ffffff;
  }}
  h1 {{
    margin: 0 0 6px 0;
    font-size: 20px;
  }}
  .sub {{
    color:#475569;
    font-size: 12px;
    margin: 0 0 12px 0;
    line-height: 1.35;
    white-space: pre-line;
  }}

  /* NEW: 90vh scrollable area (vertical + horizontal) */
  .wrap {{
    height: 90vh;
    overflow: auto;
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
    position: sticky;
    top: 0;
    z-index: 2;
  }}
  thead tr {{ border-bottom: 3px solid #2563eb; }}

  tbody td {{
    border: 1px solid #e2e8f0;
    padding: 8px 10px;
    font-size: 13px;
    vertical-align: middle;
  }}

  /* NEW: click row highlight */
  tbody tr.selected td {{
    background: #cfe8ff !important;
  }}
</style>
</head>
<body>
  <h1>{title}</h1>
  <div class="sub">{subtitle}</div>

  <div class="wrap">
    <table id="s2-table">
      <thead><tr>{head_html}</tr></thead>
      <tbody>
        {body_html}
      </tbody>
    </table>
  </div>

  <script>
    document.querySelectorAll("#s2-table tbody tr").forEach(tr => {{
      tr.addEventListener("click", () => {{
        document.querySelectorAll("#s2-table tbody tr.selected")
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
