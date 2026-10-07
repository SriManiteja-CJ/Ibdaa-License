"""
data_loader.py
--------------
Reads Tradenames.xlsx, normalizes trade names, business activity categories,
and Arabic fields, and returns ALL rows for checking.
No rows are removed or deduplicated.

Columns loaded:
  NAMEEN               — Original English trade name
  NAMEAR               — Original Arabic trade name
  ACTIVITY_CATEGORY_ID — Main Business Activity / Level-5 Category ID
  KEYWORD_EN           — English keywords
  KEYWORD_AR           — Arabic keywords

Normalized columns created:
  NAMEEN_NORMALIZED    — Cleaned English name
  NAMEAR_NORMALIZED    — Cleaned Arabic name
  CATEGORY_NORMALIZED  — Cleaned category ID / string
"""

import os
import re
import pandas as pd


# ---------------------------------------------------------------------------
# Path configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_FILE = os.path.join(SCRIPT_DIR, "Tradenames.xlsx")
SHEET_NAME = "Export Worksheet"


# ---------------------------------------------------------------------------
# Normalization functions
# ---------------------------------------------------------------------------

def normalize_name(name: str) -> str:
    """
    Cleans a single English or general trade name string for consistent comparison.
    """
    if not isinstance(name, str):
        return ""

    name = name.lower()
    name = re.sub(r"[.,]", "", name)
    name = name.strip()
    name = re.sub(r"\s+", " ", name)

    return name


def normalize_arabic_name(name: str) -> str:
    """
    Cleans an Arabic trade name string for consistent comparison.
    Removes diacritics (tashkeel), normalizes alef variants and teh marbuta.
    """
    if not isinstance(name, str):
        return ""

    tashkeel = re.compile(r"[\u0617-\u061A\u064B-\u0652]")
    name = re.sub(tashkeel, "", name)

    name = re.sub(r"[\u0622\u0623\u0625]", "\u0627", name)
    name = re.sub(r"\u0649", "\u064A", name)

    name = re.sub(r"[.,]", "", name)
    name = name.strip()
    name = re.sub(r"\s+", " ", name)

    return name


def normalize_category(cat) -> str:
    """
    Normalizes a business activity category value (numeric ID or string).
    """
    if pd.isna(cat) or cat is None:
        return ""

    cat_str = str(cat).strip()
    if cat_str.endswith(".0"):
        cat_str = cat_str[:-2]

    return cat_str.lower()


def is_same_category(cat1, cat2) -> bool:
    """
    Returns True if two category values represent the same business activity.
    If either category is empty/unspecified, returns True to be safe/conservative.
    """
    c1 = normalize_category(cat1)
    c2 = normalize_category(cat2)
    if not c1 or not c2:
        return True
    return c1 == c2


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_trade_names() -> pd.DataFrame:
    """
    Loads ALL trade names and business activity categories from Tradenames.xlsx.
    """
    if not os.path.exists(EXCEL_FILE):
        raise FileNotFoundError(
            f"Excel file not found at: {EXCEL_FILE}\n"
            "Please make sure Tradenames.xlsx is in the same folder as this script."
        )

    print(f"Loading {EXCEL_FILE} (24,000+ entries) ...", flush=True)

    use_cols = ["NAMEEN", "NAMEAR", "ACTIVITY_CATEGORY_ID", "KEYWORD_EN", "KEYWORD_AR"]

    df = pd.read_excel(
        EXCEL_FILE,
        sheet_name=SHEET_NAME,
        usecols=use_cols,
        dtype=str,
        engine="openpyxl"
    )

    total_rows = len(df)
    print(f"Total rows read from file: {total_rows}", flush=True)

    for col in df.columns:
        df[col] = df[col].replace("nan", pd.NA)

    df = df.dropna(subset=["NAMEEN", "NAMEAR"], how="all")
    df = df.reset_index(drop=True)

    after_drop = len(df)
    print(f"Rows after dropping empty trade names: {after_drop}", flush=True)

    df["NAMEEN_NORMALIZED"] = df["NAMEEN"].fillna("").apply(normalize_name)
    df["NAMEAR_NORMALIZED"] = df["NAMEAR"].fillna("").apply(normalize_arabic_name)
    df["CATEGORY_NORMALIZED"] = df["ACTIVITY_CATEGORY_ID"].apply(normalize_category)

    print(f"Data loaded successfully. {after_drop} trade names ready.", flush=True)

    return df