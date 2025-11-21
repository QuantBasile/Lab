#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import numpy as np
import pandas as pd

from Datos import create_fake_transactions  # uses your Datos.py


class DataService:
    """
    Data service with pre-loading and NumPy-based filter caches.

    Responsibilities
    ----------------
    - Generate a base DataFrame (via your Datos.py) and build NumPy caches
      for very fast filtering (no per-filter Pandas groupby / copies).

    - Apply filters described by the FiltersPanel in a purely vectorized way:
        spec = {
            "COL": {"type": "categorical", "values": [...]},
            "COL": {"type": "numeric",     "min": "...", "max": "..."},
            "COL": {"type": "date",        "start": "YYYY-mm-dd", "end": "YYYY-mm-dd"},
            ...
        }

    - Keep both the original DataFrame and the filtered view.
    """

    def __init__(self) -> None:
        # Original and filtered DataFrames
        self._df_original: pd.DataFrame | None = None
        self._df_filtered: pd.DataFrame | None = None

        # Cache length
        self._N: int = 0

        # Column → ndarray (for numeric and date columns)
        self._arr: dict[str, np.ndarray] = {}

        # Categorical caches
        #   column → int codes (category codes)
        self._cat_codes: dict[str, np.ndarray] = {}
        #   column → {value → code}
        self._cat_maps: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # 1) GENERATION + PREPROCESSING + CACHES
    # ------------------------------------------------------------------
    def generate_fake_transactions(
        self,
        von: str | None = None,
        bis: str | None = None,
        produktart: str = "ALLE",
        n_rows: int = 1_000_000,
    ) -> pd.DataFrame:
        """
        Generate the base DataFrame using your Datos.py function and
        build all NumPy caches for fast filtering.

        Parameters
        ----------
        von : str | None
            Start date (string) passed to `create_fake_transactions`.
        bis : str | None
            End date (string) passed to `create_fake_transactions`.
        produktart : str
            Product type selector ("ALLE", "TURBO", "VANILLA", ...).
        n_rows : int
            Number of rows to generate.

        Returns
        -------
        pd.DataFrame
            The full, unfiltered DataFrame.
        """
        df = create_fake_transactions(
            von=von,
            bis=bis,
            produktart=produktart,
            n_rows=n_rows,
        )

        # --- Ensure expected dtypes (Datos.py should already do this; this is defensive) ---

        # Numeric columns
        num_cols = ["TXN_AMT", "STRIKE", "RATIO", "NBR_OF_UNITS", "NBR_OF_TRADES"]
        for c in num_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

        # Date-like columns
        date_cols = [
            c
            for c in ("TRANSACTION_DATE", "EXPIRY", "DAY", "WEEK", "MONTH")
            if c in df.columns
        ]
        for c in date_cols:
            if not pd.api.types.is_datetime64_any_dtype(df[c]):
                df[c] = pd.to_datetime(df[c], errors="coerce")

        # Categorical columns
        cat_cols = [
            c
            for c in (
                "ISSUER_NAME",
                "UND_TYPE",
                "TYPE",
                "CALL_OPTION",
                "NAME",
                "ISIN",
                "UND_ISIN",
            )
            if c in df.columns
        ]
        for c in cat_cols:
            if df[c].dtype != "category":
                df[c] = df[c].astype("category")

        # --- Build caches -------------------------------------------------

        self._N = len(df)
        self._arr.clear()
        self._cat_codes.clear()
        self._cat_maps.clear()

        # Numeric arrays: direct views (no copy)
        for c in num_cols:
            if c in df.columns:
                self._arr[c] = df[c].to_numpy(copy=False)

        # Dates as int64 nanoseconds for O(1) comparisons
        for c in date_cols:
            self._arr[c] = df[c].astype("int64", copy=False)

        # Categoricals as codes + value → code maps
        for c in cat_cols:
            codes = df[c].cat.codes.to_numpy(copy=False)
            self._cat_codes[c] = codes

            # Categories can be non-string; keep original values
            cats = list(df[c].cat.categories)
            self._cat_maps[c] = {value: i for i, value in enumerate(cats)}

        self._df_original = df
        self._df_filtered = df
        return df

    # ------------------------------------------------------------------
    # 2) FAST FILTERS (NumPy)
    # ------------------------------------------------------------------
    def apply_filters(self, spec: dict | None):
        """
        Apply filters using NumPy caches.

        Parameters
        ----------
        spec : dict | None
            Filter specification from FiltersPanel, e.g.:

            {
              "ISSUER_NAME": {
                  "type": "categorical",
                  "values": ["HSBC", "CITI"]
              },
              "TXN_AMT": {
                  "type": "numeric",
                  "min": "10000",
                  "max": "500000",
              },
              "TRANSACTION_DATE": {
                  "type": "date",
                  "start": "2024-01-01",
                  "end": "2024-03-31",
              },
            }

        Returns
        -------
        pd.DataFrame | None
            Filtered DataFrame (view), or None if no data loaded.
        """
        if self._df_original is None or not spec:
            # No filters: reset to original
            self._df_filtered = self._df_original
            return self._df_filtered

        # Global mask: start with all True
        mask = np.ones(self._N, dtype=bool)

        # Iterate over columns in the spec
        for col, cfg in (spec or {}).items():
            if not cfg:
                continue

            ctype = cfg.get("type")

            # -------------------------
            # Numeric filters
            # -------------------------
            if ctype == "numeric":
                arr = self._arr.get(col)
                if arr is None:
                    # Not a numeric column or not cached
                    continue

                vmin = cfg.get("min")
                vmax = cfg.get("max")

                if vmin not in (None, ""):
                    try:
                        mask &= arr >= float(vmin)
                    except Exception:
                        # Ignore invalid user input for min
                        pass

                if vmax not in (None, ""):
                    try:
                        mask &= arr <= float(vmax)
                    except Exception:
                        # Ignore invalid user input for max
                        pass

            # -------------------------
            # Date filters
            # -------------------------
            elif ctype == "date":
                # Supports TRANSACTION_DATE, EXPIRY, DAY, WEEK, MONTH, ...
                arr = self._arr.get(col)

                # Build date cache on demand if needed
                if arr is None and col in self._df_original.columns:
                    series = self._df_original[col]

                    if not pd.api.types.is_datetime64_any_dtype(series):
                        # One-time conversion; amortized cost if it happens
                        series = pd.to_datetime(series, errors="coerce")
                        self._df_original[col] = series

                    self._arr[col] = series.astype("int64", copy=False)
                    arr = self._arr[col]

                if arr is None:
                    # Unknown date column → skip
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
                        # Inclusive: up to the last nanosecond of the end day
                        end_ts = pd.to_datetime(end)
                        end_ns = (
                            end_ts + pd.Timedelta(days=1) - pd.Timedelta(ns=1)
                        ).value
                        mask &= arr <= end_ns
                    except Exception:
                        pass

            # -------------------------
            # Categorical filters
            # -------------------------
            elif ctype == "categorical":
                vals = cfg.get("values") or []
                if not vals:
                    continue

                codes = self._cat_codes.get(col)
                v2code = self._cat_maps.get(col)

                if codes is not None and v2code is not None:
                    # Map values → codes (ignore values that do not exist in categories)
                    wanted_codes = [v2code[v] for v in vals if v in v2code]

                    if wanted_codes:
                        wanted_arr = np.asarray(wanted_codes, dtype=codes.dtype)
                        mask &= np.isin(codes, wanted_arr)
                    else:
                        # User selected values that are not present → mask all out
                        mask &= False
                else:
                    # Fallback: Pandas isin (slower, only if column not categorical)
                    if col in self._df_original.columns:
                        mask &= (
                            self._df_original[col]
                            .astype(str)
                            .isin(vals)
                            .to_numpy()
                        )

            # -------------------------
            # Other / unknown types → ignore
            # -------------------------
            else:
                continue

        # Apply mask as a view on the original DataFrame
        self._df_filtered = self._df_original.loc[mask]
        return self._df_filtered

    # ------------------------------------------------------------------
    # 3) RESET + ACCESSORS
    # ------------------------------------------------------------------
    def clear_filters(self) -> None:
        """Clear all filters and revert to the original DataFrame."""
        self._df_filtered = self._df_original

    @property
    def dataframe_filtered(self) -> pd.DataFrame | None:
        """
        Return the currently filtered DataFrame, or the original one if
        no filters have been applied yet.
        """
        if self._df_filtered is not None:
            return self._df_filtered
        return self._df_original
