"""
similarity_checker.py
---------------------
Compares a user-provided trade name (English or Arabic) against ALL existing names
in the dataset (both NAMEEN and NAMEAR).

Business Rules:
1. Search/check both English (NAMEEN) and Arabic (NAMEAR) trade names against COMPLETE dataset.
2. Exact same trade name + SAME category = duplicate and NOT allowed.
3. Exact same trade name + DIFFERENT category = ALLOWED (unless similarity >= 90%).
4. Threshold: EXACTLY 90.0% (>= 90% = SIMILAR / BLOCK, < 90% = NOT SIMILAR).
5. Do not translate Arabic names; preserve original Arabic text in results.

This file NEVER modifies Tradenames.xlsx.
It NEVER calls an LLM. All decisions are deterministic.
"""

import pandas as pd
from rapidfuzz import fuzz, process

from data_loader import normalize_name, normalize_arabic_name, normalize_category, is_same_category

# ---------------------------------------------------------------------------
# Constants — Threshold set to EXACTLY 90%
# ---------------------------------------------------------------------------

SIMILARITY_THRESHOLD = 90.0


# ---------------------------------------------------------------------------
# Function 1: calculate_similarity
# ---------------------------------------------------------------------------

def calculate_similarity(name_a: str, name_b: str) -> float:
    """
    Calculates similarity between two trade name strings (English or Arabic).
    """
    norm_en_a = normalize_name(name_a)
    norm_en_b = normalize_name(name_b)

    norm_ar_a = normalize_arabic_name(name_a)
    norm_ar_b = normalize_arabic_name(name_b)

    score_en = fuzz.token_sort_ratio(norm_en_a, norm_en_b) if norm_en_a and norm_en_b else 0
    score_ar = fuzz.token_sort_ratio(norm_ar_a, norm_ar_b) if norm_ar_a and norm_ar_b else 0

    return max(score_en, score_ar)


# ---------------------------------------------------------------------------
# Function 2: explain_match
# ---------------------------------------------------------------------------

def explain_match(user_name: str, existing_name: str, score: float) -> dict:
    """
    Produces a plain-English explanation of why two trade names are similar.
    """
    norm_user     = normalize_name(user_name)
    norm_existing = normalize_name(existing_name)

    _ignore = {"llc", "l.l.c", "trading", "co", "corp", "inc", "ltd",
               "est", "for", "and", "&", "the", "of", "a", "uaq"}

    user_tokens     = [t for t in norm_user.split()     if t not in _ignore and len(t) > 1]
    existing_tokens = [t for t in norm_existing.split() if t not in _ignore and len(t) > 1]

    user_set     = set(user_tokens)
    existing_set = set(existing_tokens)

    common_words = sorted(user_set & existing_set)

    near_matches = []
    seen_pairs   = set()
    for uw in user_tokens:
        for ew in existing_tokens:
            if uw == ew:
                continue
            pair_key = (min(uw, ew), max(uw, ew))
            if pair_key in seen_pairs:
                continue
            prefix_len = 0
            for c1, c2 in zip(uw, ew):
                if c1 == c2:
                    prefix_len += 1
                else:
                    break
            min_len = min(len(uw), len(ew))
            if prefix_len >= 4 and prefix_len >= min_len * 0.75:
                near_matches.append({"user_word": uw, "existing_word": ew})
                seen_pairs.add(pair_key)

    parts = []
    if common_words:
        word_list = ", ".join(f'"{w}"' for w in common_words[:4])
        parts.append(f"share the word(s) {word_list}")
    if near_matches:
        pair_strs = [f'"{p["user_word"]}" ≈ "{p["existing_word"]}"'
                     for p in near_matches[:2]]
        parts.append(f"contains similar spelling(s): {', '.join(pair_strs)}")

    if parts:
        explanation = f"These names are {score:.1f}% similar — they {' and '.join(parts)}."
    else:
        explanation = (
            f"These names are {score:.1f}% similar — high character-level overlap "
            f"when compared using Token Sort Ratio."
        )

    return {
        "method":       "Token Sort Ratio (RapidFuzz)",
        "common_words": common_words,
        "near_matches": near_matches,
        "explanation":  explanation
    }


# ---------------------------------------------------------------------------
# Function 3: check_exact_duplicate
# ---------------------------------------------------------------------------

