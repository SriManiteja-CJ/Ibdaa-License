import json
import logging
import re
from typing import Any, Dict, List, Optional

from data.activity_catalogue import (
    OFFICIAL_ACTIVITY_CATALOGUE,
    get_all_categories,
    get_category_by_code,
    get_category_by_id,
)
from services.llm.provider_factory import get_provider

logger = logging.getLogger(__name__)

# System prompt formatted with official catalogue definitions
CATEGORY_SUMMARY_TEXT = "\n".join([
    f"- {c['code']} ({c['name_en']} / {c['name_ar']}): {', '.join(c['representative_activities'])}"
    for c in OFFICIAL_ACTIVITY_CATALOGUE
])

ACTIVITY_MATCHING_PROMPT = f"""You are the Lead Business Activity Intelligence and Registrar Officer for DED Umm Al Quwain.
Your task is to analyze a business trade name (and optional business context/bio from their social media page) and map it to the single most suitable official business activity category and specific approved activity type.

OFFICIAL UAE / DED BUSINESS ACTIVITY CATEGORIES & APPROVED ACTIVITIES:
{CATEGORY_SUMMARY_TEXT}

RULES:
1. Carefully analyze the trade name and any context for keywords, business domain, industry indicators, and product/service offerings.
2. Select the EXACT matching category_code from the official list above (COMM_001, SERV_002, TECH_003, REST_004, MKTG_005, MDIA_006, INDU_007, LOGS_008, EDUC_009, FREE_010).
3. Select the best representative_activity from that category's approved list. If a specific niche is mentioned that aligns with the category, pick the closest representative activity.
4. Provide a clear, professional reason in English explaining why the trade name matches this activity.
5. Provide the accurate Arabic name for the selected activity.
6. Return confidence between 0.0 and 1.0 (0.9+ for strong obvious matches like "Cafe" -> REST_004, 0.7-0.85 for moderate matches).

RETURN ONLY A VALID JSON OBJECT (no markdown, no extra explanation):
{{
  "category_code": "COMM_001",
  "matched_activity_en": "Online retail",
  "matched_activity_ar": "تجارة التجزئة عبر الإنترنت",
  "confidence": 0.95,
  "reason_en": "The trade name clearly indicates an online retail store."
}}
"""


def _extract_json_safely(text: str) -> Optional[dict]:
    try:
        text = text.strip()
        text = re.sub(r"^```(?:json)?", "", text)
        text = re.sub(r"```$", "", text).strip()
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return json.loads(text)
    except Exception as exc:
        logger.warning(f"Failed to parse activity matching JSON: {exc}")
        return None


# Keyword map for robust deterministic fallback
KEYWORD_CATEGORY_MAP = [
    {
        "code": "REST_004",
        "keywords": ["cafe", "coffee", "restaurant", "bistro", "bakery", "sweets", "kitchen", "burger", "grill", "tea", "roastery", "dining", "food", "catering", "lounge", "pastry"],
        "default_act": "Cafe and Restaurant",
        "default_act_ar": "مطعم ومقهى",
    },
    {
        "code": "TECH_003",
        "keywords": ["tech", "technology", "software", "digital", "ai", "cyber", "data", "cloud", "web", "app", "systems", "solutions", "it", "code", "dev", "computing", "network"],
        "default_act": "Software development",
        "default_act_ar": "تطوير البرمجيات",
    },
    {
        "code": "MKTG_005",
        "keywords": ["marketing", "advertising", "media ads", "pr", "public relations", "branding", "seo", "social media agency", "adverts", "campaign"],
        "default_act": "Digital marketing",
        "default_act_ar": "التسويق الرقمي",
    },
    {
        "code": "MDIA_006",
        "keywords": ["design", "creative", "media", "photography", "photo", "studio", "video", "production", "content", "graphics", "film", "art"],
        "default_act": "Content creation",
        "default_act_ar": "صناعة المحتوى والخدمات الإبداعية",
    },
    {
        "code": "SERV_002",
        "keywords": ["consulting", "consultancy", "advisory", "management", "audit", "auditing", "corporate", "business services", "legal", "financial services"],
        "default_act": "Business consultancy",
        "default_act_ar": "استشارات الأعمال",
    },
    {
        "code": "COMM_001",
        "keywords": ["trading", "trade", "store", "shop", "boutique", "retail", "wholesale", "import", "export", "ecommerce", "e-commerce", "market", "mart", "fashion", "perfumes", "gifts", "clothing", "flowers"],
        "default_act": "Online retail",
        "default_act_ar": "تجارة التجزئة عبر الإنترنت",
    },
    {
        "code": "LOGS_008",
        "keywords": ["logistics", "courier", "delivery", "shipping", "freight", "cargo", "storage", "warehouse", "transport"],
        "default_act": "Courier & Delivery Services",
        "default_act_ar": "خدمات التوصيل والنقل",
    },
    {
        "code": "INDU_007",
        "keywords": ["manufacturing", "factory", "industry", "industrial", "assembly", "fabrication", "processing", "production"],
        "default_act": "Manufacturing",
        "default_act_ar": "التصنيع والإنتاج",
    },
    {
        "code": "EDUC_009",
        "keywords": ["academy", "training", "institute", "education", "tutoring", "learning", "courses", "school", "workshop"],
        "default_act": "Professional training",
        "default_act_ar": "التدريب المهني والتعليم",
    },
    {
        "code": "FREE_010",
        "keywords": ["freelance", "independent", "consultant", "specialist"],
        "default_act": "Professional freelance activities",
        "default_act_ar": "أنشطة العمل الحر والخدمات المستقلة",
    },
]


