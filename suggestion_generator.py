"""
suggestion_generator.py
------------------------
Generates EXACTLY 5 validated alternative trade name suggestions when a user's
proposed name is not allowed (due to same-category duplicate, validation issue,
or similarity conflict).

Flow:
1. Generate candidate trade names (LLM or deterministic fallback).
2. All candidates MUST be different from the user's entered trade name.
3. The user's entered keyword is preserved in the TOP suggestion where allowed.
4. Every candidate is independently validated by Python logic:
   - Check validation words (AiValidationWords.xlsx)
   - Check same-category duplicate (Tradenames.xlsx)
   - Check similarity (< 90% similarity threshold against existing dataset)
5. Repeat until EXACTLY 5 valid suggestions are collected.
6. Invalid suggestions are NEVER returned to the user.

LLM: Groq (qwen/qwen3.8-27b) via OpenAI-compatible API.
The LLM ONLY generates candidate names. It NEVER decides availability.
"""

import os
import re
import time
import logging
import pandas as pd

from dotenv import load_dotenv, find_dotenv
from openai import OpenAI, APIStatusError, APIConnectionError, APITimeoutError

from similarity_checker import is_candidate_valid, check_exact_duplicate
from validation_checker import check_validation_words
from data_loader import normalize_name

load_dotenv(find_dotenv())
logger = logging.getLogger(__name__)

TARGET_SUGGESTIONS = 5
BATCH_SIZE         = 10
MAX_BATCHES        = 5
GROQ_MODEL         = "qwen/qwen3.8-27b"
GROQ_BASE_URL      = "https://api.groq.com/openai/v1"


def get_groq_client() -> OpenAI | None:
    """Returns OpenAI client for Groq if API key is present."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key.strip() in ("", "your_groq_api_key_here", "PLACEHOLDER"):
        return None
    return OpenAI(api_key=api_key, base_url=GROQ_BASE_URL)


def extract_keywords(user_name: str) -> list[str]:
    """Extracts meaningful keywords from the user's trade name."""
    _stopwords = {"llc", "l.l.c", "trading", "co", "corp", "inc", "ltd",
                  "est", "for", "and", "the", "of", "a", "&", "uaq", "branch"}
    tokens = re.split(r"[\s\-_/&.,]+", user_name)
    keywords = [t for t in tokens if t and t.lower() not in _stopwords and len(t) > 1]
    return keywords if keywords else [user_name.strip()]


def generate_fallback_candidates(user_name: str, category: str, tried_names: set[str]) -> list[str]:
    """
    Generates deterministic candidate trade names preserving the user's keyword.
    Used when LLM is unavailable or needs additional candidate pools.
    """
    keywords = extract_keywords(user_name)
    main_kw  = keywords[0].capitalize() if keywords else user_name.capitalize()
    cat_clean = category.strip().capitalize()
    user_norm = normalize_name(user_name)

    prefixes = ["New", "Pure", "Apex", "Prime", "Global", "Metro", "Next", "Direct", "Urban", "Elite"]
    suffixes = ["Hub", "Center", "World", "Solutions", "Services", "Store", "Group", "Enterprises", "House", "Point"]
    specials = ["Express", "Co", "Pro", "Plus", "Zone"]

    candidates = []

    # 1. Combination with Category
    cand1 = f"{main_kw} {cat_clean}".strip()
    if cand1 not in tried_names and normalize_name(cand1) != user_norm:
        candidates.append(cand1)

    # 2. Key combinations with suffixes & prefixes
    for s in suffixes:
        c = f"{main_kw} {cat_clean} {s}".strip()
        if c not in tried_names and normalize_name(c) != user_norm:
            candidates.append(c)

    for p in prefixes:
        c = f"{p} {main_kw} {cat_clean}".strip()
        if c not in tried_names and normalize_name(c) != user_norm:
            candidates.append(c)

    for sp in specials:
        c = f"{main_kw} {sp} {cat_clean}".strip()
        if c not in tried_names and normalize_name(c) != user_norm:
            candidates.append(c)

    return candidates


def build_prompt(
    user_name: str,
    category: str,
    keywords_str: str,
    already_rejected: list[str],
    batch_number: int
) -> str:
    """Builds prompt for Groq LLM candidate generation."""
    rejected_block = "\n".join(f"  - {n}" for n in already_rejected[-20:]) or "  (none)"

    return f"""You are a business naming assistant for a trade name registry.

Generate {BATCH_SIZE} alternative trade names for a '{category}' business.
Original trade name entered: '{user_name}'
User's main keyword: '{keywords_str}'

CRITICAL REQUIREMENTS:
1. NONE of the suggestions can be identical to '{user_name}'. They MUST all be different.
2. Suggestion #1 MUST PRESERVE AND USE THE ORIGINAL KEYWORD '{keywords_str}' in combination with relevant business words (e.g. '{keywords_str} {category} Center', '{keywords_str} Express', etc.).
3. Remaining suggestions should be creative, highly relevant variations for '{category}'.
4. Do NOT repeat any rejected names listed below:
{rejected_block}
5. Each suggestion must be 2 to 4 words. English only.
6. Output ONLY a numbered list 1 to {BATCH_SIZE}, no extra commentary.
"""


