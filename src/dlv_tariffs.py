import pandas as pd
import numpy as np
from pathlib import Path

TARIFF_CACHE = {}

def get_tariff(knr: str) -> pd.DataFrame:
    if knr in TARIFF_CACHE:
        return TARIFF_CACHE[knr]
    loader = LOADERS.get(knr)
    if loader is None:
        return pd.DataFrame()
    result = loader()
    TARIFF_CACHE[knr] = result
    return result

LOADERS = {}
