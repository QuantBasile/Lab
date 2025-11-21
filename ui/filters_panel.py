# ui/filters_panel.py
"""
FiltersPanel – dynamic filter cards for a dashboard.

Features:
- Categorical columns:
    * Black chip style
    * Symmetric dual-list (available / selected)
    * Search box (case-insensitive)
- Numeric columns:
    * Blue card
    * Min / Max inputs
    * Clear button
- Date columns:
    * Green card
    * From / To date using SimpleDateEntry
    * Clear button

Layout:
- All inner content on white background (no gray panels).
- Subtle shadow behind each card.
- Vertical + horizontal scroll.
"""

import tkinter as tk
from tkinter import ttk
import tkinter.font as tkFont
import math
import pandas as pd
from pandas.api.types import is_numeric_dtype, is_bool_dtype

from ui.simple_calendar import SimpleDateEntry as DateEntry
HAS_TKCAL = True  # we always have our own calendar


class FiltersPanel(ttk.Frame):
    """
    Filters panel with cards:

    - Categorical → black border, dual list, search
    - Numeric     → blue border, min/max, clear
    - Date        → green border, from/to, clear

    Public API:
        build(df: pd.DataFrame)
        get_filters() -> dict
        reset()
    """

    # Layout
    PADX = 12
    PADY = 12
    ROWS = 3

    # Compact heights per card type
    CARD_H_CATEG = 160
    CARD_H_NUM = 100
    CARD_H_DATE = 110

    # Max width of a column (pixels)
    COL_WIDTH_MAX = 560

    # Shadow
    SHADOW_OFFSET = 2
    SHADOW_COLOR = "#e9efff"

    # Listbox width range (characters)
    MIN_LIST_CHARS = 1
    MAX_LIST_CHARS = 30

    def __init__(self, master=None):
        super().__init__(master)
        self._controls = {}
        self._df: pd.DataFrame | None = None

        self._build_styles()
        self._build_base()

    # ------------------------------------------------------------------
    # Styles
    # ------------------------------------------------------------------
    def _build_styles(self) -> None:
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass

        # Palette
        self.WHITE = "#ffffff"
        self.BORDER = "#c7d2fe"
        self.BLUE = "#2563eb"   # numeric
        self.GREEN = "#059669"  # dates
        self.BLACK = "#000000"  # categorical

        # Card title backgrounds
        self.TITLE_BG_NUM = "#dbeafe"   # light blue
        self.TITLE_BG_DATE = "#d1fae5"  # light green
        self.TITLE_BG_CAT = "#e5e7eb"   # light gray

        self.TITLE_FG = "#000000"
        title_font = ("Segoe UI Semibold", 11)

        # General white backgrounds
        st.configure("FiltersBody.TFrame", background=self.WHITE)
        st.configure("White.TFrame", background=self.WHITE)
        st.configure("White.TLabel", background=self.WHITE)

        # Numeric card
        st.configure(
            "NumCard.TLabelframe",
            background=self.WHITE,
            relief="solid",
            bordercolor=self.BLUE,
            borderwidth=2,
        )
        st.configure(
            "NumCard.TLabelframe.Label",
            background=self.TITLE_BG_NUM,
            foreground=self.TITLE_FG,
            padding=(10, 5),
            font=title_font,
        )

        # Date card
        st.configure(
            "DateCard.TLabelframe",
            background=self.WHITE,
            relief="solid",
            bordercolor=self.GREEN,
            borderwidth=2,
        )
        st.configure(
            "DateCard.TLabelframe.Label",
            background=self.TITLE_BG_DATE,
            foreground=self.TITLE_FG,
            padding=(10, 5),
            font=title_font,
        )

        # Categorical card
        st.configure(
            "CatCard.TLabelframe",
            background=self.WHITE,
            relief="solid",
            bordercolor=self.BLACK,
            borderwidth=2,
        )
        st.configure(
            "CatCard.TLabelframe.Label",
            background=self.TITLE_BG_CAT,
            foreground=self.TITLE_FG,
            padding=(10, 5),
            font=title_font,
        )

        # Inputs / hints
        st.configure("Filt.TEntry", padding=(3, 2))
        st.configure("Hint.TLabel", foreground=self.BLUE, background=self.WHITE)

    # ------------------------------------------------------------------
    # Base: canvas + scrollbars
    # ------------------------------------------------------------------
    def _build_base(self) -> None:
        initial_h = self.CARD_H_CATEG * 3 + 60

        self._canvas = tk.Canvas(
            self,
            background=self.WHITE,
            borderwidth=0,
            highlightthickness=0,
            height=initial_h,
        )
        self._vsb = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._hsb = ttk.Scrollbar(self, orient="horizontal", command=self._canvas.xview)
        self._canvas.configure(
            yscrollcommand=self._vsb.set,
            xscrollcommand=self._hsb.set,
        )

        self._inner = ttk.Frame(self._canvas, style="FiltersBody.TFrame")
        self._inner_id = self._canvas.create_window(
            (0, 0), window=self._inner, anchor="nw"
        )
        self._inner.bind(
            "<Configure>",
            lambda e: self._canvas.configure(
                scrollregion=self._canvas.bbox("all")
            ),
        )

        self._canvas.pack(side="left", fill="both", expand=True)
        self._vsb.pack(side="right", fill="y")
        self._hsb.pack(side="bottom", fill="x")

        # Mouse wheel: vertical; Shift+wheel: horizontal
        def _on_mousewheel(event):
            if event.num == 5 or event.delta < 0:
                self._canvas.yview_scroll(1, "units")
            elif event.num == 4 or event.delta > 0:
                self._canvas.yview_scroll(-1, "units")
            return "break"

        def _on_shift_mousewheel(event):
            if event.num == 5 or event.delta < 0:
                self._canvas.xview_scroll(1, "units")
            elif event.num == 4 or event.delta > 0:
                self._canvas.xview_scroll(-1, "units")
            return "break"

        self._canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self._canvas.bind_all("<Shift-MouseWheel>", _on_shift_mousewheel)
        self._canvas.bind_all("<Button-4>", _on_mousewheel)  # Linux
        self._canvas.bind_all("<Button-5>", _on_mousewheel)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def build(self, df: pd.DataFrame) -> None:
        """
        Build filter cards for the given dataframe.

        For each column, decides:
            - categorical
            - numeric
            - date (by name)
        and creates the appropriate card.
        """
        # Clear previous content
        for w in self._inner.winfo_children():
            w.destroy()
        self._controls.clear()
        self._df = df.copy()

        font = tkFont.Font(family="Segoe UI", size=10)
        px_char = max(1, font.measure("0"))

        # 1) Optimal listbox width (in characters) per column for categorical filters
        list_chars_by_col: dict[str, int] = {}
        for c in df.columns:
            sample = df[c].astype(str).dropna().unique()[:150]
            if sample.size == 0:
                list_chars_by_col[c] = self.MIN_LIST_CHARS
                continue
            longest = max(sample, key=len)
            px_long = font.measure(longest)
            chars = math.ceil((px_long + 10) / px_char)
            list_chars_by_col[c] = max(
                self.MIN_LIST_CHARS, min(self.MAX_LIST_CHARS, chars)
            )

        # 2) Distribution across rows/columns
        cols = list(df.columns)
        rows = self.ROWS
        cols_per_row = max(1, math.ceil(len(cols) / rows))

        for i, col in enumerate(cols):
            r = i // cols_per_row
            c = i % cols_per_row

            s = df[col]
            col_upper = col.upper()

            # Decide type based on name + dtype
            is_date_name = col_upper.endswith("DATE") or col_upper in {
                "TRANSACTION_DATE",
                "EXPIRY",
            }
            is_numeric = is_numeric_dtype(s) and not is_bool_dtype(s)
            is_categ = not (is_date_name or is_numeric)

            # ---- Card width & height per type ----
            if is_categ:
                list_chars = list_chars_by_col.get(col, self.MIN_LIST_CHARS)
                # width for one listbox (characters + small margin)
                list_px = int(list_chars * px_char + 8)
                buttons_px = 44   # column of >> and << buttons
                tail_padding = 12  # spacing to right edge

                # two lists + buttons + padding, but capped
                card_w = min(
                    max(2 * list_px + buttons_px + tail_padding, 100),
                    self.COL_WIDTH_MAX,
                )
                card_h = self.CARD_H_CATEG
            elif is_numeric:
                card_w = min(120, self.COL_WIDTH_MAX)
                card_h = self.CARD_H_NUM+20
            else:  # date
                card_w = min(160, self.COL_WIDTH_MAX)
                card_h = self.CARD_H_DATE+20

            # ---- Wrapper with shadow ----
            wrapper = ttk.Frame(self._inner, style="White.TFrame")
            wrapper.grid(
                row=r,
                column=c,
                padx=self.PADX,
                pady=self.PADY,
                sticky="nw",
            )
            wrapper.configure(
                width=card_w + self.SHADOW_OFFSET,
                height=card_h + self.SHADOW_OFFSET,
            )
            wrapper.pack_propagate(False)

            shadow = tk.Frame(
                wrapper,
                bg=self.SHADOW_COLOR,
                bd=0,
                highlightthickness=0,
            )
            shadow.place(
                x=self.SHADOW_OFFSET,
                y=self.SHADOW_OFFSET,
                width=card_w,
                height=card_h,
            )

            # ---- Card content ----
            if is_date_name:
                colframe = ttk.LabelFrame(
                    wrapper,
                    text=col,
                    style="DateCard.TLabelframe",
                )
                colframe.place(x=0, y=0, width=card_w, height=card_h)
                self._build_date(colframe, col)
            elif is_numeric:
                colframe = ttk.LabelFrame(
                    wrapper,
                    text=col,
                    style="NumCard.TLabelframe",
                )
                colframe.place(x=0, y=0, width=card_w, height=card_h)
                self._build_numeric(colframe, col)
            else:
                colframe = ttk.LabelFrame(
                    wrapper,
                    text=col,
                    style="CatCard.TLabelframe",
                )
                colframe.place(x=0, y=0, width=card_w, height=card_h)
                list_chars = list_chars_by_col.get(col, self.MIN_LIST_CHARS)
                self._build_categorical(colframe, col, s, list_chars)

        self._inner.update_idletasks()
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def get_filters(self) -> dict:
        """
        Return a filter specification dict.

        Example structure:
        {
            "ISSUER_NAME": {"type": "categorical", "values": [...]},
            "TXN_AMT":     {"type": "numeric", "min": "...", "max": "..."},
            "TRANSACTION_DATE": {"type": "date", "start": "...", "end": "..."},
        }
        """
        spec: dict[str, dict] = {}
        for col, meta in self._controls.items():
            t = meta.get("type")
            if t == "categorical":
                vals = meta["get"]()
                if vals:
                    spec[col] = {"type": "categorical", "values": vals}
            elif t == "numeric":
                vmin = meta["min"].get().strip()
                vmax = meta["max"].get().strip()
                if vmin != "" or vmax != "":
                    spec[col] = {"type": "numeric", "min": vmin, "max": vmax}
            elif t == "date":
                start = meta["start"].get().strip()
                end = meta["end"].get().strip()
                if start != "" or end != "":
                    spec[col] = {"type": "date", "start": start, "end": end}
        return spec

    def reset(self) -> None:
        """Clear all filters (categorical, numeric, date)."""
        for meta in self._controls.values():
            t = meta.get("type")
            if t == "categorical":
                meta["reset"]()
            elif t == "numeric":
                meta["min"].set("")
                meta["max"].set("")
            elif t == "date":
                meta["start"].set("")
                meta["end"].set("")

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------
    def _build_categorical(
        self,
        parent: ttk.Labelframe,
        col: str,
        s: pd.Series,
        list_chars: int,
    ) -> None:
        """Build dual-list (available/selected) for a categorical column."""
        values = sorted(v for v in s.astype(str).dropna().unique())

        # Search row
        sr = ttk.Frame(parent, style="White.TFrame")
        sr.place(x=8, y=8)
        ttk.Label(sr, text="Search", style="White.TLabel").pack(side="left")
        entry = ttk.Entry(
            sr,
            width=min(list_chars + 2, self.MAX_LIST_CHARS + 2),
            style="Filt.TEntry",
        )
        entry.pack(side="left", padx=(6, 0))

        # Dual-list area
        dl = ttk.Frame(parent, style="White.TFrame")
        dl.place(x=8, y=36)

        lb_kwargs = dict(
            height=7,
            width=list_chars,
            background=self.WHITE,
            foreground="#000000",
            selectbackground=self.BLUE,
            selectforeground=self.WHITE,
            relief="solid",
            borderwidth=1,
            exportselection=False,
        )

        left_wrap = ttk.Frame(dl, style="White.TFrame")
        right_wrap = ttk.Frame(dl, style="White.TFrame")

        lb_left = tk.Listbox(left_wrap, **lb_kwargs)
        lb_right = tk.Listbox(right_wrap, **lb_kwargs)

        hsb_left = ttk.Scrollbar(
            left_wrap,
            orient="horizontal",
            command=lb_left.xview,
        )
        hsb_right = ttk.Scrollbar(
            right_wrap,
            orient="horizontal",
            command=lb_right.xview,
        )
        lb_left.configure(xscrollcommand=hsb_left.set)
        lb_right.configure(xscrollcommand=hsb_right.set)

        # Symmetric grid: left list | buttons | right list
        dl.grid_columnconfigure(0, weight=0)
        dl.grid_columnconfigure(1, minsize=44, weight=0)
        dl.grid_columnconfigure(2, weight=0)

        left_wrap.grid(row=0, column=0, sticky="nw")
        mid = ttk.Frame(dl, style="White.TFrame")
        mid.grid(row=0, column=1, padx=6)
        right_wrap.grid(row=0, column=2, sticky="nw")

        lb_left.grid(row=0, column=0, sticky="nw")
        hsb_left.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        lb_right.grid(row=0, column=0, sticky="nw")
        hsb_right.grid(row=1, column=0, sticky="ew", pady=(2, 0))

        # Buttons between lists
        btn_kwargs = dict(
            bg=self.WHITE,
            activebackground=self.WHITE,
            relief="solid",
            bd=1,
            padx=6,
            pady=1,
            cursor="hand2",
        )
        tk.Button(
            mid,
            text=">>",
            **btn_kwargs,
            command=lambda: self._move_between(lb_left, lb_right),
        ).pack(pady=(6, 6))
        tk.Button(
            mid,
            text="<<",
            **btn_kwargs,
            command=lambda: self._move_between(lb_right, lb_left),
        ).pack()

        # Load initial values on the left
        for v in values:
            lb_left.insert("end", v)

        # Search behaviour
        def on_search(*_):
            q = entry.get().strip().lower()
            lb_left.delete(0, "end")
            if not q:
                for v in values:
                    lb_left.insert("end", v)
            else:
                for v in values:
                    if q in str(v).lower():
                        lb_left.insert("end", v)

        entry.bind("<KeyRelease>", on_search)

        # Register control for this column
        self._controls[col] = {
            "type": "categorical",
            "get": lambda lb=lb_right: [lb.get(i) for i in range(lb.size())],
            "reset": lambda lbL=lb_left, lbR=lb_right, vals=values: self._reset_dual(
                lbL, lbR, vals
            ),
        }

    def _build_numeric(self, parent: ttk.Labelframe, col: str) -> None:
        """Build numeric filter: min / max + Clear button."""
        min_var = tk.StringVar(value="")
        max_var = tk.StringVar(value="")

        frm = ttk.Frame(parent, style="White.TFrame")
        frm.place(x=8, y=12, relwidth=1.0, width=-16)

        frm.grid_columnconfigure(0, weight=1, uniform="num")
        frm.grid_columnconfigure(1, weight=1, uniform="num")

        ttk.Label(frm, text="Min", style="White.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(frm, text="Max", style="White.TLabel").grid(
            row=0, column=1, sticky="w"
        )

        e_min = ttk.Entry(frm, textvariable=min_var, style="Filt.TEntry")
        e_max = ttk.Entry(frm, textvariable=max_var, style="Filt.TEntry")
        e_min.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        e_max.grid(row=1, column=1, sticky="ew")

        tk.Button(
            frm,
            text="Clear",
            bg=self.WHITE,
            activebackground=self.WHITE,
            relief="solid",
            bd=1,
            padx=10,
            pady=2,
            cursor="hand2",
            command=lambda: (min_var.set(""), max_var.set("")),
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))

        self._controls[col] = {"type": "numeric", "min": min_var, "max": max_var}

    def _build_date(self, parent: ttk.Labelframe, col: str) -> None:
        """Build date filter: From / To with SimpleDateEntry + Clear."""
        row1 = ttk.Frame(parent, style="White.TFrame")
        row1.pack(anchor="w", pady=(10, 0))
        ttk.Label(row1, text="From", style="White.TLabel").pack(
            side="left", padx=(0, 6)
        )

        start_var = tk.StringVar()
        w1 = DateEntry(
            row1,
            width=12,
            date_pattern="yyyy-mm-dd",
            textvariable=start_var,
        )
        w1.pack(side="left")

        row2 = ttk.Frame(parent, style="White.TFrame")
        row2.pack(anchor="w", pady=(8, 0))
        ttk.Label(row2, text="To", style="White.TLabel").pack(
            side="left", padx=(0, 6)
        )

        end_var = tk.StringVar()
        w2 = DateEntry(
            row2,
            width=12,
            date_pattern="yyyy-mm-dd",
            textvariable=end_var,
        )
        w2.pack(side="left")

        tk.Button(
            parent,
            text="Clear",
            bg=self.WHITE,
            activebackground=self.WHITE,
            relief="solid",
            bd=1,
            padx=10,
            pady=2,
            cursor="hand2",
            command=lambda: (start_var.set(""), end_var.set("")),
        ).pack(anchor="w", pady=(10, 0))

        self._controls[col] = {
            "type": "date",
            "start": start_var,
            "end": end_var,
        }

    # ------------------------------------------------------------------
    # Utils
    # ------------------------------------------------------------------
    @staticmethod
    def _move_between(src: tk.Listbox, dst: tk.Listbox) -> None:
        """Move selected items from src listbox to dst listbox."""
        sel = list(src.curselection())
        for idx in sel[::-1]:
            dst.insert("end", src.get(idx))
        for idx in sel[::-1]:
            src.delete(idx)

    @staticmethod
    def _reset_dual(
        lb_left: tk.Listbox,
        lb_right: tk.Listbox,
        values,
    ) -> None:
        """Reset dual list: all values back in left list, right list empty."""
        all_right = [lb_right.get(i) for i in range(lb_right.size())]
        for v in all_right:
            lb_left.insert("end", v)
        lb_right.delete(0, "end")
        lb_left.delete(0, "end")
        for v in values:
            lb_left.insert("end", v)
