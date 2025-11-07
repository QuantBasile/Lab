# ui/volume_summary.py
import tkinter as tk
from tkinter import ttk
import pandas as pd
import numpy as np

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.ticker as mticker


class VolumeSummary(ttk.Frame):
    """
    Pestaña 'Volumen-summary' (1 fila, 2 columnas):
      [0,0] Histograma (Σ TXN_AMT por emisor) con anotaciones
      [0,1] Pie chart (Top-N, resto 'Others')

    API:
      update_view(df, color_resolver=None)
        df: DataFrame filtrado.
        color_resolver: callable opcional issuer -> color (para mantener coherencia).
    """

    TOP_N_PIE = 8

    def __init__(self, master=None):
        super().__init__(master)
        self._df = None
        self._color_resolver = None
        self._build()

    # ---------- UI ----------
    def _build(self):
        # Grid: 1 fila x 2 columnas
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)  # hist
        self.columnconfigure(1, weight=1)  # pie

        # ===== Histograma (col 0) =====
        hist_wrap = tk.Frame(self, bg="white", bd=0, highlightthickness=0)
        hist_wrap.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=10)
        hist_wrap.rowconfigure(1, weight=1)
        hist_wrap.columnconfigure(0, weight=1)

        self.fig_hist = Figure(figsize=(6, 4.2), dpi=100)
        self.ax_hist = self.fig_hist.add_subplot(111)
        self.fig_hist.subplots_adjust(left=0.08, right=0.98, top=0.9, bottom=0.30)

        self.canvas_hist = FigureCanvasTkAgg(self.fig_hist, master=hist_wrap)
        self.canvas_hist.get_tk_widget().configure(bg="white", highlightthickness=0)
        self.canvas_hist.get_tk_widget().grid(row=1, column=0, sticky="nsew")

        self.toolbar_hist = NavigationToolbar2Tk(self.canvas_hist, hist_wrap, pack_toolbar=False)
        self.toolbar_hist.update()
        self.toolbar_hist.grid(row=0, column=0, sticky="w", pady=(0, 6))
        try:
            self.toolbar_hist.configure(background="white")
            for w in self.toolbar_hist.winfo_children():
                try: w.configure(background="white")
                except Exception: pass
        except Exception:
            pass

        # ===== Pie chart (col 1) =====
        pie_wrap = tk.Frame(self, bg="white", bd=0, highlightthickness=0)
        pie_wrap.grid(row=0, column=1, sticky="nsew", padx=(6, 10), pady=10)
        pie_wrap.rowconfigure(1, weight=1)
        pie_wrap.columnconfigure(0, weight=1)

        self.fig_pie = Figure(figsize=(6, 4.2), dpi=100)
        self.ax_pie = self.fig_pie.add_subplot(111)
        self.fig_pie.subplots_adjust(left=0.05, right=0.95, top=0.92, bottom=0.05)

        self.canvas_pie = FigureCanvasTkAgg(self.fig_pie, master=pie_wrap)
        self.canvas_pie.get_tk_widget().configure(bg="white", highlightthickness=0)
        self.canvas_pie.get_tk_widget().grid(row=1, column=0, sticky="nsew")

        self.toolbar_pie = NavigationToolbar2Tk(self.canvas_pie, pie_wrap, pack_toolbar=False)
        self.toolbar_pie.update()
        self.toolbar_pie.grid(row=0, column=0, sticky="w", pady=(0, 6))
        try:
            self.toolbar_pie.configure(background="white")
            for w in self.toolbar_pie.winfo_children():
                try: w.configure(background="white")
                except Exception: pass
        except Exception:
            pass

    # ---------- API ----------
    def update_view(self, df: pd.DataFrame, color_resolver=None):
        self._df = df
        self._color_resolver = color_resolver
        self._draw()

    # ---------- Drawing ----------
    def _draw(self):
        # Limpiar
        self.ax_hist.clear()
        self.ax_pie.clear()

        # Data checks
        if self._df is None or self._df.empty:
            self._draw_empty()
            return

        s = self._df
        if "ISSUER_NAME" not in s.columns or "TXN_AMT" not in s.columns:
            self._draw_empty(msg="Missing columns")
            return

        # Totales por emisor, orden desc
        grp = s.groupby("ISSUER_NAME", dropna=False)["TXN_AMT"].sum().sort_values(ascending=False)
        emitters = grp.index.tolist()
        totals = grp.values.astype(float)
        total_all = float(s["TXN_AMT"].sum())
        denom = total_all if total_all != 0.0 else 1.0

        # ===== Histograma =====
        x = np.arange(len(emitters))
        bars = self.ax_hist.bar(x, totals)

        # Colores coherentes
        if callable(self._color_resolver):
            for i, iss in enumerate(emitters):
                try:
                    c = self._color_resolver(iss)
                    if c:
                        bars[i].set_color(c)
                        bars[i].set_alpha(0.9)
                except Exception:
                    pass

        # Ejes, formato y título
        self.ax_hist.set_xticks(x)
        self.ax_hist.set_xticklabels(emitters, rotation=30, ha="right")
        self.ax_hist.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))
        self.ax_hist.grid(True, axis="y", alpha=0.3)
        self.ax_hist.set_title("Volumen total por emisor (Σ TXN_AMT)")
        self.ax_hist.set_xlabel(""); self.ax_hist.set_ylabel("")

        # Anotaciones encima de cada barra
        ymax = 0.0
        for rect, v in zip(bars, totals):
            height = rect.get_height()
            ymax = max(ymax, height)
            if height <= 0:
                continue
            txt = f"{v:,.0f}".replace(",", " ")
            self.ax_hist.text(rect.get_x() + rect.get_width()/2, height,
                              txt, ha="center", va="bottom", fontsize=9, rotation=0, clip_on=True)
        if ymax > 0:
            self.ax_hist.set_ylim(0, ymax * 1.12)

        self.fig_hist.tight_layout()
        self.canvas_hist.draw_idle()

        # ===== Pie chart =====
        if len(emitters) > self.TOP_N_PIE:
            top_emitters = emitters[:self.TOP_N_PIE]
            top_vals = totals[:self.TOP_N_PIE]
            others_val = float(totals[self.TOP_N_PIE:].sum())
            labels = top_emitters + (["Others"] if others_val > 0 else [])
            sizes = top_vals.tolist() + ([others_val] if others_val > 0 else [])
        else:
            labels = emitters
            sizes = totals.tolist()

        # Paleta coherente; 'Others' sin resolver
        colors = []
        for lab in labels:
            if lab == "Others" or not callable(self._color_resolver):
                colors.append(None)
            else:
                try:
                    colors.append(self._color_resolver(lab))
                except Exception:
                    colors.append(None)

        self.ax_pie.pie(
            sizes,
            labels=labels,
            autopct=(lambda p: f"{p:.1f}%"),
            startangle=90,
            colors=colors if any(colors) else None
        )
        self.ax_pie.axis("equal")
        self.ax_pie.set_title("Participación de volumen (Top-N)")
        self.canvas_pie.draw_idle()

    # ---------- Helpers ----------
    def _draw_empty(self, msg="No data"):
        for ax in (self.ax_hist, self.ax_pie):
            ax.clear()
            ax.text(0.5, 0.5, msg, ha="center", va="center", transform=ax.transAxes)
        self.canvas_hist.draw()
        self.canvas_pie.draw()
