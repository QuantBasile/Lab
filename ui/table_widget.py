# ui/table_widget.py
# ---------------------------------------------------------------------
# Professional paginated + sortable table widget for Tkinter dashboards.
#
# Public API:
#     show_dataframe(df)
#
# Features:
#     - Sorting (numeric, dates, text)
#     - Pagination (first / prev / next / last)
#     - Adjustable page size
#     - Zebra-row styling
#     - Auto-sizing columns based on sample rows
#     - Clipboard copy (Ctrl+C / Cmd+C)
# ---------------------------------------------------------------------

import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont

import pandas as pd

# ---------------------------------------------------------------------
# Formatting rules per column
# ---------------------------------------------------------------------
_FORMAT_RULES = {
    "TXN_AMT":  {"kind": "number", "decimals": 2, "thousands": True,  "align": "e"},
    "STRIKE":   {"kind": "number", "decimals": 4, "thousands": False, "align": "e"},
    "RATIO":    {"kind": "number", "decimals": 6, "thousands": False, "align": "e"},
    "NBR_OF_UNITS":  {"kind": "int", "align": "e"},
    "NBR_OF_TRADES": {"kind": "int", "align": "e"},
    "TRANSACTION_DATE": {"kind": "date", "align": "center"},
    "EXPIRY":   {"kind": "date", "align": "center"},
    "DAY":      {"kind": "int", "align": "e"},
    "WEEK":     {"kind": "int", "align": "e"},
    "MONTH":    {"kind": "int", "align": "e"},
}


