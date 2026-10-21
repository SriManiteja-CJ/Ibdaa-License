import io
import json
import re
from typing import List
import PIL.Image

from services.llm.provider_factory import get_provider


EXTRACTION_PROMPT = """You are a document analysis AI for the UAE Department of Economic Development.
The expected upload type is: {document_type}.
First decide whether the provided image(s) appear to match that upload type. This is a document-type
check only; do not claim to verify authenticity. Then extract the following business license information.

Return ONLY a valid JSON object with this exact structure (no markdown, no explanation):
{{
  "document_check": {{"is_relevant": true, "message": ""}},
  "trade_name": {{"value": "", "confidence": 0.0}},
  "main_activity": {{"value": "", "confidence": 0.0}},
  "activity_sections": {{"value": [], "confidence": 0.0}},
  "social_media_account": {{"value": "", "confidence": 0.0}},
  "license_mobile_number": {{"value": "", "confidence": 0.0}},
  "license_email": {{"value": "", "confidence": 0.0}},
  "location": {{"value": "", "confidence": 0.0}},
  "address": {{"value": "", "confidence": 0.0}},
  "latitude": {{"value": "", "confidence": 0.0}},
  "longitude": {{"value": "", "confidence": 0.0}},
  "makani_number": {{"value": "", "confidence": 0.0}},
  "trade_name_arabic": {{"value": "", "confidence": 0.0}},
  "activity_arabic": {{"value": "", "confidence": 0.0}}
}}

Rules:
- Set document_check.is_relevant to false when the image(s) are blank, unreadable, or clearly not
  the expected upload type. Set it to true when they appear to be the expected type, even if a
  particular field is not present. If false, give a short, helpful message describing what to upload.
- For "Social Media Page Screenshot", expect a screenshot/image of a social media profile or page.
  For "Valid Site Plan", expect a site/location plan or map showing a property/location.
- document_check.message should be empty when the document appears relevant.
- confidence is a float between 0.0 and 1.0 (1.0 = certain, 0.0 = not found)
- For main_activity: Determine the business activity and select the best matching official activity from the 10 UAE DED categories:
  Commercial & Trading (e.g. General trading, Retail trade, Online retail, E-Commerce portal operations)
  Consulting & Professional Services (e.g. Management consultancy, Business consultancy)
  IT & Technology (e.g. Software development, IT consultancy, Cloud computing)
  Restaurants, Cafes & Food Services (e.g. Cafe and Restaurant, Bakery and Sweets, Restaurant)
  Digital Marketing & Advertising (e.g. Digital marketing, Advertising services)
  Media & Creative (e.g. Content creation, Media production, Graphic Design & Photography)
  Industrial & Manufacturing (e.g. Manufacturing, Processing, Production)
  Logistics & Warehousing (e.g. Storage, Distribution, Courier & Delivery Services)
  Education & Training (e.g. Professional training, Tutoring, Educational services)
  Freelance & Independent Services (e.g. Digital services, Creative services, Professional freelance activities)
- For activity_sections: return an array of strings representing official approved activities and ISIC descriptions
- For activity_arabic: return the corresponding Arabic name of the main_activity
- If a field is not found or unclear, set value to "" and confidence to 0.0
- For social_media_account: Extract the account handle, username, or profile handle visible on the social media page screenshot (e.g. "@username", "username" shown in the top navigation bar, header, bio, or under profile photo). Even if the username resembles the trade name (e.g. trade name "Marmot Clothing Co" and handle "@marmotclothingco"), always extract and populate the handle here. Format as "@username" or the exact handle shown.
- Only populate license_mobile_number when a phone number is explicitly identified as the
  license/application mobile number in an official license or application document. A WhatsApp
  number, page contact number, or phone number shown on a social media setup/profile screenshot is
  not a license mobile number; leave the field empty unless it is separately confirmed by an
  official document.
- For location and address, inspect the uploaded site plan/map. When latitude and longitude are
  printed on the plan (often labeled Lat and Long), extract both decimal coordinates exactly into
  latitude and longitude. Use the map pin and its labels to extract the corresponding locality and
  street/building address. Do not use an unrelated address elsewhere in the documents.
- For makani_number, extract the Makani number associated with that mapped location if it is shown
  in the documents. Preserve all digits exactly; do not substitute coordinates, phone numbers, or
  other numeric identifiers (including a PID/site-plan number), and do not infer a Makani number if
  one is not available.
- Do not hallucinate - only return values supported by visible document content or map context
"""

