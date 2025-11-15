import numpy as np
import pandas as pd
from datetime import datetime, timedelta, date


ISSUERS = np.array(["HSBC", "DB", "CITI", "BNPP", "UBS", "JPM", "GS", "MS"])
UNDERLYING_CODES = np.array([
    "AAPL", "MSFT", "SPX", "EURUSD", "XAUUSD",
    "TSLA", "NDAQ", "AMZN", "DAX", "CAC40","NASDAQ","Hensholdt","RWE","Rheinmetal",
])
UNDERLYING_TYPES = np.array(["Equity", "Index", "FX", "Commodity"])

# TIPOS DE PRODUCTO (Type)
PRODUCT_TYPES_ALL = np.array(["Vanilla", "Turbo", "Warrant", "Certificate", "CFD"])


def _parse_date(value, default=None) -> datetime:
    """Convierte VON/BIS a datetime sin hora. Si es None o vacío, devuelve default."""
    if value is None or value == "":
        return default
    if isinstance(value, datetime):
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    try:
        dt = pd.to_datetime(value)
        return datetime(dt.year, dt.month, dt.day)
    except Exception:
        return default


def create_fake_transactions(
    von=None,
    bis=None,
    produktart="ALLE",
    n_rows: int = 1_000_000,
) -> pd.DataFrame:
    """
    Genera un DataFrame de transacciones sintéticas.

    Parámetros
    ----------
    von : str | date | datetime | None
        Fecha de inicio (incluida). Ej: '2025-01-01'. Si None → hoy - 90 días.
    bis : str | date | datetime | None
        Fecha de fin (incluida). Si None → hoy.
    produktart : {'ALLE', 'TURBO', 'VANILLA'}
        - 'ALLE'    -> mezcla todos los TYPE de PRODUCT_TYPES_ALL
        - 'TURBO'   -> sólo TYPE = 'Turbo'
        - 'VANILLA' -> sólo TYPE = 'Vanilla'
    n_rows : int
        Número de filas a generar.

    Devuelve
    --------
    DataFrame con columnas:
        ISIN, UND_ISIN, NAME, ISSUER_NAME, UND_TYPE,
        NBR_OF_TRADES, CALL_OPTION, NBR_OF_UNITS,
        TRANSACTION_DATE, TXN_AMT, EXPIRY, TYPE, RATIO, STRIKE,
        DAY, WEEK, MONTH
    """
    rng = np.random.default_rng()

    # ----- rango de fechas -----
    today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
    end_dt = _parse_date(bis, default=today)
    start_dt = _parse_date(von, default=end_dt - timedelta(days=90))

    if start_dt > end_dt:
        # por si el usuario mete el rango del revés
        start_dt, end_dt = end_dt, start_dt

    date_range = pd.date_range(start_dt, end_dt, freq="D")
    if len(date_range) == 0:
        date_range = pd.date_range(end_dt, end_dt, freq="D")

    n = int(n_rows)

    # ----- tipos permitidos según produktart -----
    produktart_norm = (produktart or "ALLE").upper()
    if produktart_norm == "TURBO":
        allowed_types = np.array(["Turbo"])
    elif produktart_norm == "VANILLA":
        allowed_types = np.array(["Vanilla"])
    else:
        allowed_types = PRODUCT_TYPES_ALL

    # ----- fechas de transacción / expiración -----
    trx_dates = rng.choice(date_range, size=n)
    expiry = trx_dates + pd.to_timedelta(rng.integers(30, 365, size=n), unit="D")

    # ----- ISINs vectorizados (rápidos) -----
    # Generamos números [0, 10^10) y los formateamos como 10 dígitos + prefijo "DE"
    nums1 = rng.integers(0, 10**10, size=n, dtype=np.int64)
    isin = np.char.add("DE", np.char.zfill(nums1.astype(str), 10))

    nums2 = rng.integers(0, 10**10, size=n, dtype=np.int64)
    und_isin = np.char.add("DE", np.char.zfill(nums2.astype(str), 10))

    # ----- resto de campos, todo vectorizado -----
    # NAME = código underlying + sufijo textual
    suffixes = np.array([" Call", " Put", " Bonus", " Reverse"])
    names = np.char.add(
        rng.choice(UNDERLYING_CODES, size=n),
        rng.choice(suffixes, size=n),
    )

    issuers = rng.choice(ISSUERS, size=n)
    und_type = rng.choice(UNDERLYING_TYPES, size=n)

    call_option = rng.choice(["CALL", "PUT"], size=n)
    nbr_trades = rng.integers(1, 50, size=n)
    units = rng.integers(10, 10_000, size=n)
    strike = rng.uniform(1, 2_000, size=n).round(4)
    txn_amt = (units * strike * rng.uniform(0.5, 1.5, size=n)).round(2)

    ptype = rng.choice(allowed_types, size=n)
    ratio = rng.uniform(0.01, 1.0, size=n).round(3)

    df = pd.DataFrame(
        {
            "ISIN": isin,
            "UND_ISIN": und_isin,
            "NAME": names,
            "ISSUER_NAME": issuers,
            "UND_TYPE": und_type,
            "NBR_OF_TRADES": nbr_trades,
            "CALL_OPTION": call_option,
            "NBR_OF_UNITS": units,
            "TRANSACTION_DATE": pd.to_datetime(trx_dates),
            "TXN_AMT": txn_amt,
            "EXPIRY": expiry,  # tipo datetime64; si quieres str: expiry.date.astype(str)
            "TYPE": ptype,
            "RATIO": ratio,
            "STRIKE": strike,
        }
    )

    # ----- columnas de periodo como en Datos.py -----
    df["DAY"] = df["TRANSACTION_DATE"].dt.normalize()
    df["WEEK"] = df["TRANSACTION_DATE"].dt.to_period("W-MON").dt.start_time
    df["MONTH"] = df["TRANSACTION_DATE"].dt.to_period("M").dt.start_time

    return df
