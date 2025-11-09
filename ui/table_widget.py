#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
import math
import pandas as pd

# --- Reglas de formato (igual que tu versión) ---
_FORMAT_RULES = {
    "TXN_AMT": {"kind": "number", "decimals": 2, "thousands": True, "align": "e"},
    "STRIKE":  {"kind": "number", "decimals": 4, "thousands": False, "align": "e"},
    "RATIO":   {"kind": "number", "decimals": 6, "thousands": False, "align": "e"},
    "NBR_OF_UNITS":  {"kind": "int", "align": "e"},
    "NBR_OF_TRADES": {"kind": "int", "align": "e"},
    "TRANSACTION_DATE": {"kind": "date", "align": "center"},
    "EXPIRY":          {"kind": "date", "align": "center"},
    "DAY":          {"kind": "int", "align": "e"},
    "WEEK":           {"kind": "int", "align": "e"},
    "MONTH":          {"kind": "int", "align": "e"},
}


class TableFrame(ttk.Frame):
    """Treeview pro con look de dashboard + paginación integrada."""
    def __init__(self, master=None):
        super().__init__(master)
        # datos y metadatos
        self._df = None
        self._columns = []
        self._col_meta = {}
        self._sort_state = {}

        # paginación (siempre activada)
        self._page_var = tk.IntVar(value=1)
        self._page_size_var = tk.IntVar(value=1000)
        self._page_size_choices = (100, 500, 1000, 5000)
        self._status_var = tk.StringVar(value="Zeige 0–0 von 0")

        self._build()

    # ---------------- UI ----------------
    def _build(self):
        self._style_setup()

        # Tree
        self._tree = ttk.Treeview(self, show="headings", selectmode="extended")
        vsb = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscroll=vsb.set, xscroll=hsb.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        # layout grid
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # zebra striping
        self._tree.tag_configure("even", background="#fbfdff")
        self._tree.tag_configure("odd", background="#f2f6fb")

        # bindings
        self._tree.bind("<Control-c>", self._copy_selection)
        self._tree.bind("<Command-c>", self._copy_selection)
        self._tree.bind("<Double-Button-1>", self._on_header_double_click)

        # --- Barra de paginación (siempre visible) ---
        pagebar = ttk.Frame(self)
        pagebar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=(4, 6))
        for c in range(10):
            pagebar.columnconfigure(c, weight=0)
        pagebar.columnconfigure(9, weight=1)

        # Botones en alemán
        btn_first = ttk.Button(pagebar, text="⏮ Erste", command=self._go_first)
        btn_prev  = ttk.Button(pagebar, text="‹ Zurück", command=self._go_prev)
        ttk.Label(pagebar, text="Seite").grid(row=0, column=2, padx=(8, 4))
        ent_page = ttk.Entry(pagebar, textvariable=self._page_var, width=6)
        ent_page.bind("<Return>", lambda e: self._goto_page(self._page_var.get()))
        btn_next  = ttk.Button(pagebar, text="Weiter ›", command=self._go_next)
        btn_last  = ttk.Button(pagebar, text="Letzte ⏭", command=self._go_last)

        ttk.Label(pagebar, text=" · Seitengröße:").grid(row=0, column=6, padx=(12, 4))
        cmb_size = ttk.Combobox(
            pagebar,
            values=[str(x) for x in self._page_size_choices],
            textvariable=self._page_size_var,
            state="readonly",
            width=6,
        )
        cmb_size.bind("<<ComboboxSelected>>", lambda e: self._on_change_pagesize())

        lbl_status = ttk.Label(pagebar, textvariable=self._status_var, anchor="e")

        btn_first.grid(row=0, column=0, padx=(0, 4))
        btn_prev.grid(row=0, column=1, padx=(0, 8))
        ent_page.grid(row=0, column=3, padx=(0, 8))
        btn_next.grid(row=0, column=4, padx=(0, 4))
        btn_last.grid(row=0, column=5, padx=(0, 12))
        cmb_size.grid(row=0, column=7, padx=(0, 8))
        lbl_status.grid(row=0, column=9, sticky="e")

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
            background="#1e40af",
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
        """
        Recibe un DataFrame y lo muestra paginado.
        Mantiene compatibilidad: solo necesitas llamar a show_dataframe(df).
        """
        if df is None:
            # limpia si llega None
            self._df = pd.DataFrame()
        else:
            self._df = df

        # preparar columnas y metadatos (una vez por df)
        self._columns = list(self._df.columns)
        self._col_meta = self._detect_and_prepare_columns(self._df)
        self._setup_columns()

        # ir a página 1 y dibujar
        self._page_var.set(1)
        self._render_current_page()

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

    # ---------- paginación ----------
    def _render_current_page(self):
        """Dibuja la página actual a partir de self._df."""
        # limpiar filas
        self._tree.delete(*self._tree.get_children())

        if self._df is None or self._df.empty:
            # estado vacío
            self._tree.configure(columns=("(keine Daten)",))
            self._tree.heading("(keine Daten)", text="(keine Daten)")
            self._tree.column("(keine Daten)", width=120, anchor="center")
            self._status_var.set("Zeige 0–0 von 0")
            return

        # asegura columnas correctas
        self._tree.configure(columns=self._columns)
        for c in self._columns:
            self._tree.heading(c, text=c)

        n = len(self._df)
        ps = max(1, int(self._page_size_var.get()))
        p = max(1, int(self._page_var.get()))
        total_pages = max(1, (n + ps - 1) // ps)
        if p > total_pages:
            p = total_pages
            self._page_var.set(p)

        start = (p - 1) * ps
        end = min(start + ps, n)

        # inserta solo la página
        insert = self._tree.insert
        view_df = self._df.iloc[start:end]
        for i, row in enumerate(view_df.itertuples(index=False, name=None)):
            tags = ("even",) if (i % 2 == 0) else ("odd",)
            values = [self._format_value(self._columns[j], row[j]) for j in range(len(self._columns))]
            insert("", "end", values=values, tags=tags)

        # autosize con muestras de la página
        self._autosize_columns(sample_rows=min(len(view_df), 500))
        self._status_var.set(
            f"Zeige {start+1:,}–{end:,} von {n:,}".replace(",", " ")
        )

    def _on_change_pagesize(self):
        self._page_var.set(1)
        self._render_current_page()

    def _goto_page(self, page: int):
        try:
            p = int(page)
        except Exception:
            p = 1
        if p < 1:
            p = 1
        self._page_var.set(p)
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
        total_pages = max(1, (n + ps - 1) // ps)
        self._goto_page(min(total_pages, self._page_var.get() + 1))

    def _go_last(self):
        if self._df is None:
            return
        n = len(self._df)
        ps = max(1, int(self._page_size_var.get()))
        total_pages = max(1, (n + ps - 1) // ps)
        self._goto_page(total_pages)

    # ---------- ordenar ----------
    def _on_sort(self, col):
        if self._df is None or self._df.empty:
            return
        asc = self._sort_state.get(col, {}).get("ascending")
        asc = True if asc is None else (not asc)
        self._sort_state[col] = {"ascending": asc}

        # ordenar df completo (para que aplique a todas las páginas)
        try:
            kind = self._col_meta[col]["kind"]
            if kind in ("int", "number"):
                # intentar convertir, si falla entonces ordenar por string
                s = pd.to_numeric(self._df[col], errors="coerce")
                self._df = self._df.assign(__sort__=s)
                self._df = (
                    self._df.sort_values(
                        by="__sort__", ascending=asc, na_position="last"
                    ).drop(columns="__sort__")
                )
            else:
                self._df = self._df.sort_values(
                    by=col, ascending=asc, na_position="last"
                )
        except Exception:
            # fallback: ordenar por texto
            self._df = self._df.sort_values(by=col, ascending=asc, na_position="last")

        # actualizar encabezados (flecha en la col actual)
        for c in self._columns:
            self._set_header(
                c,
                text=c,
                ascending=self._sort_state.get(c, {}).get("ascending")
                if c == col
                else None,
            )

        # redibujar página 1 tras ordenar
        self._page_var.set(1)
        self._render_current_page()

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
