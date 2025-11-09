#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import pandas as pd
from pandas.api.types import (
    is_numeric_dtype,
    is_datetime64_any_dtype,
    is_bool_dtype,
)
from Datos import create_fake_transactions   # o desde data.fake_generator


class DataService:
    """
    Servicio de datos para la app.

    - generate_fake_transactions(...)  -> genera y PREPROCESA el DataFrame base.
    - apply_filters(spec)              -> aplica los filtros del FiltersPanel de forma vectorizada y rápida.
    - clear_filters()                  -> quita filtros.
    - dataframe_filtered (property)    -> devuelve el df filtrado (o el original si no hay filtros).
    """

    def __init__(self):
        self._df_original: pd.DataFrame | None = None
        self._df_filtered: pd.DataFrame | None = None

    # ------------------------------------------------------------------
    # 1) GENERACIÓN Y PREPROCESADO
    # ------------------------------------------------------------------
    def generate_fake_transactions(self, von=None, bis=None, produktart="ALLE", n_rows=1_000_000):
        """
        Genera el DataFrame base y lo guarda como _df_original.
        Además:
          - Convierte tipos (fechas, numéricos, categóricos) UNA sola vez.
          - Resetea cualquier filtro previo.
        """
        df = create_fake_transactions(von=von, bis=bis, produktart=produktart, n_rows=n_rows)
        if not isinstance(df, pd.DataFrame):
            raise ValueError("create_fake_transactions debe devolver un DataFrame")

        df = df.reset_index(drop=True)
        df = self._prepare_dataframe(df)

        self._df_original = df
        self._df_filtered = df
        return df

    def _prepare_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepara el DataFrame para que aplicar filtros sea MUY rápido:
          - Fechas como datetime64.
          - Numéricos bien tipados.
          - Cadenas relevantes como 'category'.
        Se hace solo una vez al cargar/generar datos.
        """
        df = df.copy()

        # ---------- 1) Fechas ----------
        date_cols = []
        for col in df.columns:
            name = col.upper()
            if name.endswith("DATE") or name in {"TRANSACTION_DATE", "EXPIRY"}:
                date_cols.append(col)

        for col in date_cols:
            if not is_datetime64_any_dtype(df[col]):
                df[col] = pd.to_datetime(df[col], errors="coerce")

        # ---------- 2) Numéricos ----------
        # Si create_fake_transactions ya ha puesto bien los dtypes,
        # esto será rápido; si no, se corrige aquí.
        for col in df.columns:
            if is_bool_dtype(df[col]) or is_datetime64_any_dtype(df[col]):
                continue
            # Si la columna ya es numérica, no tocamos.
            if is_numeric_dtype(df[col]):
                continue
            # Heurística: intentar numérico en columnas típicas
            if col.upper() in {
                "NBR_OF_TRADES",
                "NBR_OF_UNITS",
                "TXN_AMT",
                "STRIKE",
                "RATIO",
            }:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # ---------- 3) Categóricos ----------
        # Columnas claramente categóricas
        categ_cols = [
            "ISIN",
            "UND_ISIN",
            "NAME",
            "ISSUER_NAME",
            "UND_TYPE",
            "CALL_OPTION",
            "TYPE",
        ]
        for col in categ_cols:
            if col in df.columns and not is_numeric_dtype(df[col]) and not is_datetime64_any_dtype(df[col]):
                df[col] = df[col].astype("category")

        # También podemos pasar a category objetos con pocos únicos
        for col in df.columns:
            if col in categ_cols:
                continue
            s = df[col]
            if s.dtype == "object" and not is_datetime64_any_dtype(s):
                nunique = s.nunique(dropna=True)
                # si hay pocas categorías, compensa
                if 0 < nunique <= 200:
                    df[col] = s.astype("category")

        return df

    # ------------------------------------------------------------------
    # 2) APLICAR FILTROS (rápido)
    # ------------------------------------------------------------------
    def apply_filters(self, spec: dict):
        """
        Aplica los filtros definidos por FiltersPanel.get_filters() sobre _df_original.

        Formato esperado por columna (según filters_panel.py):
          - {'type': 'categorical', 'values': [...]}
          - {'type': 'numeric',    'min': '...', 'max': '...'}
          - {'type': 'date',       'start': 'YYYY-MM-DD', 'end': 'YYYY-MM-DD'}

        Implementación optimizada:
          - Usa una única máscara numpy (mask &= ...).
          - No reconvierte tipos (se confía en _prepare_dataframe).
          - Rompe pronto si la máscara queda vacía.
        """
        if self._df_original is None:
            self._df_filtered = None
            return None

        df = self._df_original

        if not spec:
            # Sin filtros → todo el df
            self._df_filtered = df
            return df

        n = len(df)
        if n == 0:
            self._df_filtered = df
            return df

        mask = np.ones(n, dtype=bool)

        # Orden de tipos de filtro: primero los más restrictivos
        TYPE_ORDER = ["categorical", "date", "numeric"]

        for ftype in TYPE_ORDER:
            for col, cfg in spec.items():
                if col not in df.columns:
                    continue
                if cfg.get("type") != ftype:
                    continue

                # ------------- CATEGÓRICO -------------
                if ftype == "categorical":
                    vals = cfg.get("values") or []
                    if not vals:
                        continue

                    # Si es category, isin es muy rápido
                    series = df[col]
                    valid = series.astype(str).isin(vals).to_numpy()
                    mask &= valid

                # ------------- FECHA -------------
                elif ftype == "date":
                    start = cfg.get("start") or ""
                    end = cfg.get("end") or ""
                    if not start and not end:
                        continue

                    col_vals = df[col].to_numpy()  # datetime64[ns]

                    if start:
                        try:
                            start_ts = pd.to_datetime(start)
                            mask &= col_vals >= start_ts
                        except Exception:
                            pass

                    if end:
                        try:
                            end_ts = pd.to_datetime(end)
                            mask &= col_vals <= end_ts
                        except Exception:
                            pass

                # ------------- NUMÉRICO -------------
                elif ftype == "numeric":
                    vmin_str = (cfg.get("min") or "").strip()
                    vmax_str = (cfg.get("max") or "").strip()
                    if not vmin_str and not vmax_str:
                        continue

                    col_vals = df[col].to_numpy()

                    vmin = None
                    vmax = None
                    if vmin_str:
                        try:
                            vmin = float(vmin_str)
                        except Exception:
                            vmin = None
                    if vmax_str:
                        try:
                            vmax = float(vmax_str)
                        except Exception:
                            vmax = None

                    if vmin is not None:
                        mask &= col_vals >= vmin
                    if vmax is not None:
                        mask &= col_vals <= vmax

                # Si ya no queda ninguna fila, podemos cortar
                if not mask.any():
                    break
            # Comprobar también aquí para romper el bucle exterior
            if not mask.any():
                break

        self._df_filtered = df.loc[mask]
        return self._df_filtered

    # ------------------------------------------------------------------
    # 3) RESET / ACCESSORS
    # ------------------------------------------------------------------
    def clear_filters(self):
        """Quita filtros y vuelve al DataFrame original."""
        self._df_filtered = self._df_original

    @property
    def dataframe_filtered(self) -> pd.DataFrame | None:
        """
        Devuelve el DataFrame filtrado si existe; en caso contrario, el original.
        """
        return self._df_filtered if self._df_filtered is not None else self._df_original
