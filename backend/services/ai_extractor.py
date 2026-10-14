import io
import json
import re
from typing import List
import PIL.Image

from services.llm.provider_factory import get_provider


EXTRACTION_PROMPT = """You are a document analysis AI for the UAE Department of Economic Development.
Analyze the provided document image(s) carefully and extract the following business license information.

Return ONLY a valid JSON object with this exact structure (no markdown, no explanation):
{{
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
- confidence is a float between 0.0 and 1.0 (1.0 = certain, 0.0 = not found)
- For activity_sections: return an array of strings like ["12849 - Printing product design", "43469 - Social media marketing"]
- If a field is not found or unclear, set value to "" and confidence to 0.0
- main_activity means the product sold or service provided by the business, not its trade name.
  Determine it from clear evidence such as an official activity description, social-page category
  or bio, or visible products/services. A trade name alone is not enough unless it unambiguously
  describes the activity. Return a concise activity; if the evidence does not identify one clearly,
  leave it empty.
- social_media_account means the account handle, username, or account URL visible on a social
  media page. Do not put the business display name or trade name in this field unless it is also
  explicitly shown as the account username/handle.
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


async def extract_from_documents(images: List[PIL.Image.Image]) -> dict:
    """
    Run document extraction using the configured LLM provider.
    Returns a dict with field-level results: {field: {value, confidence, status}}
    """
    provider = get_provider()
    raw_response = await provider.analyze_document(images, EXTRACTION_PROMPT)

    try:
        extracted = _extract_json(raw_response)
    except Exception:
        # Return all empty on parse failure
        return _empty_result()

    result = {}
    for field, data in extracted.items():
        if isinstance(data, dict):
            value = data.get("value", "")
            confidence = float(data.get("confidence", 0.0))
        else:
            value = data
            confidence = 0.5

        if confidence >= 0.85:
            status = "auto_filled"
        elif confidence >= 0.5:
            status = "needs_review"
        else:
            status = "not_found"

        result[field] = {
            "value": value,
            "confidence": confidence,
            "status": status,
        }

    return result


def _empty_result() -> dict:
    fields = [
        "trade_name", "main_activity", "activity_sections",
        "social_media_account", "license_mobile_number", "license_email",
        "location", "address", "latitude", "longitude", "makani_number",
        "trade_name_arabic", "activity_arabic",
    ]
    return {
        f: {"value": "" if f != "activity_sections" else [], "confidence": 0.0, "status": "not_found"}
        for f in fields
    }
