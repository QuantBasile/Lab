import tkinter as tk
from tkinter import ttk, messagebox
from services.data_service import DataService
from ui.filters_panel import FiltersPanel
from ui.table_widget import TableFrame
from ui.volume_sheet import VolumeSheet
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
        self.btn_toggle_filters.config(state="disabled")
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


        # Panel de filtros (ocultable)
        self.filters_wrap = ttk.Frame(inner, style="Card.TFrame")
        self.filters_panel = FiltersPanel(self.filters_wrap)
        
        # Notebook con tabs
        self.nb = ttk.Notebook(inner, style="CustomNotebook")
        self.nb.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Tab 0: Table
        tab_table = ttk.Frame(self.nb)
        self.table = TableFrame(tab_table)
        self.table.pack(fill="both", expand=True)
        self.nb.add(tab_table, text="Tabla")

        # Tab 1: Volume
        tab_volume = ttk.Frame(self.nb)
        self.volume_sheet = VolumeSheet(tab_volume)
        self.volume_sheet.pack(fill="both", expand=True)
        self.nb.add(tab_volume, text="Volumen")

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
        if not self.filters_wrap.winfo_manager():
            # filtros a pantalla “grande”
            self.filters_wrap.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 8))
            self.filters_panel.pack(side="top", fill="both", expand=True)
            self.btn_toggle_filters.configure(text="Ocultar filtros ▲")
        # el notebook cede espacio
        self.nb.pack_configure(expand=False)
        self.btn_toggle_filters.config(state="normal")
    
    def _hide_filters(self):
        if self.filters_wrap.winfo_manager():
            self.filters_wrap.pack_forget()
            self.btn_toggle_filters.configure(text="Mostrar filtros ▼")
        # el notebook vuelve a ocupar todo
        self.nb.pack_configure(expand=True)


    def _toggle_filters(self):
        if self.filters_wrap.winfo_manager():
            self._hide_filters()
        else:
            self._show_filters()

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
