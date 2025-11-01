#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 31 23:05:42 2025

@author: fran
"""
## 🧩 ui/table_widget.py

# ui/table_widget.py
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
import math

# Reglas de formato por nombre de columna (si quieres, ajusta aquí)
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
    """
    Treeview pro:
      - Estilos 'clam', cabeceras en negrita y hover suave
      - Zebra striping (filas alternas)
      - Alineación numérica a la derecha y fechas centradas
      - Formato profesional: miles, decimales, etc.
      - Sort por cabeceras con flecha ▲ ▼
      - Auto-anchos por contenido (rápido)
      - Copiar filas al portapapeles (Ctrl+C)
    API pública:
      - show_dataframe(df)
    """
    def __init__(self, master=None):
        super().__init__(master)
        self._df = None
        self._columns = []
        self._col_meta = {}      # nombre -> {align, kind, fmt}
        self._sort_state = {}    # nombre -> {"ascending": bool}
        self._build()

    # ---------- construcción y estilos ----------
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

        # zebra striping via tags
        self._tree.tag_configure("odd", background="#fafafa")
        self._tree.tag_configure("even", background="#ffffff")

        # bindings
        self._tree.bind("<Control-c>", self._copy_selection)
        self._tree.bind("<Command-c>", self._copy_selection)  # mac
        # (opcional) doble click ordena también
        self._tree.bind("<Double-Button-1>", self._on_header_double_click)
        
        # dentro de _build() tras crear self._tree:
        self._tree.tag_configure("even", background="#fbfdff")
        self._tree.tag_configure("odd",  background="#f2f6fb")
        # y si usas algún highlight propio:
        self._tree.tag_configure("HL",   background="#fff3c4")

    def _style_setup(self):
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass

        # Ajustar altura de fila y fuente
        base_font = tkfont.nametofont("TkDefaultFont")
        st.configure("Treeview", rowheight=24, font=base_font)
        # Cabeceras: más padding y negrita
        header_font = base_font.copy()
        header_font.configure(weight="bold")
        st.configure("Treeview.Heading", font=header_font, padding=(8, 4))
        # Borde/relieve sutil en hover (depende del tema)
        st.map("Treeview", background=[("selected", "#e6ecff")])

    # ---------- API ----------
    def show_dataframe(self, df):
        """Renderiza df (hasta 1000 filas según control externo)."""
        if df is None:
            return
        self._df = df
        self._columns = list(df.columns)
        self._col_meta = self._detect_and_prepare_columns(df)

        # Configurar columnas + cabeceras
        self._setup_columns()

        # Volcar datos
        self._tree.delete(*self._tree.get_children())
        insert = self._tree.insert

        # zebra striping y formato
        for i, row in enumerate(df.itertuples(index=False, name=None)):
            tags = ("even",) if (i % 2 == 0) else ("odd",)
            values = [self._format_value(self._columns[j], row[j]) for j in range(len(self._columns))]
            insert("", "end", values=values, tags=tags)

        # Autosize final
        self._autosize_columns(sample_rows=min(len(df), 500))

    # ---------- columnas, formatos, tamaños ----------
    def _detect_and_prepare_columns(self, df):
        meta = {}
        for col in df.columns:
            # heurística de tipo
            rule = _FORMAT_RULES.get(col, {})
            kind = rule.get("kind")
            align = rule.get("align")

            if kind is None:
                dtype = str(df[col].dtype)
                if "int" in dtype:
                    kind = "int"; align = align or "e"
                elif "float" in dtype:
                    kind = "number"; align = align or "e"
                elif "datetime" in dtype:
                    kind = "date"; align = align or "center"
                else:
                    kind = "text"; align = align or "w"

            # formato decimal/thousands por defecto
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

            # Título + callback de sort con flecha
            self._set_header(col, text=col, ascending=None)
            self._tree.column(col, anchor=anchor, width=120, stretch=True)

    def _set_header(self, col, text, ascending):
        # añade ▲/▼ si ascending no es None
        suffix = ""
        if ascending is True:
            suffix = "  ▲"
        elif ascending is False:
            suffix = "  ▼"
        self._tree.heading(col, text=f"{text}{suffix}", command=lambda c=col: self._on_sort(c))

    def _format_value(self, col, v):
        if v is None:
            return ""
        kind = self._col_meta[col]["kind"]
        if kind == "int":
            try:
                return f"{int(v):,}".replace(",", " ")  # espacio fino para miles
            except Exception:
                return str(v)
        if kind == "number":
            d = self._col_meta[col]["decimals"] or 2
            try:
                # miles con coma fina; ajusta si quieres estilo europeo
                s = f"{float(v):,.{d}f}"
                s = s.replace(",", " ")  # separador miles
                return s
            except Exception:
                return str(v)
        if kind == "date":
            return str(v)
        # texto
        return str(v)

    def _autosize_columns(self, sample_rows=300):
        """Mide encabezado y algunas celdas para un ancho adecuado."""
        font = tkfont.nametofont("TkDefaultFont")
        header_font = tkfont.nametofont("TkHeadingFont") if "TkHeadingFont" in tkfont.names() else font

        # recolectar muestras
        samples = {c: [c] for c in self._columns}  # arranca con el propio encabezado
        children = self._tree.get_children("")
        for i, iid in enumerate(children[:sample_rows]):
            vals = self._tree.item(iid, "values")
            for c, val in zip(self._columns, vals):
                samples[c].append(str(val))

        min_w = 80
        max_w = 380
        padding = 24  # margen visual

        for c in self._columns:
            # mide el más largo
            widths = [font.measure(s) for s in samples[c]]
            w = max(widths) + padding
            w = max(min_w, min(w, max_w))
            # encabezado algo más ancho si hace falta
            w_head = header_font.measure(c) + padding
            self._tree.column(c, width=max(w, w_head))

    # ---------- sort ----------
    def _on_sort(self, col):
        if self._df is None:
            return
        asc = self._sort_state.get(col, {}).get("ascending")
        # toggle: None -> True -> False -> True ...
        asc = True if asc is None else (not asc)
        self._sort_state[col] = {"ascending": asc}

        # pandas sort para estabilidad (aunque aquí ordenamos lo visual)
        # Ordenamos las filas VISIBLES del tree por la representación formateada,
        # para no re-crear el modelo entero.
        rows = []
        for iid in self._tree.get_children(""):
            item = self._tree.item(iid, "values")
            rows.append((iid, item))

        idx = self._columns.index(col)

        def _key(t):
            val = t[1][idx]
            # intenta numérico si corresponde
            kind = self._col_meta[col]["kind"]
            if kind in ("int", "number"):
                # elimina separadores finos y posibles espacios
                try:
                    s = str(val).replace(" ", "").replace(",", "")
                    return float(s)
                except Exception:
                    return math.inf
            return str(val)

        rows.sort(key=_key, reverse=(not asc))

        for i, (iid, _) in enumerate(rows):
            self._tree.move(iid, "", i)
            # re-aplicar zebra
            self._tree.item(iid, tags=("even",) if i % 2 == 0 else ("odd",))

        # actualizar flechas en headers (solo en la columna activa)
        for c in self._columns:
            self._set_header(c, text=c, ascending=self._sort_state.get(c, {}).get("ascending") if c == col else None)

    def _on_header_double_click(self, event):
        # Si doble click es sobre una cabecera, ordena por esa columna
        region = self._tree.identify("region", event.x, event.y)
        if region != "heading":
            return
        col_id = self._tree.identify_column(event.x)  # e.g. '#3'
        try:
            idx = int(col_id.lstrip("#")) - 1
            col = self._columns[idx]
        except Exception:
            return
        self._on_sort(col)

    # ---------- copiar al portapapeles ----------
    def _copy_selection(self, event=None):
        sel = self._tree.selection()
        if not sel:
            return "break"
        # exporta CSV con columnas visibles en orden
        lines = []
        lines.append(",".join(self._columns))
        for iid in sel:
            vals = [str(v) for v in self._tree.item(iid, "values")]
            # escapado básico CSV
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
