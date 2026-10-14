from pydantic import BaseModel
from typing import Any, Dict, Optional


class FieldResult(BaseModel):
    value: Any
    confidence: float
    status: str  # "auto_filled" | "needs_review" | "not_found"


class ExtractionResult(BaseModel):
    trade_name: FieldResult
    main_activity: FieldResult
    activity_sections: FieldResult
    social_media_account: FieldResult
    license_mobile_number: FieldResult
    license_email: FieldResult
    location: FieldResult
    address: FieldResult
    latitude: FieldResult
    longitude: FieldResult
    makani_number: FieldResult
    trade_name_arabic: FieldResult
    activity_arabic: FieldResult
