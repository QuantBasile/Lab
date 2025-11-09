# ui/volume_summary.py
import tkinter as tk
from tkinter import ttk
import pandas as pd
import numpy as np

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.ticker as mticker

# 🔹 Colores globales por Emittent
from utils.issuer_colors import get_issuer_color


class VolumeSummary(ttk.Frame):
    """
    Pestaña 'Volumen-Übersicht' (1 Zeile, 2 Spalten):

      [0,0] Histogramm (Σ TXN_AMT nach Emittent, gestapelt nach UND_TYPE falls vorhanden)
             – über jeder Säule: Gesamtvolumen
             – in jedem Segment: Anteil dieses UND_TYPE am Emittenten-Volumen (%)

      [0,1] Histogramm (Marktanteil in % nach Emittent)

    API:
      update_view(df)
        df: gefiltertes DataFrame.
    """

    def __init__(self, master=None):
        super().__init__(master)
        self._df = None
        self._build()

    # ---------- UI ----------
    def _build(self):
        # Grid: 1 Zeile x 2 Spalten
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)  # linkes Histogramm
        self.columnconfigure(1, weight=1)  # rechtes Histogramm

        # ===== Linkes Histogramm (gestapelt) =====
        left_wrap = tk.Frame(self, bg="white", bd=0, highlightthickness=0)
        left_wrap.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=10)
        left_wrap.rowconfigure(1, weight=1)
        left_wrap.columnconfigure(0, weight=1)

        self.fig_left = Figure(figsize=(6, 4.2), dpi=100)
        self.ax_left = self.fig_left.add_subplot(111)
        self.fig_left.subplots_adjust(left=0.08, right=0.98, top=0.9, bottom=0.30)

        self.canvas_left = FigureCanvasTkAgg(self.fig_left, master=left_wrap)
        self.canvas_left.get_tk_widget().configure(bg="white", highlightthickness=0)
        self.canvas_left.get_tk_widget().grid(row=1, column=0, sticky="nsew")

        self.toolbar_left = NavigationToolbar2Tk(self.canvas_left, left_wrap, pack_toolbar=False)
        self.toolbar_left.update()
        self.toolbar_left.grid(row=0, column=0, sticky="w", pady=(0, 6))
        try:
            self.toolbar_left.configure(background="white")
            for w in self.toolbar_left.winfo_children():
                try:
                    w.configure(background="white")
                except Exception:
                    pass
        except Exception:
            pass

        # ===== Rechtes Histogramm (Marktanteil %) =====
        right_wrap = tk.Frame(self, bg="white", bd=0, highlightthickness=0)
        right_wrap.grid(row=0, column=1, sticky="nsew", padx=(6, 10), pady=10)
        right_wrap.rowconfigure(1, weight=1)
        right_wrap.columnconfigure(0, weight=1)

        self.fig_right = Figure(figsize=(6, 4.2), dpi=100)
        self.ax_right = self.fig_right.add_subplot(111)
        self.fig_right.subplots_adjust(left=0.08, right=0.98, top=0.9, bottom=0.30)

        self.canvas_right = FigureCanvasTkAgg(self.fig_right, master=right_wrap)
        self.canvas_right.get_tk_widget().configure(bg="white", highlightthickness=0)
        self.canvas_right.get_tk_widget().grid(row=1, column=0, sticky="nsew")

        self.toolbar_right = NavigationToolbar2Tk(self.canvas_right, right_wrap, pack_toolbar=False)
        self.toolbar_right.update()
        self.toolbar_right.grid(row=0, column=0, sticky="w", pady=(0, 6))
        try:
            self.toolbar_right.configure(background="white")
            for w in self.toolbar_right.winfo_children():
                try:
                    w.configure(background="white")
                except Exception:
                    pass
        except Exception:
            pass

    # ---------- API ----------
    def update_view(self, df: pd.DataFrame):
        self._df = df
        self._draw()

    # ---------- Helpers de formato ----------
    def _format_volume_tick(self, x, pos):
        """
        Formato dinámico del eje Y (Volumen):
          - < 1 Mio: estándar con miles: 12,345
          - >= 1 Mio: abreviado en M, p.ej. 1.1M, 2M, 10M
        """
        abs_x = abs(x)
        if abs_x >= 1_000_000:
            value = x / 1_000_000.0
            if abs_x >= 10_000_000:
                return f"{value:,.0f}M"
            else:
                return f"{value:,.1f}M"
        else:
            return f"{x:,.0f}"

    def _format_pct_tick(self, x, pos):
        """Formato para ejes de porcentaje."""
        return f"{x:.0f} %"

    # ---------- Drawing ----------
    def _draw(self):
        # Limpiar
        self.ax_left.clear()
        self.ax_right.clear()

        # Data checks
        if self._df is None or self._df.empty:
            self._draw_empty()
            return

        s = self._df
        if "ISSUER_NAME" not in s.columns or "TXN_AMT" not in s.columns:
            self._draw_empty(msg="Spalten fehlen")
            return

        # Totales por emisor, orden desc
        grp = (
            s.groupby("ISSUER_NAME", dropna=False, observed=False)["TXN_AMT"]
            .sum()
            .sort_values(ascending=False)
        )
        emitters = grp.index.tolist()
        totals = grp.values.astype(float)
        total_all = float(s["TXN_AMT"].sum())
        denom_all = total_all if total_all != 0.0 else 1.0

        x = np.arange(len(emitters))

        # ===================== LINKES HISTOGRAMM =====================
        has_und_type = "UND_TYPE" in s.columns

        if has_und_type:
            # tabla Emittent x UND_TYPE (Volumen)
            pivot = (
                s.groupby(["ISSUER_NAME", "UND_TYPE"], dropna=False, observed=False)["TXN_AMT"]
                .sum()
                .unstack(fill_value=0.0)
            )
            pivot = pivot.reindex(index=emitters)

            und_types = list(pivot.columns)
            bottom = np.zeros(len(emitters), dtype=float)

            # paleta simple para UND_TYPE
            base_colors = [
                "#2563eb",  # blau
                "#059669",  # grün
                "#f97316",  # orange
                "#7c3aed",  # violett
                "#e11d48",  # rot
            ]
            color_map = {
                ut: base_colors[i % len(base_colors)]
                for i, ut in enumerate(und_types)
            }

            # Para etiquetas de % dentro de las barras necesitamos los totales por Emittent
            totals_per_issuer = pivot.sum(axis=1).values  # misma orden que emitters

            for ut in und_types:
                vals = pivot[ut].values.astype(float)
                bars = self.ax_left.bar(
                    x,
                    vals,
                    bottom=bottom,
                    label=str(ut),
                    color=color_map.get(ut),
                    alpha=0.9,
                )

                # Porcentaje dentro de la barra (segmento vs total Emittent)
                for i, b in enumerate(bars):
                    h = b.get_height()
                    total_iss = totals_per_issuer[i]
                    if h <= 0 or total_iss <= 0:
                        continue
                    pct = (h / total_iss) * 100.0
                    # texto centrado en el segmento
                    bx = b.get_x() + b.get_width() / 2.0
                    by = b.get_y() + h / 2.0
                    self.ax_left.text(
                        bx,
                        by,
                        f"{pct:.1f}%",
                        ha="center",
                        va="center",
                        fontsize=8,
                        color="white" if pct > 10 else "black",
                    )

                bottom += vals

            self.ax_left.legend(title="UND_TYPE", fontsize=8, title_fontsize=9)
            ymax_left = bottom.max() if bottom.size > 0 else 0.0
        else:
            # Fallback: no hay UND_TYPE -> barras simples con color por Emittent
            bars_left = self.ax_left.bar(x, totals)
            for i, iss in enumerate(emitters):
                color = get_issuer_color(iss)
                if color:
                    bars_left[i].set_color(color)
                    bars_left[i].set_alpha(0.9)
            ymax_left = totals.max() if totals.size > 0 else 0.0
            # En este caso no hay % por UND_TYPE dentro de barras

        # Etiqueta con el volumen total encima de cada barra (usar bottom final si stacked, si no totals)
        volumes_for_label = bottom if has_und_type else totals
        for i, vol in enumerate(volumes_for_label):
            if vol <= 0:
                continue
            bx = x[i]
            # usar el mismo formateo de volumen
            txt = self._format_volume_tick(vol, None)
            self.ax_left.text(
                bx,
                vol,
                txt,
                ha="center",
                va="bottom",
                fontsize=9,
                rotation=0,
                clip_on=True,
            )

        # Ejes, formato y título del izquierdo
        self.ax_left.set_xticks(x)
        self.ax_left.set_xticklabels(emitters, rotation=20, ha="right")
        self.ax_left.yaxis.set_major_formatter(
            mticker.FuncFormatter(self._format_volume_tick)
        )
        self.ax_left.grid(True, axis="y", alpha=0.3)
        if has_und_type:
            self.ax_left.set_title("Volumen nach Emittent und Basiswerttyp (Σ TXN_AMT)")
        else:
            self.ax_left.set_title("Volumen nach Emittent (Σ TXN_AMT)")
        self.ax_left.set_xlabel("")
        self.ax_left.set_ylabel("")
        if ymax_left > 0:
            self.ax_left.set_ylim(0, ymax_left * 1.12)

        self.fig_left.tight_layout()
        self.canvas_left.draw_idle()

        # ===================== RECHTES HISTOGRAMM (Marktanteil %) =====================
        share_pct = (totals / denom_all) * 100.0  # Marktanteil pro Emittent

        bars_right = self.ax_right.bar(x, share_pct)

        # Colores por Emittent
        for i, iss in enumerate(emitters):
            color = get_issuer_color(iss)
            if color:
                bars_right[i].set_color(color)
                bars_right[i].set_alpha(0.9)

        # Etiqueta de porcentaje encima de cada barra
        ymax_right = 0.0
        for b, pct in zip(bars_right, share_pct):
            h = b.get_height()
            ymax_right = max(ymax_right, h)
            bx = b.get_x() + b.get_width() / 2.0
            if h <= 0:
                continue
            self.ax_right.text(
                bx,
                h,
                f"{pct:.1f}%",
                ha="center",
                va="bottom",
                fontsize=9,
                rotation=0,
                clip_on=True,
            )

        # Ejes, formato y título del derecho
        self.ax_right.set_xticks(x)
        self.ax_right.set_xticklabels(emitters, rotation=20, ha="right")
        self.ax_right.yaxis.set_major_formatter(
            mticker.FuncFormatter(self._format_pct_tick)
        )
        self.ax_right.grid(True, axis="y", alpha=0.3)
        self.ax_right.set_title("Marktanteil nach Emittent (Volumen %)")
        self.ax_right.set_xlabel("")
        self.ax_right.set_ylabel("")
        if ymax_right > 0:
            self.ax_right.set_ylim(0, ymax_right * 1.12)

        self.fig_right.tight_layout()
        self.canvas_right.draw_idle()

    # ---------- Helpers ----------
    def _draw_empty(self, msg="Keine Daten"):
        for ax in (self.ax_left, self.ax_right):
            ax.clear()
            ax.text(0.5, 0.5, msg, ha="center", va="center", transform=ax.transAxes)
        self.canvas_left.draw()
        self.canvas_right.draw()
