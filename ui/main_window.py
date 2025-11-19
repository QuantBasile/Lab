import tkinter as tk
from tkinter import ttk, messagebox
#from tkcalendar import DateEntry    
from services.data_service import DataService
from ui.filters_panel import FiltersPanel
from ui.table_widget import TableFrame
from ui.volume_sheet import VolumeSheet
from ui.volume_summary import VolumeSummary
from ui.volume_perc import VolumePercentage
from ui.volume_table import VolumeTable
from ui.call_put_share import CallPutShare
from ui.call_put_rolling import CallPutRolling
from ui.hsbc_marktanteil import HSBCMarktanteil
from ui.top20_names import Top20Names
from ui.simple_calendar import SimpleDateEntry as DateEntry
import traceback
from datetime import date, timedelta  


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

        # ======== Shell sin sidebar ========
        shell = ttk.Frame(self, style="Card.TFrame")
        shell.pack(side="top", fill="both", expand=True, padx=12, pady=12)
        
        # --- Content (ocupa todo el espacio) ---
        content = ttk.Frame(shell, style="Card.TFrame")
        content.pack(side="left", fill="both", expand=True)

        inner = ttk.Frame(content, style="CardInner.TFrame")
        inner.pack(fill="both", expand=True)
        

        # === Actions Row: fechas + tipo de producto ===
        actions = ttk.Frame(inner, style="Actions.TFrame")
        actions.pack(side="top", fill="x", padx=10, pady=8)
        
        # Fechas con DateEntry (tkcalendar o SimpleDateEntry)
        ttk.Label(actions, text="Von:").pack(side="left")
        self.von_var = tk.StringVar()
        self.von_date = DateEntry(
            actions,
            textvariable=self.von_var,
            date_pattern="yyyy-mm-dd",
            width=12,
        )
        self._style_green(self.von_date)   # <<< NUEVO
        self.von_date.pack(side="left", padx=(4, 10))
        
        ttk.Label(actions, text="Bis:").pack(side="left")
        self.bis_var = tk.StringVar()
        self.bis_date = DateEntry(
            actions,
            textvariable=self.bis_var,
            date_pattern="yyyy-mm-dd",
            width=12,
        )
        self._style_green(self.bis_date)   # <<< NUEVO
        self.bis_date.pack(side="left", padx=(4, 16))
        
        # Valores por defecto: últimos 90 días
        today = date.today()
        self.bis_date.set_date(today)
        self.von_date.set_date(today - timedelta(days=90))

        
        # Botones de generación (input) en lila claro
        btn_input_kwargs = dict(
            bg="#e9d5ff",
            fg="#000000",
            activebackground="#ddd6fe",
            relief="flat",
            padx=10,
            pady=5,
            cursor="hand2",
        )
        
        self.btn_alle = tk.Button(
            actions,
            text="Alle",
            command=lambda: self.on_generate("ALLE"),
            **btn_input_kwargs,
        )
        self.btn_alle.pack(side="left", padx=(0, 6))
        
        self.btn_turbo = tk.Button(
            actions,
            text="Turbo",
            command=lambda: self.on_generate("TURBO"),
            **btn_input_kwargs,
        )
        self.btn_turbo.pack(side="left", padx=(0, 6))
        
        self.btn_vanilla = tk.Button(
            actions,
            text="Vanilla",
            command=lambda: self.on_generate("VANILLA"),
            **btn_input_kwargs,
        )
        self.btn_vanilla.pack(side="left", padx=(0, 12))

        
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


        tab_callput = ttk.Frame(self.nb, style="CardInner.TFrame")
        self.call_put_share = CallPutShare(tab_callput)
        self.call_put_share.pack(side="top", fill="both", expand=True)
        self.nb.add(tab_callput, text="CALL/PUT share")
        
        tab_cproll = ttk.Frame(self.nb, style="CardInner.TFrame")
        self.call_put_rolling = CallPutRolling(tab_cproll)
        self.call_put_rolling.pack(side="top", fill="both", expand=True)
        self.nb.add(tab_cproll, text="CALL/PUT rolling 7d")
        
        tab_hsbc = ttk.Frame(self.nb)
        self.hsbc_marktanteil = HSBCMarktanteil(tab_hsbc)
        self.hsbc_marktanteil.pack(fill="both", expand=True)
        self.nb.add(tab_hsbc, text="HSBC Marktanteil")
        
        tab_top20 = ttk.Frame(self.nb)
        self.top20_sheet = Top20Names(tab_top20)
        self.top20_sheet.pack(fill="both", expand=True)
        self.nb.add(tab_top20, text="Top 20 Names")



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
    def on_generate(self, produktart):
        """Genera datos usando las fechas seleccionadas y el tipo de producto."""
        von = (self.von_var.get() or "").strip() or None
        bis = (self.bis_var.get() or "").strip() or None

        # Desactivar botones de entrada mientras se genera
        for btn in (self.btn_alle, self.btn_turbo, self.btn_vanilla):
            btn.config(state="disabled")
        self.update_idletasks()

        try:
            df = self.service.generate_fake_transactions(
                von=von,
                bis=bis,
                produktart=produktart,
                n_rows=1_000_000,   # ajusta si quieres menos filas
            )
        except Exception:
            traceback.print_exc()
            messagebox.showerror("Fehler", "Die Daten konnten nicht generiert werden.")
            return
        finally:
            for btn in (self.btn_alle, self.btn_turbo, self.btn_vanilla):
                btn.config(state="normal")

        # Reconstruir filtros y refrescar todas las vistas
        self.filters_panel.build(df)
        self._show_filters()
    
        # Activar botones
        self.btn_apply.config(state="normal")
        self.btn_clear.config(state="normal")
    
        # 🔹 Simular clic automático en el botón "Borrar filtros"
        try:
            # Si el botón tiene asignado un comando (normalmente _on_clear_clicked)
            if hasattr(self.btn_clear, "invoke"):
                self.btn_clear.invoke()  # esto ejecuta el mismo callback del botón
            else:
                # Fallback si no existe invoke (raro)
                if hasattr(self.filters_panel, "_on_clear_clicked"):
                    self.filters_panel._on_clear_clicked()
        except Exception as e:
            print(f"[on_generate] Error al ejecutar auto-clear: {e}")
    
        # 🔹 Finalmente refrescar la vista principal
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
        # No recalcules todo, simplemente aplica filtros vacíos
        self.service.apply_filters({})
        self._refresh_views()


    def _refresh_views(self):
        df_view = self.service.dataframe_filtered.head(self.MAX_DISPLAY).copy()
        self.table.show_dataframe(df_view)

        df_full = self.service.dataframe_filtered
        self.volume_sheet.update_plot(df_full)
        self.volume_summary.update_view(df_full)
        self.volume_percentage.update_plot(df_full)
        self.volume_table.update_view(df_full)
        self.call_put_share.update_plot(df_full)
        self.call_put_rolling.update_plot(df_full)
        self.hsbc_marktanteil.update_plot(df_full)
        self.top20_sheet.update_plot(df_full)

        
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

    def _style_green(self, date_entry):
        """Aplica fondo verde claro al widget SimpleDateEntry."""
        try:
            date_entry.entry.configure(
                background="#E6F4EA",
                foreground="#000000",
            )
            date_entry.btn.configure(
                background="#E6F4EA",
                activebackground="#C7DFC9",
            )
        except Exception:
            pass
