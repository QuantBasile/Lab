# ui/martin_style_sheet.py
from __future__ import annotations

import os
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.font as tkfont

import numpy as np
import pandas as pd


class MartinStyleSheet(ttk.Frame):
    """
    PERFORMANCE ranking sheet (Canvas, virtual rendering) + fast auto-width.

    Optimizations:
      - Groupby fixed (underlying) with robust fallback mapping (UND_NAME/NAME/...)
      - Top = ALL issuers
      - No click-to-sort
      - Virtual rendering: draw only visible rows/cols
      - Auto-width (minimal, no cut) computed efficiently:
          * rank cols width derived from longest issuer label (O(#issuers))
          * group width from max group string length (vectorized)
          * all width from worst-case / max value

    Business rules:
      - Mode: ABSOLUT / PRO_ZEILE (row-normalized)
      - ALL always absolute
      - HSBC cell always red (wherever it appears)
      - GROUP semaphore based on HSBC absolute rank:
          #1 -> 🟢 green
          #2–#5 -> 🟡 yellow
          >#5 -> 🔴 red
      - ALL row label: 🏁 ALL
      - Copy (Excel) and Create HTML (reports/)
      - Title: "Ranking per underlyings"
    """

    MODES = ("ABSOLUT", "PRO_ZEILE")

    ISSUER_COL = "ISSUER_NAME"
    VALUE_COL = "TXN_AMT"

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

    # Hard minimums (avoid too tiny)
    MIN_GROUP_W = 140
    MIN_RANK_W = 90
    MIN_ALL_W = 90

    # Hard maximums (avoid comically wide)
    MAX_GROUP_W = 520
    MAX_RANK_W = 360
    MAX_ALL_W = 160

    HEADER_H = 44
    ROW_H = 32
    PAD_X = 10

    def __init__(self, master=None):
        super().__init__(master)

        self._df: pd.DataFrame | None = None
        self._pivot_abs: pd.DataFrame = pd.DataFrame()

        self._mode = tk.StringVar(value="ABSOLUT")

        # Render caches
        self._issuers: list[str] = []
        self._cols: list[str] = []
        self._col_widths: list[int] = []
        self._col_x: list[int] = []

        self._view_df: pd.DataFrame = pd.DataFrame()
        self._cell_bg: dict[tuple[int, int], str] = {}  # (row_idx, col_idx) -> bg color

        # Status
        self._status_msg: str | None = None

        # Title (single line)
        self._title_str = "Ranking per underlyings"

        # Fonts
        self._font_body = tkfont.Font(family="Segoe UI", size=11)
        self._font_body_bold = tkfont.Font(family="Segoe UI Semibold", size=11)
        self._font_head = tkfont.Font(family="Segoe UI Semibold", size=11)
        self._font_title = tkfont.Font(family="Segoe UI Semibold", size=16)
        self._font_big = tkfont.Font(family="Segoe UI Semibold", size=13)

        # For ultra-fast width estimation:
        # approximate pixel width per character (computed once)
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

        self.ALL_ROW_BG = "#eef2ff"
        self.ALL_ROW_FG = "#111827"

        # Cell highlights
        self.HSBC_RED = "#fee2e2"
        self.GROUP_GREEN = "#dcfce7"
        self.GROUP_YELLOW = "#fef9c3"
        self.GROUP_RED = "#ffe4e6"

        # Buttons
        self.BTN_BG = "#2563eb"
        self.BTN_BG2 = "#0ea5e9"
        self.BTN_FG = "#ffffff"

        st.configure("Martin.TFrame", background=self.WHITE)
        st.configure("MartinTop.TFrame", background=self.WHITE)
        st.configure("MartinTitle.TLabel", background=self.WHITE, foreground=self.TEXT,
                     font=("Segoe UI Semibold", 16))
        st.configure("MartinHint.TLabel", background=self.WHITE, foreground=self.SUBTEXT,
                     font=("Segoe UI", 10))

    # ---------------- UI ----------------
    def _build_ui(self):
        self.configure(style="Martin.TFrame")
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        top = ttk.Frame(self, style="MartinTop.TFrame")
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        top.columnconfigure(2, weight=1)

        # Single title only
        title_wrap = ttk.Frame(top, style="MartinTop.TFrame")
        title_wrap.grid(row=0, column=0, rowspan=2, sticky="w")

        self._title_var = tk.StringVar(value=self._title_str)
        ttk.Label(title_wrap, textvariable=self._title_var, style="MartinTitle.TLabel").grid(row=0, column=0, sticky="w")

        # Controls + actions (mode + buttons)
        ctr = ttk.Frame(top, style="MartinTop.TFrame")
        ctr.grid(row=0, column=2, rowspan=2, sticky="e")

        ttk.Label(ctr, text="Ansicht:", style="MartinHint.TLabel").grid(row=0, column=0, padx=(0, 6))
        cb_mode = ttk.Combobox(ctr, values=self.MODES, textvariable=self._mode,
                               state="readonly", width=12)
        cb_mode.grid(row=0, column=1)
        cb_mode.bind("<<ComboboxSelected>>", lambda e: self._refresh())

        btns = ttk.Frame(ctr, style="MartinTop.TFrame")
        btns.grid(row=1, column=0, columnspan=2, sticky="e", pady=(10, 0))

        tk.Button(
            btns, text="Copy (Excel)", command=self._copy_excel_ready,
            bg=self.BTN_BG, fg=self.BTN_FG, activebackground="#1d4ed8",
            relief="flat", padx=12, pady=6, cursor="hand2"
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            btns, text="Create HTML", command=self._create_html_report,
            bg=self.BTN_BG2, fg=self.BTN_FG, activebackground="#0284c7",
            relief="flat", padx=12, pady=6, cursor="hand2"
        ).pack(side="left")

        # Canvas + scrollbars
        body = ttk.Frame(self, style="Martin.TFrame")
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

        self._canvas.bind("<Configure>", lambda e: self._on_resize())

        # mouse wheel
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind_all("<Shift-MouseWheel>", self._on_shift_mousewheel)
        self._canvas.bind_all("<Button-4>", self._on_mousewheel)  # Linux
        self._canvas.bind_all("<Button-5>", self._on_mousewheel)

        # Ctrl+C
        self._canvas.bind_all("<Control-c>", self._copy_excel_ready)
        self._canvas.bind_all("<Command-c>", self._copy_excel_ready)

    # ---------------- Public API ----------------
    def update_view(self, df: pd.DataFrame):
        self._df = df
        self._rebuild_and_refresh()

    # ---------------- Build pipeline ----------------
    def _rebuild_and_refresh(self):
        self._prepare_pivot_abs()
        if self._status_msg is None:
            self._compute_view_and_colors()
            self._compute_auto_widths_fast()
            self._update_scrollregion()
        else:
            self._view_df = pd.DataFrame()
            self._cell_bg.clear()
            self._cols = []
            self._col_widths = []
            self._col_x = []
            self._canvas.configure(scrollregion=(0, 0, 1, 1))
        self._redraw()

    def _refresh(self):
        if self._status_msg is None and not self._pivot_abs.empty:
            self._compute_view_and_colors()
            self._compute_auto_widths_fast()
            self._update_scrollregion()
        self._redraw()

    def _prepare_pivot_abs(self):
        self._pivot_abs = pd.DataFrame()
        self._issuers = []
        self._status_msg = None

        if self._df is None or self._df.empty:
            self._status_msg = "No data available.\nLoad data first (Generate / Apply filters)."
            return

        s = self._df

        missing = [c for c in (self.ISSUER_COL, self.VALUE_COL) if c not in s.columns]
        if missing:
            self._status_msg = (
                "Ranking cannot be built.\n"
                f"Missing columns: {', '.join(missing)}\n"
                "Tip: check your DataService output schema."
            )
            return

        group_col = next((c for c in self.GROUP_CANDIDATES if c in s.columns), None)
        if group_col is None:
            self._status_msg = (
                "Ranking cannot be built.\n"
                "Missing underlying column.\n"
                f"Tried: {', '.join(self.GROUP_CANDIDATES)}"
            )
            return

        slim = s[[group_col, self.ISSUER_COL, self.VALUE_COL]].copy()
        slim.rename(columns={group_col: "_GROUP"}, inplace=True)

        pv = pd.pivot_table(
            slim,
            index="_GROUP",
            columns=self.ISSUER_COL,
            values=self.VALUE_COL,
            aggfunc="sum",
            fill_value=0.0,
            observed=False,
        )
        pv.columns.name = None
        pv = pv.reindex(sorted(pv.columns), axis=1)
        pv = pv.loc[pv.sum(axis=1).sort_values(ascending=False).index]

        pv.index.name = "GROUP"
        self._pivot_abs = pv
        self._issuers = list(pv.columns)

        n = len(self._issuers)
        if n == 0 or pv.empty:
            self._status_msg = "Ranking is empty.\n(After filters, there are no issuers/volumes.)"
            return

        self._cols = ["GROUP"] + [f"{i}°" for i in range(1, n + 1)] + ["ALL"]

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

    # ---------------- Compute view + colors ----------------
    def _compute_view_and_colors(self):
        self._view_df = pd.DataFrame()
        self._cell_bg.clear()

        pv = self._pivot_abs
        if pv.empty:
            return

        issuers = self._issuers
        mode = self._mode.get()
        is_pro_zeile = (mode == "PRO_ZEILE")

        row_sum = pv.sum(axis=1).astype(float)
        pv_pct = None
        if is_pro_zeile:
            denom = row_sum.replace(0.0, np.nan)
            pv_pct = pv.div(denom, axis=0).fillna(0.0) * 100.0

        rows = pv.index.to_list()
        n_rows = len(rows)
        n_iss = len(issuers)

        pv_np = pv.to_numpy(dtype=float, copy=False)
        hsbc_idx = issuers.index("HSBC") if "HSBC" in issuers else None

        view_rows: list[list[str]] = []

        for r_i in range(n_rows):
            g = rows[r_i]
            vals = pv_np[r_i]
            order = np.argsort(-vals)  # ranking ALWAYS by absolute values

            hsbc_pos = None
            if hsbc_idx is not None:
                hsbc_pos = int(np.where(order == hsbc_idx)[0][0]) + 1

            group_raw = str(g)
            group_label = group_raw
            if hsbc_pos is not None:
                if hsbc_pos == 1:
                    self._cell_bg[(r_i, 0)] = self.GROUP_GREEN
                    group_label = "🟢 " + group_raw
                elif 2 <= hsbc_pos <= 5:
                    self._cell_bg[(r_i, 0)] = self.GROUP_YELLOW
                    group_label = "🟡 " + group_raw
                else:
                    self._cell_bg[(r_i, 0)] = self.GROUP_RED
                    group_label = "🔴 " + group_raw

            rank_texts = [""] * n_iss

            if not is_pro_zeile:
                for k, j in enumerate(order):
                    issuer = issuers[j]
                    txt = f"{issuer}: {self._fmt_abs_compact_int_commas(float(vals[j]))}"
                    if issuer == "HSBC":
                        self._cell_bg[(r_i, 1 + k)] = self.HSBC_RED
                        txt = "🏦 " + txt
                    rank_texts[k] = txt
            else:
                row_pct = pv_pct.iloc[r_i].to_numpy(dtype=float, copy=False)  # type: ignore[union-attr]
                for k, j in enumerate(order):
                    issuer = issuers[j]
                    txt = f"{issuer}: {self._fmt_pct_1d(float(row_pct[j]))}"
                    if issuer == "HSBC":
                        self._cell_bg[(r_i, 1 + k)] = self.HSBC_RED
                        txt = "🏦 " + txt
                    rank_texts[k] = txt

            all_val = float(row_sum.iloc[r_i])
            view_rows.append([group_label] + rank_texts + [self._fmt_abs_compact_int_commas(all_val)])

        # 🏁 ALL row
        col_tot = pv.sum(axis=0).to_numpy(dtype=float, copy=False)
        grand_total = float(col_tot.sum())
        global_order = np.argsort(-col_tot)

        rank_texts = [""] * n_iss
        if not is_pro_zeile:
            for k, j in enumerate(global_order):
                issuer = issuers[j]
                txt = f"{issuer}: {self._fmt_abs_compact_int_commas(float(col_tot[j]))}"
                if issuer == "HSBC":
                    txt = "🏦 " + txt
                rank_texts[k] = txt
        else:
            total_market = grand_total if grand_total != 0 else 1.0
            for k, j in enumerate(global_order):
                issuer = issuers[j]
                txt = f"{issuer}: {self._fmt_pct_1d(100.0 * float(col_tot[j]) / total_market)}"
                if issuer == "HSBC":
                    txt = "🏦 " + txt
                rank_texts[k] = txt

        view_rows.append(["🏁 ALL"] + rank_texts + [self._fmt_abs_compact_int_commas(grand_total)])

        self._view_df = pd.DataFrame(view_rows, columns=self._cols)

    # ---------------- Fast auto-width (minimal, no cut) ----------------
    def _compute_auto_widths_fast(self):
        """
        Compute minimal widths without measuring every cell.
        Strategy:
          - GROUP width from max len of group strings (vectorized)
          - Rank widths from longest issuer name + fixed numeric tail
          - ALL width from worst-case numeric string
        """
        if self._view_df.empty:
            return

        n_iss = len(self._issuers)
        # GROUP max length (use raw groups without emoji prefix for estimate)
        group_series = self._view_df["GROUP"].astype(str)
        # remove semaphore emojis if present (cheap)
        group_clean = group_series.str.replace("🟢 ", "", regex=False).str.replace("🟡 ", "", regex=False).str.replace("🔴 ", "", regex=False)
        max_group_len = int(group_clean.str.len().max() or 0)

        # Rank: longest issuer name drives width
        max_issuer_len = max((len(x) for x in self._issuers), default=0)

        # numeric tail length:
        # ABS: ": 999,999M" -> 10 chars incl space, %, k/M vary; add some headroom
        # PRO_ZEILE: ": 100.0%" -> 8 chars
        if self._mode.get() == "PRO_ZEILE":
            tail = len(": 100.0%")
        else:
            tail = len(": 999,999M")

        # plus possible "🏦 " prefix
        tail += len("🏦 ")

        # Convert to px with char_px estimate + padding
        group_w = max_group_len * self._char_px + (self.PAD_X * 2) + 18
        rank_w = (max_issuer_len + tail) * self._char_px + (self.PAD_X * 2) + 18

        # ALL: estimate from max formatted ALL
        all_series = self._view_df["ALL"].astype(str)
        max_all_len = int(all_series.str.len().max() or 0)
        all_w = max_all_len * self._char_px + (self.PAD_X * 2) + 18

        # clamp
        group_w = int(min(self.MAX_GROUP_W, max(self.MIN_GROUP_W, group_w)))
        rank_w = int(min(self.MAX_RANK_W, max(self.MIN_RANK_W, rank_w)))
        all_w = int(min(self.MAX_ALL_W, max(self.MIN_ALL_W, all_w)))

        self._col_widths = [group_w] + [rank_w] * n_iss + [all_w]
        self._col_x = self._compute_col_x(self._col_widths)

    @staticmethod
    def _compute_col_x(widths: list[int]) -> list[int]:
        x = [0]
        s = 0
        for w in widths:
            s += int(w)
            x.append(s)
        return x

    # ---------------- Scroll / virtual rendering ----------------
    def _on_vscroll(self, *args):
        self._canvas.yview(*args)
        self._redraw()

    def _on_hscroll(self, *args):
        self._canvas.xview(*args)
        self._redraw()

    def _on_resize(self):
        # no heavy work here; just redraw viewport
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

    def _redraw(self):
        self._canvas.delete("all")

        if self._status_msg is not None:
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

        if self._view_df.empty or not self._cols or not self._col_x:
            return

        total_h = self.HEADER_H + len(self._view_df) * self.ROW_H
        r0, r1 = self._visible_row_range()
        c0, c1 = self._visible_col_range()

        vx0 = self._col_x[c0]
        vx1 = self._col_x[c1 + 1]

        # Header
        self._canvas.create_rectangle(vx0, 0, vx1, self.HEADER_H, fill=self.HEADER_BG, outline=self.HEADER_BG)
        self._canvas.create_rectangle(vx0, self.HEADER_H - 3, vx1, self.HEADER_H, fill=self.HEADER_ACCENT, outline=self.HEADER_ACCENT)

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

            self._canvas.create_text(
                tx, self.HEADER_H / 2 - 1,
                text=col, fill=self.HEADER_FG, font=self._font_head, anchor=anchor
            )
            self._canvas.create_line(x_right, 0, x_right, self.HEADER_H, fill="#111827", width=1)

        # Body
        for ri in range(r0, r1 + 1):
            y0 = self.HEADER_H + ri * self.ROW_H
            y1 = y0 + self.ROW_H

            is_all = str(self._view_df.iloc[ri]["GROUP"]).startswith("🏁")
            base_bg = self.ALL_ROW_BG if is_all else (self.ROW_EVEN if (ri % 2 == 0) else self.ROW_ODD)

            for ci in range(c0, c1 + 1):
                x_left = self._col_x[ci]
                x_right = self._col_x[ci + 1]
                cw = x_right - x_left

                bg = self._cell_bg.get((ri, ci), base_bg)
                self._canvas.create_rectangle(x_left, y0, x_right, y1, fill=bg, outline=self.GRID)

                val = str(self._view_df.iat[ri, ci])

                if self._cols[ci] == "GROUP":
                    anchor = "w"
                    tx = x_left + self.PAD_X
                else:
                    anchor = "center"
                    tx = x_left + cw / 2

                self._canvas.create_text(
                    tx, (y0 + y1) / 2,
                    text=val,
                    fill=self.ALL_ROW_FG if is_all else self.TEXT,
                    font=self._font_body_bold if is_all else self._font_body,
                    anchor=anchor
                )

        # Separators after 1° and 5°
        def col_index(name: str):
            try:
                return self._cols.index(name)
            except ValueError:
                return None

        i1 = col_index("1°")
        if i1 is not None and c0 <= i1 <= c1:
            xx = self._col_x[i1 + 1]
            self._canvas.create_line(xx, 0, xx, total_h, fill=self.SEP_BLACK, width=2)

        i5 = col_index("5°")
        if i5 is not None and c0 <= i5 <= c1:
            xx = self._col_x[i5 + 1]
            self._canvas.create_line(xx, 0, xx, total_h, fill=self.SEP_BLACK, width=2)

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

    # ---------------- Copy Excel-ready ----------------
    def _copy_excel_ready(self, event=None):
        if self._view_df.empty:
            try:
                if event is None:
                    messagebox.showinfo("Copy", "No data to copy.")
            except Exception:
                pass
            return "break"

        cols = self._cols
        lines = ["\t".join(cols)]
        for r in range(len(self._view_df)):
            row = [str(self._view_df.iat[r, c]) for c in range(len(cols))]
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

    # ---------------- Create HTML report ----------------
    def _create_html_report(self):
        if self._view_df.empty:
            messagebox.showinfo("Create HTML", "No data for report.")
            return

        try:
            reports_dir = os.path.abspath(os.path.join(os.getcwd(), "reports"))
            os.makedirs(reports_dir, exist_ok=True)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"ranking_{ts}.html"
            fpath = os.path.join(reports_dir, fname)

            title = self._title_str

            df = self._view_df
            cols = self._cols

            def bg_for_cell(r, c):
                bg = self._cell_bg.get((r, c))
                if bg:
                    return bg
                if str(df.iat[r, 0]).startswith("🏁"):
                    return self.ALL_ROW_BG
                return self.ROW_EVEN if (r % 2 == 0) else self.ROW_ODD

            head_html = "".join([f"<th>{c}</th>" for c in cols])

            body_rows = []
            for r in range(len(df)):
                tds = []
                for c_i, c in enumerate(cols):
                    bg = bg_for_cell(r, c_i)
                    align = "left" if c == "GROUP" else "center"
                    extra = " sep-right" if c in ("1°", "5°") else ""
                    tds.append(
                        f"<td class='{extra}' style='background:{bg}; text-align:{align};'>{df.iat[r, c_i]}</td>"
                    )
                body_rows.append("<tr>" + "".join(tds) + "</tr>")
            body_html = "\n".join(body_rows)

            # MOBILE FRIENDLY: wrap with horizontal scroll
            html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ranking</title>
