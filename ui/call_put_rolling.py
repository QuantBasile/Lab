# ui/call_put_rolling.py
import tkinter as tk
from tkinter import ttk
import pandas as pd
import numpy as np

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
from matplotlib.lines import Line2D

# 🔹 Farben pro Emittent (aus JSON)
from utils.issuer_colors import get_issuer_color
from pandas.api.types import is_datetime64_any_dtype



class CallPutRolling(ttk.Frame):
    """
    Reiter: 7-Tage-Rolling-Volumen nach Emittent, getrennt nach CALL/PUT.

    Layout:
      - Linke Sidebar: Emittentenliste mit Checkboxes (Alle AN / AUS)
      - Mitte: eine Figur mit einem Plot:
          * 7-Tage-Rolling (TXN_AMT) je Emittent und CALL/PUT
          * Farbe = Emittent (global aus JSON)
          * Linienstil = Optionstyp (CALL / PUT / andere)
    """

    def __init__(self, master=None):
        super().__init__(master)
        self._df = None

        self._issuers = []
        self._issuer_vars = {}      # issuer -> BooleanVar
        self._issuer_checks = {}    # issuer -> Checkbutton
        self._issuer_colors = {}    # issuer -> Farbe (hex o.ä.)

        self._full_range = None     # DatetimeIndex der Tage
        self._lines_vol = {}        # (issuer, cp) -> Line2D

        self._build()

    # ------------- Zeitspalten-Helper --------------
    def _ensure_time_cols(self, df: pd.DataFrame) -> pd.DataFrame:
        """Stellt sicher, dass DAY aus TRANSACTION_DATE abgeleitet ist.
    
        Optimizado:
        - No copia si no hace falta.
        - Sólo convierte a datetime si la columna no lo es.
        """
        if df is None or df.empty:
            return df
    
        s = df
        if "TRANSACTION_DATE" not in s.columns:
            return s
    
        # Convertir a datetime sólo si hace falta
        if not is_datetime64_any_dtype(s["TRANSACTION_DATE"]):
            s = s.copy()
            s["TRANSACTION_DATE"] = pd.to_datetime(
                s["TRANSACTION_DATE"], errors="coerce"
            )
    
        s = s.dropna(subset=["TRANSACTION_DATE"])
    
        # DAY sólo si no existe
        if "DAY" not in s.columns:
            if not s._is_copy:
                s = s.copy()
            s["DAY"] = s["TRANSACTION_DATE"].dt.normalize()
    
        return s


    # ------------- UI build --------------
    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        # Sidebar Emittenten
        self.sidebar = tk.Frame(
            self, bg="#FFF4E5", bd=0, highlightthickness=0, width=140
        )
        self.sidebar.grid(row=1, column=0, sticky="nsw", padx=(6, 8), pady=(4, 6))
        self.sidebar.grid_propagate(False)
        self._build_sidebar()

        # Plot-Bereich
        center = tk.Frame(self, bg="white", bd=0, highlightthickness=0)
        center.grid(row=1, column=1, sticky="nsew", padx=(0, 6), pady=(4, 6))
        center.rowconfigure(1, weight=1)
        center.columnconfigure(0, weight=1)

        # Figur mit einem einzigen Achsenobjekt
        self.fig = Figure(figsize=(12, 5.8), dpi=100)
        self.ax_vol = self.fig.add_subplot(1, 1, 1)
        self.fig.subplots_adjust(left=0.06, right=0.98,
                                 bottom=0.14, top=0.90)

        self.canvas = FigureCanvasTkAgg(self.fig, master=center)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.configure(bg="white", highlightthickness=0)
        self.canvas_widget.grid(row=1, column=0, sticky="nsew")

        # Toolbar
        self.toolbar = NavigationToolbar2Tk(self.canvas, center, pack_toolbar=False)
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
        tk.Label(
            self.sidebar,
            text="Emittenten",
            bg="#FFF4E5",
            fg="#7A3E00",
            font=("Segoe UI Semibold", 10),
        ).pack(anchor="w", padx=4, pady=(4, 2))

        btns = tk.Frame(self.sidebar, bg="#FFF4E5")
        btns.pack(fill="x", padx=4, pady=(0, 4))

        tk.Button(
            btns,
            text="Alle AN",
            command=self._all_on,
            bg="white",
            relief="solid",
            bd=1,
            padx=4,
            pady=1,
            cursor="hand2",
        ).pack(fill="x", pady=(0, 4))

        tk.Button(
            btns,
            text="Alle AUS",
            command=self._all_off,
            bg="white",
            relief="solid",
            bd=1,
            padx=4,
            pady=1,
            cursor="hand2",
        ).pack(fill="x", pady=(0, 4))

        # Scrollbare Emittentenliste
        list_container = tk.Frame(self.sidebar, bg="#FFF4E5")
        list_container.pack(fill="both", expand=True, padx=4, pady=(2, 6))

        self._issuer_canvas = tk.Canvas(
            list_container,
            borderwidth=0,
            highlightthickness=0,
            bg="#FFF4E5",
            width=128,
        )
        vsb = ttk.Scrollbar(
            list_container, orient="vertical", command=self._issuer_canvas.yview
        )
        self._issuer_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        self._issuer_inner = tk.Frame(self._issuer_canvas, bg="#FFF4E5")
        self._issuer_canvas.create_window(
            (0, 0), window=self._issuer_inner, anchor="nw"
        )
        self._issuer_inner.bind(
            "<Configure>",
            lambda e: self._issuer_canvas.configure(
                scrollregion=self._issuer_canvas.bbox("all")
            ),
        )
        self._issuer_canvas.pack(side="left", fill="both", expand=True)

    # ------------- API --------------
    def update_plot(self, df: pd.DataFrame):
        """Nimmt gefiltertes DataFrame entgegen und zeichnet den Reiter neu."""
        self._df = df
        self._draw_all()

    # ------------- Format-Helper --------------
    def _format_volume_tick(self, x, pos):
        """
        Format für Volumen-Achse:
          - < 1 Mio:  Standard mit Tausender-Trennzeichen (12,345)
          - >= 1 Mio: in Mio, z.B. 1M, 1,1M, 10M
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

    def _set_dynamic_ylim(self):
        """Passt die Y-Achse an die aktuell vorhandenen Linien an."""
        vals = []
        for ln in self._lines_vol.values():
            y = ln.get_ydata()
            if y is None:
                continue
            arr = np.asarray(y, dtype=float)
            arr = arr[~np.isnan(arr)]
            if arr.size:
                vals.append(arr.max())
        if not vals:
            return
        ymax = max(vals)
        if ymax <= 0:
            ymax = 1.0
        self.ax_vol.set_ylim(0, ymax * 1.1)

    # ------------- Zeichnen --------------
    def _draw_all(self):
        # Achse und Strukturen leeren
        self.ax_vol.clear()
        self._issuer_vars.clear()
        self._issuer_checks.clear()
        self._issuer_colors.clear()
        self._lines_vol.clear()
        self._full_range = None
        self._issuers = []

        for w in self._issuer_inner.winfo_children():
            w.destroy()

        if self._df is None or self._df.empty:
            self.ax_vol.text(
                0.5,
                0.5,
                "Keine Daten",
                ha="center",
                va="center",
                transform=self.ax_vol.transAxes,
            )
            self.canvas.draw_idle()
            return

        s = self._ensure_time_cols(self._df)

        required = {"TRANSACTION_DATE", "TXN_AMT", "CALL_OPTION", "ISSUER_NAME"}
        if not required.issubset(s.columns):
            msg = "Fehlende Spalten: " + ", ".join(sorted(required - set(s.columns)))
            self.ax_vol.text(
                0.5, 0.5, msg, ha="center", va="center", transform=self.ax_vol.transAxes
            )
            self.canvas.draw_idle()
            return

        s["CALL_OPTION"] = s["CALL_OPTION"].astype(str)
        s["ISSUER_NAME"] = s["ISSUER_NAME"].astype(str)

        # Emittenten & durchgängiger Datumsbereich
        self._issuers = sorted(s["ISSUER_NAME"].unique())
        self._full_range = pd.date_range(s["DAY"].min(), s["DAY"].max(), freq="D")

        # Sidebar Emittenten
        for iss in self._issuers:
            var = tk.BooleanVar(value=False)
            cb = tk.Checkbutton(
                self._issuer_inner,
                text=iss,
                variable=var,
                bg="#FFF4E5",
                activebackground="#FFF4E5",
                anchor="w",
                padx=4,
                pady=1,
                relief="flat",
                command=lambda i=iss: self._toggle_issuer(i),
            )
            cb.pack(fill="x", padx=0, pady=1)
            self._issuer_vars[iss] = var
            self._issuer_checks[iss] = cb

        # CALL/PUT-Ausprägungen
        callput_values = sorted(s["CALL_OPTION"].unique())

        # Linien generieren
        for iss in self._issuers:
            color = get_issuer_color(iss)
            if color is None:
                # Fallback, falls Emittent nicht im JSON ist
                color = self.ax_vol._get_lines.get_next_color()
            self._issuer_colors[iss] = color

            for cp in callput_values:
                mask = (s["ISSUER_NAME"] == iss) & (s["CALL_OPTION"] == cp)
                if not mask.any():
                    continue

                daily = (
                    s.loc[mask]
                    .groupby("DAY", sort=False)["TXN_AMT"]
                    .sum()
                    .reindex(self._full_range)
                    .fillna(0.0)  # Tage ohne Trades => Volumen 0
                )

                # 7-Tage-Rolling mit 0 für fehlende Tage
                roll_vol = (
                    pd.Series(daily.values, index=self._full_range)
                    .rolling(window=7, min_periods=1)
                    .mean()
                )


                color_line = self._issuer_colors[iss]
                ls = self._linestyle_for_callput(cp)

                (ln_v,) = self.ax_vol.plot(
                    self._full_range,
                    roll_vol.values,
                    linewidth=1.4,
                    color=color_line,
                    linestyle=ls,
                    label=f"{iss} {cp}",
                )
                ln_v.set_visible(False)
                self._lines_vol[(iss, cp)] = ln_v

        # Checkboxes farblich nach Emittent einfärben
        for iss, cb in self._issuer_checks.items():
            color = get_issuer_color(iss, fallback=self._issuer_colors.get(iss))
            if color:
                try:
                    cb.configure(
                        fg=color,
                        activeforeground=color,
                        selectcolor="#FFF4E5",
                    )
                except Exception:
                    pass

        # Achsenformat
        self._format_vol_axis()

        # Dynamische Y-Achse
        self._set_dynamic_ylim()

        # Legenden: Emittenten (Farben) und Typen (Linienstil)
        self._build_legends(callput_values)

        self.canvas.draw_idle()

    # ---------- Achsenformat ----------
    def _format_vol_axis(self):
        locator = mdates.AutoDateLocator()
        formatter = mdates.AutoDateFormatter(locator)
        self.ax_vol.xaxis.set_major_locator(locator)
        self.ax_vol.xaxis.set_major_formatter(formatter)
        self.ax_vol.yaxis.set_major_formatter(
            mticker.FuncFormatter(self._format_volume_tick)
        )
        self.ax_vol.grid(True, alpha=0.3)
        self.ax_vol.set_title("7-Tage-Rolling-Volumen nach Emittent und CALL/PUT")
        self.ax_vol.set_xlabel("")
        self.ax_vol.set_ylabel("")
        self.ax_vol.tick_params(axis="x", rotation=20)
        self.ax_vol.tick_params(axis="y", rotation=0)

        # X-Achse auf den gesamten Datenbereich setzen
        if self._full_range is not None and len(self._full_range) > 0:
            self.ax_vol.set_xlim(self._full_range.min(), self._full_range.max())

    # ---------- Linienstile ----------
    @staticmethod
    def _linestyle_for_callput(cp_value: str) -> str:
        key = str(cp_value).upper()
        if key in ("CALL", "C"):
            return "-"
        if key in ("PUT", "P"):
            return "--"
        return ":"  # andere Typen

    # ---------- Legenden ----------
    def _build_legends(self, callput_values):
        # Legende für Emittenten (Farben)
        issuer_handles = []
        issuer_labels = []
        for iss in self._issuers:
            color = self._issuer_colors.get(iss)
            if not color:
                continue
            h = Line2D([0], [0], color=color, linewidth=2.0)
            issuer_handles.append(h)
            issuer_labels.append(iss)

        # Legende für Typ (CALL/PUT) – Linienstil
        style_handles = []
        style_labels = []

        types_seen = set()
        for cp in callput_values:
            key = str(cp).upper()
            if key in ("CALL", "C"):
                normalized = "CALL"
            elif key in ("PUT", "P"):
                normalized = "PUT"
            else:
                normalized = cp

            if normalized in types_seen:
                continue
            types_seen.add(normalized)

            ls = self._linestyle_for_callput(cp)
            h = Line2D([0], [0], color="black", linestyle=ls, linewidth=2.0)
            style_handles.append(h)
            style_labels.append(normalized)

        # Zwei getrennte Legenden: links Emittenten, rechts Typ
        if issuer_handles:
            leg1 = self.ax_vol.legend(
                issuer_handles,
                issuer_labels,
                title="Emittenten",
                loc="upper left",
                fontsize=8,
            )
            self.ax_vol.add_artist(leg1)

        if style_handles:
            self.ax_vol.legend(
                style_handles,
                style_labels,
                title="Typ",
                loc="upper right",
                fontsize=8,
            )

    # ---------- Toggles ----------
    def _toggle_issuer(self, issuer: str):
        on = bool(self._issuer_vars[issuer].get())
        for (iss, cp), ln in list(self._lines_vol.items()):
            if iss == issuer:
                ln.set_visible(on)
        # Y-Limits nach Sichtbarkeit neu setzen
        self._set_dynamic_ylim()
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
