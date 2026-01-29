# ui/martin_style_sheet.py
from __future__ import annotations

import os
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.font as tkfont

import pandas as pd
import numpy as np


class MartinStyleSheet(ttk.Frame):
    """
    Martin (Canvas-based, cell-level styling, CEO-ready).

    - Groupby selector (UND_NAME / CALL_OPTION / UND_TYPE / TYPE)
    - Mode: ABSOLUT or PRO_ZEILE_% (row-normalized)
    - Column ALL ALWAYS absolute
    - Columns: GROUP, 1°, 2°, ..., N°, ALL
    - Rank cells show "ISSUER: value"
    - Sorting by clicking header (numeric sort for ranks/ALL, lexicographic for GROUP)
    - Vertical separators after 1° and after 5°
    - HSBC:
        * HSBC cell ALWAYS light red (wherever HSBC appears in the Top-N).
    - NEW: Semaphore on GROUP based on HSBC absolute rank (best=1):
        * rank == 1 -> GROUP cell green + 🟢
        * rank 2..5 -> GROUP cell yellow + 🟡
        * rank > 5 -> GROUP cell red + 🔴
        * if HSBC not present in columns -> no semaphore icon/color
    - ALL row label: 🏁 ALL
    - Formatting:
        * ABS: integer compact with commas + suffix: 999 / 111,111k / 12,345M
        * %: 1 decimal: 1.1%
    - Alignment:
        * GROUP left
        * others centered
    - Buttons:
        * Copy (Excel): TSV clipboard
        * Create HTML: writes report to ./reports and copies file:// path
    """

    GROUP_FIELDS = ("UND_NAME", "CALL_OPTION", "UND_TYPE", "TYPE")
    MODES = ("ABSOLUT", "PRO_ZEILE_%")

    def __init__(self, master=None, top_n: int = 6):
        super().__init__(master)

        self._df: pd.DataFrame | None = None
        self._pivot_abs: pd.DataFrame = pd.DataFrame()

        # UI state
        self._group_by = tk.StringVar(value="UND_NAME")
        self._mode = tk.StringVar(value="ABSOLUT")
        self._top_n = tk.IntVar(value=int(top_n))

        # Render data
        self._view_df: pd.DataFrame = pd.DataFrame()  # display strings
        self._sort_df: pd.DataFrame = pd.DataFrame()  # numeric sort data (for proper sorting)
        self._cell_bg: dict[tuple[int, str], str] = {}  # (row_idx, col_name) -> color
        self._sort_state: dict[str, bool | None] = {}  # col -> asc?

        # Layout
        self._cols: list[str] = []
        self._col_widths: dict[str, int] = {}

        # Canvas geometry
        self._header_h = 48
        self._row_h = 36
        self._pad_x = 12

        # Fonts
        self._font_body = tkfont.Font(family="Segoe UI", size=11)
        self._font_body_bold = tkfont.Font(family="Segoe UI Semibold", size=11)
        self._font_head = tkfont.Font(family="Segoe UI Semibold", size=11)
        self._font_title = tkfont.Font(family="Segoe UI Semibold", size=16)

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

        # Semaphore for GROUP
        self.GROUP_GREEN = "#dcfce7"   # light green
        self.GROUP_YELLOW = "#fef9c3"  # light yellow
        self.GROUP_RED = "#ffe4e6"     # light red/pink

        # Buttons
        self.BTN_BG = "#2563eb"
        self.BTN_FG = "#ffffff"
        self.BTN_BG2 = "#0ea5e9"

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

        # Title block
        title_wrap = ttk.Frame(top, style="MartinTop.TFrame")
        title_wrap.grid(row=0, column=0, rowspan=2, sticky="w")

        ttk.Label(title_wrap, text="Martin", style="MartinTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            title_wrap,
            text="⚡ Executive Snapshot · Top issuers per group · Zero noise",
            style="MartinHint.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Controls + actions
        ctr = ttk.Frame(top, style="MartinTop.TFrame")
        ctr.grid(row=0, column=2, rowspan=2, sticky="e")

        ttk.Label(ctr, text="Gruppieren:", style="MartinHint.TLabel").grid(row=0, column=0, padx=(0, 6))
        cb_group = ttk.Combobox(ctr, values=self.GROUP_FIELDS, textvariable=self._group_by,
                                state="readonly", width=14)
        cb_group.grid(row=0, column=1)
        cb_group.bind("<<ComboboxSelected>>", lambda e: self._rebuild_and_refresh())

        ttk.Label(ctr, text="Ansicht:", style="MartinHint.TLabel").grid(row=0, column=2, padx=(12, 6))
        cb_mode = ttk.Combobox(ctr, values=self.MODES, textvariable=self._mode,
                               state="readonly", width=12)
        cb_mode.grid(row=0, column=3)
        cb_mode.bind("<<ComboboxSelected>>", lambda e: self._refresh())

        ttk.Label(ctr, text="Top:", style="MartinHint.TLabel").grid(row=0, column=4, padx=(12, 6))
        sp_top = ttk.Spinbox(ctr, from_=3, to=12, increment=1, textvariable=self._top_n, width=4,
                             command=self._refresh)
        sp_top.grid(row=0, column=5)

        # Buttons row
        btns = ttk.Frame(ctr, style="MartinTop.TFrame")
        btns.grid(row=1, column=0, columnspan=6, sticky="e", pady=(10, 0))

        self.btn_copy = tk.Button(
            btns, text="Copy (Excel)", command=self._copy_excel_ready,
            bg=self.BTN_BG, fg=self.BTN_FG, activebackground="#1d4ed8",
            relief="flat", padx=12, pady=6, cursor="hand2"
        )
        self.btn_copy.pack(side="left", padx=(0, 8))

        self.btn_html = tk.Button(
            btns, text="Create HTML", command=self._create_html_report,
            bg=self.BTN_BG2, fg=self.BTN_FG, activebackground="#0284c7",
            relief="flat", padx=12, pady=6, cursor="hand2"
        )
        self.btn_html.pack(side="left")

        # Body with scrollbars
        body = ttk.Frame(self, style="Martin.TFrame")
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(body, bg=self.WHITE, highlightthickness=0, bd=0)
        self._vsb = ttk.Scrollbar(body, orient="vertical", command=self._canvas.yview)
        self._hsb = ttk.Scrollbar(body, orient="horizontal", command=self._canvas.xview)
        self._canvas.configure(yscrollcommand=self._vsb.set, xscrollcommand=self._hsb.set)

        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._vsb.grid(row=0, column=1, sticky="ns")
        self._hsb.grid(row=1, column=0, sticky="ew")

        self._canvas.bind("<Configure>", lambda e: self._redraw())
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind_all("<Shift-MouseWheel>", self._on_shift_mousewheel)
        self._canvas.bind_all("<Button-4>", self._on_mousewheel)  # Linux
        self._canvas.bind_all("<Button-5>", self._on_mousewheel)

        # Click to sort (header hit test)
        self._canvas.bind("<Button-1>", self._on_click)

        # Ctrl+C = copy (Excel)
        self._canvas.bind_all("<Control-c>", self._copy_excel_ready)
        self._canvas.bind_all("<Command-c>", self._copy_excel_ready)

        self._set_columns()

    # ---------------- Public API ----------------
    def update_view(self, df: pd.DataFrame):
        self._df = df
        self._rebuild_and_refresh()

    # ---------------- Data build ----------------
    def _rebuild_and_refresh(self):
        self._prepare_pivot_abs()
        self._refresh()

    def _prepare_pivot_abs(self):
        self._pivot_abs = pd.DataFrame()
        if self._df is None or self._df.empty:
            return

        s = self._df.copy()
        grp = self._group_by.get()
        idx_col = self._resolve_index_column(s, grp)

        if "ISSUER_NAME" not in s.columns or "TXN_AMT" not in s.columns:
            return

        pv = pd.pivot_table(
            s,
            index=idx_col,
            columns="ISSUER_NAME",
            values="TXN_AMT",
            aggfunc="sum",
            fill_value=0.0,
            observed=False,
        )

        pv = pv.reindex(sorted(pv.columns), axis=1)
        pv = pv.loc[pv.sum(axis=1).sort_values(ascending=False).index]

        pv.index.name = "GROUP"
        pv.columns.name = None

        self._pivot_abs = pv

    def _resolve_index_column(self, df: pd.DataFrame, grp: str) -> str:
        if grp != "UND_NAME":
            if grp not in df.columns:
                df[grp] = f"({grp} fehlt)"
            return grp

        if "UND_NAME" in df.columns:
            return "UND_NAME"
        if "NAME" in df.columns:
            df["UND_NAME_FALLBACK"] = df["NAME"]
            return "UND_NAME_FALLBACK"

        df["UND_NAME_SYN"] = "(UND_NAME fehlt)"
        return "UND_NAME_SYN"

    # ---------------- Columns ----------------
    def _set_columns(self):
        top_n = int(self._top_n.get())
        self._cols = ["GROUP"] + [f"{i}°" for i in range(1, top_n + 1)] + ["ALL"]

    # ---------------- Formatting ----------------
    @staticmethod
    def _fmt_int_commas(n: int) -> str:
        return f"{n:,}"

    def _fmt_abs_compact_int_commas(self, x: float) -> str:
        """
        Compact integer with commas BEFORE suffix:
          < 1,000       -> 999
          >= 1,000      -> 111,111k  (rounded to nearest thousand)
          >= 1,000,000  -> 12,345M   (rounded to nearest million)
        """
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

    # ---------------- Compute view + cell colors ----------------
    def _compute_rank_tables(self):
        self._view_df = pd.DataFrame()
        self._sort_df = pd.DataFrame()
        self._cell_bg.clear()

        if self._pivot_abs.empty:
            return

        self._set_columns()
        top_n = int(self._top_n.get())
        mode = self._mode.get()

        pv = self._pivot_abs.copy()
        issuers = pv.columns.to_list()

        row_tot = pv.sum(axis=1).replace(0, np.nan)
        all_abs = pv.sum(axis=1).fillna(0.0)

        pv_pct = None
        if mode == "PRO_ZEILE_%":
            pv_pct = (pv.div(row_tot, axis=0).fillna(0.0) * 100.0)

        view_rows = []
        sort_rows = []

        for r_i, g in enumerate(pv.index.to_list()):
            vals = pv.loc[g].values.astype(float)

            # ranking by absolute
            order = np.argsort(-vals)  # desc
            top_idx = order[:top_n]

            # HSBC absolute rank (1-based)
            hsbc_pos = None
            if "HSBC" in issuers:
                hsbc_idx = issuers.index("HSBC")
                hsbc_pos = int(np.where(order == hsbc_idx)[0][0]) + 1

            # Semaphore for GROUP
            group_label_raw = str(g)
            group_label = group_label_raw
            if hsbc_pos is not None:
                if hsbc_pos == 1:
                    self._cell_bg[(r_i, "GROUP")] = self.GROUP_GREEN
                    group_label = "🟢 " + group_label_raw
                elif 2 <= hsbc_pos <= 5:
                    self._cell_bg[(r_i, "GROUP")] = self.GROUP_YELLOW
                    group_label = "🟡 " + group_label_raw
                else:
                    self._cell_bg[(r_i, "GROUP")] = self.GROUP_RED
                    group_label = "🔴 " + group_label_raw

            rank_texts = []
            rank_nums = []

            for k, j in enumerate(top_idx, start=1):
                issuer = issuers[j]
                v_abs = float(vals[j])
                rank_nums.append(v_abs)

                col_name = f"{k}°"
                if mode == "ABSOLUT":
                    txt = f"{issuer}: {self._fmt_abs_compact_int_commas(v_abs)}"
                else:
                    v_pct = float(pv_pct.loc[g, issuer]) if pv_pct is not None else 0.0
                    txt = f"{issuer}: {self._fmt_pct_1d(v_pct)}"

                # HSBC cell ALWAYS red if it appears
                if issuer == "HSBC":
                    self._cell_bg[(r_i, col_name)] = self.HSBC_RED
                    # optional: tiny icon for clarity (looks great)
                    txt = "🏦 " + txt

                rank_texts.append(txt)

            while len(rank_texts) < top_n:
                rank_texts.append("")
                rank_nums.append(0.0)

            all_val = float(all_abs.loc[g])

            # view row uses decorated GROUP label; sort row uses raw GROUP label for correct sorting
            view_row = [group_label] + rank_texts + [self._fmt_abs_compact_int_commas(all_val)]
            sort_row = [group_label_raw] + rank_nums + [all_val]

            view_rows.append(view_row)
            sort_rows.append(sort_row)

        self._view_df = pd.DataFrame(view_rows, columns=self._cols)
        self._sort_df = pd.DataFrame(sort_rows, columns=self._cols)

        # Add ALL row (global totals)
        col_tot = pv.sum(axis=0).values.astype(float)
        total_market = float(col_tot.sum()) if float(col_tot.sum()) != 0 else 1.0
        global_order = np.argsort(-col_tot)
        top_idx = global_order[:top_n]

        rank_texts = []
        rank_nums = []
        for k, j in enumerate(top_idx, start=1):
            issuer = issuers[j]
            v_abs = float(col_tot[j])
            rank_nums.append(v_abs)
            if mode == "ABSOLUT":
                txt = f"{issuer}: {self._fmt_abs_compact_int_commas(v_abs)}"
            else:
                txt = f"{issuer}: {self._fmt_pct_1d(100.0 * v_abs / total_market)}"
            if issuer == "HSBC":
                txt = "🏦 " + txt
            rank_texts.append(txt)

        while len(rank_texts) < top_n:
            rank_texts.append("")
            rank_nums.append(0.0)

        grand_total = float(col_tot.sum())

        # 🏁 ALL in view; raw "ALL" in sort
        self._view_df.loc[len(self._view_df)] = ["🏁 ALL"] + rank_texts + [self._fmt_abs_compact_int_commas(grand_total)]
        self._sort_df.loc[len(self._sort_df)] = ["ALL"] + rank_nums + [grand_total]

    # ---------------- Sorting ----------------
    def _sort_by(self, col: str):
        if self._sort_df.empty:
            return
        asc = self._sort_state.get(col, None)
        asc = True if asc is None else (not asc)
        self._sort_state[col] = asc

        df_sort = self._sort_df.copy()
        df_view = self._view_df.copy()

        if col == "GROUP":
            # Sort by RAW group values (no icons)
            key = df_sort["GROUP"].astype(str)
            order = key.argsort(kind="mergesort")
            if not asc:
                order = order[::-1]
        else:
            key = pd.to_numeric(df_sort[col], errors="coerce").fillna(-np.inf)
            order = key.argsort(kind="mergesort")
            if not asc:
                order = order[::-1]

        self._sort_df = df_sort.iloc[order].reset_index(drop=True)
        self._view_df = df_view.iloc[order].reset_index(drop=True)

        # IMPORTANT: we must reorder highlights too (row indices changed).
        # Cheapest robust approach: rebuild everything from scratch (still fast for CEO-view).
        self._compute_rank_tables()

        # After rebuild, apply the same sort direction again (without toggling)
        # to keep visual consistent with user click.
        # (This is OK: table sizes are moderate; correctness > micro-optimizations.)
        self._apply_sort_no_toggle(col, asc)

    def _apply_sort_no_toggle(self, col: str, asc: bool):
        df_sort = self._sort_df.copy()
        df_view = self._view_df.copy()

        if col == "GROUP":
            key = df_sort["GROUP"].astype(str)
            order = key.argsort(kind="mergesort")
            if not asc:
                order = order[::-1]
        else:
            key = pd.to_numeric(df_sort[col], errors="coerce").fillna(-np.inf)
            order = key.argsort(kind="mergesort")
            if not asc:
                order = order[::-1]

        self._sort_df = df_sort.iloc[order].reset_index(drop=True)
        self._view_df = df_view.iloc[order].reset_index(drop=True)

        # Rebuild highlights by scanning the view:
        # - GROUP semaphore based on icon prefix is already baked in view,
        #   but we need bg colors + HSBC cell red.
        # We'll rebuild from view strings for stability.
        self._rebuild_highlights_from_view()

    def _rebuild_highlights_from_view(self):
        """Recreate cell highlights from current visible view (keeps row order)."""
        self._cell_bg.clear()
        top_n = int(self._top_n.get())

        for r in range(len(self._view_df)):
            grp = str(self._view_df.loc[r, "GROUP"])

            # GROUP semaphore background based on icon prefix
            if grp.startswith("🟢"):
                self._cell_bg[(r, "GROUP")] = self.GROUP_GREEN
            elif grp.startswith("🟡"):
                self._cell_bg[(r, "GROUP")] = self.GROUP_YELLOW
            elif grp.startswith("🔴"):
                self._cell_bg[(r, "GROUP")] = self.GROUP_RED

            # HSBC cell background if present in ranks
            for k in range(1, top_n + 1):
                coln = f"{k}°"
                txt = str(self._view_df.loc[r, coln])
                if "HSBC:" in txt:
                    self._cell_bg[(r, coln)] = self.HSBC_RED

    # ---------------- AutoWidth ----------------
    def _compute_autowidths(self, canvas_width: int) -> dict[str, int]:
        # caps & mins
        MIN_GROUP = 220
        MAX_GROUP = 520

        MIN_RANK = 220
        MAX_RANK = 560

        MIN_ALL = 120
        MAX_ALL = 200

        pad = self._pad_x * 2 + 22
        widths = {}

        for c in self._cols:
            widths[c] = self._font_head.measure(c) + pad

        if not self._view_df.empty:
            for c in self._cols:
                mx = widths[c]
                for v in self._view_df[c].astype(str).tolist():
                    mx = max(mx, self._font_body.measure(v) + pad)
                widths[c] = mx

        for c in self._cols:
            if c == "GROUP":
                widths[c] = int(min(MAX_GROUP, max(MIN_GROUP, widths[c])))
            elif c == "ALL":
                widths[c] = int(min(MAX_ALL, max(MIN_ALL, widths[c])))
            else:
                widths[c] = int(min(MAX_RANK, max(MIN_RANK, widths[c])))

        total = sum(widths.values())
        if canvas_width > 0 and total < canvas_width:
            extra = canvas_width - total
            rank_cols = [c for c in self._cols if c not in ("GROUP", "ALL")]
            buckets = rank_cols + ["GROUP"]
            if buckets:
                per = extra // len(buckets)
                for c in buckets:
                    widths[c] += per
                widths["GROUP"] += (extra - per * len(buckets))

            # enforce caps again
            for c in self._cols:
                if c == "GROUP":
                    widths[c] = int(min(MAX_GROUP, widths[c]))
                elif c == "ALL":
                    widths[c] = int(min(MAX_ALL, widths[c]))
                else:
                    widths[c] = int(min(MAX_RANK, widths[c]))

        return widths

    # ---------------- Render ----------------
    def _refresh(self):
        self._compute_rank_tables()
        self._redraw()

    def _redraw(self):
        self._canvas.delete("all")
        self._set_columns()

        canvas_w = int(self._canvas.winfo_width() or 900)
        self._col_widths = self._compute_autowidths(canvas_w)

        n_rows = 0 if self._view_df.empty else len(self._view_df)
        total_h = self._header_h + n_rows * self._row_h
        total_w = sum(self._col_widths[c] for c in self._cols)

        # Header base + accent
        self._canvas.create_rectangle(0, 0, total_w, self._header_h, fill=self.HEADER_BG, outline=self.HEADER_BG)
        self._canvas.create_rectangle(0, self._header_h - 3, total_w, self._header_h,
                                      fill=self.HEADER_ACCENT, outline=self.HEADER_ACCENT)

        # Header labels
        x = 0
        for col in self._cols:
            cw = self._col_widths[col]

            txt = col
            if col in self._sort_state and self._sort_state[col] is not None:
                txt = f"{col} {'▲' if self._sort_state[col] else '▼'}"

            if col == "GROUP":
                anchor = "w"
                tx = x + self._pad_x
            else:
                anchor = "center"
                tx = x + cw / 2

            self._canvas.create_text(tx, self._header_h / 2 - 1, text=txt,
                                     fill=self.HEADER_FG, font=self._font_head, anchor=anchor)

            self._canvas.create_line(x + cw, 0, x + cw, self._header_h, fill="#111827", width=1)
            x += cw

        # Body
        if not self._view_df.empty:
            for r in range(n_rows):
                y0 = self._header_h + r * self._row_h
                y1 = y0 + self._row_h

                is_all_row = str(self._view_df.iloc[r]["GROUP"]).startswith("🏁")
                base_bg = self.ALL_ROW_BG if is_all_row else (self.ROW_EVEN if (r % 2 == 0) else self.ROW_ODD)

                x = 0
                for col in self._cols:
                    cw = self._col_widths[col]
                    bg = self._cell_bg.get((r, col), base_bg)

                    self._canvas.create_rectangle(x, y0, x + cw, y1, fill=bg, outline=self.GRID)

                    val = str(self._view_df.iloc[r][col])

                    if col == "GROUP":
                        anchor = "w"
                        tx = x + self._pad_x
                    else:
                        anchor = "center"
                        tx = x + cw / 2

                    self._canvas.create_text(
                        tx, (y0 + y1) / 2,
                        text=val,
                        fill=self.ALL_ROW_FG if is_all_row else self.TEXT,
                        font=self._font_body_bold if is_all_row else self._font_body,
                        anchor=anchor
                    )
                    x += cw

        # separators after 1° and 5°
        def x_after(col_name: str) -> int | None:
            if col_name not in self._cols:
                return None
            xx = 0
            for c in self._cols:
                xx += self._col_widths[c]
                if c == col_name:
                    return xx
            return None

        x1 = x_after("1°")
        if x1 is not None:
            self._canvas.create_line(x1, 0, x1, total_h, fill=self.SEP_BLACK, width=2)

        x5 = x_after("5°")
        if x5 is not None:
            self._canvas.create_line(x5, 0, x5, total_h, fill=self.SEP_BLACK, width=2)

        self._canvas.configure(scrollregion=(0, 0, total_w, total_h))

    # ---------------- Events ----------------
    def _on_mousewheel(self, event):
        if getattr(event, "delta", 0) != 0:
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        else:
            if event.num == 5:
                self._canvas.yview_scroll(1, "units")
            elif event.num == 4:
                self._canvas.yview_scroll(-1, "units")
        return "break"

    def _on_shift_mousewheel(self, event):
        if getattr(event, "delta", 0) != 0:
            self._canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
        else:
            if event.num == 5:
                self._canvas.xview_scroll(1, "units")
            elif event.num == 4:
                self._canvas.xview_scroll(-1, "units")
        return "break"

    def _on_click(self, event):
        # Sort only if click is within header row
        y = self._canvas.canvasy(event.y)
        x = self._canvas.canvasx(event.x)
        if y > self._header_h:
            return

        acc = 0
        clicked = None
        for col in self._cols:
            acc_next = acc + self._col_widths.get(col, 200)
            if acc <= x < acc_next:
                clicked = col
                break
            acc = acc_next

        if clicked:
            self._sort_by(clicked)
            self._redraw()

    # ---------------- Copy Excel-ready ----------------
    def _copy_excel_ready(self, event=None):
        if self._view_df.empty:
            try:
                messagebox.showinfo("Copy", "No data to copy.")
            except Exception:
                pass
            return "break"

        cols = self._cols
        lines = ["\t".join(cols)]
        for r in range(len(self._view_df)):
            row = [str(self._view_df.iloc[r][c]) for c in cols]
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
            fname = f"martin_{self._group_by.get()}_{self._mode.get()}_{ts}.html"
            fpath = os.path.join(reports_dir, fname)

            title = f"Martin – Executive Snapshot ({self._group_by.get()} · {self._mode.get()})"

            df = self._view_df.copy()
            cols = self._cols

            def bg_for_cell(r, c):
                bg = self._cell_bg.get((r, c))
                if bg:
                    return bg
                if str(df.iloc[r]["GROUP"]).startswith("🏁"):
                    return self.ALL_ROW_BG
                # zebra
                return self.ROW_EVEN if (r % 2 == 0) else self.ROW_ODD

            # build table
            head_html = "".join([f"<th>{c}</th>" for c in cols])

            body_rows = []
            for r in range(len(df)):
                tds = []
                for c in cols:
                    bg = bg_for_cell(r, c)
                    align = "left" if c == "GROUP" else "center"
                    extra = ""
                    # separators after 1° and after 5°
                    if c in ("1°", "5°"):
                        extra = " sep-right"
                    tds.append(
                        f"<td class='{extra}' style='background:{bg}; text-align:{align};'>{df.iloc[r][c]}</td>"
                    )
                body_rows.append("<tr>" + "".join(tds) + "</tr>")
            body_html = "\n".join(body_rows)

            html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{
    font-family: Segoe UI, Arial, sans-serif;
    margin: 22px;
    color: #0b1220;
    background: #ffffff;
  }}
  .hero {{
    display:flex; align-items:flex-end; justify-content:space-between;
    margin-bottom: 14px;
  }}
  .chip {{
    display:inline-block;
    padding: 7px 12px;
    border-radius: 999px;
    background: #0b1220;
    color: white;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: .2px;
  }}
  h1 {{
    margin: 10px 0 0 0;
    font-size: 22px;
  }}
  .meta {{
    color:#475569;
    font-size: 12px;
    text-align:right;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 10px 28px rgba(2,6,23,0.10);
  }}
  thead th {{
    background: #0b1220;
    color: white;
    text-align: center;
    padding: 12px 10px;
    font-weight: 800;
    font-size: 13px;
    border-right: 1px solid #111827;
  }}
  thead th:first-child {{
    text-align:left;
  }}
  thead tr {{
    border-bottom: 3px solid #2563eb;
  }}
  tbody td {{
    border: 1px solid #e2e8f0;
    padding: 10px 10px;
    font-size: 13px;
  }}
  .sep-right {{
    border-right: 2px solid #000000 !important;
  }}
</style>
</head>
<body>
  <div class="hero">
    <div>
      <div class="chip">Martin</div>
      <h1>{title}</h1>
    </div>
    <div class="meta">
      Generated: {ts}<br>
      Semaphore: 🟢 #1 · 🟡 #2–#5 · 🔴 &gt;#5<br>
      ALL is always absolute
    </div>
  </div>

  <table>
    <thead><tr>{head_html}</tr></thead>
    <tbody>
      {body_html}
    </tbody>
  </table>
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
