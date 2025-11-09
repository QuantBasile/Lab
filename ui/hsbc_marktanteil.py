import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import numpy as np
import csv

from pandas.api.types import is_datetime64_any_dtype

class HSBCMarktanteil(ttk.Frame):
    """
    Registerkarte fokussiert auf HSBC:
    - Tabelle aller Underlyings (UND_NAME / NAME), an denen HSBC beteiligt ist.
    - Für jedes Underlying:
        * HSBC-Volumen (letzter Monat und letzte Woche)
        * Marktanteil (%) im Monat und in der Woche
        * Veränderung des Marktanteils (in Prozentpunkten) gegenüber dem vorherigen Zeitraum
        * Gesamtmarktvolumen (nur letzter Monat)
    """

    TARGET_ISSUER = "HSBC"

    def __init__(self, master=None):
        super().__init__(master)

        self._df = None
        self._summary_df = None

        self._columns = []
        self._headers = []
        self._sort_state = {}  # col -> ascending True/False

        self._build_ui()

    # ------------ Zeitspalten-Helper -------------
    @staticmethod
    def _ensure_time_cols(df: pd.DataFrame) -> pd.DataFrame:
        """Stellt sicher, dass WEEK und MONTH aus TRANSACTION_DATE abgeleitet sind (optimizado)."""
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
        if "WEEK" not in s.columns:
            need_copy = True
        if "MONTH" not in s.columns:
            need_copy = True
    
        if need_copy:
            s = s.copy()
            if "WEEK" not in s.columns:
                s["WEEK"] = s["TRANSACTION_DATE"].dt.to_period("W-MON").dt.start_time
            if "MONTH" not in s.columns:
                s["MONTH"] = s["TRANSACTION_DATE"].dt.to_period("M").dt.start_time
    
        return s


    # ------------ UI-Aufbau -------------
    def _build_ui(self):
        # Layout
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        # Obere Zeile: Titel + Buttons
        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        top.columnconfigure(0, weight=1)

        title = ttk.Label(
            top,
            text="HSBC Marktanteil nach Underlying",
            font=("Segoe UI Semibold", 11),
        )
        title.grid(row=0, column=0, sticky="w", padx=(2, 8))

        btn_copy = ttk.Button(top, text="Kopieren", command=self._copy_selection)
        btn_export = ttk.Button(top, text="Als CSV exportieren", command=self._export_csv)
        btn_copy.grid(row=0, column=1, padx=(4, 4))
        btn_export.grid(row=0, column=2, padx=(0, 2))

        # Tabelle + Scrollbars
        table_frame = ttk.Frame(self)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 4))
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_frame, show="headings", selectmode="extended"
        )
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        # Treeview-Style (wie im alten Stil)
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

        # Zebra-Streifen
        self.tree.tag_configure("even", background="#f9fafb")
        self.tree.tag_configure("odd", background="#ffffff")

        # Strg+C → kopieren
        self.tree.bind("<Control-c>", lambda e: self._copy_selection())

        # Untere Infozeile
        info_frame = ttk.Frame(self)
        info_frame.grid(row=2, column=0, sticky="w", padx=10, pady=(2, 8))

        self.lbl_months = ttk.Label(info_frame, text="", font=("Segoe UI", 9))
        self.lbl_weeks = ttk.Label(info_frame, text="", font=("Segoe UI", 9))
        self.lbl_months.grid(row=0, column=0, sticky="w", padx=(0, 20))
        self.lbl_weeks.grid(row=0, column=1, sticky="w")

    # ------------ Öffentliche API -------------
    def update_plot(self, df: pd.DataFrame):
        """Entry-Point: nimmt gefiltertes DataFrame und aktualisiert die Registerkarte."""
        self._df = df
        self._refresh()

    # ------------ Hauptlogik -------------
    def _refresh(self):
        # Tree zurücksetzen
        for col in self.tree["columns"]:
            self.tree.heading(col, text="")
        self.tree.delete(*self.tree.get_children())
        self._summary_df = None
        self._columns = []
        self._headers = []
        self._sort_state = {}

        if self._df is None or self._df.empty:
            self.tree["columns"] = ("UNDERLYING",)
            self.tree.heading("UNDERLYING", text="Underlying")
            self.lbl_months.config(
                text="Letzter Monat: -   ·   Vorheriger Monat: -"
            )
            self.lbl_weeks.config(
                text="Letzte Woche: -   ·   Vorherige Woche: -"
            )
            return

        s = self._ensure_time_cols(self._df)

        # Underlying-Spalte bestimmen
        if "UND_NAME" in s.columns:
            und_col = "UND_NAME"
        elif "NAME" in s.columns:
            und_col = "NAME"
        else:
            und_col = "UNDERLYING"
            if und_col not in s.columns:
                s[und_col] = "(unbekannt)"

        s["ISSUER_NAME"] = s["ISSUER_NAME"].astype(str)
        mask_hsbc = s["ISSUER_NAME"] == self.TARGET_ISSUER

        # Falls HSBC nicht vorkommt
        if not mask_hsbc.any():
            self.tree["columns"] = ("UNDERLYING",)
            self.tree.heading("UNDERLYING", text="Underlying")
            self.lbl_months.config(
                text="Letzter Monat: -   ·   Vorheriger Monat: -"
            )
            self.lbl_weeks.config(
                text="Letzte Woche: -   ·   Vorherige Woche: -"
            )
            return

        # --- Verfügbare Wochen/Monate ---
        weeks = sorted(s["WEEK"].dropna().unique())
        months = sorted(s["MONTH"].dropna().unique())
        if not weeks or not months:
            self.tree["columns"] = ("UNDERLYING",)
            self.tree.heading("UNDERLYING", text="Underlying")
            self.lbl_months.config(
                text="Letzter Monat: -   ·   Vorheriger Monat: -"
            )
            self.lbl_weeks.config(
                text="Letzte Woche: -   ·   Vorherige Woche: -"
            )
            return

        last_week = weeks[-1]
        prev_week = weeks[-2] if len(weeks) > 1 else None
        last_month = months[-1]
        prev_month = months[-2] if len(months) > 1 else None

        # --- Monatsaggregation (Gesamtmarkt + HSBC) ---
        tot_m = (
            s.groupby(["MONTH", und_col], sort=False, observed=False)["TXN_AMT"]
            .sum()
            .rename("TOT_M")
        )
        hsbc_m = (
            s[mask_hsbc]
            .groupby(["MONTH", und_col], sort=False, observed=False)["TXN_AMT"]
            .sum()
            .rename("HSBC_M")
        )
        df_m = pd.concat([hsbc_m, tot_m], axis=1).reset_index()
        df_m["HSBC_M"] = df_m["HSBC_M"].fillna(0.0)
        df_m["TOT_M"] = df_m["TOT_M"].fillna(0.0)
        df_m["SHARE_M_%"] = np.where(
            df_m["TOT_M"] > 0, df_m["HSBC_M"] / df_m["TOT_M"] * 100.0, 0.0
        )

        # Letzter & vorheriger Monat
        m_last = df_m[df_m["MONTH"] == last_month].set_index(und_col)
        if prev_month is not None:
            m_prev = df_m[df_m["MONTH"] == prev_month].set_index(und_col)
        else:
            m_prev = pd.DataFrame(columns=df_m.columns).set_index(und_col)

        # --- Wochenaggregation ---
        tot_w = (
            s.groupby(["WEEK", und_col], sort=False, observed=False)["TXN_AMT"]
            .sum()
            .rename("TOT_W")
        )
        hsbc_w = (
            s[mask_hsbc]
            .groupby(["WEEK", und_col], sort=False, observed=False)["TXN_AMT"]
            .sum()
            .rename("HSBC_W")
        )
        df_w = pd.concat([hsbc_w, tot_w], axis=1).reset_index()
        df_w["HSBC_W"] = df_w["HSBC_W"].fillna(0.0)
        df_w["TOT_W"] = df_w["TOT_W"].fillna(0.0)
        df_w["SHARE_W_%"] = np.where(
            df_w["TOT_W"] > 0, df_w["HSBC_W"] / df_w["TOT_W"] * 100.0, 0.0
        )

        w_last = df_w[df_w["WEEK"] == last_week].set_index(und_col)
        if prev_week is not None:
            w_prev = df_w[df_w["WEEK"] == prev_week].set_index(und_col)
        else:
            w_prev = pd.DataFrame(columns=df_w.columns).set_index(und_col)

        # --- Zusammenfassung pro Underlying ---
        rows = []
        for underlying, row_m in m_last.iterrows():
            vol_m = float(row_m.get("HSBC_M", 0.0))
            share_m = float(row_m.get("SHARE_M_%", 0.0))
            tot_vol_m = float(row_m.get("TOT_M", 0.0))

            if underlying in m_prev.index:
                share_m_prev = float(m_prev.loc[underlying].get("SHARE_M_%", 0.0))
            else:
                share_m_prev = 0.0
            delta_m = share_m - share_m_prev

            if underlying in w_last.index:
                row_w = w_last.loc[underlying]
                vol_w = float(row_w.get("HSBC_W", 0.0))
                share_w = float(row_w.get("SHARE_W_%", 0.0))
            else:
                vol_w = 0.0
                share_w = 0.0

            if underlying in w_prev.index:
                share_w_prev = float(w_prev.loc[underlying].get("SHARE_W_%", 0.0))
            else:
                share_w_prev = 0.0
            delta_w = share_w - share_w_prev

            rows.append(
                {
                    "UNDERLYING": underlying,
                    "HSBC_VOL_M": vol_m,
                    "SHARE_M_%": share_m,
                    "DELTA_M_pp": delta_m,
                    "HSBC_VOL_W": vol_w,
                    "SHARE_W_%": share_w,
                    "DELTA_W_pp": delta_w,
                    "TOT_VOL_M": tot_vol_m,
                }
            )

        if not rows:
            self.tree["columns"] = ("UNDERLYING",)
            self.tree.heading("UNDERLYING", text="Underlying")
            self.lbl_months.config(
                text="Letzter Monat: -   ·   Vorheriger Monat: -"
            )
            self.lbl_weeks.config(
                text="Letzte Woche: -   ·   Vorherige Woche: -"
            )
            return

        summary = pd.DataFrame(rows)

        # Standard-Sortierung: nach HSBC-Volumen (Monat) absteigend
        summary = summary.sort_values("HSBC_VOL_M", ascending=False).reset_index(
            drop=True
        )
        self._summary_df = summary

        # Spalten & Überschriften
        self._columns = [
            "UNDERLYING",
            "HSBC_VOL_M",
            "SHARE_M_%",
            "DELTA_M_pp",
            "HSBC_VOL_W",
            "SHARE_W_%",
            "DELTA_W_pp",
            "TOT_VOL_M",
        ]
        self._headers = [
            "Underlying",
            "HSBC Volumen (Monat)",
            "Marktanteil Monat (%)",
            "Δ Marktanteil Monat (pp)",
            "HSBC Volumen (Woche)",
            "Marktanteil Woche (%)",
            "Δ Marktanteil Woche (pp)",
            "Gesamtvolumen Monat",
        ]
        self.tree["columns"] = self._columns
        self._sort_state = {}

        # Kopfzeilen mit Sortier-Callback
        for col, header in zip(self._columns, self._headers):
            self.tree.heading(col, text=header, command=lambda c=col: self._on_sort(c))
            anchor = "w" if col == "UNDERLYING" else "e"
            self.tree.column(col, width=130, anchor=anchor, stretch=True)

        # Tabelle füllen
        self._populate_tree(summary)

        # Infozeile unten
        fmt = lambda x: pd.to_datetime(x).strftime("%Y-%m-%d") if pd.notna(x) else "-"
        self.lbl_months.config(
            text=f"Letzter Monat: {fmt(last_month)}   ·   Vorheriger Monat: {fmt(prev_month)}"
        )
        self.lbl_weeks.config(
            text=f"Letzte Woche: {fmt(last_week)}   ·   Vorherige Woche: {fmt(prev_week)}"
        )

    # ------------ Tabelle befüllen -------------
    def _populate_tree(self, df: pd.DataFrame):
        self.tree.delete(*self.tree.get_children())
        for idx, row in df.iterrows():
            vals = [
                row["UNDERLYING"],
                f"{row['HSBC_VOL_M']:,.0f}".replace(",", " "),
                f"{row['SHARE_M_%']:.2f}",
                f"{row['DELTA_M_pp']:+.2f}",
                f"{row['HSBC_VOL_W']:,.0f}".replace(",", " "),
                f"{row['SHARE_W_%']:.2f}",
                f"{row['DELTA_W_pp']:+.2f}",
                f"{row['TOT_VOL_M']:,.0f}".replace(",", " "),
            ]
            tag = "even" if idx % 2 == 0 else "odd"
            self.tree.insert("", "end", values=vals, tags=(tag,))

    # ------------ Sortierung -------------
    def _on_sort(self, col: str):
        if self._summary_df is None or self._summary_df.empty:
            return

        asc = not self._sort_state.get(col, False)
        self._sort_state = {col: asc}

        df = self._summary_df.sort_values(col, ascending=asc).reset_index(drop=True)
        self._summary_df = df

        # Pfeile in Kopfzeile
        for c, base in zip(self._columns, self._headers):
            arrow = ""
            if c == col:
                arrow = " ▲" if asc else " ▼"
            self.tree.heading(
                c,
                text=base + arrow,
                command=lambda cc=c: self._on_sort(cc),
            )

        self._populate_tree(df)

    # ------------ Kopieren -------------
    def _copy_selection(self):
        if not self._columns:
            return

        sel = self.tree.selection()
        if not sel:
            return

        lines = [",".join(self._headers)]

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
            # In manchen Umgebungen kann das fehlschlagen (z.B. SSH ohne CLIPBOARD)
            pass

    # ------------ CSV-Export -------------
    def _export_csv(self):
        if self._summary_df is None or self._summary_df.empty:
            messagebox.showinfo("Exportieren", "Keine Daten zum Exportieren.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[
                ("CSV-Dateien", "*.csv"),
                ("Alle Dateien", "*.*"),
            ],
            title="HSBC-Marktanteil als CSV exportieren",
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self._headers)
                for iid in self.tree.get_children():
                    vals = list(self.tree.item(iid, "values"))
                    writer.writerow(vals)
        except Exception as ex:
            messagebox.showerror("Exportieren", f"Fehler beim Export:\n{ex}")
        else:
            messagebox.showinfo("Exportieren", f"Erfolgreich exportiert nach:\n{path}")
