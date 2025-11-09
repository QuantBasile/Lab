# ui/call_put_share.py
import tkinter as tk
from tkinter import ttk
import pandas as pd
import numpy as np

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.ticker as mticker
import matplotlib.dates as mdates

from pandas.api.types import is_datetime64_any_dtype


class CallPutShare(ttk.Frame):
    """
    Reiter zur Analyse des Marktanteils CALL vs. PUT.

    Layout (eine 2x2-Figur):
      [0,0] Gestapelte Tagesbalken: % CALL vs. PUT am Tagesvolumen.
      [0,1] Gestapelte Wochenbalken: % CALL vs. PUT am Wochenvolumen.
      [1,0] Gestapelte Balken je Emittent: % CALL vs. PUT am Emittentenvolumen.
      [1,1] Globales Kreisdiagramm: % CALL vs. PUT am Gesamtvolumen.

    API:
      update_plot(df: pd.DataFrame)
        - erhält gefiltertes DataFrame.
        - benötigt Spalten: TRANSACTION_DATE, TXN_AMT, CALL_OPTION, ISSUER_NAME.
    """

    def __init__(self, master=None):
        super().__init__(master)
        self._df = None
        self._build()

    # ---------------- Zeitspalten-Helper ----------------
    def _ensure_time_cols(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Stellt sicher, dass DAY und WEEK vorhanden sind.
        Optimizado: menos copias y conversiones.
        """
        if df is None or df.empty:
            return df

        s = df
        if "TRANSACTION_DATE" not in s.columns:
            return s

        if not is_datetime64_any_dtype(s["TRANSACTION_DATE"]):
            s = s.copy()
            s["TRANSACTION_DATE"] = pd.to_datetime(
                s["TRANSACTION_DATE"], errors="coerce"
            )

        s = s.dropna(subset=["TRANSACTION_DATE"])

        need_copy = False
        if "DAY" not in s.columns:
            need_copy = True
        if "WEEK" not in s.columns:
            need_copy = True

        if need_copy:
            s = s.copy()
            if "DAY" not in s.columns:
                s["DAY"] = s["TRANSACTION_DATE"].dt.normalize()
            if "WEEK" not in s.columns:
                s["WEEK"] = s["TRANSACTION_DATE"].dt.to_period("W-MON").dt.start_time

        return s

    # ---------------- UI build ----------------
    def _build(self):
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        container = tk.Frame(self, bg="white", bd=0, highlightthickness=0)
        container.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        container.rowconfigure(1, weight=1)
        container.columnconfigure(0, weight=1)

        # Figur mit 4 Subplots
        self.fig = Figure(figsize=(12, 6.8), dpi=100)
        gs = self.fig.add_gridspec(2, 2, height_ratios=[1, 1])

        self.ax_day    = self.fig.add_subplot(gs[0, 0])  # täglich %
        self.ax_week   = self.fig.add_subplot(gs[0, 1])  # wöchentlich %
        self.ax_issuer = self.fig.add_subplot(gs[1, 0])  # je Emittent
        self.ax_pie    = self.fig.add_subplot(gs[1, 1])  # globales Pie

        self.fig.subplots_adjust(
            left=0.06, right=0.98,
            bottom=0.10, top=0.94,
            wspace=0.30, hspace=0.35,
        )

        self.canvas = FigureCanvasTkAgg(self.fig, master=container)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.configure(bg="white", highlightthickness=0)
        self.canvas_widget.grid(row=1, column=0, sticky="nsew")

        # Toolbar
        self.toolbar = NavigationToolbar2Tk(self.canvas, container, pack_toolbar=False)
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

    # ---------------- API ----------------
    def update_plot(self, df: pd.DataFrame):
        """Erhält gefiltertes DataFrame und zeichnet den Reiter 'CALL/PUT Anteil' neu."""
        self._df = df
        self._draw_all()

    # ---------------- Drawing ----------------
    def _draw_all(self):
        # Achsen leeren
        for ax in (self.ax_day, self.ax_week, self.ax_issuer, self.ax_pie):
            ax.clear()

        if self._df is None or self._df.empty:
            for ax in (self.ax_day, self.ax_week, self.ax_issuer, self.ax_pie):
                ax.text(
                    0.5,
                    0.5,
                    "Keine Daten",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                )
            self.canvas.draw_idle()
            return

        s = self._ensure_time_cols(self._df)

        required = {"TRANSACTION_DATE", "TXN_AMT", "CALL_OPTION", "ISSUER_NAME"}
        if not required.issubset(s.columns):
            msg = "Fehlende Spalten: " + ", ".join(sorted(required - set(s.columns)))
            for ax in (self.ax_day, self.ax_week, self.ax_issuer, self.ax_pie):
                ax.text(0.5, 0.5, msg, ha="center", va="center", transform=ax.transAxes)
            self.canvas.draw_idle()
            return

        # Typen normalisieren
        s["CALL_OPTION"] = s["CALL_OPTION"].astype(str)
        s["ISSUER_NAME"] = s["ISSUER_NAME"].astype(str)

        # Kategorien CALL/PUT (oder was im Feld steht)
        cp_categories = sorted(s["CALL_OPTION"].unique())
        if len(cp_categories) == 0:
            for ax in (self.ax_day, self.ax_week, self.ax_issuer, self.ax_pie):
                ax.text(
                    0.5,
                    0.5,
                    "Keine CALL/PUT-Daten",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                )
            self.canvas.draw_idle()
            return

        colors = self._get_callput_colors(cp_categories)

        # ===== [0,0] Tägliche 100%-Balken =====
        self._draw_daily_share_bars(s, cp_categories, colors)

        # ===== [0,1] Wöchentliche 100%-Balken =====
        self._draw_weekly_share_bars(s, cp_categories, colors)

        # ===== [1,0] Emittentenanteil =====
        self._draw_issuer_share(s, cp_categories, colors)

        # ===== [1,1] Globales CALL/PUT-Pie =====
        self._draw_global_pie(s, cp_categories, colors)

        self.canvas.draw_idle()

    # ---------- Tägliche Anteile: gestapelte Balken ----------
    # ---------- Tägliche Anteile: gestapelte Balken ----------
    def _draw_daily_share_bars(self, s: pd.DataFrame, cats, colors):
        grp = (
            s.groupby(["DAY", "CALL_OPTION"], sort=False)["TXN_AMT"]
            .sum()
            .reset_index()
            .sort_values("DAY")
        )
        if grp.empty:
            self.ax_day.text(
                0.5,
                0.5,
                "Keine Tagesdaten",
                ha="center",
                va="center",
                transform=self.ax_day.transAxes,
            )
            return
    
        pivot = grp.pivot(index="DAY", columns="CALL_OPTION", values="TXN_AMT").fillna(0.0)
        pivot = pivot.reindex(columns=cats)
    
        total = pivot.sum(axis=1)
        pct = pivot.div(total.replace(0.0, np.nan), axis=0) * 100.0
        pct = pct.fillna(0.0)
    
        days = list(pct.index)
        n = len(days)
        x = np.arange(n)
    
        bottom = np.zeros(n)
        for i, cat in enumerate(cats):
            vals = pct[cat].values
            self.ax_day.bar(
                x,
                vals,
                bottom=bottom,
                label=cat,
                color=colors[i],
                alpha=0.9,
            )
            bottom += vals
    
        # ---- XTICKS BEGRENZEN AUF MAX 10 ----
        max_ticks = 10
        if n <= max_ticks:
            tick_idx = np.arange(n)
        else:
            tick_idx = np.linspace(0, n - 1, max_ticks, dtype=int)
        tick_labels = [days[i].strftime("%Y-%m-%d") for i in tick_idx]
    
        self.ax_day.set_xticks(tick_idx)
        self.ax_day.set_xticklabels(tick_labels, rotation=20, ha="right")
    
        self.ax_day.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}%"))
        self.ax_day.set_ylim(0, 100)
        self.ax_day.grid(True, axis="y", alpha=0.3)
        self.ax_day.set_title("Anteil CALL vs. PUT am Tagesvolumen (%)")
        self.ax_day.set_xlabel("")
        self.ax_day.set_ylabel("")
        self.ax_day.legend(loc="upper right", fontsize=8)
    
    # ---------- Wöchentliche Anteile: gestapelte Balken ----------
    def _draw_weekly_share_bars(self, s: pd.DataFrame, cats, colors):
        grp = (
            s.groupby(["WEEK", "CALL_OPTION"], sort=False)["TXN_AMT"]
            .sum()
            .reset_index()
            .sort_values("WEEK")
        )
        if grp.empty:
            self.ax_week.text(
                0.5,
                0.5,
                "Keine Wochendaten",
                ha="center",
                va="center",
                transform=self.ax_week.transAxes,
            )
            return
    
        pivot = grp.pivot(index="WEEK", columns="CALL_OPTION", values="TXN_AMT").fillna(0.0)
        pivot = pivot.reindex(columns=cats)
    
        total = pivot.sum(axis=1)
        pct = pivot.div(total.replace(0.0, np.nan), axis=0) * 100.0
        pct = pct.fillna(0.0)
    
        weeks = list(pct.index)
        n = len(weeks)
        x = np.arange(n)
    
        bottom = np.zeros(n)
        for i, cat in enumerate(cats):
            vals = pct[cat].values
            self.ax_week.bar(
                x,
                vals,
                bottom=bottom,
                label=cat,
                color=colors[i],
                alpha=0.9,
            )
            bottom += vals
    
        # ---- XTICKS BEGRENZEN AUF MAX 10 ----
        max_ticks = 10
        if n <= max_ticks:
            tick_idx = np.arange(n)
        else:
            tick_idx = np.linspace(0, n - 1, max_ticks, dtype=int)
        tick_labels = [f"{weeks[i].isocalendar().year}-W{weeks[i].isocalendar().week:02d}" for i in tick_idx]
    
        self.ax_week.set_xticks(tick_idx)
        self.ax_week.set_xticklabels(tick_labels, rotation=20, ha="right")
    
        self.ax_week.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}%"))
        self.ax_week.set_ylim(0, 100)
        self.ax_week.grid(True, axis="y", alpha=0.3)
        self.ax_week.set_title("Anteil CALL vs. PUT am Wochenvolumen (%)")
        self.ax_week.set_xlabel("")
        self.ax_week.set_ylabel("")
        self.ax_week.legend(loc="upper right", fontsize=8)


    # ---------- Emittentenanteil ----------
    def _draw_issuer_share(self, s: pd.DataFrame, cats, colors):
        grp = (
            s.groupby(["ISSUER_NAME", "CALL_OPTION"], sort=False)["TXN_AMT"]
            .sum()
            .reset_index()
        )
        if grp.empty:
            self.ax_issuer.text(
                0.5,
                0.5,
                "Keine Emittentendaten",
                ha="center",
                va="center",
                transform=self.ax_issuer.transAxes,
            )
            return

        pivot = grp.pivot(index="ISSUER_NAME", columns="CALL_OPTION", values="TXN_AMT").fillna(0.0)
        pivot = pivot.reindex(columns=cats)
        pivot = pivot.sort_index()

        total = pivot.sum(axis=1)
        pct = pivot.div(total.replace(0.0, np.nan), axis=0) * 100.0
        pct = pct.fillna(0.0)

        issuers = list(pct.index)
        x = np.arange(len(issuers))

        bottom = np.zeros(len(issuers))
        for i, cat in enumerate(cats):
            vals = pct[cat].values
            self.ax_issuer.bar(
                x,
                vals,
                bottom=bottom,
                label=cat,
                color=colors[i],
                alpha=0.9,
            )
            bottom += vals

        self.ax_issuer.set_xticks(x)
        self.ax_issuer.set_xticklabels(issuers, rotation=20, ha="right")
        self.ax_issuer.yaxis.set_major_formatter(
            mticker.StrMethodFormatter("{x:,.0f}%")
        )
        self.ax_issuer.set_ylim(0, 100)
        self.ax_issuer.grid(True, axis="y", alpha=0.3)
        self.ax_issuer.set_title("Anteil CALL vs. PUT je Emittent (%)")
        self.ax_issuer.set_xlabel("")
        self.ax_issuer.set_ylabel("")
        self.ax_issuer.legend(loc="upper right", fontsize=8)

    # ---------- Globales Pie ----------
    def _draw_global_pie(self, s: pd.DataFrame, cats, colors):
        grp = s.groupby("CALL_OPTION")["TXN_AMT"].sum()
        vals = [grp.get(c, 0.0) for c in cats]
        if sum(vals) == 0:
            self.ax_pie.text(
                0.5,
                0.5,
                "Kein Volumen",
                ha="center",
                va="center",
                transform=self.ax_pie.transAxes,
            )
            return

        self.ax_pie.pie(
            vals,
            labels=cats,
            autopct=lambda p: f"{p:.1f}%",
            colors=colors,
            startangle=90,
        )
        self.ax_pie.axis("equal")
        self.ax_pie.set_title("Globaler Anteil CALL vs. PUT")

    # ---------- Farb-Helper ----------
    def _get_callput_colors(self, cats):
        """
        Weist stabile Farben für CALL/PUT (und ggf. andere Kategorien) zu.
        CALL -> Blau, PUT -> Orange. Andere -> Matplotlib-Defaults.
        """
        colors = []
        default_cycle = ["#2563eb", "#f97316", "#16a34a", "#9333ea"]
        for i, c in enumerate(cats):
            key = str(c).upper()
            if key in ("CALL", "C"):
                colors.append("#2563eb")  # Blau
            elif key in ("PUT", "P"):
                colors.append("#f97316")  # Orange
            else:
                colors.append(default_cycle[i % len(default_cycle)])
        return colors
