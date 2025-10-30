#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Oct 30 20:40:24 2025

@author: fran
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def create_fake_transactions(n_rows=1_000_000):
    np.random.seed(42)

    # --- ISIN-like generators ---
    def random_isin():
        return 'DE' + ''.join(np.random.choice(list('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 10))

    def random_name(prefix_list):
        return np.random.choice(prefix_list) + " " + np.random.choice(["Alpha", "Beta", "Plus", "Max", "Pro"])

    issuers = ["Goldman Sachs", "HSBC", "BNP Paribas", "Société Générale", "UBS", "J.P. Morgan", "Deutsche Bank"]
    underlyings = ["AAPL", "MSFT", "SPX", "EURUSD", "XAUUSD", "TSLA", "NDAQ", "AMZN", "DAX", "CAC40"]
    und_types = ["Equity", "Index", "FX", "Commodity"]
    types = ["Warrant", "Certificate", "Option", "Turbo", "CFD"]

    # --- Dates ---
    today = datetime.today()
    start_date = today - timedelta(days=90)
    dates = pd.to_datetime(np.random.randint(start_date.timestamp(), today.timestamp(), size=n_rows), unit='s')
    expiries = dates + pd.to_timedelta(np.random.randint(30, 365, size=n_rows), unit='D')

    # --- Numerical fields ---
    df = pd.DataFrame({
        "ISIN": [random_isin() for _ in range(n_rows)],
        "UND_ISIN": [random_isin() for _ in range(n_rows)],
        "NAME": [random_name(underlyings) for _ in range(n_rows)],
        "ISSUER_NAME": np.random.choice(issuers, size=n_rows),
        "UND_TYPE": np.random.choice(und_types, size=n_rows),
        "NBR_OF_TRADES": np.random.randint(1, 100, size=n_rows),
        "CALL_OPTION": np.random.choice(["Call", "Put"], size=n_rows),
        "NBR_OF_UNITS": np.random.randint(10, 10000, size=n_rows),
        "TRANSACTION_DATE": dates.strftime("%Y-%m-%d"),
        "TXN_AMT": np.round(np.random.uniform(1_000, 1_000_000, size=n_rows), 2),
        "EXPIRY": expiries.strftime("%Y-%m-%d"),
        "TYPE": np.random.choice(types, size=n_rows),
        "RATIO": np.round(np.random.uniform(0.01, 1.0, size=n_rows), 3),
        "STRIKE": np.round(np.random.uniform(50, 500, size=n_rows), 2)
    })

    return df

#df = create_fake_transactions()
#print(df.head())
#print(df.info())

