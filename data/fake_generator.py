import numpy as np
import pandas as pd
from datetime import date
import string


ISSUERS = ["HSBC", "DB", "CITI", "BNPP", "UBS", "JPM", "GS", "MS"]
UNDERLYING_TYPES = ["STOCK", "INDEX", "ETF", "FX", "COMMODITY"]
PRODUCT_TYPES = ["WARRANT", "TURBO", "BARRIER", "VANILLA"]
NAMES = [
"Call Tesla", "Put Tesla", "Call Nvidia", "Put Nvidia",
"Call DAX", "Put DAX", "Call EURUSD", "Put EURUSD",
]

def _random_isin(n):
    letters = np.random.choice(list(string.ascii_uppercase), size=(n, 2))
    alnum = np.random.choice(list(string.ascii_uppercase + string.digits), size=(n, 10))
    isin = ["".join(l) + "".join(a) for l, a in zip(letters, alnum)]
    return np.array(isin)




def _random_dates(n, months=3):
    end = pd.Timestamp(date.today())
    start = end - pd.DateOffset(months=months)
    days = (end - start).days
    offsets = np.random.randint(0, max(days, 1), size=n)
    dt = (start + pd.to_timedelta(offsets, unit="D")).normalize()
    return dt




def create_fake_transactions(n_rows: int = 1_000_000, months: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng()

    
    trx_date = _random_dates(n_rows, months=months)
    expiry_offsets = rng.integers(7, 366, size=n_rows)
    expiry = pd.to_datetime(trx_date) + pd.to_timedelta(expiry_offsets, unit="D")
    
    
    call_put = rng.choice(["CALL", "PUT"], size=n_rows)
    und_type = rng.choice(UNDERLYING_TYPES, size=n_rows)
    issuer = rng.choice(ISSUERS, size=n_rows)
    ptype = rng.choice(PRODUCT_TYPES, size=n_rows)
    name = rng.choice(NAMES, size=n_rows)
    
    
    strike = rng.uniform(1, 2000, size=n_rows).round(4)
    ratio = rng.uniform(0.01, 10.0, size=n_rows).round(6)
    nbr_trades = rng.integers(1, 50, size=n_rows)
    units = rng.integers(1, 10000, size=n_rows)
    txn_amt = (units * strike * rng.uniform(0.5, 1.5, size=n_rows)).round(2)
    
    
    df = pd.DataFrame({
    "ISIN": _random_isin(n_rows),
    "UND_ISIN": _random_isin(n_rows),
    "NAME": name,
    "ISSUER_NAME": issuer,
    "UND_TYPE": und_type,
    "NBR_OF_TRADES": nbr_trades,
    "CALL_OPTION": call_put,
    "NBR_OF_UNITS": units,
    "TRANSACTION_DATE": trx_date.date.astype(str),
    "TXN_AMT": txn_amt,
    "EXPIRY": expiry.date.astype(str),
    "TYPE": ptype,
    "RATIO": ratio,
    "STRIKE": strike,
    })
    
    
    ordered_cols = [
    "ISIN", "UND_ISIN", "NAME", "ISSUER_NAME", "UND_TYPE",
    "NBR_OF_TRADES", "CALL_OPTION", "NBR_OF_UNITS",
    "TRANSACTION_DATE", "TXN_AMT", "EXPIRY", "TYPE", "RATIO", "STRIKE"
    ]
    return df[ordered_cols]