#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 31 23:06:46 2025

@author: fran
"""

## 🧠 services/data_service.py

from data.fake_generator import create_fake_transactions
from utils.logging_config import get_logger
import pandas as pd

class DataService:
    def __init__(self):
        self._log = get_logger(__name__)
        self._df_cache = None
        self._df_original = None
        self._df_filtered = None


    def generate_fake_transactions(self, n_rows: int):
        self._log.info("Generando datos fake", extra={"n_rows": n_rows})
        df = create_fake_transactions(n_rows=n_rows, months=3)
        self._df_original = df
        self._df_filtered = df
        self._log.info("Datos generados", extra={"shape": df.shape})
        return df

    @property
    def dataframe(self):
        return self._df_cache


    def apply_filters(self, spec: dict):
        if self._df_original is None:
            return None
        df = self._df_original
        mask = pd.Series(True, index=df.index)
    
        for col, cfg in (spec or {}).items():
            if col not in df.columns:
                continue
            ctype = cfg.get("type")
            if ctype == "categorical":
                vals = cfg.get("values") or []
                if vals:
                    mask &= df[col].astype(str).isin(vals)
            elif ctype == "numeric":
                vmin = cfg.get("min")
                vmax = cfg.get("max")
                s = pd.to_numeric(df[col], errors="coerce")
                if vmin is not None:
                    mask &= s >= float(vmin)
                if vmax is not None:
                    mask &= s <= float(vmax)
            elif ctype == "date":
                start = cfg.get("start")
                end = cfg.get("end")
                s = pd.to_datetime(df[col], errors="coerce")
                if start:
                    mask &= s >= pd.to_datetime(start)
                if end:
                    mask &= s <= pd.to_datetime(end)
    
        self._df_filtered = df[mask]
        return self._df_filtered
    
    def clear_filters(self):
        self._df_filtered = self._df_original
    
    @property
    def dataframe_filtered(self):
        return self._df_filtered if self._df_filtered is not None else self._df_original
