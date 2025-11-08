import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import numpy as np
import csv


class HSBCMarktanteil(ttk.Frame):
    """
    Pestaña enfocada en HSBC:
    - Tabla de TODOS los subyacentes (UND_NAME / NAME) donde HSBC opera.
    - Para cada subyacente se muestra:
        * Volumen HSBC último mes y última semana
        * Marktanteil (%) mes y semana
        * Cambio de Marktanteil (en puntos porcentuales) vs periodo anterior
        * Volumen total del mercado (último mes, no solo HSBC)
    - Sin paginación (scroll sencillo).
    - Abajo solo textos:
        * Último mes / mes anterior
        * Última semana / semana anterior
    - Botones:
        * Copiar (filas seleccionadas) al portapapeles en CSV
        * Exportar CSV (toda la tabla visible)
    - Cabeceras clicables para ordenar columnas (con ▲ / ▼).
    """

    TARGET_ISSUER = "HSBC"  # cambia aquí si en tus datos el nombre es distinto

    def __init__(self, master=None):
        super().__init__(master)
        self._df = None

        # Data interna para la tabla
        self._summary_df = None
        self._columns = []
        self._headers = []
        self._sort_state = {}  # col -> ascending True/False

        self._build_ui()

    # ------------ helpers columnas tiempo -------------
    @staticmethod
    def _ensure_time_cols(df: pd.DataFrame) -> pd.DataFrame:
        """Garantiza WEEK y MONTH a partir de TRANSACTION_DATE."""
        if df is None or df.empty:
            return df
        s = df.copy()

        if "TRANSACTION_DATE" not in s.columns:
            return s

        if not pd.api.types.is_datetime64_any_dtype(s["TRANSACTION_DATE"]):
            s["TRANSACTION_DATE"] = pd.to_datetime(s["TRANSACTION_DATE"], errors="coerce")

        s = s.dropna(subset=["TRANSACTION_DATE"])

        if "WEEK" not in s.columns:
            s["WEEK"] = s["TRANSACTION_DATE"].dt.to_period("W-MON").dt.start_time
        if "MONTH" not in s.columns:
            s["MONTH"] = s["TRANSACTION_DATE"].dt.to_period("M").dt.start_time

        return s

    # ------------ UI -------------
    def _build_ui(self):
        self.rowconfigure(2, weight=1)   # la tabla está en row=2
        self.columnconfigure(0, weight=1)

        title = ttk.Label(
            self,
            text="HSBC Marktanteil por subyacente",
            font=("Segoe UI Semibold", 11),
        )
        title.grid(row=0, column=0, sticky="w", padx=10, pady=(8, 2))

        # Barra de botones (Copiar / Exportar CSV)
        toolbar = ttk.Frame(self)
        toolbar.grid(row=1, column=0, sticky="w", padx=8, pady=(2, 2))

        btn_copy = ttk.Button(toolbar, text="Copiar", command=self._copy_selection)
        btn_export = ttk.Button(toolbar, text="Export CSV", command=self._export_csv)
        btn_copy.grid(row=0, column=0, padx=(0, 4))
        btn_export.grid(row=0, column=1, padx=(4, 0))

        # Contenedor tabla + scroll
        table_frame = ttk.Frame(self)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(4, 4))
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(table_frame, show="headings", selectmode="extended")
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        # Estilos básicos
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "HSBCTree.Treeview",
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground="#111111",
            rowheight=24,
            font=("Segoe UI", 10),
        )
        style.configure(
            "HSBCTree.Treeview.Heading",
            background="#1e40af",
            foreground="#ffffff",
            font=("Segoe UI Semibold", 10),
            padding=(6, 4),
        )
        self.tree.configure(style="HSBCTree.Treeview")

        # Zebra striping (solo filas alternas)
        self.tree.tag_configure("even", background="#f9fafb")
        self.tree.tag_configure("odd", background="#ffffff")

        # Bind para copiar con Ctrl+C
        self.tree.bind("<Control-c>", lambda e: self._copy_selection())

        # Resumen textual abajo
        info_frame = ttk.Frame(self)
        info_frame.grid(row=3, column=0, sticky="w", padx=10, pady=(4, 8))

        self.lbl_months = ttk.Label(info_frame, text="", font=("Segoe UI", 9))
        self.lbl_weeks = ttk.Label(info_frame, text="", font=("Segoe UI", 9))

        self.lbl_months.grid(row=0, column=0, sticky="w", padx=(0, 20))
        self.lbl_weeks.grid(row=0, column=1, sticky="w")

    # ------------ API pública -------------
    def update_plot(self, df: pd.DataFrame):
        """Entry point: recibe DF filtrado global y refresca la pestaña."""
        self._df = df
        self._refresh()

    # ------------ lógica principal -------------
    def _refresh(self):
        # Reset árbol
        for col in self.tree["columns"]:
            self.tree.heading(col, text="", command=None)
        self.tree.delete(*self.tree.get_children())
        self._summary_df = None
        self._columns = []
        self._headers = []
        self._sort_state = {}

        if self._df is None or self._df.empty:
            self.tree["columns"] = ("UNDERLYING",)
            self.tree.heading("UNDERLYING", text="UNDERLYING")
            self.lbl_months.config(text="Último mes: -   ·   Mes anterior: -")
            self.lbl_weeks.config(text="Última semana: -   ·   Semana anterior: -")
            return

        s = self._ensure_time_cols(self._df)

        # Determinar columna de subyacente
        if "UND_NAME" in s.columns:
            und_col = "UND_NAME"
        elif "NAME" in s.columns:
            und_col = "NAME"
        else:
            und_col = "UNDERLYING"
            if und_col not in s.columns:
                s[und_col] = "(unknown)"

        s["ISSUER_NAME"] = s["ISSUER_NAME"].astype(str)
        mask_hsbc = s["ISSUER_NAME"] == self.TARGET_ISSUER
        if not mask_hsbc.any():
            self.tree["columns"] = ("UNDERLYING",)
            self.tree.heading("UNDERLYING", text="UNDERLYING")
            self.lbl_months.config(text="Último mes: -   ·   Mes anterior: -")
            self.lbl_weeks.config(text="Última semana: -   ·   Semana anterior: -")
            return

        # --- Semanas / meses disponibles ---
        weeks = sorted(s["WEEK"].dropna().unique())
        months = sorted(s["MONTH"].dropna().unique())
        if not weeks or not months:
            self.tree["columns"] = ("UNDERLYING",)
            self.tree.heading("UNDERLYING", text="UNDERLYING")
            self.lbl_months.config(text="Último mes: -   ·   Mes anterior: -")
            self.lbl_weeks.config(text="Última semana: -   ·   Semana anterior: -")
            return

        last_week = weeks[-1]
        prev_week = weeks[-2] if len(weeks) > 1 else None
        last_month = months[-1]
        prev_month = months[-2] if len(months) > 1 else None

        # --- AGRUPACIONES MENSUALES ---
        tot_m = s.groupby(["MONTH", und_col], sort=False)["TXN_AMT"].sum().rename("TOT_M")
        hsbc_m = s[mask_hsbc].groupby(["MONTH", und_col], sort=False)["TXN_AMT"].sum().rename("HSBC_M")
        df_m = pd.concat([hsbc_m, tot_m], axis=1).reset_index()
        df_m["HSBC_M"] = df_m["HSBC_M"].fillna(0.0)
        df_m["TOT_M"] = df_m["TOT_M"].fillna(0.0)
        df_m["SHARE_M_%"] = np.where(df_m["TOT_M"] > 0, df_m["HSBC_M"] / df_m["TOT_M"] * 100.0, 0.0)

        m_last = df_m[df_m["MONTH"] == last_month].set_index(und_col)
        if prev_month is not None:
            m_prev = df_m[df_m["MONTH"] == prev_month].set_index(und_col)
        else:
            m_prev = pd.DataFrame(columns=df_m.columns).set_index(und_col)

        # --- AGRUPACIONES SEMANALES ---
        tot_w = s.groupby(["WEEK", und_col], sort=False)["TXN_AMT"].sum().rename("TOT_W")
        hsbc_w = s[mask_hsbc].groupby(["WEEK", und_col], sort=False)["TXN_AMT"].sum().rename("HSBC_W")
        df_w = pd.concat([hsbc_w, tot_w], axis=1).reset_index()
        df_w["HSBC_W"] = df_w["HSBC_W"].fillna(0.0)
        df_w["TOT_W"] = df_w["TOT_W"].fillna(0.0)
        df_w["SHARE_W_%"] = np.where(df_w["TOT_W"] > 0, df_w["HSBC_W"] / df_w["TOT_W"] * 100.0, 0.0)

        w_last = df_w[df_w["WEEK"] == last_week].set_index(und_col)
        if prev_week is not None:
            w_prev = df_w[df_w["WEEK"] == prev_week].set_index(und_col)
        else:
            w_prev = pd.DataFrame(columns=df_w.columns).set_index(und_col)

        # --- Construir resumen por subyacente (basado en último mes) ---
        rows = []
        for underlying, row_m in m_last.iterrows():
            vol_m = float(row_m.get("HSBC_M", 0.0))
            share_m = float(row_m.get("SHARE_M_%", 0.0))
            tot_vol_m = float(row_m.get("TOT_M", 0.0))   # volumen total mercado (último mes)

            share_m_prev = 0.0
            if underlying in m_prev.index:
                share_m_prev = float(m_prev.loc[underlying].get("SHARE_M_%", 0.0))
            delta_m = share_m - share_m_prev

            # Semana: puede no existir
            if underlying in w_last.index:
                row_w = w_last.loc[underlying]
                vol_w = float(row_w.get("HSBC_W", 0.0))
                share_w = float(row_w.get("SHARE_W_%", 0.0))
            else:
                vol_w = 0.0
                share_w = 0.0

            share_w_prev = 0.0
            if underlying in w_prev.index:
                share_w_prev = float(w_prev.loc[underlying].get("SHARE_W_%", 0.0))
            delta_w = share_w - share_w_prev

            rows.append({
                "UNDERLYING": underlying,
                "HSBC_VOL_M": vol_m,
                "SHARE_M_%": share_m,
                "DELTA_M_pp": delta_m,
                "HSBC_VOL_W": vol_w,
                "SHARE_W_%": share_w,
                "DELTA_W_pp": delta_w,
                "TOT_VOL_M": tot_vol_m,
            })

        if not rows:
            self.tree["columns"] = ("UNDERLYING",)
            self.tree.heading("UNDERLYING", text="UNDERLYING")
            self.lbl_months.config(text="Último mes: -   ·   Mes anterior: -")
            self.lbl_weeks.config(text="Última semana: -   ·   Semana anterior: -")
            return

        summary = pd.DataFrame(rows)

        # Orden por defecto: volumen mensual HSBC descendente (todos, sin limitar)
        summary = summary.sort_values("HSBC_VOL_M", ascending=False).reset_index(drop=True)

        # Guardar internamente
        self._summary_df = summary

        # Configurar columnas en Treeview
        self._columns = [
            "UNDERLYING",
            "HSBC_VOL_M", "SHARE_M_%", "DELTA_M_pp",
            "HSBC_VOL_W", "SHARE_W_%", "DELTA_W_pp",
            "TOT_VOL_M",
        ]
        self._headers = [
            "UNDERLYING",
            "HSBC vol mes", "Share mes (%)", "Δ Share mes (pp)",
            "HSBC vol semana", "Share semana (%)", "Δ Share semana (pp)",
            "Volumen total mes",
        ]
        self.tree["columns"] = self._columns
        self._sort_state = {}  # reset sort

        # Configurar cabeceras con callback para ordenar
        for col, text in zip(self._columns, self._headers):
            self.tree.heading(
                col,
                text=text,
                command=lambda c=col: self._on_sort(c)
            )
            anchor = "w" if col == "UNDERLYING" else "e"
            self.tree.column(col, width=130, anchor=anchor, stretch=True)

        # Rellenar tabla
        self._populate_tree(self._summary_df)

        # Textos inferior: último/prev mes y semana
        def _fmt_date(x):
            try:
                return pd.to_datetime(x).date().isoformat()
            except Exception:
                return "-"

        txt_months = (
            f"Último mes: {_fmt_date(last_month)}   ·   "
            f"Mes anterior: {_fmt_date(prev_month) if prev_month is not None else '-'}"
        )
        txt_weeks = (
            f"Última semana: {_fmt_date(last_week)}   ·   "
            f"Semana anterior: {_fmt_date(prev_week) if prev_week is not None else '-'}"
        )

        self.lbl_months.config(text=txt_months)
        self.lbl_weeks.config(text=txt_weeks)

    # ---------- rellenar Treeview ----------
    def _populate_tree(self, df: pd.DataFrame):
        self.tree.delete(*self.tree.get_children())
        if df is None or df.empty:
            return

        for idx, row in df.iterrows():
            underlying = row["UNDERLYING"]

            vol_m = row["HSBC_VOL_M"]
            vol_w = row["HSBC_VOL_W"]
            share_m = row["SHARE_M_%"]
            delta_m = row["DELTA_M_pp"]
            share_w = row["SHARE_W_%"]
            delta_w = row["DELTA_W_pp"]
            tot_vol_m = row["TOT_VOL_M"]

            values = [
                underlying,
                f"{vol_m:,.0f}".replace(",", " "),
                f"{share_m:,.2f}",
                f"{delta_m:+.2f}",
                f"{vol_w:,.0f}".replace(",", " "),
                f"{share_w:,.2f}",
                f"{delta_w:+.2f}",
                f"{tot_vol_m:,.0f}".replace(",", " "),
            ]

            base_tag = "even" if (len(self.tree.get_children()) % 2 == 0) else "odd"
            self.tree.insert("", "end", values=values, tags=(base_tag,))

    # ---------- ordenar por columna ----------
    def _on_sort(self, col: str):
        if self._summary_df is None or self._summary_df.empty:
            return

        # Toggle asc/desc
        current = self._sort_state.get(col)
        asc = True if current is None else not current
        self._sort_state = {col: asc}  # sólo una columna con estado guardado

        # Ordenar DataFrame
        try:
            sorted_df = self._summary_df.sort_values(col, ascending=asc, kind="mergesort")
        except Exception:
            # fallback: ordenar como string
            sorted_df = self._summary_df.copy()
            sorted_df["_tmp_col_sort"] = sorted_df[col].astype(str)
            sorted_df = sorted_df.sort_values("_tmp_col_sort", ascending=asc, kind="mergesort")
            sorted_df = sorted_df.drop(columns="_tmp_col_sort")

        self._summary_df = sorted_df.reset_index(drop=True)

        # Actualizar cabeceras con flechas
        for c, base_text in zip(self._columns, self._headers):
            state = self._sort_state.get(c)
            suffix = ""
            if state is True:
                suffix = " ▲"
            elif state is False:
                suffix = " ▼"
            self.tree.heading(
                c,
                text=base_text + suffix,
                command=lambda col=c: self._on_sort(col)
            )

        # Repintar tabla
        self._populate_tree(self._summary_df)

    # ---------- copiar selección ----------
    def _copy_selection(self):
        if not self._columns:
            return

        sel = self.tree.selection()
        if not sel:
            return

        # Cabecera
        lines = [",".join(self._headers)]

        # Filas seleccionadas
        for iid in sel:
            vals = list(self.tree.item(iid, "values"))
            row = []
            for v in vals:
                v = str(v)
                v = v.replace('"', '""')
                if any(ch in v for ch in [",", '"', "\n"]):
                    v = f'"{v}"'
                row.append(v)
            lines.append(",".join(row))

        txt = "\n".join(lines)
        try:
            self.clipboard_clear()
            self.clipboard_append(txt)
        except Exception:
            pass  # en entornos raros puede fallar

    # ---------- export CSV ----------
    def _export_csv(self):
        if self._summary_df is None or self._summary_df.empty:
            messagebox.showinfo("Export CSV", "No hay datos para exportar.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Exportar HSBC Marktanteil a CSV",
        )
        if not path:
            return

        # Exportar en el orden actual visible (treeview)
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self._headers)
                for iid in self.tree.get_children():
                    vals = list(self.tree.item(iid, "values"))
                    writer.writerow(vals)
        except Exception as ex:
            messagebox.showerror("Export CSV", f"Error al exportar CSV:\n{ex}")
        else:
            messagebox.showinfo("Export CSV", f"Exportado correctamente a:\n{path}")
