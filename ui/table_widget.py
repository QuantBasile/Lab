#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
import math

_FORMAT_RULES = {
    "TXN_AMT": {"kind": "number", "decimals": 2, "thousands": True, "align": "e"},
    "STRIKE":  {"kind": "number", "decimals": 4, "thousands": False, "align": "e"},
    "RATIO":   {"kind": "number", "decimals": 6, "thousands": False, "align": "e"},
    "NBR_OF_UNITS":  {"kind": "int", "align": "e"},
    "NBR_OF_TRADES": {"kind": "int", "align": "e"},
    "TRANSACTION_DATE": {"kind": "date", "align": "center"},
    "EXPIRY":          {"kind": "date", "align": "center"},
}

class TableFrame(ttk.Frame):
    """ Treeview pro, con look de dashboard """
    def __init__(self, master=None):
        super().__init__(master)
        self._df = None
        self._columns = []
        self._col_meta = {}
        self._sort_state = {}
        self._build()

    def _build(self):
        self._style_setup()
        self._tree = ttk.Treeview(self, show="headings", selectmode="extended")
        vsb = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscroll=vsb.set, xscroll=hsb.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # zebra striping
        self._tree.tag_configure("even", background="#fbfdff")
        self._tree.tag_configure("odd", background="#f2f6fb")

        self._tree.bind("<Control-c>", self._copy_selection)
        self._tree.bind("<Command-c>", self._copy_selection)
        self._tree.bind("<Double-Button-1>", self._on_header_double_click)

    def _style_setup(self):
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
    
        base_font = ("Segoe UI", 11)
        header_font = ("Segoe UI Semibold", 11)
    
        st.configure(
            "Treeview",
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground="#111111",
            rowheight=28,
            font=base_font,
            borderwidth=0,
        )
        st.configure(
            "Treeview.Heading",
            background="#1e40af",   # mismo que topbar/heading
            foreground="#ffffff",
            font=header_font,
            relief="flat",
            padding=(10, 6),
        )
        st.map(
            "Treeview",
            background=[("selected", "#cfe8ff")],
            foreground=[("selected", "#111111")],
        )


    # ---------- API ----------
    def show_dataframe(self, df):
        if df is None:
            return
        self._df = df
        self._columns = list(df.columns)
        self._col_meta = self._detect_and_prepare_columns(df)
        self._setup_columns()
        self._tree.delete(*self._tree.get_children())
        insert = self._tree.insert
        for i, row in enumerate(df.itertuples(index=False, name=None)):
            tags = ("even",) if (i % 2 == 0) else ("odd",)
            values = [self._format_value(self._columns[j], row[j]) for j in range(len(self._columns))]
            insert("", "end", values=values, tags=tags)
        self._autosize_columns(sample_rows=min(len(df), 500))

    # ---------- setup ----------
    def _detect_and_prepare_columns(self, df):
        meta = {}
        for col in df.columns:
            rule = _FORMAT_RULES.get(col, {})
            kind = rule.get("kind")
            align = rule.get("align")
            if kind is None:
                dtype = str(df[col].dtype)
                if "int" in dtype:
                    kind, align = "int", "e"
                elif "float" in dtype:
                    kind, align = "number", "e"
                elif "datetime" in dtype:
                    kind, align = "date", "center"
                else:
                    kind, align = "text", "w"
            decimals = rule.get("decimals", 0 if kind == "int" else (2 if kind == "number" else None))
            thousands = bool(rule.get("thousands", kind in ("int", "number")))
            meta[col] = {"kind": kind, "align": align, "decimals": decimals, "thousands": thousands}
        return meta

    def _setup_columns(self):
        self._tree.configure(columns=self._columns)
        for col in self._columns:
            align = self._col_meta[col]["align"]
            anchor = {"w": "w", "e": "e", "center": "center"}.get(align, "w")
            self._set_header(col, text=col, ascending=None)
            self._tree.column(col, anchor=anchor, width=120, stretch=True)

    def _set_header(self, col, text, ascending):
        suffix = ""
        if ascending is True:
            suffix = " ▲"
        elif ascending is False:
            suffix = " ▼"
        self._tree.heading(col, text=f"{text}{suffix}", command=lambda c=col: self._on_sort(c))

    def _format_value(self, col, v):
        if v is None:
            return ""
        kind = self._col_meta[col]["kind"]
        try:
            if kind == "int":
                return f"{int(v):,}".replace(",", " ")
            if kind == "number":
                d = self._col_meta[col]["decimals"] or 2
                s = f"{float(v):,.{d}f}".replace(",", " ")
                return s
        except Exception:
            pass
        return str(v)

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

    # ---------- sort ----------
    def _on_sort(self, col):
        if self._df is None:
            return
        asc = self._sort_state.get(col, {}).get("ascending")
        asc = True if asc is None else (not asc)
        self._sort_state[col] = {"ascending": asc}
        rows = [(iid, self._tree.item(iid, "values")) for iid in self._tree.get_children("")]
        idx = self._columns.index(col)

        def _key(t):
            val = t[1][idx]
            kind = self._col_meta[col]["kind"]
            if kind in ("int", "number"):
                try:
                    return float(str(val).replace(" ", "").replace(",", ""))
                except Exception:
                    return math.inf
            return str(val)

        rows.sort(key=_key, reverse=(not asc))
        for i, (iid, _) in enumerate(rows):
            self._tree.move(iid, "", i)
            self._tree.item(iid, tags=("even",) if i % 2 == 0 else ("odd",))
        for c in self._columns:
            self._set_header(c, text=c, ascending=self._sort_state.get(c, {}).get("ascending") if c == col else None)

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

    # ---------- copiar ----------
    def _copy_selection(self, event=None):
        sel = self._tree.selection()
        if not sel:
            return "break"
        lines = [",".join(self._columns)]
        for iid in sel:
            vals = [str(v) for v in self._tree.item(iid, "values")]
            row = []
            for v in vals:
                v = v.replace('"', '""')
                if ("," in v) or ('"' in v) or ("\n" in v):
                    v = f'"{v}"'
                row.append(v)
            lines.append(",".join(row))
        txt = "\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(txt)
        return "break"