def match_activity_deterministic(trade_name: str, context: Optional[str] = None) -> Dict[str, Any]:
    """Fallback keyword matching algorithm with phrase length and specificity scoring."""
    text = f" {trade_name} {context or ''} ".lower()

    best_match = None
    best_score = 0

    for mapping in KEYWORD_CATEGORY_MAP:
        cat = get_category_by_code(mapping["code"])
        if not cat:
            continue
        for kw in mapping["keywords"]:
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, text) or kw in text:
                score = len(kw) * (2 if " " in kw else 1)
                if score > best_score:
                    best_score = score
                    best_match = {
                        "category_code": cat["code"],
                        "category_id": cat["category_id"],
                        "category_name_en": cat["name_en"],
                        "category_name_ar": cat["name_ar"],
                        "matched_activity_en": mapping["default_act"],
                        "matched_activity_ar": mapping["default_act_ar"],
                        "available_activities": cat["representative_activities"],
                        "isic_codes": cat.get("isic_codes", []),
                        "confidence": 0.88 if score > 5 else 0.75,
                        "match_reason": f"Matched based on business keyword '{kw}' identified in the trade name.",
                        "status": "auto_filled",
                    }

    if best_match:
        return best_match

    # Default to Commercial & Trading if no specific keyword triggered
    cat = get_category_by_code("COMM_001")
    return {
        "category_code": cat["code"],
        "category_id": cat["category_id"],
        "category_name_en": cat["name_en"],
        "category_name_ar": cat["name_ar"],
        "matched_activity_en": "General trading",
        "matched_activity_ar": "التجارة العامة",
        "available_activities": cat["representative_activities"],
        "isic_codes": cat.get("isic_codes", []),
        "confidence": 0.60,
        "match_reason": "Assigned Commercial & Trading as default baseline activity.",
        "status": "needs_review",
    }


async def match_activity_for_trade_name(
    trade_name: str,
    trade_name_arabic: Optional[str] = None,
    context: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main AI function to discover the best activity from the official DED catalogue
    for a given trade name extracted from social media.
    """
    cleaned_name = (trade_name or "").strip()
    if not cleaned_name:
        cat = get_category_by_code("COMM_001")
        return {
            "category_code": cat["code"],
            "category_id": cat["category_id"],
            "category_name_en": cat["name_en"],
            "category_name_ar": cat["name_ar"],
            "matched_activity_en": "",
            "matched_activity_ar": "",
            "available_activities": cat["representative_activities"],
            "isic_codes": cat.get("isic_codes", []),
            "confidence": 0.0,
            "match_reason": "No trade name provided.",
            "status": "not_found",
        }

    user_prompt = (
        f"TRADE NAME (ENGLISH): {cleaned_name}\n"
        f"TRADE NAME (ARABIC): {trade_name_arabic or 'None'}\n"
        f"SOCIAL MEDIA CONTEXT / BIO / PRODUCTS: {context or 'None provided'}\n\n"
        "Analyze the business nature and return the exact JSON matching the official catalogue."
    )

    full_prompt = f"{ACTIVITY_MATCHING_PROMPT}\n\nUser Input:\n{user_prompt}"

    try:
        provider = get_provider()
        raw_response = await provider.analyze_document([], full_prompt)
        parsed = _extract_json_safely(raw_response)

        if parsed and "category_code" in parsed:
            cat_code = parsed.get("category_code", "").upper().strip()
            cat = get_category_by_code(cat_code) or get_category_by_code("COMM_001")

            matched_act = parsed.get("matched_activity_en")
            # If the model suggested an activity not directly in representative_activities, validate or select closest
            if not matched_act or matched_act not in cat["representative_activities"]:
                for rep in cat["representative_activities"]:
                    if matched_act and (matched_act.lower() in rep.lower() or rep.lower() in matched_act.lower()):
                        matched_act = rep
                        break
                if not matched_act:
                    matched_act = cat["representative_activities"][0]

            matched_act_ar = parsed.get("matched_activity_ar") or cat["name_ar"]
            confidence = float(parsed.get("confidence", 0.9))
            reason = parsed.get("reason_en") or f"Matched to {cat['name_en']} based on trade name."

            return {
                "category_code": cat["code"],
                "category_id": cat["category_id"],
                "category_name_en": cat["name_en"],
                "category_name_ar": cat["name_ar"],
                "matched_activity_en": matched_act,
                "matched_activity_ar": matched_act_ar,
                "available_activities": cat["representative_activities"],
                "isic_codes": cat.get("isic_codes", []),
                "confidence": confidence,
                "match_reason": reason,
                "status": "auto_filled" if confidence >= 0.75 else "needs_review",
            }
    except Exception as exc:
        logger.warning(f"LLM activity matching failed, falling back to deterministic: {exc}")

    return match_activity_deterministic(cleaned_name, context)
