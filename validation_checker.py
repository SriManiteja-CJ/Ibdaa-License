"""
validation_checker.py
---------------------
Loads AiValidationWords.xlsx and AIValidationType.xlsx and checks whether
a proposed trade name contains any validation-flagged / prohibited words.

Known file structure:
  AiValidationWords.xlsx  — sheet: AI_TRADENAME_VALIDATION_WORDS
    Columns: ID, WORD, LANG, VALIDATION_TYPE_ID

  AIValidationType.xlsx   — sheet: AI_TRADENAME_VALIDATION_TYPE
    Columns: ID, TYPE_NAME_AR, TYPE_NAME_EN, TYPE_ORDER, IS_ACTIVE,
             IS_DELETED, DO_SIMILARITY_SEARCH, DO_STEMMING,
             DO_NORMALIZATION, TYPE_KEY

The LLM is NEVER used here. All decisions are deterministic lookups.
Nothing in this file modifies either Excel file.
"""

import os
import re
import pandas as pd
from data_loader import normalize_arabic_name

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
WORDS_FILE  = os.path.join(SCRIPT_DIR, "AiValidationWords.xlsx")
TYPES_FILE  = os.path.join(SCRIPT_DIR, "AIValidationType.xlsx")

WORDS_SHEET = "AI_TRADENAME_VALIDATION_WORDS"
TYPES_SHEET = "AI_TRADENAME_VALIDATION_TYPE"

# In-memory lookup: lowercase_phrase → {word_id, word, type_id, type_name, type_name_ar}
_WORD_MAP: dict | None = None


# ---------------------------------------------------------------------------
# load_validation_data
# ---------------------------------------------------------------------------

def load_validation_data() -> dict:
    """
    Reads both Excel files and builds the in-memory lookup map.
    Called once at server startup.
    """
    global _WORD_MAP

    if not os.path.exists(WORDS_FILE):
        return {"loaded": False, "words_count": 0, "types_count": 0,
                "error": f"AiValidationWords.xlsx not found at {WORDS_FILE}"}

    if not os.path.exists(TYPES_FILE):
        return {"loaded": False, "words_count": 0, "types_count": 0,
                "error": f"AIValidationType.xlsx not found at {TYPES_FILE}"}

    try:
        words_df = pd.read_excel(
            WORDS_FILE, sheet_name=WORDS_SHEET, dtype=str, engine="openpyxl"
        )
        types_df = pd.read_excel(
            TYPES_FILE, sheet_name=TYPES_SHEET, dtype=str, engine="openpyxl"
        )
    except Exception as e:
        return {"loaded": False, "words_count": 0, "types_count": 0,
                "error": f"Error reading Excel files: {e}"}

    # Build type_id → {type_name_en, type_name_ar}
    type_lookup: dict[str, dict] = {}
    for _, row in types_df.iterrows():
        tid  = str(row.get("ID", "")).strip()
        name_en = str(row.get("TYPE_NAME_EN", "")).strip()
        name_ar = str(row.get("TYPE_NAME_AR", "")).strip()
        if tid and tid != "nan":
            type_lookup[tid] = {
                "type_name_en": name_en.strip('"').strip() if name_en and name_en != "nan" else f"Type {tid}",
                "type_name_ar": name_ar.strip('"').strip() if name_ar and name_ar != "nan" else f"Type {tid}"
            }

    # Build word map: lowercase_phrase → metadata
    _WORD_MAP = {}
    for _, row in words_df.iterrows():
        word    = str(row.get("WORD", "")).strip()
        word_id = str(row.get("ID", "")).strip()
        type_id = str(row.get("VALIDATION_TYPE_ID", "")).strip()

        if not word or word == "nan":
            continue

        # Clean punctuation and normalize spacing & Arabic chars
        key = re.sub(r"[.\-_/&,]", " ", word.lower().strip())
        key = normalize_arabic_name(key)
        key = re.sub(r"\s+", " ", key).strip()

        type_info = type_lookup.get(type_id, {"type_name_en": f"Type {type_id}", "type_name_ar": f"Type {type_id}"})

        if key and key not in _WORD_MAP:
            _WORD_MAP[key] = {
                "word":         word,       # original casing from Excel
                "word_id":      word_id,
                "type_id":      type_id,
                "type_name":    type_info["type_name_en"],
                "type_name_ar": type_info["type_name_ar"]
            }

    return {
        "loaded":      True,
        "words_count": len(_WORD_MAP),
        "types_count": len(type_lookup),
        "error":       None
    }


# ---------------------------------------------------------------------------
# check_validation_words
# ---------------------------------------------------------------------------

def check_validation_words(trade_name: str) -> dict:
    """
    Checks whether a trade name contains any validation/prohibited words.
    Matching is purely deterministic — case-insensitive phrase lookup up to 6-grams.
    """
    if _WORD_MAP is None:
        return {
            "validation_required": False,
            "flagged_words":       [],
            "validation_loaded":   False
        }

    clean = re.sub(r"[.\-_/&,]", " ", trade_name.lower())
    clean = normalize_arabic_name(clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    tokens = clean.split()

    MAX_NGRAM = 6
    phrases_to_check = []
    for n in range(1, MAX_NGRAM + 1):
        for i in range(len(tokens) - n + 1):
            phrases_to_check.append(" ".join(tokens[i:i + n]))

    flagged = []
    seen    = set()

    for phrase in phrases_to_check:
        # Pass 1: exact match
        if phrase in _WORD_MAP and phrase not in seen:
            seen.add(phrase)
            info = _WORD_MAP[phrase]
            flagged.append({
                "word":         info["word"],
                "word_id":      info["word_id"],
                "type_id":      info["type_id"],
                "type_name":    info["type_name"],
                "type_name_ar": info.get("type_name_ar", info["type_name"])
            })
            continue

        # Pass 2: prefix/suffix variation match
        if " " not in phrase:
            for val_key, val_info in _WORD_MAP.items():
                if " " in val_key or val_key in seen:
                    continue

                val_len = len(val_key)
                tok_len = len(phrase)

                if val_len < 4:
                    continue

                if phrase.startswith(val_key):
                    coverage = val_len / tok_len
                    if coverage >= 0.70:
                        seen.add(val_key)
                        flagged.append({
                            "word":         val_info["word"],
                            "word_id":      val_info["word_id"],
                            "type_id":      val_info["type_id"],
                            "type_name":    val_info["type_name"],
                            "type_name_ar": val_info.get("type_name_ar", val_info["type_name"])
                        })
                        break

                if val_key.startswith(phrase):
                    coverage = tok_len / val_len
                    if coverage >= 0.70:
                        seen.add(val_key)
                        flagged.append({
                            "word":         val_info["word"],
                            "word_id":      val_info["word_id"],
                            "type_id":      val_info["type_id"],
                            "type_name":    val_info["type_name"],
                            "type_name_ar": val_info.get("type_name_ar", val_info["type_name"])
                        })
                        break

    return {
        "validation_required": len(flagged) > 0,
        "flagged_words":       flagged,
        "validation_loaded":   True
    }