class TableFrame(ttk.Frame):
    """
    A high-quality table component with:
        • Pagination
        • Sorting
        • Auto-sized columns
        • Clipboard copy
        • Dashboard styling

    Simply call:
        table.show_dataframe(df)
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def __init__(self, master=None):
        super().__init__(master)

        # Internal state
        self._df = None
        self._columns = []
        self._col_meta = {}
        self._sort_state = {}

        # Pagination
        self._page_var = tk.IntVar(value=1)
        self._page_size_var = tk.IntVar(value=1000)
        self._page_size_choices = (100, 500, 1000, 5000)
        self._status_var = tk.StringVar(value="Showing 0–0 of 0")

        # Build UI
        self._build()

    # ------------------------------------------------------------------
    def _build(self):
        self._setup_style()

        # --- Treeview ----------------------------------------------------
        self._tree = ttk.Treeview(self, show="headings", selectmode="extended")
        vsb = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscroll=vsb.set, xscroll=hsb.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Zebra rows
        self._tree.tag_configure("even", background="#fbfdff")
        self._tree.tag_configure("odd", background="#f2f6fb")

        # Bindings
        self._tree.bind("<Control-c>", self._copy_selection)
        self._tree.bind("<Command-c>", self._copy_selection)
        self._tree.bind("<Double-Button-1>", self._on_header_double_click)

        # --- Pagination bar ----------------------------------------------
        pagebar = ttk.Frame(self)
        pagebar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=(4, 6))
        for c in range(10):
            pagebar.columnconfigure(c, weight=0)
        pagebar.columnconfigure(9, weight=1)

        # Buttons (English)
        btn_first = ttk.Button(pagebar, text="⏮ First", command=self._go_first)
        btn_prev  = ttk.Button(pagebar, text="‹ Prev", command=self._go_prev)
        ttk.Label(pagebar, text="Page").grid(row=0, column=2, padx=(8, 4))
        ent_page = ttk.Entry(pagebar, textvariable=self._page_var, width=6)
        ent_page.bind("<Return>", lambda e: self._goto_page(self._page_var.get()))
        btn_next  = ttk.Button(pagebar, text="Next ›", command=self._go_next)
        btn_last  = ttk.Button(pagebar, text="Last ⏭", command=self._go_last)

        ttk.Label(pagebar, text=" · Page size:").grid(row=0, column=6, padx=(12, 4))
        cmb_size = ttk.Combobox(
            pagebar,
            values=[str(x) for x in self._page_size_choices],
            textvariable=self._page_size_var,
            state="readonly",
            width=6,
        )
        cmb_size.bind("<<ComboboxSelected>>", lambda e: self._on_change_pagesize())

        lbl_status = ttk.Label(pagebar, textvariable=self._status_var, anchor="e")

        # Grid
        btn_first.grid(row=0, column=0, padx=(0, 4))
        btn_prev.grid(row=0, column=1, padx=(0, 8))
        ent_page.grid(row=0, column=3, padx=(0, 8))
        btn_next.grid(row=0, column=4, padx=(0, 4))
        btn_last.grid(row=0, column=5, padx=(0, 12))
        cmb_size.grid(row=0, column=7, padx=(0, 8))
        lbl_status.grid(row=0, column=9, sticky="e")

    # ------------------------------------------------------------------
    def _setup_style(self):
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass

        st.configure(
            "Treeview",
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground="#111",
            rowheight=28,
            font=("Segoe UI", 11),
            borderwidth=0,
        )
        st.configure(
            "Treeview.Heading",
            background="#1e40af",
            foreground="#ffffff",
            font=("Segoe UI Semibold", 11),
            padding=(10, 6),
        )
        st.map(
            "Treeview",
            background=[("selected", "#cfe8ff")],
            foreground=[("selected", "#111111")],
        )

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------
    def show_dataframe(self, df):
        """
        Accepts a DataFrame and displays it with pagination.

        This is the only method your other screens need.
        """
        self._df = df.copy() if df is not None else pd.DataFrame()

        self._columns = list(self._df.columns)
        self._col_meta = self._detect_and_prepare_columns(self._df)
        self._setup_columns()

        self._page_var.set(1)
        self._render_current_page()

    # ------------------------------------------------------------------
    # Column setup and formatting
    # ------------------------------------------------------------------
    def _detect_and_prepare_columns(self, df):
        """Infer column types for formatting/alignment."""
        meta = {}
        for col in df.columns:
            rule = _FORMAT_RULES.get(col, {})
            kind = rule.get("kind")

            if kind is None:
                dtype = str(df[col].dtype)
                if "int" in dtype:
                    kind = "int"
                elif "float" in dtype:
                    kind = "number"
                elif "datetime" in dtype:
                    kind = "date"
                else:
                    kind = "text"

            align = rule.get("align", "e" if kind in ("int", "number") else "w")
            decimals = rule.get("decimals", 0 if kind == "int" else (2 if kind == "number" else None))
            thousands = bool(rule.get("thousands", kind in ("int", "number")))

            meta[col] = {
                "kind": kind,
                "align": align,
                "decimals": decimals,
                "thousands": thousands,
            }
        return meta

    def _setup_columns(self):
        self._tree.configure(columns=self._columns)
        for col in self._columns:
            align = self._col_meta[col]["align"]
            anchor = {"w": "w", "e": "e", "center": "center"}.get(align, "w")
            self._set_header(col, text=col, ascending=None)
            self._tree.column(col, anchor=anchor, width=120, stretch=True)

    def _set_header(self, col, text, ascending):
        arrow = " ▲" if ascending is True else (" ▼" if ascending is False else "")
        self._tree.heading(
            col,
            text=f"{text}{arrow}",
            command=lambda c=col: self._on_sort(c),
        )

    # Formatting individual cell values
    def _format_value(self, col, v):
        if v is None:
            return ""
        meta = self._col_meta[col]
        kind = meta["kind"]

        try:
            if kind == "int":
                return f"{int(v):,}".replace(",", " ")
            if kind == "number":
                d = meta["decimals"] or 2
                return f"{float(v):,.{d}f}".replace(",", " ")
        except Exception:
            pass

        return str(v)

    # Automatically size columns based on sample rows
    def _autosize_columns(self, sample_rows=300):
        font = tkfont.nametofont("TkDefaultFont")
        samples = {c: [c] for c in self._columns}

        children = self._tree.get_children("")
        for i, iid in enumerate(children[:sample_rows]):
            vals = self._tree.item(iid, "values")
            for c, val in zip(self._columns, vals):
                samples[c].append(str(val))

        min_w, max_w, padding = 80, 380, 24
        for c in self._columns:
            widths = [font.measure(s) for s in samples[c]]
            w = max(widths) + padding
            self._tree.column(c, width=max(min_w, min(w, max_w)))

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------
    def _render_current_page(self):
        """Render the visible slice of the dataframe."""
        self._tree.delete(*self._tree.get_children())

        if self._df is None or self._df.empty:
            self._tree.configure(columns=("No data",))
            self._tree.heading("No data", text="No data")
            self._tree.column("No data", width=120, anchor="center")
            self._status_var.set("Showing 0–0 of 0")
            return

        n_rows = len(self._df)
        page_size = max(1, int(self._page_size_var.get()))
        page = max(1, int(self._page_var.get()))
        total_pages = max(1, (n_rows + page_size - 1) // page_size)

        if page > total_pages:
            page = total_pages
            self._page_var.set(page)

        start = (page - 1) * page_size
        end = min(start + page_size, n_rows)

        slice_df = self._df.iloc[start:end]

        for i, row in enumerate(slice_df.itertuples(index=False, name=None)):
            tag = "even" if i % 2 == 0 else "odd"
            values = [
                self._format_value(self._columns[j], row[j])
                for j in range(len(self._columns))
            ]
            self._tree.insert("", "end", values=values, tags=(tag,))

        # Auto size after inserting rows
        self._autosize_columns(sample_rows=min(len(slice_df), 500))

        self._status_var.set(
            f"Showing {start+1:,}–{end:,} of {n_rows:,}".replace(",", " ")
        )

    def _on_change_pagesize(self):
        self._page_var.set(1)
        self._render_current_page()

    def _goto_page(self, page):
        try:
            page = int(page)
        except Exception:
            page = 1
        page = max(1, page)
        self._page_var.set(page)
        self._render_current_page()

    def _go_first(self):
        self._goto_page(1)

    def _go_prev(self):
        self._goto_page(max(1, self._page_var.get() - 1))

    def _go_next(self):
        if self._df is None:
            return
        n = len(self._df)
        ps = max(1, int(self._page_size_var.get()))
        total_pages = (n + ps - 1) // ps
        self._goto_page(min(total_pages, self._page_var.get() + 1))

    def _go_last(self):
        if self._df is None:
            return
        n = len(self._df)
        ps = max(1, int(self._page_size_var.get()))
        total_pages = (n + ps - 1) // ps
        self._goto_page(total_pages)

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------
    def _on_sort(self, col):
        if self._df is None or col not in self._df.columns:
            return
    
        asc = self._sort_state.get(col, {}).get("ascending")
        asc = True if asc is None else (not asc)
        self._sort_state[col] = {"ascending": asc}
    
        kind = self._col_meta.get(col, {}).get("kind", "text")
    
        df2 = self._df.copy()
    
        if kind in ("int", "number"):
            s = pd.to_numeric(df2[col], errors="coerce")
            df2 = df2.assign(__sortkey=s)
            df2 = df2.sort_values("__sortkey", ascending=asc, na_position="last").drop(columns="__sortkey")
        elif kind == "date":
            s = pd.to_datetime(df2[col], errors="coerce")
            df2 = df2.assign(__sortkey=s)
            df2 = df2.sort_values("__sortkey", ascending=asc, na_position="last").drop(columns="__sortkey")
        else:
            s = df2[col].astype(str)
            df2 = df2.assign(__sortkey=s)
            df2 = df2.sort_values("__sortkey", ascending=asc, na_position="last").drop(columns="__sortkey")
    
        # repintar manteniendo estado
        self.show_dataframe(df2)
    
        # actualizar flechas en headers
        for c in self._columns:
            self._set_header(
                c, text=c,
                ascending=self._sort_state.get(c, {}).get("ascending") if c == col else None
            )


    def _on_header_double_click(self, event):
        region = self._tree.identify("region", event.x, event.y)
        if region != "heading":
            return
        col_id = self._tree.identify_column(event.x)
        try:
            idx = int(col_id.lstrip("#")) - 1
            col = self._columns[idx]
        except Exception:
            return
        self._on_sort(col)

    # ------------------------------------------------------------------
    # Clipboard
    # ------------------------------------------------------------------
    def _copy_selection(self, event=None):
        sel = self._tree.selection()
        if not sel:
            return "break"

        lines = [",".join(self._columns)]
        for iid in sel:
            vals = [str(v) for v in self._tree.item(iid, "values")]
            escaped = []
            for v in vals:
                v = v.replace('"', '""')
                if any(ch in v for ch in [",", '"', "\n"]):
                    v = f'"{v}"'
                escaped.append(v)
            lines.append(",".join(escaped))

        text = "\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(text)
        return "break"