def check_exact_duplicate(user_name: str, category: str, df: pd.DataFrame) -> dict:
    """
    Checks if the exact same trade name (English or Arabic) exists in the SAME category.

    Rules:
    - Same name (NAMEEN or NAMEAR) + SAME category = DUPLICATE (NOT ALLOWED)
    - Same name + DIFFERENT category = NOT duplicate (ALLOWED, subject to similarity check)
    """
    norm_en = normalize_name(user_name)
    norm_ar = normalize_arabic_name(user_name)
    user_cat_norm = normalize_category(category)

    same_cat_matches = []
    diff_cat_matches = []

    for idx, row in df.iterrows():
        existing_en = row["NAMEEN_NORMALIZED"]
        existing_ar = row["NAMEAR_NORMALIZED"]
        row_cat     = row["CATEGORY_NORMALIZED"]

        is_name_match = (
            (norm_en and norm_en == existing_en) or
            (norm_ar and norm_ar == existing_ar) or
            (norm_en and norm_en == existing_ar) or
            (norm_ar and norm_ar == existing_en)
        )

        if is_name_match:
            same_category = is_same_category(user_cat_norm, row_cat)
            match_data = {
                "original_name": row["NAMEEN"] if row["NAMEEN"] else row["NAMEAR"],
                "name_ar": row["NAMEAR"] if row["NAMEAR"] else "",
                "category_id": row["ACTIVITY_CATEGORY_ID"],
                "same_category": same_category
            }
            if same_category:
                same_cat_matches.append(match_data)
            else:
                diff_cat_matches.append(match_data)

    if same_cat_matches:
        return {
            "is_duplicate": True,
            "duplicate_in_same_category": True,
            "message": "This trade name already exists in the provided dataset for this business activity.",
            "matching_records": same_cat_matches,
            "diff_cat_records": diff_cat_matches
        }

    return {
        "is_duplicate": False,
        "duplicate_in_same_category": False,
        "message": "No exact duplicate in this business category.",
        "matching_records": [],
        "diff_cat_records": diff_cat_matches
    }


# ---------------------------------------------------------------------------
# Function 4: check_trade_name
# ---------------------------------------------------------------------------

def check_trade_name(user_name: str, category: str, df: pd.DataFrame) -> dict:
    """
    Full trade name check against COMPLETE dataset with EXACTLY 90% similarity threshold.

    Rules:
    - Scores >= 90.0% are flagged as SIMILAR and BLOCK the trade name.
    - Scores < 90.0% are NOT flagged and NOT displayed.
    """
    user_norm_en = normalize_name(user_name)
    user_norm_ar = normalize_arabic_name(user_name)

    # 1. Exact Duplicate Check
    dup_result = check_exact_duplicate(user_name, category, df)

    # 2. Vectorized Similarity Check with score_cutoff=90.0
    existing_en = df["NAMEEN_NORMALIZED"].tolist()
    existing_ar = df["NAMEAR_NORMALIZED"].tolist()

    scores_en = []
    if user_norm_en:
        mat_en = process.cdist([user_norm_en], existing_en, scorer=fuzz.token_sort_ratio, score_cutoff=SIMILARITY_THRESHOLD)
        scores_en = mat_en[0]

    scores_ar = []
    query_ar = user_norm_ar if user_norm_ar else user_norm_en
    if query_ar:
        mat_ar = process.cdist([query_ar], existing_ar, scorer=fuzz.token_sort_ratio, score_cutoff=SIMILARITY_THRESHOLD)
        scores_ar = mat_ar[0]

    raw_matches = []
    n_rows = len(df)

    for i in range(n_rows):
        sc_e = float(scores_en[i]) if i < len(scores_en) else 0.0
        sc_a = float(scores_ar[i]) if i < len(scores_ar) else 0.0
        best_sc = max(sc_e, sc_a)

        # STRICT 90.0% THRESHOLD CUTOFF
        if best_sc >= SIMILARITY_THRESHOLD:
            orig_en = str(df["NAMEEN"].iloc[i]).strip() if pd.notna(df["NAMEEN"].iloc[i]) and str(df["NAMEEN"].iloc[i]).strip() != "nan" else ""
            orig_ar = str(df["NAMEAR"].iloc[i]).strip() if pd.notna(df["NAMEAR"].iloc[i]) and str(df["NAMEAR"].iloc[i]).strip() != "nan" else ""
            display_name = orig_en if orig_en else orig_ar

            row_cat  = df["CATEGORY_NORMALIZED"].iloc[i]
            score_v  = round(float(best_sc), 1)
            same_cat = is_same_category(category, row_cat)

            raw_matches.append({
                "original_name": display_name,
                "name_ar": orig_ar,
                "score": score_v,
                "category_id": df["ACTIVITY_CATEGORY_ID"].iloc[i],
                "same_category": same_cat,
                "explanation": explain_match(user_name, display_name, score_v)
            })

    raw_matches.sort(key=lambda x: x["score"], reverse=True)
    similar_found = len(raw_matches) > 0

    return {
        "user_name":          user_name,
        "user_normalized":    user_norm_en or user_norm_ar,
        "category":           category,
        "is_exact_duplicate": dup_result["is_duplicate"],
        "duplicate_message":  dup_result["message"] if dup_result["is_duplicate"] else "",
        "similar_found":      similar_found,
        "matches":            raw_matches,
        "dup_result":         dup_result
    }


