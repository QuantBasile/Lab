#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import pandas as pd
from Datos import create_fake_transactions  # usa tu Datos.py

class DataService:
    """
    Servicio de datos con precarga y filtros vectorizados (NumPy).

    - generate_fake_transactions(von=None, bis=None, produktart="ALLE", n_rows=1_000_000)
      Genera el DF base y construye caches NumPy para filtrar rápido.

    - apply_filters(spec): spec del FiltersPanel, con claves:
        {
          "COL": {"type":"categorical","values":[...]},
          "COL": {"type":"numeric","min":"...","max":"..."},
          "COL": {"type":"date","start":"YYYY-mm-dd","end":"YYYY-mm-dd"}
        }

    - clear_filters(), dataframe_filtered
    """

    def __init__(self):
        self._df_original: pd.DataFrame | None = None
        self._df_filtered: pd.DataFrame | None = None

        # caches
        self._N: int = 0
        self._arr: dict[str, np.ndarray] = {}      # columnas numéricas/fecha -> ndarray
        self._cat_codes: dict[str, np.ndarray] = {}  # columna categórica -> codes
        self._cat_maps: dict[str, dict] = {}         # valor -> code

    # ------------------------------------------------------------------
    # 1) GENERACIÓN + PREPROCESADO + CACHES
    # ------------------------------------------------------------------
    def generate_fake_transactions(
        self,
        von=None,
        bis=None,
        produktart: str = "ALLE",
        n_rows: int = 1_000_000,
    ) -> pd.DataFrame:
        """
        Genera con tu Datos.py y construye caches para filtros rápidos.
        """
        df = create_fake_transactions(von=von, bis=bis, produktart=produktart, n_rows=n_rows)

        # Asegura dtypes esperados (Datos.py ya los deja bien, esto es seguridad)
        # Numéricos:
        num_cols = ["TXN_AMT", "STRIKE", "RATIO", "NBR_OF_UNITS", "NBR_OF_TRADES"]
        for c in num_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

        # Fechas:
        date_cols = [c for c in ("TRANSACTION_DATE", "EXPIRY", "DAY", "WEEK", "MONTH") if c in df.columns]
        for c in date_cols:
            if not pd.api.types.is_datetime64_any_dtype(df[c]):
                df[c] = pd.to_datetime(df[c], errors="coerce")

        # Categóricas:
        cat_cols = [c for c in ("ISSUER_NAME", "UND_TYPE", "TYPE", "CALL_OPTION", "NAME", "ISIN", "UND_ISIN") if c in df.columns]
        for c in cat_cols:
            if c in df.columns and df[c].dtype != "category":
                df[c] = df[c].astype("category")

        # ---- CACHES ----
        self._N = len(df)
        self._arr.clear()
        self._cat_codes.clear()
        self._cat_maps.clear()

        # Numéricos -> arrays directos (sin copia)
        for c in num_cols:
            if c in df.columns:
                self._arr[c] = df[c].to_numpy(copy=False)

        # Fechas -> int64 ns para comparaciones O(1)
        for c in date_cols:
            self._arr[c] = df[c].astype("int64", copy=False)


        # Categóricos -> codes + mapa valor->code
        for c in cat_cols:
            codes = df[c].cat.codes.to_numpy(copy=False)
            self._cat_codes[c] = codes
            # ¡Ojo!: categorías pueden ser objetos no str; mantenemos su valor original
            cats = list(df[c].cat.categories)
            self._cat_maps[c] = {v: i for i, v in enumerate(cats)}

        self._df_original = df
        self._df_filtered = df
        return df

    # ------------------------------------------------------------------
    # 2) FILTROS RÁPIDOS (NumPy)
    # ------------------------------------------------------------------
    def apply_filters(self, spec: dict | None):
        """
        Aplica filtros usando caches NumPy. spec en el formato de FiltersPanel.
        """
        if self._df_original is None or not spec:
            self._df_filtered = self._df_original
            return self._df_filtered

        mask = np.ones(self._N, dtype=bool)

        for col, cfg in (spec or {}).items():
            ctype = (cfg or {}).get("type")

            # ---------- Numéricos ----------
            if ctype == "numeric":
                arr = self._arr.get(col)
                if arr is None:
                    # columna no numérica o no cacheada
                    continue
                vmin = cfg.get("min")
                vmax = cfg.get("max")
                if vmin not in (None, ""):
                    try:
                        mask &= arr >= float(vmin)
                    except Exception:
                        pass
                if vmax not in (None, ""):
                    try:
                        mask &= arr <= float(vmax)
                    except Exception:
                        pass

            # ---------- Fechas ----------
            elif ctype == "date":
                # Soporta TRANSACTION_DATE, EXPIRY, DAY, WEEK, MONTH
                arr = self._arr.get(col)
                if arr is None and col in self._df_original.columns:
                    # cache on-demand si viene un col de fecha no precargado
                    if pd.api.types.is_datetime64_any_dtype(self._df_original[col]):
                        self._arr[col] = self._df_original[col].astype("int64", copy=False)

                        arr = self._arr[col]
                    else:
                        # intenta convertir una vez (coste amortizado si pasa)
                        s = pd.to_datetime(self._df_original[col], errors="coerce")
                        self._df_original[col] = s
                        self._arr[col] = s.astype("int64", copy=False)
                        arr = self._arr[col]
                if arr is None:
                    continue

                start = cfg.get("start")
                end = cfg.get("end")
                if start:
                    try:
                        start_ns = pd.to_datetime(start).value
                        mask &= arr >= start_ns
                    except Exception:
                        pass
                if end:
                    try:
                        # inclusivo hasta el final del día
                        end_ns = (pd.to_datetime(end) + pd.Timedelta(days=1) - pd.Timedelta(ns=1)).value
                        mask &= arr <= end_ns
                    except Exception:
                        pass

            # ---------- Categóricos ----------
            elif ctype == "categorical":
                vals = cfg.get("values") or []
                if not vals:
                    continue

                codes = self._cat_codes.get(col)
                v2code = self._cat_maps.get(col)

                if codes is not None and v2code is not None:
                    # Convierte valores -> codes (ignora los que no existen)
                    wanted = [v2code[v] for v in vals if v in v2code]
                    if wanted:
                        mask &= np.isin(codes, np.asarray(wanted, dtype=codes.dtype))
                    else:
                        mask &= False
                else:
                    # fallback: isin de pandas (más lento, sólo si columna no está como category)
                    if col in self._df_original.columns:
                        mask &= self._df_original[col].astype(str).isin(vals).to_numpy()

            # Otros tipos: ignorar
            else:
                continue

        self._df_filtered = self._df_original.loc[mask]
        return self._df_filtered

    # ------------------------------------------------------------------
    # 3) RESET + ACCESSORS
    # ------------------------------------------------------------------
    def clear_filters(self):
        """Quita filtros y vuelve al DataFrame original."""
        self._df_filtered = self._df_original

    @property
    def dataframe_filtered(self) -> pd.DataFrame | None:
        """Devuelve el DF filtrado si existe; si no, el original."""
        return self._df_filtered if self._df_filtered is not None else self._df_original