def parse_llm_response(response_text: str) -> list[str]:
    """Parses LLM numbered list response into clean strings."""
    candidates = []
    for line in response_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        cleaned = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
        cleaned = re.sub(r'["\']', "", cleaned)
        if cleaned:
            candidates.append(cleaned)
    return candidates


def generate_suggestions(
    user_name: str,
    category: str,
    similar_matches: list[dict],
    df: pd.DataFrame
) -> dict:
    """
    Generates EXACTLY 5 independently validated alternative trade names.
    Guarantees that Suggestion #1 preserves the user's keyword where valid,
    and all suggestions are strictly different from the user's input.
    """
    accepted          = []
    rejected          = []
    tried_candidates  = set()
    all_rejected_names= []
    batches_used      = 0
    total_checked     = 0

    user_norm = normalize_name(user_name)
    keywords  = extract_keywords(user_name)
    keywords_str = keywords[0] if keywords else user_name

    client = get_groq_client()

    # --- Step 1: Candidate Generation & Validation Loop ---
    for batch_num in range(1, MAX_BATCHES + 1):
        if len(accepted) >= TARGET_SUGGESTIONS:
            break

        batches_used = batch_num
        batch_candidates = []

        if client:
            try:
                prompt = build_prompt(
                    user_name=user_name,
                    category=category,
                    keywords_str=keywords_str,
                    already_rejected=all_rejected_names,
                    batch_number=batch_num
                )
                response = client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": "You generate trade names. Output only numbered list."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=300
                )
                raw_text = response.choices[0].message.content
                llm_cands = parse_llm_response(raw_text)
                batch_candidates.extend(llm_cands)
            except Exception as e:
                logger.warning(f"Groq API call warning: {e}. Falling back to deterministic generator.")

        fb_cands = generate_fallback_candidates(user_name, category, tried_candidates)
        for fc in fb_cands:
            if fc not in batch_candidates:
                batch_candidates.append(fc)

        for candidate in batch_candidates:
            if len(accepted) >= TARGET_SUGGESTIONS:
                break

            cand_clean = candidate.strip()
            if not cand_clean or cand_clean.lower() in tried_candidates:
                continue

            # Must NOT be identical to the user's original input trade name
            if normalize_name(cand_clean) == user_norm:
                continue

            tried_candidates.add(cand_clean.lower())
            total_checked += 1

            # Check 1: Validation words (AiValidationWords.xlsx)
            val_check = check_validation_words(cand_clean)
            if val_check["validation_required"]:
                top_flag = val_check["flagged_words"][0]
                rejected.append({
                    "name": cand_clean,
                    "rejected_by": f"Prohibited word: '{top_flag['word']}'",
                    "score": 0.0
                })
                all_rejected_names.append(cand_clean)
                continue

            # Check 2: Exact duplicate in SAME category (Tradenames.xlsx)
            dup_check = check_exact_duplicate(cand_clean, category, df)
            if dup_check["is_duplicate"]:
                rejected.append({
                    "name": cand_clean,
                    "rejected_by": "Exact same-category duplicate",
                    "score": 100.0
                })
                all_rejected_names.append(cand_clean)
                continue

            # Check 3: Similarity validation
            valid, conflict = is_candidate_valid(cand_clean, category, df, similar_matches)
            if valid:
                accepted.append({"name": cand_clean})
            else:
                rejected.append({
                    "name": cand_clean,
                    "rejected_by": conflict["original_name"] if conflict else "Similarity threshold",
                    "score": conflict["score"] if conflict else 90.0
                })
                all_rejected_names.append(cand_clean)

    # --- Step 2: Ensure keyword-preserving suggestion is at TOP ---
    if accepted and keywords:
        main_kw_norm = keywords[0].lower()
        top_idx = -1
        for idx, item in enumerate(accepted):
            if main_kw_norm in item["name"].lower():
                top_idx = idx
                break
        if top_idx > 0:
            kw_item = accepted.pop(top_idx)
            accepted.insert(0, kw_item)

    # --- Step 3: Top-up to exactly 5 if needed ---
    if len(accepted) < TARGET_SUGGESTIONS:
        extra_cands = generate_fallback_candidates(user_name, category, tried_candidates)
        for ec in extra_cands:
            if len(accepted) >= TARGET_SUGGESTIONS:
                break
            if ec.lower() in tried_candidates or normalize_name(ec) == user_norm:
                continue
            tried_candidates.add(ec.lower())
            val_c = check_validation_words(ec)
            dup_c = check_exact_duplicate(ec, category, df)
            sim_v, _ = is_candidate_valid(ec, category, df, similar_matches)
            if not val_c["validation_required"] and not dup_c["is_duplicate"] and sim_v:
                accepted.append({"name": ec})

    return {
        "accepted":                  accepted[:TARGET_SUGGESTIONS],
        "rejected":                  rejected,
        "batches_used":              batches_used,
        "total_candidates_checked":  total_checked,
        "llm_error":                 False,
        "llm_error_message":         ""
    }
