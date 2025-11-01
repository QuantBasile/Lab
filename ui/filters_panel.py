#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 31 23:29:39 2025

@author: fran
"""
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ui/filters_panel.py
import tkinter as tk
from tkinter import ttk
import pandas as pd
from pandas.api.types import (
    is_numeric_dtype, is_bool_dtype, is_datetime64_any_dtype
)
import math
# Calendario opcional
try:
    from tkcalendar import DateEntry
    HAS_TKCAL = True
except Exception:
    HAS_TKCAL = False





# -------------------- Dual list para categóricos (drag & drop) --------------------
class DualListCategorical(ttk.Frame):
    """
    Dos columnas: 'Disponibles' (izq) y 'Seleccionados' (der) con drag & drop.
    - Buscador para filtrar la lista izquierda.
    - Botones >> / << por accesibilidad.
    API:
      - get_selected() -> list[str]
      - reset()        -> limpia seleccionados y recarga disponibles
    """
    def __init__(self, master, values, *, height=10):
        super().__init__(master)
        self.all_values = sorted([str(v) for v in values])
        self._drag_data = {"source": None, "value": None}
        self._build(height)

    def _build(self, height):
        # Top: buscador
        top = ttk.Frame(self); top.pack(fill="x")
        ttk.Label(top, text="Buscar").pack(side="left")
        self.search_var = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.search_var, width=24)
        entry.pack(side="left", padx=(6, 0))
        self.search_var.trace_add("write", lambda *_: self._reload_available())

        body = ttk.Frame(self); body.pack(fill="both", expand=True, pady=(4, 0))

        # Izquierda (disponibles)
        left = ttk.Frame(body); left.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="Disponibles").pack(anchor="w", pady=(0, 4))
        self.lb_left  = tk.Listbox(left,  selectmode="extended", exportselection=False,
                           height=height, background="#ffffff", relief="solid", borderwidth=1)
        lsb = ttk.Scrollbar(left, orient="vertical", command=self.lb_left.yview)
        self.lb_left.configure(yscrollcommand=lsb.set)
        self.lb_left.pack(side="left", fill="both", expand=True)
        lsb.pack(side="right", fill="y")

        # Centro (botones)
        mid = ttk.Frame(body); mid.pack(side="left", padx=6)
        ttk.Button(mid, text=">>", command=self._move_right).pack(pady=(24, 6))
        ttk.Button(mid, text="<<", command=self._move_left).pack()

        # Derecha (seleccionados)
        right = ttk.Frame(body); right.pack(side="left", fill="both", expand=True)
        ttk.Label(right, text="Seleccionados (se aplican)").pack(anchor="w", pady=(0, 4))
        self.lb_right = tk.Listbox(right, selectmode="extended", exportselection=False,
                           height=height, background="#ffffff", relief="solid", borderwidth=1)
        rsb = ttk.Scrollbar(right, orient="vertical", command=self.lb_right.yview)
        self.lb_right.configure(yscrollcommand=rsb.set)
        self.lb_right.pack(side="left", fill="both", expand=True)
        rsb.pack(side="right", fill="y")

        self._reload_available()

        # Drag & Drop básico
        for lb in (self.lb_left, self.lb_right):
            lb.bind("<ButtonPress-1>", self._on_drag_start)
            lb.bind("<B1-Motion>", self._on_drag_motion)
            lb.bind("<ButtonRelease-1>", self._on_drag_drop)

    # --------- helpers de lista ---------
    def _fill(self, lb, items):
        lb.delete(0, "end")
        for v in items:
            lb.insert("end", v)

    def _listbox_items(self, lb):
        return [lb.get(i) for i in range(lb.size())]

    def _reload_available(self):
        q = self.search_var.get().strip().lower()
        current_right = set(self._listbox_items(self.lb_right))
        items = [v for v in self.all_values if (not q or q in v.lower()) and v not in current_right]
        self._fill(self.lb_left, items)

    def _move_right(self):
        sel = [self.lb_left.get(i) for i in self.lb_left.curselection()]
        if not sel:
            return
        right_items = set(self._listbox_items(self.lb_right))
        for v in sel:
            if v not in right_items:
                self.lb_right.insert("end", v)
        self._reload_available()

    def _move_left(self):
        sel_idx = list(self.lb_right.curselection())
        sel_idx.sort(reverse=True)
        for i in sel_idx:
            self.lb_right.delete(i)
        self._reload_available()

    # --------- Drag & Drop ---------
    def _on_drag_start(self, event):
        lb = event.widget
        idx = lb.nearest(event.y)
        if idx < 0:
            return
        self._drag_data["source"] = lb
        self._drag_data["value"] = lb.get(idx)

    def _on_drag_motion(self, event):
        # (opcional) resaltar destino o cambiar cursor
        pass

    def _on_drag_drop(self, event):
        src = self._drag_data["source"]
        val = self._drag_data["value"]
        self._drag_data = {"source": None, "value": None}
        if not src or val is None:
            return
        dst = event.widget
        if dst not in (self.lb_left, self.lb_right):
            return

        if src is self.lb_left and dst is self.lb_right:
            # mover izquierda -> derecha
            if val not in self._listbox_items(self.lb_right):
                self.lb_right.insert("end", val)
            self._reload_available()
        elif src is self.lb_right and dst is self.lb_left:
            # mover derecha -> izquierda
            items = self._listbox_items(self.lb_right)
            if val in items:
                idx = items.index(val)
                self.lb_right.delete(idx)
            self._reload_available()

    # --------- API público ---------
    def get_selected(self):
        return self._listbox_items(self.lb_right)

    def reset(self):
        self.lb_right.delete(0, "end")
        self._reload_available()


# ------------------------------ Panel principal de filtros ------------------------------
class FiltersPanel(ttk.Frame):
    """
    Panel dinámico de filtros por columna (orden del DataFrame).
      - Numéricos: min/max + "Restaurar"
      - Categóricos: dual-list con DnD (izq disponibles / der seleccionados)
      - Fechas: desde / hasta + "Limpiar"
    API:
      - build(df: pd.DataFrame)
      - get_filters() -> dict
      - reset()
    """
    
    COL_WIDTH = 520
    COL_HEIGHT = 200   # antes 220
    NUMERIC_HEIGHT = 140  # <- nuevo para numéricos compactos


    def __init__(self, master=None):
        super().__init__(master)
        self._controls = {}
        self._canvas = None
        self._inner = None
        self._styles()
        self._build_base()

    # ---------- Estilos ----------
    def _styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("CustomNotebook.Tab", padding=(18, 8), borderwidth=0)
        style.configure("FiltersBody.TFrame", background="#ffffff")
        style.configure("Filt.TLabelframe", padding=12, background="#ffffff")
        style.configure("Filt.TLabelframe.Label", padding=(6,0,6,0), background="#ffffff", foreground="#0b0b0b")
        style.configure("Filt.TEntry", padding=(4,2))
        style.configure("Hint.TLabel", foreground="#2563eb")






    # ---------- Base scroll horizontal ----------
    def _build_base(self):
        # Alto cómodo (3 filas visibles). El resto se verá con scroll vertical.
        initial_rows = 3
        initial_h = self.COL_HEIGHT * initial_rows + 60
    
        # --- Canvas con scroll horizontal y vertical ---
        self._canvas = tk.Canvas(
            self,
            background="#ffffff",
            borderwidth=0,
            highlightthickness=0,
            height=initial_h,
        )
        # barras de scroll
        vsb = ttk.Scrollbar(self, orient="vertical",   command=self._canvas.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self._canvas.xview)
        self._canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    
        # contenedor interno
        self._inner = ttk.Frame(self._canvas, style="FiltersBody.TFrame")
        # actualizar área scroll cuando cambie el tamaño del contenido
        self._inner.bind("<Configure>", lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._window_id = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
    
        # layout: canvas a la izquierda, vsb a la derecha, hsb abajo
        self._canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
    
        # --- Wheel bindings: rueda = vertical; Shift+rueda = horizontal ---
        def _on_mousewheel(event):
            # Windows/Mac usan event.delta; X11 usa Button-4/5
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
    
        # Windows/Mac
        self._canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self._canvas.bind_all("<Shift-MouseWheel>", _on_shift_mousewheel)
        # X11 (Linux)
        self._canvas.bind_all("<Button-4>", _on_mousewheel)
        self._canvas.bind_all("<Button-5>", _on_mousewheel)




    # ---------- Construcción dinámica ----------
    def build(self, df: pd.DataFrame):
        # limpiar
        for child in self._inner.winfo_children():
            child.destroy()
        self._controls.clear()
        

        cols = list(df.columns)
        ROWS = 3
        cols_per_row = math.ceil(len(cols) / ROWS)
        
        for i, col in enumerate(cols):
            r = i // cols_per_row
            c = i % cols_per_row
        
            colframe = ttk.LabelFrame(self._inner, text=col, style="Filt.TLabelframe")
            colframe.grid(row=r, column=c, padx=12, pady=12, sticky="nw")
            colframe.pack_propagate(False)
            # compacta numéricos con altura menor, el resto altura normal
            colframe.configure(width=self.COL_WIDTH, height=self.COL_HEIGHT)
        
            s = df[col]
            is_date_name = col.upper().endswith("DATE") or col.upper() in {"TRANSACTION_DATE", "EXPIRY"}
            if is_datetime64_any_dtype(s) or is_date_name:
                self._build_date(colframe, col)
            elif is_numeric_dtype(s) and not is_bool_dtype(s):
                self._build_numeric(colframe, col, s)
            else:
                self._build_categorical(colframe, col, s)


        # Recalcular scroll
        self._inner.update_idletasks()
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        self._canvas.xview_moveto(0.0)  # empieza mostrando la primera columna


    # ---------- Subcomponentes ----------
    def _build_date(self, parent, col):
        # Contenedor compacto (dos columnas)
        row = ttk.Frame(parent); row.pack(anchor="w", pady=(0, 4))
        ttk.Label(row, text="Desde").pack(side="left", padx=(0, 6))
    
        if HAS_TKCAL:
            start_var = tk.StringVar()
            start_w = DateEntry(row, width=12, date_pattern="yyyy-mm-dd", textvariable=start_var,
                    background="#e6f0ff", foreground="#000000", bordercolor="#cbd5ff",
                    headersbackground="#e6f0ff", normalbackground="#ffffff",
                    weekendbackground="#ffffff", othermonthbackground="#ffffff")
            start_w.pack(side="left")
        else:
            start_var = tk.StringVar()
            start_w = ttk.Entry(row, textvariable=start_var, width=12, style="Filt.TEntry")
            start_w.pack(side="left")
    
        row2 = ttk.Frame(parent); row2.pack(anchor="w", pady=(6, 0))
        ttk.Label(row2, text="Hasta").pack(side="left", padx=(0, 6))
    
        if HAS_TKCAL:
            end_var = tk.StringVar()
            end_w = DateEntry(row2, width=12, date_pattern="yyyy-mm-dd",
                              textvariable=end_var)
            end_w.pack(side="left")
        else:
            end_var = tk.StringVar()
            end_w = ttk.Entry(row2, textvariable=end_var, width=12, style="Filt.TEntry")
            end_w.pack(side="left")
    
        # Ayuda + limpiar
        ttk.Label(parent, text="Formato: YYYY-MM-DD", style="Hint.TLabel").pack(anchor="w", pady=(6, 0))
        ttk.Button(parent, text="Limpiar",
                   command=lambda: (start_var.set(""), end_var.set(""))
                   ).pack(anchor="w", pady=(8, 0))
    
        self._controls[col] = {"type": "date", "start": start_var, "end": end_var}

    def _build_numeric(self, parent, col, s: pd.Series):
        vmin, vmax = s.min(), s.max()
        min_var = tk.StringVar(value=str(vmin))
        max_var = tk.StringVar(value=str(vmax))
    
        # Reducir altura de la tarjeta numérica
        try:
            parent.configure(height=self.NUMERIC_HEIGHT)
        except Exception:   
            pass
    
        row = ttk.Frame(parent); row.pack(anchor="w", pady=(0, 2))
        ttk.Label(row, text="Min").pack(side="left", padx=(0, 4))
        ttk.Entry(row, textvariable=min_var, width=8, style="Filt.TEntry").pack(side="left", padx=(0, 8))
        ttk.Label(row, text="Max").pack(side="left", padx=(0, 4))
        ttk.Entry(row, textvariable=max_var, width=8, style="Filt.TEntry").pack(side="left")
    
        hint = ttk.Label(parent, text=f"Actual: [{vmin} … {vmax}]", style="Hint.TLabel")
        hint.pack(anchor="w", pady=(6, 0))
    
        ttk.Button(parent, text="Restaurar",
                   command=lambda: (min_var.set(str(vmin)), max_var.set(str(vmax)))
                   ).pack(anchor="w", pady=(6, 0))
    
        self._controls[col] = {"type": "numeric", "min": min_var, "max": max_var, "_bounds": (vmin, vmax)}


    def _build_categorical(self, parent, col, s: pd.Series):
        values = pd.Index(s.astype(str).unique()).dropna().tolist()
        dual = DualListCategorical(parent, values=values, height=10)
        dual.pack(fill="both", expand=True, padx=6, pady=2)

        self._controls[col] = {"type": "categorical", "dual": dual}

    # ---------- API pública ----------
    def get_filters(self) -> dict:
        spec = {}
        for col, ctrl in self._controls.items():
            t = ctrl["type"]
            if t == "numeric":
                vmin = ctrl["min"].get().strip()
                vmax = ctrl["max"].get().strip()
                vmin = float(vmin) if vmin != "" else None
                vmax = float(vmax) if vmax != "" else None
                if vmin is not None or vmax is not None:
                    spec[col] = {"type": "numeric", "min": vmin, "max": vmax}

            elif t == "categorical":
                sel = ctrl["dual"].get_selected()
                if sel:
                    spec[col] = {"type": "categorical", "values": sel}

            elif t == "date":
                start = ctrl["start"].get().strip()
                end = ctrl["end"].get().strip()
                if start or end:
                    spec[col] = {"type": "date", "start": start or None, "end": end or None}
        return spec

    def reset(self):
        for _, ctrl in self._controls.items():
            t = ctrl["type"]
            if t == "numeric":
                ctrl["min"].set("")
                ctrl["max"].set("")
            elif t == "categorical":
                ctrl["dual"].reset()
            elif t == "date":
                ctrl["start"].set("")
                ctrl["end"].set("")
