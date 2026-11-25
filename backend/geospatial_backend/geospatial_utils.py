# LUNGSIGHT_PSGC_NO_MANUAL_GEO_V2
"""Shared helpers for live patient geospatial reporting.

No synthetic geographic points or demonstration patient cases.
"""
AGE_GROUPS = ("0–17", "18–39", "40–59", "60+")


def month_shift(year, month, delta):
    index = year * 12 + month - 1 + delta
    return index // 12, index % 12 + 1
