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


class CallPutRolling(ttk.Frame):
    """
    Pestaña: Rolling 7 días por emisor, diferenciando CALL/PUT.

    Layout:
      - Sidebar izquierda: lista de emisores con checkboxes (Todos ON / OFF)
      - Centro: UNA figura con 1 gráfico:
          * Volumen rolling 7d (TXN_AMT) por emisor y CALL/PUT
          * Color = emisor
          * linestyle = tipo de opción (CALL/PUT/otro)

    Convención de estilos:
      - Color: por emisor (constante en el gráfico)
      - linestyle:
          CALL / C  -> '-'
          PUT  / P  -> '--'
          otros     -> ':'

    API:
      update_plot(df: pd.DataFrame)
        Requiere columnas mínimas:
          TRANSACTION_DATE, TXN_AMT, CALL_OPTION, ISSUER_NAME
    """

    def __init__(self, master=None):
        super().__init__(master)
        self._df = None

        self._issuers = []
        self._issuer_vars = {}     # issuer -> BooleanVar
        self._issuer_checks = {}   # issuer -> Checkbutton
        self._issuer_colors = {}   # issuer -> color (hex)

        self._full_range = None    # DatetimeIndex de días
        self._lines_vol = {}       # (issuer, cp) -> Line2D

        self._build()

    # ------------- helpers de tiempo --------------
    def _ensure_time_cols(self, df: pd.DataFrame) -> pd.DataFrame:
        """Garantiza que exista DAY a partir de TRANSACTION_DATE."""
        if df is None or df.empty:
            return df
        s = df.copy()

        if "TRANSACTION_DATE" not in s.columns:
            return s

        if not pd.api.types.is_datetime64_any_dtype(s["TRANSACTION_DATE"]):
            s["TRANSACTION_DATE"] = pd.to_datetime(s["TRANSACTION_DATE"], errors="coerce")

        s = s.dropna(subset=["TRANSACTION_DATE"])

        if "DAY" not in s.columns:
            s["DAY"] = s["TRANSACTION_DATE"].dt.normalize()

        return s

    # ------------- UI build --------------
    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        # Sidebar emisores
        self.sidebar = tk.Frame(self, bg="#FFF4E5", bd=0, highlightthickness=0, width=140)
        self.sidebar.grid(row=1, column=0, sticky="nsw", padx=(6, 8), pady=(4, 6))
        self.sidebar.grid_propagate(False)
        self._build_sidebar()

        # Contenedor central para plot
        center = tk.Frame(self, bg="white", bd=0, highlightthickness=0)
        center.grid(row=1, column=1, sticky="nsew", padx=(0, 6), pady=(4, 6))
        center.rowconfigure(1, weight=1)
        center.columnconfigure(0, weight=1)

        # Figura con un solo eje
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
            text="Emisores",
            bg="#FFF4E5",
            fg="#7A3E00",
            font=("Segoe UI Semibold", 10),
        ).pack(anchor="w", padx=4, pady=(4, 2))

        btns = tk.Frame(self.sidebar, bg="#FFF4E5")
        btns.pack(fill="x", padx=4, pady=(0, 4))

        tk.Button(
            btns, text="Todos ON", command=self._all_on,
            bg="white", relief="solid", bd=1, padx=4, pady=1, cursor="hand2"
        ).pack(fill="x", pady=(0, 4))

        tk.Button(
            btns, text="Todos OFF", command=self._all_off,
            bg="white", relief="solid", bd=1, padx=4, pady=1, cursor="hand2"
        ).pack(fill="x", pady=(0, 4))

        # scroll para emisores
        list_container = tk.Frame(self.sidebar, bg="#FFF4E5")
        list_container.pack(fill="both", expand=True, padx=4, pady=(2, 6))

        self._issuer_canvas = tk.Canvas(
            list_container, borderwidth=0, highlightthickness=0, bg="#FFF4E5", width=128
        )
        vsb = ttk.Scrollbar(list_container, orient="vertical", command=self._issuer_canvas.yview)
        self._issuer_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        self._issuer_inner = tk.Frame(self._issuer_canvas, bg="#FFF4E5")
        self._issuer_canvas.create_window((0, 0), window=self._issuer_inner, anchor="nw")
        self._issuer_inner.bind(
            "<Configure>",
            lambda e: self._issuer_canvas.configure(scrollregion=self._issuer_canvas.bbox("all")),
        )
        self._issuer_canvas.pack(side="left", fill="both", expand=True)

    # ------------- API pública --------------
    def update_plot(self, df: pd.DataFrame):
        """Recibe DF filtrado y redibuja la pestaña."""
        self._df = df
        self._draw_all()

    # ------------- drawing --------------
    def _draw_all(self):
        # limpiar eje y estructuras
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
            self.ax_vol.text(0.5, 0.5, "No data", ha="center", va="center", transform=self.ax_vol.transAxes)
            self.canvas.draw_idle()
            return

        s = self._ensure_time_cols(self._df)

        required = {"TRANSACTION_DATE", "TXN_AMT", "CALL_OPTION", "ISSUER_NAME"}
        if not required.issubset(s.columns):
            msg = "Missing: " + ", ".join(sorted(required - set(s.columns)))
            self.ax_vol.text(0.5, 0.5, msg, ha="center", va="center", transform=self.ax_vol.transAxes)
            self.canvas.draw_idle()
            return

        s["CALL_OPTION"] = s["CALL_OPTION"].astype(str)
        s["ISSUER_NAME"] = s["ISSUER_NAME"].astype(str)

        # Issuers & rango de días
        self._issuers = sorted(s["ISSUER_NAME"].unique())
        self._full_range = pd.date_range(s["DAY"].min(), s["DAY"].max(), freq="D")

        # Sidebar emisores
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

        # Asignar colores por emisor usando el ciclo de la ax_vol
        callput_values = sorted(s["CALL_OPTION"].unique())

        for iss in self._issuers:
            if iss not in self._issuer_colors:
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
                    .fillna(0.0)
                )

                # rolling 7 días (media simple)
                roll_vol = pd.Series(daily.values, index=self._full_range).rolling(
                    window=7, min_periods=1
                ).mean()

                color = self._issuer_colors[iss]
                ls = self._linestyle_for_callput(cp)

                (ln_v,) = self.ax_vol.plot(
                    self._full_range,
                    roll_vol.values,
                    linewidth=1.4,
                    color=color,
                    linestyle=ls,
                    label=f"{iss} {cp}",
                )
                ln_v.set_visible(False)
                self._lines_vol[(iss, cp)] = ln_v

        # Formato de eje
        self._format_vol_axis()

        # Leyendas compactas: una por emisores (colores), otra por estilo (CALL/PUT)
        self._build_legends(callput_values)

        self.canvas.draw_idle()

    # ---------- formato eje ----------
    def _format_vol_axis(self):
        locator = mdates.AutoDateLocator()
        formatter = mdates.AutoDateFormatter(locator)
        self.ax_vol.xaxis.set_major_locator(locator)
        self.ax_vol.xaxis.set_major_formatter(formatter)
        self.ax_vol.yaxis.set_major_formatter(mticker.StrMethodFormatter('{x:,.0f}'))
        self.ax_vol.grid(True, alpha=0.3)
        self.ax_vol.set_title("Volumen rolling 7d por emisor y CALL/PUT")
        self.ax_vol.set_xlabel("")
        self.ax_vol.set_ylabel("")
        self.ax_vol.tick_params(axis="x", rotation=45)
        self.ax_vol.tick_params(axis="y", rotation=0)

    # ---------- estilos ----------
    @staticmethod
    def _linestyle_for_callput(cp_value: str) -> str:
        key = str(cp_value).upper()
        if key in ("CALL", "C"):
            return "-"
        if key in ("PUT", "P"):
            return "--"
        return ":"  # otros tipos

    # ---------- leyendas ----------
    def _build_legends(self, callput_values):
        # Leyenda de emisores (colores)
        issuer_handles = []
        issuer_labels = []
        for iss in self._issuers:
            color = self._issuer_colors.get(iss)
            if not color:
                continue
            h = Line2D([0], [0], color=color, linewidth=2.0)
            issuer_handles.append(h)
            issuer_labels.append(iss)

        # Leyenda de estilos CALL/PUT (linestyle)
        style_handles = []
        style_labels = []

        # Usamos un set de "tipos" normalizados (CALL, PUT, OTHER)
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

        # Colocamos dos leyendas: emisores (abajo izquierda) y estilos (abajo derecha)
        if issuer_handles:
            leg1 = self.ax_vol.legend(
                issuer_handles,
                issuer_labels,
                title="Emisores",
                loc="upper left",
                fontsize=8,
            )
            self.ax_vol.add_artist(leg1)

        if style_handles:
            self.ax_vol.legend(
                style_handles,
                style_labels,
                title="Tipo",
                loc="upper right",
                fontsize=8,
            )

    # ---------- toggles ----------
    def _toggle_issuer(self, issuer: str):
        on = bool(self._issuer_vars[issuer].get())
        for (iss, cp), ln in list(self._lines_vol.items()):
            if iss == issuer:
                ln.set_visible(on)
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
