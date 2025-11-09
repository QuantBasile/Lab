# ui/volume_table.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import numpy as np

from ui.table_widget import TableFrame


class VolumeTable(ttk.Frame):
    """
    Reiter 'Volumen-Tabelle':
      - Zeilen = wählbare Gruppierung (UND_NAME / CALL_OPTION / UND_TYPE / TYPE)
      - Spalten = ISSUER_NAME
      - Werte = Σ TXN_AMT
      - Modi: ABSOLUT | PRO_ZEILE_%
      - Optionale Summen (Zeile 'ALL' und Spalte 'ALL')
      - Export: CSV des sichtbaren Inhalts
      - Kopieren in die Zwischenablage (TSV)
      - Status: Dimensionen (Zeilen × Spalten) des dargestellten Inhalts
    """

    GROUP_FIELDS = ("UND_NAME", "CALL_OPTION", "UND_TYPE", "TYPE")
    MODES = ("ABSOLUT", "PRO_ZEILE_%")

    def __init__(self, master=None):
        super().__init__(master)
        self._df = None
        self._pivot_abs = pd.DataFrame()
        self._pivot_view = pd.DataFrame()

        self._group_by = tk.StringVar(value="UND_NAME")
        self._mode = tk.StringVar(value="ABSOLUT")
        self._with_totals = tk.BooleanVar(value=True)
        self._index_name = "UND_NAME"

        self._build_style()
        self._build()

    # ---------------- Style ----------------
    def _build_style(self):
        """Definiert den grünen Hintergrundrahmen nur für diese Registerkarte."""
        self.LIGHT_GREEN = "#e6f7ec"  # sehr helles Grün für den Rahmen

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "VolumeTable.TFrame",
            background=self.LIGHT_GREEN,
        )

        # diesen Stil auf das Wurzel-Frame anwenden
        self.configure(style="VolumeTable.TFrame")

    # ---------------- UI ----------------
    def _build(self):
        # Layout principal
        self.rowconfigure(1, weight=1)   # tabla
        self.columnconfigure(0, weight=1)

        # Topbar (controles)
        top = ttk.Frame(self, style="VolumeTable.TFrame")
        top.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        for c in range(10):
            top.columnconfigure(c, weight=0)
        top.columnconfigure(9, weight=1)

        ttk.Label(top, text="Gruppieren nach:").grid(row=0, column=0, padx=(0, 6))
        cmb_group = ttk.Combobox(
            top,
            values=self.GROUP_FIELDS,
            textvariable=self._group_by,
            width=14,
            state="readonly",
        )
        cmb_group.grid(row=0, column=1)
        cmb_group.bind("<<ComboboxSelected>>", lambda e: self._rebuild_and_refresh())

        ttk.Label(top, text="Ansicht:").grid(row=0, column=2, padx=(12, 6))
        cmb_mode = ttk.Combobox(
            top,
            values=self.MODES,
            textvariable=self._mode,
            width=12,
            state="readonly",
        )
        cmb_mode.grid(row=0, column=3)
        cmb_mode.bind("<<ComboboxSelected>>", lambda e: self._refresh_table())

        chk = ttk.Checkbutton(
            top,
            text="Summen einblenden",
            variable=self._with_totals,
            command=self._refresh_table,
        )
        chk.grid(row=0, column=4, padx=(12, 0))

        # Acciones: Copiar / Export CSV
        btn_copy = ttk.Button(top, text="Kopieren", command=self._copy_to_clipboard)
        btn_csv = ttk.Button(top, text="Als CSV exportieren", command=self._export_csv)
        btn_copy.grid(row=0, column=5, padx=(12, 4))
        btn_csv.grid(row=0, column=6, padx=(4, 0))

        # Contenedor de tabla
        body = ttk.Frame(self, style="VolumeTable.TFrame")
        body.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 4))
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        self.table = TableFrame(body)
        self.table.grid(row=0, column=0, sticky="nsew")

        # Status bar (dimensiones)
        status = ttk.Frame(self, style="VolumeTable.TFrame")
        status.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        status.columnconfigure(0, weight=1)
        self._shape_var = tk.StringVar(value="Dimensionen: 0 × 0")
        self.lbl_shape = ttk.Label(status, textvariable=self._shape_var, anchor="e")
        self.lbl_shape.grid(row=0, column=0, sticky="e")

    # ---------------- API ----------------
    def update_view(self, df: pd.DataFrame):
        """Nimmt gefiltertes DataFrame entgegen und aktualisiert die Tabelle."""
        self._df = df
        self._rebuild_and_refresh()

    # ------------- Build + Refresh -------------
    def _rebuild_and_refresh(self):
        self._prepare_pivot()
        self._refresh_table()

    def _prepare_pivot(self):
        self._pivot_abs = pd.DataFrame()
        self._pivot_view = pd.DataFrame()

        if self._df is None or self._df.empty:
            return

        s = self._df.copy()

        # Resolver campo de agrupación
        grp_field = self._group_by.get()
        idx_col_internal = grp_field

        if grp_field == "UND_NAME":
            if "UND_NAME" in s.columns:
                idx_col_internal = "UND_NAME"
                self._index_name = "UND_NAME"
            elif "NAME" in s.columns:
                s["UND_NAME_FALLBACK"] = s["NAME"]
                idx_col_internal = "UND_NAME_FALLBACK"
                self._index_name = "UND_NAME"
            else:
                idx_col_internal = "UND_NAME_SYN"
                s[idx_col_internal] = "(UND_NAME fehlt)"
                self._index_name = "UND_NAME"
        else:
            if grp_field not in s.columns:
                s[grp_field] = f"({grp_field} fehlt)"
            self._index_name = grp_field
            idx_col_internal = grp_field

        if "ISSUER_NAME" not in s.columns or "TXN_AMT" not in s.columns:
            return

        pv = pd.pivot_table(
            s,
            index=idx_col_internal,
            columns="ISSUER_NAME",
            values="TXN_AMT",
            aggfunc="sum",
            fill_value=0.0,
            observed=False
        )

        # Orden estable
        pv = pv.reindex(sorted(pv.columns), axis=1)
        row_totals = pv.sum(axis=1).sort_values(ascending=False)
        pv = pv.loc[row_totals.index]

        self._pivot_abs = pv.rename_axis(index=self._index_name, columns="ISSUER_NAME")

    def _compute_view(self) -> pd.DataFrame:
        pv = self._pivot_abs.copy()
        if pv.empty:
            return pv

        mode = self._mode.get()

        if mode == "ABSOLUT":
            # Kompatibilität: falls noch alter Wert im State -> mappen
            mode = "ABSOLUT"  # no-op, aber por seguridad
        # Modus-Übersetzung: intern arbeiten wir mit deutschem Text
        if mode == "ABSOLUT":
            out = pv
        elif mode == "ABSOLUT":  # fallback
            out = pv
        else:  # PRO_ZEILE_%
            sums = pv.sum(axis=1).replace(0.0, np.nan)
            out = pv.div(sums, axis=0).fillna(0.0) * 100.0

        if self._with_totals.get():
            out = self._with_totals_df(out, self._mode.get())

        return out

    def _with_totals_df(self, dfv: pd.DataFrame, mode: str) -> pd.DataFrame:
        df = dfv.copy()
        if df.empty:
            return df

        if mode in ("ABSOLUT", "ABSOLUT"):  # por si hubiera estado antiguo en el state
            row_sum = df.sum(axis=1)
            col_sum = df.sum(axis=0)
            all_sum = row_sum.sum()
            df["ALL"] = row_sum
            df.loc["ALL"] = list(col_sum.values) + [all_sum]
        else:  # PRO_ZEILE_%
            df["ALL"] = 100.0
            col_avg = df.drop(columns=["ALL"], errors="ignore").mean(axis=0)
            df.loc["ALL"] = list(col_avg.values) + [100.0]
        return df

    def _refresh_table(self):
        try:
            self._pivot_view = self._compute_view()
            if self._pivot_view.empty:
                self.table.show_dataframe(pd.DataFrame(columns=[self._index_name]))
                self._force_right_alignment()
                self._update_shape_label(0, 0)
                return

            # Mover 'ALL' al final si existe
            idx = list(self._pivot_view.index)
            if "ALL" in idx:
                idx_no_all = [i for i in idx if i != "ALL"]
                idx = idx_no_all + ["ALL"]
                self._pivot_view = self._pivot_view.loc[idx]

            df_show = (
                self._pivot_view.reset_index().rename(columns={self._index_name: "GROUP"})
            )
            self.table.show_dataframe(df_show)

            # Forzar alineación a la derecha de todas las columnas en ESTA tabla
            self._force_right_alignment()

            # Status de dimensiones (Zeilen × Spalten) tal y como se ve en pantalla
            r, c = df_show.shape  # incluye columna GROUP
            self._update_shape_label(r, c)

        except Exception as ex:
            messagebox.showerror("Fehler", f"Tabelle konnte nicht aktualisiert werden:\n{ex}")

    def _force_right_alignment(self):
        """
        Fuerza que todas las columnas del Treeview de esta pestaña
        aparezcan alineadas a la derecha.
        """
        tree = self.table._tree  # usamos el Treeview interno de TableFrame
        cols = tree["columns"]
        for c in cols:
            tree.column(c, anchor="e")

    # ---------------- Export / Clipboard ----------------
    def _export_csv(self):
        if self._pivot_view is None or self._pivot_view.empty:
            messagebox.showinfo("Exportieren", "Keine Daten zum Exportieren.")
            return
        df_out = (
            self._pivot_view.reset_index().rename(columns={self._index_name: "GROUP"})
        )
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        try:
            df_out.to_csv(path, index=False)
            messagebox.showinfo("Exportieren", f"Erfolgreich exportiert:\n{path}")
        except Exception as ex:
            messagebox.showerror("Exportieren", f"Export fehlgeschlagen:\n{ex}")

    def _copy_to_clipboard(self):
        """Kopiert den sichtbaren Tabelleninhalt (TSV) in die Zwischenablage."""
        if self._pivot_view is None or self._pivot_view.empty:
            messagebox.showinfo("Kopieren", "Keine Daten zum Kopieren.")
            return
        df_out = (
            self._pivot_view.reset_index().rename(columns={self._index_name: "GROUP"})
        )
        try:
            tsv = df_out.to_csv(sep="\t", index=False)
            self.clipboard_clear()
            self.clipboard_append(tsv)
            self.update()
            messagebox.showinfo("Kopieren", "Tabelle in die Zwischenablage kopiert.")
        except Exception as ex:
            messagebox.showerror("Kopieren", f"Konnte nicht kopiert werden:\n{ex}")

    # ---------------- Helpers ----------------
    def _update_shape_label(self, rows: int, cols: int):
        self._shape_var.set(f"Dimensionen: {rows} × {cols}")
