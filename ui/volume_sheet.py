# ui/volume_sheet.py
import tkinter as tk
from tkinter import ttk
import pandas as pd
import numpy as np

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.ticker as mticker
import matplotlib.dates as mdates


class VolumeSheet(ttk.Frame):
    """
    Dashboard de Volumen:
      Fila 1 (span 2 col): Líneas de media móvil N días (selector N)
      Fila 2 (2 col): Barras semanales (izq) + Barras mensuales (dcha)
    Sidebar (naranja claro) con toggles de emisores y botones Todos ON/OFF.
    """

    def __init__(self, master=None):
        super().__init__(master)
        self._df = None

        # Visibilidad y artistas
        self._lines_roll = {}    # issuer -> Line2D
        self._bars_week = {}     # issuer -> [Rectangles]
        self._bars_month = {}    # issuer -> [Rectangles]
        self._issuer_vars = {}   # issuer -> tk.BooleanVar

        # Base para recomputar rolling
        self._issuers = []
        self._full_range = None                       # DatetimeIndex diario continuo
        self._daily_series_per_issuer = {}            # issuer -> Series index full_range

        self._build()

    # ---------------- UI build ----------------
    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        # Sidebar (estrecha, naranja claro)
        self.sidebar = tk.Frame(self, bg="#FFF4E5", bd=0, highlightthickness=0, width=140)
        self.sidebar.grid(row=1, column=0, sticky="nsw", padx=(6, 8), pady=(4, 6))
        self.sidebar.grid_propagate(False)
        self._build_sidebar()

        # Área de plots
        right = tk.Frame(self, bg="white", bd=0, highlightthickness=0)
        right.grid(row=1, column=1, sticky="nsew", padx=(0, 6), pady=(4, 6))
        right.rowconfigure(3, weight=1)
        right.columnconfigure(0, weight=1)

        # Barra superior con selector de ventana para rolling
        topbar = tk.Frame(right, bg="white")
        topbar.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        tk.Label(topbar, text="Media móvil (días):", bg="white").pack(side="left")
        self.window_var = tk.StringVar(value="7")
        self.window_combo = ttk.Combobox(
            topbar, textvariable=self.window_var,
            values=["1", "3", "7", "10", "21", "30"], width=4, state="readonly"
        )
        self.window_combo.pack(side="left", padx=(6, 0))
        self.window_combo.bind("<<ComboboxSelected>>", lambda e: self._recompute_rolling())
        apply_btn = tk.Button(
            topbar, text="Aplicar", bg="white",
            relief="solid", bd=1, padx=8, pady=2, cursor="hand2",
            command=self._recompute_rolling
        )
        apply_btn.pack(side="left", padx=(8, 0))
                
        

        # Figura con gridspec 2x2 (rolling ocupa toda la fila superior)
        self.fig = Figure(figsize=(12, 6.6), dpi=100)
        gs = self.fig.add_gridspec(2, 2, height_ratios=[1, 1])

        self.ax_roll  = self.fig.add_subplot(gs[0, :])   # fila completa
        self.ax_week  = self.fig.add_subplot(gs[1, 0])   # abajo izq
        self.ax_month = self.fig.add_subplot(gs[1, 1])   # abajo dcha
        self.fig.subplots_adjust(left=0.07, right=0.98, wspace=0.32, hspace=0.32, bottom=0.12, top=0.94)

        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.configure(bg="white", highlightthickness=0)
        self.canvas_widget.grid(row=3, column=0, sticky="nsew")

        # Toolbar (fondo blanco)
        self.toolbar = NavigationToolbar2Tk(self.canvas, right, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.grid(row=2, column=0, sticky="w", pady=(0, 6))
        try:
            self.toolbar.configure(background="white")
            for w in self.toolbar.winfo_children():
                try:
                    w.configure(background="white")
                except Exception:
                    pass
        except Exception:
            pass

    def _build_sidebar(self):
        title = tk.Label(self.sidebar, text="Emisores", bg="#FFF4E5", fg="#7A3E00",
                         font=("Segoe UI Semibold", 10))
        title.pack(anchor="w", padx=4, pady=(4, 2))

        # Botones globales (pequeños y en columna)
        btns = tk.Frame(self.sidebar, bg="#FFF4E5")
        btns.pack(fill="x", padx=4, pady=(0, 4))
        for text, cmd in (("Todos ON", self._all_on), ("Todos OFF", self._all_off)):
            tk.Button(
                btns, text=text, command=cmd, bg="white",
                relief="solid", bd=1, padx=4, pady=1, cursor="hand2"
            ).pack(fill="x", pady=(0, 6))

        # Lista scrolleable de emisores (estrecha)
        list_container = tk.Frame(self.sidebar, bg="#FFF4E5")
        list_container.pack(fill="both", expand=True, padx=4, pady=(2, 6))

        self._issuer_canvas = tk.Canvas(list_container, borderwidth=0, highlightthickness=0,
                                        bg="#FFF4E5", width=128)
        vsb = ttk.Scrollbar(list_container, orient="vertical", command=self._issuer_canvas.yview)
        self._issuer_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._issuer_inner = tk.Frame(self._issuer_canvas, bg="#FFF4E5")
        self._issuer_canvas.create_window((0, 0), window=self._issuer_inner, anchor="nw")
        self._issuer_inner.bind("<Configure>", lambda e: self._issuer_canvas.configure(
            scrollregion=self._issuer_canvas.bbox("all")))
        self._issuer_canvas.pack(side="left", fill="both", expand=True)

        self._issuer_checks_parent = self._issuer_inner

    # -------------- API ----------------
    def update_plot(self, df: pd.DataFrame):
        """Recibe el DF FILTRADO y (re)construye composición + datos."""
        self._df = df
        self._draw_all()

    # -------------- Drawing --------------
    def _draw_all(self):
        # Limpiar ejes y estados
        for ax in (self.ax_roll, self.ax_week, self.ax_month):
            ax.clear()
        self._lines_roll.clear()
        self._bars_week.clear()
        self._bars_month.clear()
        self._daily_series_per_issuer.clear()
        self._issuers = []
        self._full_range = None

        if self._df is None or self._df.empty:
            for ax in (self.ax_roll, self.ax_week, self.ax_month):
                ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            self.canvas.draw()
            return

        s = self._df.copy()
        s["TRANSACTION_DATE"] = pd.to_datetime(s["TRANSACTION_DATE"], errors="coerce")
        s = s.dropna(subset=["TRANSACTION_DATE"])
        if s.empty:
            for ax in (self.ax_roll, self.ax_week, self.ax_month):
                ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            self.canvas.draw()
            return

        # ==== Preparación común ====
        s["DAY"] = s["TRANSACTION_DATE"].dt.normalize()
        s["MONTH"] = s["TRANSACTION_DATE"].dt.to_period("M").apply(lambda r: r.start_time)
        s["WEEK"]  = s["TRANSACTION_DATE"].dt.to_period("W-MON").apply(lambda r: r.start_time)

        self._issuers = sorted(s["ISSUER_NAME"].unique())
        self._full_range = pd.date_range(s["DAY"].min(), s["DAY"].max(), freq="D")

        # Series diarias por emisor (para recomputar rolling con cualquier ventana)
        for iss in self._issuers:
            si = s[s["ISSUER_NAME"] == iss]
            daily = si.groupby("DAY")["TXN_AMT"].sum().reindex(self._full_range).fillna(0.0)
            self._daily_series_per_issuer[iss] = daily

        # Sidebar toggles (todos OFF)
        for w in self._issuer_checks_parent.winfo_children():
            w.destroy()
        self._issuer_vars.clear()
        for iss in self._issuers:
            var = tk.BooleanVar(value=False)
            cb = tk.Checkbutton(self._issuer_checks_parent, text=iss, variable=var,
                                bg="#FFF4E5", activebackground="#FFF4E5",
                                anchor="w", padx=4, pady=1, relief="flat",
                                command=lambda i=iss: self._toggle_issuer(i))
            cb.pack(fill="x", padx=0, pady=1)
            self._issuer_vars[iss] = var

        # ==== Rolling (línea) ====
        self._plot_rolling(initial=True)

        # ==== Barras semanales ====
        grouped_week = s.groupby(["WEEK", "ISSUER_NAME"])["TXN_AMT"].sum().reset_index().sort_values(by="WEEK")
        pivot_w = grouped_week.pivot(index="WEEK", columns="ISSUER_NAME", values="TXN_AMT").fillna(0.0).sort_index()
        if not pivot_w.empty:
            weeks = pivot_w.index.to_pydatetime()
            n_weeks = len(weeks)
            n_iss = len(self._issuers)
            group_width = 0.85
            bar_width = group_width / max(n_iss, 1)
            x = np.arange(n_weeks)
            for i, iss in enumerate(self._issuers):
                offs = (i - (n_iss - 1) / 2.0) * bar_width
                series = pivot_w.get(iss)
                vals = series.values if series is not None else np.zeros(n_weeks)
                bars = self.ax_week.bar(x + offs, vals, width=bar_width, label=iss)
                for b in bars:
                    b.set_visible(False)
                self._bars_week[iss] = list(bars)
            week_labels = [f"{d.isocalendar().year}-W{d.isocalendar().week:02d}" for d in weeks]
            self.ax_week.set_xticks(x)
            self.ax_week.set_xticklabels(week_labels, rotation=25, ha="right")
            self._format_axes(self.ax_week, title="Volumen por semana (Σ TXN_AMT)")

        # ==== Barras mensuales ====
        grouped_month = s.groupby(["MONTH", "ISSUER_NAME"])["TXN_AMT"].sum().reset_index().sort_values(by="MONTH")
        pivot_m = grouped_month.pivot(index="MONTH", columns="ISSUER_NAME", values="TXN_AMT").fillna(0.0).sort_index()
        if not pivot_m.empty:
            months = pivot_m.index.to_pydatetime()
            n_months = len(months)
            n_iss = len(self._issuers)
            group_width = 0.85
            bar_width = group_width / max(n_iss, 1)
            x = np.arange(n_months)
            for i, iss in enumerate(self._issuers):
                offs = (i - (n_iss - 1) / 2.0) * bar_width
                series = pivot_m.get(iss)
                vals = series.values if series is not None else np.zeros(n_months)
                bars = self.ax_month.bar(x + offs, vals, width=bar_width, label=iss)
                for b in bars:
                    b.set_visible(False)
                self._bars_month[iss] = list(bars)
            self.ax_month.set_xticks(x)
            self.ax_month.set_xticklabels([dt.strftime("%Y-%m") for dt in months], rotation=25, ha="right")
            self._format_axes(self.ax_month, title="Volumen por mes (Σ TXN_AMT)")

        self.canvas.draw()

    # ---- Rolling helpers ----
    def _plot_rolling(self, initial=False):
        """Dibuja / actualiza el plot rolling según la ventana actual."""
        window = int(self.window_var.get())
        self.ax_roll.clear()

        locator = mdates.AutoDateLocator()
        formatter = mdates.AutoDateFormatter(locator)
        self.ax_roll.xaxis.set_major_locator(locator)
        self.ax_roll.xaxis.set_major_formatter(formatter)
        self.ax_roll.yaxis.set_major_formatter(mticker.StrMethodFormatter('{x:,.0f}'))
        self.ax_roll.tick_params(axis="y", labelrotation=45)
        self.ax_roll.grid(True, alpha=0.3)
        self.ax_roll.set_title(f"Media móvil {window} días (Σ TXN_AMT)")

        # líneas por emisor (conservar visibilidad si no es inicial)
        for iss in self._issuers:
            daily = self._daily_series_per_issuer[iss]
            roll = daily.rolling(window=window, min_periods=1).mean()
            ln, = self.ax_roll.plot(self._full_range, roll.values, linewidth=1.6, label=iss)
            if initial:
                ln.set_visible(False)  # todos OFF al inicio
            else:
                ln.set_visible(bool(self._issuer_vars.get(iss, tk.BooleanVar(False)).get()))
            self._lines_roll[iss] = ln

        # autoformato de fechas
        self.fig.autofmt_xdate(rotation=25)

    def _recompute_rolling(self):
        """Recalcula solo el gráfico rolling al cambiar la ventana."""
        if self._df is None or self._full_range is None:
            return
        # Guarda visibilidad actual para respetarla tras redibujar
        vis = {iss: bool(var.get()) for iss, var in self._issuer_vars.items()}
        self._plot_rolling(initial=False)
        # Reaplica visibilidad
        for iss, on in vis.items():
            ln = self._lines_roll.get(iss)
            if ln is not None:
                ln.set_visible(on)
        self.canvas.draw_idle()

    # ---------- helpers de formato ----------
    def _format_axes(self, ax, title):
        ax.yaxis.set_major_formatter(mticker.StrMethodFormatter('{x:,.0f}'))
        ax.grid(True, axis="y", alpha=0.3)
        ax.set_title(title)
        # Sin etiquetas de ejes (solo ticks)
        ax.set_xlabel("")
        ax.set_ylabel("")

    # ---- Sidebar actions ----
    def _toggle_issuer(self, issuer: str):
        """Mostrar/ocultar un emisor en los 3 gráficos según el toggle."""
        on = bool(self._issuer_vars[issuer].get())
        # línea rolling
        ln = self._lines_roll.get(issuer)
        if ln is not None:
            ln.set_visible(on)
        # barras
        for b in self._bars_week.get(issuer, []):
            b.set_visible(on)
        for b in self._bars_month.get(issuer, []):
            b.set_visible(on)
        self.canvas.draw_idle()

    def _all_on(self):
        for iss, var in self._issuer_vars.items():
            if not var.get():
                var.set(True)
                self._toggle_issuer(iss)

    def _all_off(self):
        for iss, var in self._issuer_vars.items():
            if var.get():
                var.set(False)
                self._toggle_issuer(iss)
