import tkinter as tk
from tkinter import ttk, messagebox
from services.data_service import DataService
from ui.filters_panel import FiltersPanel
from ui.table_widget import TableFrame
from ui.volume_sheet import VolumeSheet
from ui.volume_summary import VolumeSummary
from ui.volume_perc import VolumePercentage
from ui.volume_table import VolumeTable
import traceback


class MainWindow(tk.Frame):
    MAX_DISPLAY = 1000

    def __init__(self, master=None):
        super().__init__(master)
        self.service = DataService()
        self._build_ui()

    def _build_ui(self):
        # ======== Topbar ========
        topbar = ttk.Frame(self, style="Topbar.TFrame")
        topbar.pack(side="top", fill="x")
        ttk.Label(topbar, text="Marktanteil Dashboard", style="Topbar.TLabel").pack(side="left", padx=12, pady=10)

        # ======== Shell con sidebar + content ========
        shell = ttk.Frame(self, style="Card.TFrame")
        shell.pack(side="top", fill="both", expand=True, padx=12, pady=12)

        # donde creas el sidebar:
        sidebar = ttk.Frame(shell, style="Sidebar.TFrame", width=220)
        sidebar.pack(side="left", fill="y"); sidebar.pack_propagate(False)
        
        # cabecera de navegación (reemplaza el Label actual):
        ttk.Label(sidebar, text="Navigation", style="SidebarHeader.TLabel"
                 ).pack(anchor="w", padx=12, pady=(12, 6))

        self.btn_nav_table = ttk.Button(sidebar, text="📄  Table", style="Nav.TButton",
                                        command=lambda: self._nav_select(0))
        self.btn_nav_table.pack(fill="x", padx=12, pady=4)

        self.btn_nav_volume = ttk.Button(sidebar, text="📈  Volume (Σ TXN_AMT)", style="Nav.TButton",
                                         command=lambda: self._nav_select(1))
        self.btn_nav_volume.pack(fill="x", padx=12, pady=4)

        # --- Content (todo lo demás aquí) ---
        content = ttk.Frame(shell, style="Card.TFrame")
        content.pack(side="left", fill="both", expand=True, padx=(12, 0))

        inner = ttk.Frame(content, style="CardInner.TFrame")
        inner.pack(fill="both", expand=True)
        
        
        

        # === Actions Row: todo en una sola línea (tk.Button con color real) ===
        actions = ttk.Frame(inner, style="Actions.TFrame")
        actions.pack(side="top", fill="x", padx=10, pady=8)
        
        ttk.Label(actions, text="Filas a generar:").pack(side="left")
        self.rows_var = tk.IntVar(value=1_000_000)
        self.rows_spin = ttk.Spinbox(actions, from_=10, to=5_000_000, increment=50_000,
                                     textvariable=self.rows_var, width=10)
        self.rows_spin.pack(side="left", padx=(6, 12))
        
        self.btn_generate = tk.Button(
            actions, text="Generar datos (3 meses)",
            bg="#2563eb", fg="white", activebackground="#1d4ed8",
            relief="flat", padx=12, pady=6, command=self.on_generate, cursor="hand2"
        )
        self.btn_generate.pack(side="left", padx=(0, 12))
        
        self.btn_toggle_filters = tk.Button(
            actions, text="Ocultar filtros ▲",
            bg="#e0ecff", fg="#0b0b0b", activebackground="#cfe2ff",
            relief="flat", padx=10, pady=5, command=self._toggle_filters, cursor="hand2"
        )
        #self.btn_toggle_filters.config(state="disabled")
        self.btn_toggle_filters.pack(side="left", padx=(0, 12))
        
        self.btn_apply = tk.Button(
            actions, text="Aplicar filtros",
            bg="#2563eb", fg="white", activebackground="#1d4ed8",
            relief="flat", padx=12, pady=6, command=self.on_apply_filters, cursor="hand2"
        )
        self.btn_apply.config(state="disabled")
        self.btn_apply.pack(side="left")
        
        self.btn_clear = tk.Button(
            actions, text="Borrar filtros",
            bg="#e0ecff", fg="#0b0b0b", activebackground="#cfe2ff",
            relief="flat", padx=10, pady=5, command=self.on_clear_filters, cursor="hand2"
        )

        self.btn_clear.config(state="disabled")
        self.btn_clear.pack(side="left", padx=(8, 0))


        # --- Splitter vertical: filtros arriba / notebook abajo ---
        self.split = ttk.Panedwindow(inner, orient="vertical")
        self.split.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Pane 1: filtros (wrap + panel dentro)
        self.filters_wrap = ttk.Frame(self.split, style="Card.TFrame")
        self.filters_panel = FiltersPanel(self.filters_wrap)
        
        # MUY IMPORTANTE: empaca el panel dentro del wrap
        self.filters_panel.pack(side="top", fill="both", expand=True)
        
        # Pane 2: notebook (metemos el notebook dentro de un wrap)
        self.nb_wrap = ttk.Frame(self.split, style="Card.TFrame")
        self.nb = ttk.Notebook(self.nb_wrap, style="CustomNotebook")
        self.nb.pack(side="top", fill="both", expand=True)
        
        # Añadir panes al splitter con pesos y minsize
        self.split.add(self.filters_wrap, weight=1)         # filtros crecen/encogen
        self.split.add(self.nb_wrap, weight=3)              # notebook ocupa más
        #self.split.paneconfigure(self.filters_wrap, minsize=120)  # altura mínima de filtros
        #self.split.paneconfigure(self.nb_wrap,      minsize=200)
        
        # Tabs como tenías:
        tab_table = ttk.Frame(self.nb)
        self.table = TableFrame(tab_table); self.table.pack(fill="both", expand=True)
        self.nb.add(tab_table, text="Tabla")
        
        tab_volume = ttk.Frame(self.nb)
        self.volume_sheet = VolumeSheet(tab_volume)
        self.volume_sheet.pack(fill="both", expand=True)
        self.nb.add(tab_volume, text="Volumen")
        
        tab_volsum = ttk.Frame(self.nb, style="CardInner.TFrame")
        self.volume_summary = VolumeSummary(tab_volsum)
        self.volume_summary.pack(side="top", fill="both", expand=True)
        self.nb.add(tab_volsum, text="Volumen-summary")
        
        tab_volpct = ttk.Frame(self.nb, style="CardInner.TFrame")
        self.volume_percentage = VolumePercentage(tab_volpct)
        self.volume_percentage.pack(side="top", fill="both", expand=True)
        self.nb.add(tab_volpct, text="Volumen-%")
        
        
        tab_vtable = ttk.Frame(self.nb, style="CardInner.TFrame")
        self.volume_table = VolumeTable(tab_vtable)
        self.volume_table.pack(side="top", fill="both", expand=True)
        self.nb.add(tab_vtable, text="volumen_tabla")


        


        # Selección por defecto en sidebar
        self._nav_set_active(self.btn_nav_table)

    # ====== Sidebar helpers ======
    def _nav_select(self, index: int):
        self.nb.select(index)
        if index == 0:
            self._nav_set_active(self.btn_nav_table)
        else:
            self._nav_set_active(self.btn_nav_volume)

    def _nav_set_active(self, btn_active):
        # Reset look
        for b in (self.btn_nav_table, self.btn_nav_volume):
            b.configure(style="Nav.TButton")
        # Emular activo: color de fondo suave
        btn_active.configure(style="Nav.TButton")

    # ====== Filtros toggle ======
    def _show_filters(self):
        # si ya está presente, nada
        panes = self.split.panes()
        if str(self.filters_wrap) in panes:
            return
        # reinsertar arriba y restaurar altura previa si la guardamos
        self.split.insert(0, self.filters_wrap)
        self.split.paneconfigure(self.filters_wrap, weight=1, minsize=120)
        try:
            if hasattr(self, "_last_sash"):
                self.split.sashpos(0, self._last_sash)
        except Exception:
            pass
        self.btn_toggle_filters.configure(text="Ocultar filtros ▲", state="normal")
    
    def _hide_filters(self):
        # guarda la posición del sash antes de ocultar
        try:
            self._last_sash = self.split.sashpos(0)
        except Exception:
            self._last_sash = None
        try:
            self.split.forget(self.filters_wrap)
        except Exception:
            pass
        self.btn_toggle_filters.configure(text="Mostrar filtros ▼", state="normal")


    # ====== Lógica ======
    def on_generate(self):
            n_rows = int(self.rows_var.get())
            self.btn_generate.config(state="disabled")
            self.update_idletasks()
            try:
                df = self.service.generate_fake_transactions(n_rows=n_rows)
            except Exception:
                traceback.print_exc()
                messagebox.showerror("Error", "No se pudieron generar los datos.")
                return
            finally:
                self.btn_generate.config(state="normal")
        
            self.filters_panel.build(df)
            self._show_filters()
            self.btn_apply.config(state="normal")
            self.btn_clear.config(state="normal")
            self._refresh_views()


    def on_apply_filters(self):
        try:
            spec = self.filters_panel.get_filters()
            self.service.apply_filters(spec)
        except Exception:
            traceback.print_exc()
            messagebox.showerror("Error", "Falló la aplicación de filtros.")
            return
        self._refresh_views()

    def on_clear_filters(self):
        self.filters_panel.reset()
        self.service.clear_filters()
        self._refresh_views()

    def _refresh_views(self):
        df_view = self.service.dataframe_filtered.head(self.MAX_DISPLAY).copy()
        self.table.show_dataframe(df_view)

        df_full = self.service.dataframe_filtered
        self.volume_sheet.update_plot(df_full)
        color_resolver = getattr(self.volume_sheet, "get_issuer_color", None)
        self.volume_summary.update_view(df_full, color_resolver=color_resolver)
        self.volume_percentage.update_plot(df_full)
        self.volume_table.update_view(df_full)
        
    def _get_split_height(self):
        """Altura útil del panedwindow para calcular mitad. Usa bbox del pane 0."""
        try:
            # bbox del primer sash: (x1, y1, x2, y2)
            # Pero a veces bbox no está; como fallback usa altura del contenedor 'inner'
            self.update_idletasks()
            h = self.split.winfo_height()
            if h <= 1 and hasattr(self, "inner"):
                h = self.inner.winfo_height()
            return max(100, h)  # evita cero
        except Exception:
            return 600  # fallback razonable
    
    def _set_filters_height_px(self, pixels: int):
        """Coloca el sash en una posición tal que el pane superior (filtros) mida 'pixels'."""
        try:
            self.update_idletasks()
            # sashpos(0, y) fija la posición vertical del primer separador
            self.split.sashpos(0, max(0, int(pixels)))
        except Exception:
            pass
    
    def _show_filters_half(self):
        """Muestra filtros con ~50% de alto."""
        total_h = self._get_split_height()
        target = int(total_h * 0.5)
        # guarda última altura “buena”
        self._last_filters_px = target
        self._set_filters_height_px(target)
        self.btn_toggle_filters.configure(text="Ocultar filtros ▲")
    
    def _hide_filters_collapse(self):
        """Colapsa filtros: altura mínima (respeta minsize del pane si existe)."""
        # intenta respetar minsize configurado; si no, usa 0 + un pequeño margen
        try:
            pane_conf = self.split.pane(self.filters_wrap)
            minsize = int(pane_conf.get("minsize", 0))
        except Exception:
            minsize = 0
        target = minsize  # colapsado
        self._set_filters_height_px(target)
        self.btn_toggle_filters.configure(text="Mostrar filtros ▼")
    
    def _toggle_filters(self):
        """Alterna entre colapsado y mitad de página."""
        self.update_idletasks()
        current = self.split.sashpos(0)
        # heurística: si está casi colapsado => expandir a mitad;
        # si no, colapsar.
        try:
            pane_conf = self.split.pane(self.filters_wrap)
            minsize = int(pane_conf.get("minsize", 0))
        except Exception:
            minsize = 0
    
        near_collapsed = (current <= minsize + 4)
        if near_collapsed:
            # usa la última altura buena si existe; si no, mitad
            target = getattr(self, "_last_filters_px", int(self._get_split_height() * 0.5))
            self._set_filters_height_px(target)
            self.btn_toggle_filters.configure(text="Ocultar filtros ▲")
        else:
            # guarda la altura actual como “buena” antes de colapsar
            self._last_filters_px = current
            self._hide_filters_collapse()

