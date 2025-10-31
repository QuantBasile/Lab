#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 31 23:06:46 2025

@author: fran
"""

from data.fake_generator import create_fake_transactions
from utils.logging_config import get_logger




class DataService:
    def __init__(self):
        self._log = get_logger(__name__)
        self._df_cache = None
    
    
    def generate_fake_transactions(self, n_rows: int):
        self._log.info("Generando datos fake", extra={"n_rows": n_rows})
        df = create_fake_transactions(n_rows=n_rows, months=3)
        self._df_cache = df
        self._log.info("Datos generados", extra={"shape": df.shape})
        return df
        
    
    @property
    def dataframe(self):
        return self._df_cache