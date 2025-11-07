# services/data_service.py  (o tu ruta actual)
from data.fake_generator import create_fake_transactions
import pandas as pd

class DataService:
    def __init__(self):
        self._df_original = None
        self._df_filtered = None

    # --- NUEVO: normalizador central de fechas y columnas derivadas ---
    @staticmethod
    def _ensure_time_cols(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df
        s = df.copy()

        # Asegurar TRANSACTION_DATE como datetime
        if "TRANSACTION_DATE" in s.columns and not pd.api.types.is_datetime64_any_dtype(s["TRANSACTION_DATE"]):
            s["TRANSACTION_DATE"] = pd.to_datetime(s["TRANSACTION_DATE"], errors="coerce")

        # Quitar filas sin fecha válida
        if "TRANSACTION_DATE" in s.columns:
            s = s.dropna(subset=["TRANSACTION_DATE"])

            # Crear derivadas si faltan
            if "DAY" not in s.columns:
                s["DAY"] = s["TRANSACTION_DATE"].dt.normalize()
            if "WEEK" not in s.columns:
                s["WEEK"] = s["TRANSACTION_DATE"].dt.to_period("W-MON").dt.start_time
            if "MONTH" not in s.columns:
                s["MONTH"] = s["TRANSACTION_DATE"].dt.to_period("M").dt.start_time

        return s

    def generate_fake_transactions(self, n_rows: int):
        df = create_fake_transactions(n_rows=n_rows, months=3)
        df = self._ensure_time_cols(df)  # <- garantizar columnas aquí
        self._df_original = df
        self._df_filtered = df
        return df

    def apply_filters(self, spec: dict):
        if self._df_original is None:
            return None

        # Siempre filtrar sobre un DF con columnas temporales bien formadas
        df = self._ensure_time_cols(self._df_original)

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
                vmin = cfg.get("min"); vmax = cfg.get("max")
                s = pd.to_numeric(df[col], errors="coerce")
                if vmin is not None and str(vmin) != "":
                    mask &= s >= float(vmin)
                if vmax is not None and str(vmax) != "":
                    mask &= s <= float(vmax)

            elif ctype == "date":
                start = cfg.get("start"); end = cfg.get("end")
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
        # Devuelve SIEMPRE con columnas temporales garantizadas
        base = self._df_filtered if self._df_filtered is not None else self._df_original
        return self._ensure_time_cols(base) if base is not None else None

