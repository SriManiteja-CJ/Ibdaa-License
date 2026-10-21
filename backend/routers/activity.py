from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from data.activity_catalogue import get_all_categories, get_category_by_code
from services.activity_matcher import match_activity_for_trade_name

router = APIRouter(prefix="/api/activity", tags=["activity"])


class SuggestActivityRequest(BaseModel):
    trade_name: str
    trade_name_arabic: Optional[str] = None
    context: Optional[str] = None


class ActivityCategoryResponse(BaseModel):
    category_id: int
    code: str
    name_en: str
    name_ar: str
    representative_activities: List[str]
    isic_codes: Optional[List[Dict[str, str]]] = []


@router.get("/categories")
async def list_activity_categories():
    """Returns the list of 10 official DED business activity categories and approved activities."""
    return {
        "success": True,
        "categories": get_all_categories(),
    }


@router.post("/suggest")
async def suggest_activity(request: SuggestActivityRequest):
    """
    Given a trade name and optional context (from social media page or user input),
    finds the best fitting business activity category and specific approved activity type.
    """
    if not request.trade_name or not request.trade_name.strip():
        raise HTTPException(status_code=400, detail="Trade name must not be empty.")

    match_result = await match_activity_for_trade_name(
        trade_name=request.trade_name,
        trade_name_arabic=request.trade_name_arabic,
        context=request.context,
    )

    return {
        "success": True,
        "recommendation": match_result,
    }
