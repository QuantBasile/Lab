# ui/volume_sheet.py
# ui/volume_sheet.py
import tkinter as tk
from tkinter import ttk
import pandas as pd
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


class VolumeSheet(ttk.Frame):
    """
    Dos gráficos:
      1) Línea diaria: Σ TXN_AMT por día y por ISSUER_NAME.
      2) Barras mensuales (agrupadas): Σ TXN_AMT por mes y por ISSUER_NAME.
    Leyendas interactivas (clic en emisor para mostrar/ocultar).
    """

    def __init__(self, master=None):
        super().__init__(master)
        self._df = None
        self._cid_pick = None  # id del evento pick para no duplicar callbacks
        self._build()

    def _build(self):
        # Figura con 2 subplots (1 fila x 2 columnas)
        self.fig = Figure(figsize=(11.5, 4.8), dpi=100)
        self.ax_day = self.fig.add_subplot(1, 2, 1)
        self.ax_month = self.fig.add_subplot(1, 2, 2)

        # Más espacio horizontal + margen derecho para leyendas
        self.fig.subplots_adjust(left=0.25, right=0.78, wspace=0.55, bottom=0.08)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill="both", expand=True)

    # ---------- API ----------
    def update_plot(self, df: pd.DataFrame):
        self._df = df
        self._draw()

    # ---------- Pintado ----------
    def _draw(self):
        self.ax_day.clear()
        self.ax_month.clear()

        if self._df is None or self._df.empty:
            for ax in (self.ax_day, self.ax_month):
                ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            self.canvas.draw()
            return

        s = self._df.copy()
        s["TRANSACTION_DATE"] = pd.to_datetime(s["TRANSACTION_DATE"], errors="coerce")
        s = s.dropna(subset=["TRANSACTION_DATE"])
        if s.empty:
            for ax in (self.ax_day, self.ax_month):
                ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            self.canvas.draw()
            return

        # Top emisores para activar por defecto (3)
        top_emitters = (
            s.groupby("ISSUER_NAME")["TXN_AMT"].sum().sort_values(ascending=False).head(3).index.tolist()
        )

        # ===== 1) LÍNEA DIARIA =====
        s["DAY"] = s["TRANSACTION_DATE"].dt.normalize()
        grouped_day = (
            s.groupby(["DAY", "ISSUER_NAME"])["TXN_AMT"]
             .sum()
             .reset_index()
             .sort_values(by="DAY")
        )

        issuers_day = grouped_day["ISSUER_NAME"].unique()
        lines_by_issuer = {}
        for issuer in issuers_day:
            sub = grouped_day[grouped_day["ISSUER_NAME"] == issuer]
            line, = self.ax_day.plot(sub["DAY"], sub["TXN_AMT"], marker="o", linewidth=1.6, label=issuer)
            # visible sólo si es top emisor
            line.set_visible(issuer in top_emitters)
            lines_by_issuer[issuer] = line

        # Eje X fechas auto
        locator = mdates.AutoDateLocator()
        formatter = mdates.AutoDateFormatter(locator)
        self.ax_day.xaxis.set_major_locator(locator)
        self.ax_day.xaxis.set_major_formatter(formatter)
        self.fig.autofmt_xdate(rotation=25)

        # Eje Y miles
        self.ax_day.yaxis.set_major_formatter(mticker.StrMethodFormatter('{x:,.0f}'))
        self.ax_day.set_title("Volumen por día (Σ TXN_AMT) por emisor")
        self.ax_day.set_xlabel("Fecha")
        self.ax_day.set_ylabel("Volumen")
        self.ax_day.grid(True, alpha=0.3)

        # Leyenda interactiva (proxies)
        # Leyenda interactiva (proxies)
        line_proxies = [Line2D([0], [0], color=lines_by_issuer[e].get_color(), lw=2) for e in issuers_day]
        leg_day = self.ax_day.legend(
            line_proxies, issuers_day,
            title="Emisor (clic para activar/ocultar)",
            bbox_to_anchor=(-0.28, 1.0), loc="upper right",  # <<— izquierda, fuera del plot
            borderaxespad=0., frameon=False, fontsize=9
        )  

        # ===== 2) BARRAS MENSUALES AGRUPADAS =====
        s["MONTH"] = s["TRANSACTION_DATE"].dt.to_period("M").apply(lambda r: r.start_time)
        grouped_month = (
            s.groupby(["MONTH", "ISSUER_NAME"])["TXN_AMT"]
             .sum()
             .reset_index()
        )

        pivot = grouped_month.pivot(index="MONTH", columns="ISSUER_NAME", values="TXN_AMT").fillna(0.0)
        pivot = pivot.sort_index()

        bars_by_issuer = {}
        if not pivot.empty:
            months = pivot.index.to_pydatetime()
            n_months = len(months)
            issuers = list(pivot.columns)
            n_issuers = len(issuers)

            group_width = 0.8
            bar_width = group_width / max(n_issuers, 1)
            x = np.arange(n_months)

            for i, issuer in enumerate(issuers):
                offsets = (i - (n_issuers - 1) / 2.0) * bar_width
                bars = self.ax_month.bar(x + offsets, pivot[issuer].values, width=bar_width, label=issuer)
                # visible solo si es top emisor
                for b in bars:
                    b.set_visible(issuer in top_emitters)
                bars_by_issuer[issuer] = bars

            month_labels = [dt.strftime("%Y-%m") for dt in months]
            self.ax_month.set_xticks(x)
            self.ax_month.set_xticklabels(month_labels, rotation=25, ha="right")

            self.ax_month.yaxis.set_major_formatter(mticker.StrMethodFormatter('{x:,.0f}'))
            self.ax_month.set_title("Volumen por mes (Σ TXN_AMT) por emisor")
            self.ax_month.set_xlabel("Mes")
            self.ax_month.set_ylabel("Volumen")
            self.ax_month.grid(True, axis="y", alpha=0.3)

            # Leyenda interactiva (proxies Patch)
            bar_colors = []
            # usa el color de una de las barras del issuer si está disponible
            for issuer in issuers:
                # Si aún no hay barras visibles, matplotlib asignó colores por ciclo; tomamos el de la primera barra
                color = bars_by_issuer[issuer][0].get_facecolor() if len(bars_by_issuer[issuer]) else (0.3, 0.3, 0.3, 1.0)
                bar_colors.append(color)
            bar_proxies = [Patch(facecolor=c) for c in bar_colors]
            leg_month = self.ax_month.legend(
                bar_proxies, issuers,
                title="Emisor (clic para activar/ocultar)",
                bbox_to_anchor=(1.02, 1.0), loc="upper left",
                borderaxespad=0., frameon=False, fontsize=9
            )
        else:
            self.ax_month.text(0.5, 0.5, "No data", ha="center", va="center", transform=self.ax_month.transAxes)
            leg_month = None

        # ---- Interactividad de leyendas (robusta con proxies) ----
        self._connect_legend_interactivity(leg_day, issuers_day, lines_by_issuer,
                                           leg_month, list(bars_by_issuer.keys()), bars_by_issuer)

        # Ajustes finales
        # más espacio inferior para la leyenda del primer subplot
        self.fig.subplots_adjust(right=0.76, wspace=0.6, bottom=0.22)

        self.canvas.draw()

    # ---------- Interactividad ----------
    def _connect_legend_interactivity(self, leg_day, issuers_day, lines_by_issuer,
                                      leg_month, issuers_month, bars_by_issuer):
        # Evita duplicar múltiples conexiones si se actualiza el gráfico a menudo
        if self._cid_pick is not None:
            self.fig.canvas.mpl_disconnect(self._cid_pick)
            self._cid_pick = None

        # Mapa: nombre -> (tipo, objeto grafico)
        # tipo: "line" o "bars"
        legend_hitboxes = {}
        if leg_day is not None:
            for txt, issuer in zip(leg_day.get_texts(), issuers_day):
                txt.set_picker(True)
                legend_hitboxes[txt] = ("line", issuer)

        if leg_month is not None:
            for txt, issuer in zip(leg_month.get_texts(), issuers_month):
                txt.set_picker(True)
                legend_hitboxes[txt] = ("bars", issuer)

        def on_pick(event):
            target = event.artist
            if target not in legend_hitboxes:
                return
            kind, issuer = legend_hitboxes[target]
            if kind == "line":
                line = lines_by_issuer.get(issuer)
                if line is None:
                    return
                line.set_visible(not line.get_visible())
            else:
                bars = bars_by_issuer.get(issuer, [])
                if not bars:
                    return
                new_vis = not bars[0].get_visible()
                for b in bars:
                    b.set_visible(new_vis)
            # Feedback visual en el texto de leyenda
            alpha_new = 1.0 if (kind == "line" and lines_by_issuer[issuer].get_visible()) or \
                                (kind == "bars" and bars_by_issuer[issuer][0].get_visible()) else 0.5
            target.set_alpha(alpha_new)
            self.canvas.draw_idle()

        # Conectar un único pick handler
        self._cid_pick = self.fig.canvas.mpl_connect("pick_event", on_pick)
