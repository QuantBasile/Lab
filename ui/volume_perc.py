# ui/volume_percentage.py
import tkinter as tk
from tkinter import ttk
import pandas as pd
import numpy as np

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.ticker as mticker
import matplotlib.dates as mdates


class VolumePercentage(ttk.Frame):
    """
    Dashboard de Volumen en Porcentaje (2x2):
      [0,0] Líneas % diario (cada emisor / total del día * 100)
      [0,1] Líneas % rolling 7d (media simple del % diario)
      [1,0] Barras % semanal (cada emisor / total de la semana * 100)
      [1,1] Barras % mensual (cada emisor / total del mes * 100)

    Requiere DAY, WEEK, MONTH ya precomputadas en el DF.
    """

    def __init__(self, master=None):
        super().__init__(master)
        self._df = None

        # Artistas por emisor
        self._lines_day = {}     # issuer -> Line2D (% diario)
        self._lines_roll = {}    # issuer -> Line2D (% rolling 7d)
        self._bars_week = {}     # issuer -> [Rectangles] (% semanal)
        self._bars_month = {}    # issuer -> [Rectangles] (% mensual)
        self._issuer_vars = {}   # issuer -> tk.BooleanVar
        self._issuer_checkwidgets = {}  # issuer -> Checkbutton

        # Base diaria para rolling
        self._issuers = []
        self._full_range = None
        self._daily_pct_per_issuer = {}  # issuer -> Series (% diario)

        self._build()

    # ---------------- UI build ----------------
    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        # Sidebar
        self.sidebar = tk.Frame(self, bg="#FFF4E5", bd=0, highlightthickness=0, width=140)
        self.sidebar.grid(row=1, column=0, sticky="nsw", padx=(6, 8), pady=(4, 6))
        self.sidebar.grid_propagate(False)
        self._build_sidebar()

        # Área de plots
        right = tk.Frame(self, bg="white", bd=0, highlightthickness=0)
        right.grid(row=1, column=1, sticky="nsew", padx=(0, 6), pady=(4, 6))
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        # Figura con 4 subplots (2x2)
        self.fig = Figure(figsize=(12, 6.6), dpi=100)
        gs = self.fig.add_gridspec(2, 2, height_ratios=[1, 1])

        self.ax_day   = self.fig.add_subplot(gs[0, 0])  # arriba izq (% diario)
        self.ax_roll  = self.fig.add_subplot(gs[0, 1])  # arriba dcha (% rolling 7d)
        self.ax_week  = self.fig.add_subplot(gs[1, 0])  # abajo izq (% semanal)
        self.ax_month = self.fig.add_subplot(gs[1, 1])  # abajo dcha (% mensual)
        self.fig.subplots_adjust(left=0.07, right=0.98, wspace=0.32, hspace=0.32, bottom=0.12, top=0.94)

        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.configure(bg="white", highlightthickness=0)
        self.canvas_widget.grid(row=1, column=0, sticky="nsew")

        # Toolbar
        self.toolbar = NavigationToolbar2Tk(self.canvas, right, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.grid(row=0, column=0, sticky="w", pady=(0, 6))
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

        # Botones globales
        btns = tk.Frame(self.sidebar, bg="#FFF4E5")
        btns.pack(fill="x", padx=4, pady=(0, 4))
        for text, cmd in (("Todos ON", self._all_on), ("Todos OFF", self._all_off)):
            tk.Button(
                btns, text=text, command=cmd, bg="white",
                relief="solid", bd=1, padx=4, pady=1, cursor="hand2"
            ).pack(fill="x", pady=(0, 6))

        # Lista scrolleable de emisores
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
        """Recibe DF filtrado (con DAY/WEEK/MONTH ya precomputadas) y redibuja."""
        self._df = df
        self._draw_all()

    # -------------- Drawing --------------
    def _draw_all(self):
        # Limpiar ejes y estados
        for ax in (self.ax_day, self.ax_roll, self.ax_week, self.ax_month):
            ax.clear()
        self._lines_day.clear()
        self._lines_roll.clear()
        self._bars_week.clear()
        self._bars_month.clear()
        self._daily_pct_per_issuer.clear()
        self._issuer_checkwidgets.clear()
        self._issuers = []
        self._full_range = None

        if self._df is None or self._df.empty:
            for ax in (self.ax_day, self.ax_roll, self.ax_week, self.ax_month):
                ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            self.canvas.draw_idle()
            return

        s = self._df.copy()
        if "ISSUER_NAME" in s.columns:
            s["ISSUER_NAME"] = s["ISSUER_NAME"].astype("category")

        # Issuers y rango diario
        self._issuers = sorted(s["ISSUER_NAME"].unique())
        self._full_range = pd.date_range(s["DAY"].min(), s["DAY"].max(), freq="D")

        # -------- % DIARIO POR EMISOR (base del rolling) --------
        tot_day = s.groupby("DAY", sort=False)["TXN_AMT"].sum().reindex(self._full_range).fillna(0.0)
        for iss in self._issuers:
            si = s[s["ISSUER_NAME"] == iss]
            daily_amt = si.groupby("DAY", sort=False)["TXN_AMT"].sum().reindex(self._full_range).fillna(0.0)
            pct = np.where(tot_day.values > 0.0, (daily_amt.values / tot_day.values) * 100.0, 0.0)
            self._daily_pct_per_issuer[iss] = pd.Series(pct, index=self._full_range)

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
            self._issuer_checkwidgets[iss] = cb

        # ==== [0,0] Líneas % diario ====
        for iss in self._issuers:
            series = self._daily_pct_per_issuer[iss]
            ln, = self.ax_day.plot(self._full_range, series.values, linewidth=1.3, label=iss)
            ln.set_visible(False)
            self._lines_day[iss] = ln
        self._format_date_axis_pct(self.ax_day, "Cuota diaria por emisor (% del total del día)")

        # ==== [0,1] Líneas % rolling 7 días ====
        for iss in self._issuers:
            daily_pct = self._daily_pct_per_issuer[iss]
            roll = pd.Series(daily_pct.values, index=self._full_range).rolling(window=7, min_periods=1).mean()
            ln, = self.ax_roll.plot(self._full_range, roll.values, linewidth=1.6, label=iss)
            ln.set_visible(False)
            self._lines_roll[iss] = ln
        self._format_date_axis_pct(self.ax_roll, "Media móvil 7 días (cuota %)")

        # Colorea toggles con color de rolling
        for iss, ln in self._lines_roll.items():
            color = ln.get_color()
            if iss in self._issuer_checkwidgets:
                try:
                    self._issuer_checkwidgets[iss].configure(fg=color, activeforeground=color, selectcolor="#FFF4E5")
                except Exception:
                    pass

        # ==== [1,0] Barras % semanales ====
        grouped_week = s.groupby(["WEEK", "ISSUER_NAME"], sort=False)["TXN_AMT"].sum().reset_index().sort_values("WEEK")
        pivot_w = grouped_week.pivot(index="WEEK", columns="ISSUER_NAME", values="TXN_AMT").fillna(0.0).sort_index()
        if not pivot_w.empty:
            row_sums = pivot_w.sum(axis=1).replace(0.0, np.nan)
            pct_w = pivot_w.div(row_sums, axis=0).fillna(0.0) * 100.0

            weeks = pct_w.index.to_pydatetime()
            n_weeks = len(weeks)
            n_iss = len(self._issuers)
            group_width = 0.85
            bar_width = group_width / max(n_iss, 1)
            x = np.arange(n_weeks)
            for i, iss in enumerate(self._issuers):
                offs = (i - (n_iss - 1) / 2.0) * bar_width
                vals = pct_w.get(iss)
                vals = vals.values if vals is not None else np.zeros(n_weeks)
                bars = self.ax_week.bar(x + offs, vals, width=bar_width, label=iss)
                # color coherente con rolling
                color = self._lines_roll.get(iss).get_color() if iss in self._lines_roll else None
                if color:
                    for b in bars:
                        b.set_color(color); b.set_alpha(0.85)
                for b in bars:
                    b.set_visible(False)
                self._bars_week[iss] = list(bars)
            week_labels = [f"{d.isocalendar().year}-W{d.isocalendar().week:02d}" for d in weeks]
            self.ax_week.set_xticks(x)
            self.ax_week.set_xticklabels(week_labels, rotation=45, ha="right")
            self._format_pct_axis(self.ax_week, "Cuota semanal por emisor (% del total semanal)")

        # ==== [1,1] Barras % mensuales ====
        grouped_month = s.groupby(["MONTH", "ISSUER_NAME"], sort=False)["TXN_AMT"].sum().reset_index().sort_values("MONTH")
        pivot_m = grouped_month.pivot(index="MONTH", columns="ISSUER_NAME", values="TXN_AMT").fillna(0.0).sort_index()
        if not pivot_m.empty:
            row_sums = pivot_m.sum(axis=1).replace(0.0, np.nan)
            pct_m = pivot_m.div(row_sums, axis=0).fillna(0.0) * 100.0

            months = pct_m.index.to_pydatetime()
            n_months = len(months)
            n_iss = len(self._issuers)
            group_width = 0.85
            bar_width = group_width / max(n_iss, 1)
            x = np.arange(n_months)
            for i, iss in enumerate(self._issuers):
                offs = (i - (n_iss - 1) / 2.0) * bar_width
                vals = pct_m.get(iss)
                vals = vals.values if vals is not None else np.zeros(n_months)
                bars = self.ax_month.bar(x + offs, vals, width=bar_width, label=iss)
                color = self._lines_roll.get(iss).get_color() if iss in self._lines_roll else None
                if color:
                    for b in bars:
                        b.set_color(color); b.set_alpha(0.85)
                for b in bars:
                    b.set_visible(False)
                self._bars_month[iss] = list(bars)
            self.ax_month.set_xticks(x)
            self.ax_month.set_xticklabels([dt.strftime("%Y-%m") for dt in months], rotation=45, ha="right")
            self._format_pct_axis(self.ax_month, "Cuota mensual por emisor (% del total mensual)")

        self.canvas.draw_idle()

    # ---------- helpers de formato ----------
    def _format_date_axis_pct(self, ax, title):
        locator = mdates.AutoDateLocator()
        formatter = mdates.AutoDateFormatter(locator)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)
        ax.yaxis.set_major_formatter(mticker.StrMethodFormatter('{x:,.0f}%'))
        ax.grid(True, alpha=0.3)
        ax.set_title(title)
        ax.set_xlabel(""); ax.set_ylabel("")
        # Ticks X rotados 45°, Y en posición recta (rot 0)
        ax.tick_params(axis="x", rotation=45)
        ax.tick_params(axis="y", rotation=0)

    def _format_pct_axis(self, ax, title):
        ax.yaxis.set_major_formatter(mticker.StrMethodFormatter('{x:,.0f}%'))
        ax.grid(True, axis="y", alpha=0.3)
        ax.set_title(title)
        ax.set_xlabel(""); ax.set_ylabel("")

    # ---- Sidebar actions ----
    def _toggle_issuer(self, issuer: str):
        on = bool(self._issuer_vars[issuer].get())
        ln_d = self._lines_day.get(issuer)
        if ln_d is not None:
            ln_d.set_visible(on)
        ln_r = self._lines_roll.get(issuer)
        if ln_r is not None:
            ln_r.set_visible(on)
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

    def get_issuer_color(self, issuer: str):
        ln = self._lines_roll.get(issuer) or self._lines_day.get(issuer)
        return ln.get_color() if ln else None