# Keep requests below Groq's input-token-per-minute limit as well as its image-count limit.
MAX_IMAGES_PER_REQUEST = 2


def _extract_json(text: str) -> dict:
    """Robustly extract JSON from LLM response text."""
    text = text.strip()
    # Remove markdown code fences
    text = re.sub(r"```(?:json)?", "", text).strip()
    # Find first { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return json.loads(text)


def _field_result(value, confidence: float) -> dict:
    if confidence >= 0.85:
        status = "auto_filled"
    elif confidence >= 0.5:
        status = "needs_review"
    else:
        status = "not_found"
    return {"value": value, "confidence": confidence, "status": status}


def merge_extractions(current: dict, incoming: dict) -> dict:
    for field, candidate in incoming.items():
        if field not in current:
            continue
        if field == "activity_sections":
            values = current[field]["value"] + candidate["value"]
            current[field] = _field_result(
                list(dict.fromkeys(values)),
                max(current[field]["confidence"], candidate["confidence"]),
            )
        elif (
            candidate["value"] not in ("", None)
            and (
                current[field]["value"] in ("", None)
                or candidate["confidence"] > current[field]["confidence"]
            )
        ):
            current[field] = candidate
    return current


def _normalize_extraction(extracted: dict) -> dict:
    result = _empty_result()
    for field, data in extracted.items():
        if field not in result:
            continue
        if isinstance(data, dict):
            value = data.get("value", result[field]["value"])
            confidence = float(data.get("confidence", 0.0))
        else:
            value = data
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))
        result[field] = _field_result(value, confidence)
    return result


async def extract_from_documents(
    images: List[PIL.Image.Image], document_type: str
) -> dict:
    """Analyze page batches and merge the extraction for one uploaded document."""
    # For site plans, all primary information (coordinates, Makani, address) is on page 1
    if document_type == "Valid Site Plan" and len(images) > 1:
        images = images[:1]

    provider = get_provider()
    prompt = EXTRACTION_PROMPT.format(document_type=document_type)
    merged = _empty_result()
    relevant = False
    rejection_message = ""

    for start in range(0, len(images), MAX_IMAGES_PER_REQUEST):
        batch = images[start:start + MAX_IMAGES_PER_REQUEST]
        raw_response = await provider.analyze_document(batch, prompt)
        extracted = _extract_json(raw_response)

        document_check = extracted.get("document_check", {})
        if document_check.get("is_relevant") is True:
            relevant = True
        elif not rejection_message:
            rejection_message = document_check.get("message", "")

        merge_extractions(merged, _normalize_extraction(extracted))

    # If a trade name was extracted, ensure official activity matching from the DED catalogue
    trade_name_val = merged.get("trade_name", {}).get("value")
    if trade_name_val:
        from services.activity_matcher import match_activity_for_trade_name
        act_result = await match_activity_for_trade_name(
            trade_name=trade_name_val,
            trade_name_arabic=merged.get("trade_name_arabic", {}).get("value"),
            context=merged.get("main_activity", {}).get("value"),
        )
        if act_result and act_result.get("matched_activity_en"):
            cur_conf = merged.get("main_activity", {}).get("confidence", 0.0)
            if cur_conf < 0.85 or not merged.get("main_activity", {}).get("value"):
                merged["main_activity"] = _field_result(
                    act_result["matched_activity_en"], act_result["confidence"]
                )
            if not merged.get("activity_arabic", {}).get("value"):
                merged["activity_arabic"] = _field_result(
                    act_result["matched_activity_ar"], act_result["confidence"]
                )
            merged["activity_category"] = _field_result(
                act_result["category_name_en"], act_result["confidence"]
            )
            merged["activity_reason"] = _field_result(
                act_result["match_reason"], act_result["confidence"]
            )
            if not merged.get("activity_sections", {}).get("value"):
                merged["activity_sections"] = _field_result(
                    act_result["available_activities"], act_result["confidence"]
                )

    return {
        "is_relevant": relevant,
        "message": rejection_message,
        "extraction": merged,
    }


def _empty_result() -> dict:
    fields = [
        "trade_name", "main_activity", "activity_sections",
        "social_media_account", "license_mobile_number", "license_email",
        "location", "address", "latitude", "longitude", "makani_number",
        "trade_name_arabic", "activity_arabic",
        "activity_category", "activity_reason",
    ]
    return {
        f: {"value": "" if f != "activity_sections" else [], "confidence": 0.0, "status": "not_found"}
        for f in fields
    }
