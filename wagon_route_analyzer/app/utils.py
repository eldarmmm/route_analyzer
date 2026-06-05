"""Вспомогательные функции маршрутного отчёта."""

import re
import pandas as pd


def safe_str(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ''
    return str(val).strip()


def safe_filename(name):
    name = re.sub(r'[\\/:*?"<>|]', '_', str(name))
    name = re.sub(r'[\x00-\x1f]', '', name)
    return name.strip('_ ')


def clean_station_name(name):
    """Убирает суффиксы вида (эксп.), (перев.) и т.д. для отображения."""
    return re.sub(r'(?i)\s*\([^)]*\)\s*$', '', safe_str(name)).strip()


def hours_between(a, b):
    try:
        if pd.notna(a) and pd.notna(b):
            delta = (pd.Timestamp(b) - pd.Timestamp(a)).total_seconds() / 3600
            return round(max(delta, 0), 2)
    except Exception:
        pass
    return 0


def fmt_dt(v):
    try:
        if v is None or pd.isna(v):
            return ''
        ts = pd.Timestamp(v)
        if ts.tzinfo is not None:
            ts = ts.tz_convert(None)
        return ts.strftime('%d.%m.%Y %H:%M')
    except Exception:
        return str(v) if v is not None else ''


def clean_for_excel(df):
    """Безопасная очистка DataFrame перед openpyxl."""
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].apply(fmt_dt)
        else:
            out[col] = out[col].apply(lambda x: '' if x is None or (isinstance(x, float) and pd.isna(x)) else x)
    return out


def norm_text(v):
    return safe_str(v).upper()