<style>
  body {{
    font-family: Segoe UI, Arial, sans-serif;
    margin: 18px;
    color: #0b1220;
    background: #ffffff;
  }}
  .hero {{
    display:flex; align-items:flex-end; justify-content:space-between;
    margin-bottom: 12px;
    gap: 12px;
    flex-wrap: wrap;
  }}
  h1 {{
    margin: 10px 0 0 0;
    font-size: 20px;
  }}
  .sub {{
    margin-top: 4px;
    color:#475569;
    font-size: 12px;
  }}

  .table-wrap {{
    overflow-x: auto;
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
  thead th:first-child {{ text-align:left; }}
  thead tr {{ border-bottom: 3px solid #2563eb; }}
  tbody td {{
    border: 1px solid #e2e8f0;
    padding: 10px 10px;
    font-size: 13px;
  }}
  .sep-right {{ border-right: 2px solid #000000 !important; }}
</style>
</head>
<body>
    <div class="hero">
      <div>
        <h1>{title}</h1>
        <div class="sub">Semaphore: 🟢 #1 · 🟡 #2–#5 · 🔴 &gt;#5 · ALL always absolute</div>
      </div>
    </div>

  <div class="table-wrap">
    <table>
      <thead><tr>{head_html}</tr></thead>
      <tbody>
        {body_html}
      </tbody>
    </table>
  </div>
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