# ---------------------------------------------------------------------------
# Function 5: is_candidate_valid
# ---------------------------------------------------------------------------

def is_candidate_valid(
    candidate_name: str,
    category: str,
    df: pd.DataFrame,
    user_similar_matches: list[dict] | None = None
) -> tuple[bool, dict | None]:
    """
    Independently validates an LLM-generated suggestion against COMPLETE dataset.

    Rules:
    1. Must NOT be an exact duplicate in the SAME category.
    2. Must NOT score >= 90.0% similarity against ANY existing name in dataset.
    3. Must NOT score >= 90.0% similarity against user's conflicting matches.
    """
    dup_res = check_exact_duplicate(candidate_name, category, df)
    if dup_res["is_duplicate"]:
        return False, {"original_name": candidate_name, "score": 100.0, "reason": "Exact same-category duplicate"}

    cand_norm_en = normalize_name(candidate_name)
    cand_norm_ar = normalize_arabic_name(candidate_name)

    names_en = df["NAMEEN_NORMALIZED"].tolist()
    names_ar = df["NAMEAR_NORMALIZED"].tolist()
    orig_en  = df["NAMEEN"].tolist()
    orig_ar  = df["NAMEAR"].tolist()

    if cand_norm_en:
        scores_m = process.cdist([cand_norm_en], names_en, scorer=fuzz.token_sort_ratio, score_cutoff=SIMILARITY_THRESHOLD)
        for i, s in enumerate(scores_m[0]):
            if s >= SIMILARITY_THRESHOLD:
                disp = orig_en[i] if pd.notna(orig_en[i]) else orig_ar[i]
                return False, {"original_name": disp, "score": round(float(s), 1), "reason": f"Similarity score {s:.1f}% >= 90.0%"}

    if cand_norm_ar:
        scores_ar_m = process.cdist([cand_norm_ar], names_ar, scorer=fuzz.token_sort_ratio, score_cutoff=SIMILARITY_THRESHOLD)
        for i, s in enumerate(scores_ar_m[0]):
            if s >= SIMILARITY_THRESHOLD:
                disp = orig_ar[i] if pd.notna(orig_ar[i]) else orig_en[i]
                return False, {"original_name": disp, "score": round(float(s), 1), "reason": f"Arabic similarity score {s:.1f}% >= 90.0%"}

    if user_similar_matches:
        for existing in user_similar_matches[:5]:
            ex_norm_en = normalize_name(existing["original_name"])
            ex_norm_ar = normalize_arabic_name(existing.get("name_ar", ""))
            sc_e = fuzz.token_sort_ratio(cand_norm_en, ex_norm_en) if cand_norm_en and ex_norm_en else 0
            sc_a = fuzz.token_sort_ratio(cand_norm_ar, ex_norm_ar) if cand_norm_ar and ex_norm_ar else 0
            score = max(sc_e, sc_a)
            if score >= SIMILARITY_THRESHOLD:
                return False, {"original_name": existing["original_name"], "score": round(score, 1), "reason": "Conflict with user match"}

    return True, None
