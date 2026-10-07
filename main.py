"""
main.py
-------
FastAPI application for Trade Name Validation and Similarity Checking.

Business Rules Implemented:
1. Trade name can exist in DIFFERENT business categories.
2. Same trade name must NOT exist in the SAME business category.
3. EXACTLY 90% similarity threshold (>= 90% = SIMILAR / BLOCK, < 90% = NOT SIMILAR).
4. Displays ONLY the TOP 2 highest-similarity matches in the UI (only >= 90%).
5. Validation word check (AiValidationWords.xlsx / AIValidationType.xlsx).
6. Original Arabic trade names (NAMEAR) preserved and returned in results without translation.
7. 5 validated alternative suggestions generated when original name is not allowed,
   with the user's original keyword preserved in the top suggestion where valid.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from data_loader import load_trade_names
from similarity_checker import check_trade_name, check_exact_duplicate
from suggestion_generator import generate_suggestions
from validation_checker import load_validation_data, check_validation_words


# ---------------------------------------------------------------------------
# App state & Constants
# ---------------------------------------------------------------------------

app_state: dict = {}
TOP_MATCHES_LIMIT = 2  # Display ONLY the TOP 2 highest-similarity matches >= 90%


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Loads dataset and validation files at server startup."""
    print("\nServer starting — loading 24,000+ trade names dataset...", flush=True)
    app_state["df"] = load_trade_names()
    print("Trade name dataset ready.", flush=True)

    print("Loading validation data...", flush=True)
    val_result = load_validation_data()
    app_state["validation_status"] = val_result
    if val_result["loaded"]:
        print(f"Validation data ready: {val_result['words_count']} words, "
              f"{val_result['types_count']} types.", flush=True)
    else:
        print(f"Validation data NOT loaded: {val_result['error']}", flush=True)

    print("\n==================================================", flush=True)
    print("  🚀 Application is running at: http://localhost:8000", flush=True)
    print("  👉 Open http://localhost:8000 in your browser", flush=True)
    print("==================================================\n", flush=True)
    yield
    app_state.clear()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Trade Name Validation API",
    description="Validates trade names against business rules, categories, Arabic names, and dataset with 90% threshold.",
    version="2.0.0",
    lifespan=lifespan
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class TradeNameRequest(BaseModel):
    trade_name: str
    category:   str

    @field_validator("trade_name", "category")
    @classmethod
    def must_not_be_empty(cls, value: str, info) -> str:
        if not value or not value.strip():
            raise ValueError(f"{info.field_name} must not be empty.")
        return value.strip()


class SimilarMatch(BaseModel):
    original_name: str
    name_ar:       str = ""
    score:         float
    category_id:   str = ""
    same_category: bool = False
    explanation:   str = ""
    common_words:  list[str] = []


class Suggestion(BaseModel):
    name: str


class RejectedCandidate(BaseModel):
    name:        str
    rejected_by: str
    score:       float


class FlaggedWord(BaseModel):
    word:         str
    word_id:      str
    type_id:      str
    type_name:    str
    type_name_ar: str = ""


class TradeNameResponse(BaseModel):
    trade_name:           str
    category:             str
    status:               str          # "ALLOWED", "DUPLICATE_FOUND", "VALIDATION_FAILED", "SIMILAR_FOUND"
    allowed:              bool         # True if user can continue with this trade name
    is_exact_duplicate:   bool = False
    duplicate_message:    str  = ""

    similar_found:        bool
    total_matches:        int
    similar_names:        list[SimilarMatch]  # Top 2 matches >= 90% only
    message:              str

    suggestions:          list[Suggestion]
    rejected_candidates:  list[RejectedCandidate]
    llm_error:            bool = False
    llm_error_message:    str  = ""

    validation_available: bool
    validation_required:  bool
    flagged_words:        list[FlaggedWord]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def serve_ui():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="index.html is missing.")
    return FileResponse(index_path)


@app.get("/validation-status", include_in_schema=False)
async def validation_status():
    vs = app_state.get("validation_status", {})
    return {
        "loaded":      vs.get("loaded", False),
        "words_count": vs.get("words_count", 0),
        "types_count": vs.get("types_count", 0),
        "error":       vs.get("error")
    }


@app.post("/check-trade-name", response_model=TradeNameResponse)
async def check_trade_name_endpoint(request: TradeNameRequest):
    df = app_state.get("df")
    if df is None:
        raise HTTPException(status_code=503, detail="Dataset not loaded. Restart server.")

    val_status = app_state.get("validation_status", {})
    validation_available = val_status.get("loaded", False)

    # ------------------------------------------------------------------
    # Step 1: Validation Word Check (Prohibited/Restricted/Profanity)
    # ------------------------------------------------------------------
    flagged_words = []
    validation_required = False
    if validation_available:
        val_res = check_validation_words(request.trade_name)
        validation_required = val_res["validation_required"]
        flagged_words = [
            FlaggedWord(
                word=fw["word"],
                word_id=fw["word_id"],
                type_id=fw["type_id"],
                type_name=fw["type_name"],
                type_name_ar=fw.get("type_name_ar", fw["type_name"])
            )
            for fw in val_res["flagged_words"]
        ]

    if validation_required:
        return TradeNameResponse(
            trade_name=request.trade_name,
            category=request.category,
            status="VALIDATION_FAILED",
            allowed=False,
            is_exact_duplicate=False,
            duplicate_message="",
            similar_found=False,
            total_matches=0,
            similar_names=[],
            message="These word(s) cannot be used in trade names.Please remove them and enter a different trade name.",
            suggestions=[],
            rejected_candidates=[],
            llm_error=False,
            llm_error_message="",
            validation_available=validation_available,
            validation_required=True,
            flagged_words=flagged_words
        )

    # ------------------------------------------------------------------
    # Step 2: Check Exact Duplicate in SAME Category (English & Arabic)
    # ------------------------------------------------------------------
    dup_res = check_exact_duplicate(request.trade_name, request.category, df)
    if dup_res["is_duplicate"]:
        gen_res = generate_suggestions(
            user_name=request.trade_name,
            category=request.category,
            similar_matches=[],
            df=df
        )
        return TradeNameResponse(
            trade_name=request.trade_name,
            category=request.category,
            status="DUPLICATE_FOUND",
            allowed=False,
            is_exact_duplicate=True,
            duplicate_message=dup_res["message"],
            similar_found=False,
            total_matches=0,
            similar_names=[],
            message="Reason: Same trade name already exists for this business activity.",
            suggestions=[Suggestion(name=s["name"]) for s in gen_res["accepted"]],
            rejected_candidates=[
                RejectedCandidate(name=r["name"], rejected_by=r["rejected_by"], score=r["score"])
                for r in gen_res["rejected"]
            ],
            llm_error=gen_res.get("llm_error", False),
            llm_error_message=gen_res.get("llm_error_message", ""),
            validation_available=validation_available,
            validation_required=False,
            flagged_words=[]
        )

    # ------------------------------------------------------------------
    # Step 3: Similarity Check against COMPLETE dataset (Threshold >= 90%)
    # ------------------------------------------------------------------
    sim_res = check_trade_name(request.trade_name, request.category, df)
    all_matches = sim_res["matches"]  # STRICTLY matches >= 90.0%
    total_matches = len(all_matches)
    top_matches = all_matches[:TOP_MATCHES_LIMIT]  # Display ONLY TOP 2

    similar_names = [
        SimilarMatch(
            original_name=m["original_name"],
            name_ar=m.get("name_ar", ""),
            score=m["score"],
            category_id=str(m.get("category_id", "")),
            same_category=m.get("same_category", False),
            explanation=m.get("explanation", {}).get("explanation", ""),
            common_words=m.get("explanation", {}).get("common_words", [])
        )
        for m in top_matches
    ]

    # Rule 4: If ANY existing trade name has similarity >= 90%, original name MUST BE BLOCKED
    if sim_res["similar_found"]:
        gen_res = generate_suggestions(
            user_name=request.trade_name,
            category=request.category,
            similar_matches=all_matches,
            df=df
        )
        return TradeNameResponse(
            trade_name=request.trade_name,
            category=request.category,
            status="SIMILAR_FOUND",
            allowed=False,
            is_exact_duplicate=False,
            duplicate_message="",
            similar_found=True,
            total_matches=total_matches,
            similar_names=similar_names,
            message="Reason: Similar trade name found",
            suggestions=[Suggestion(name=s["name"]) for s in gen_res["accepted"]],
            rejected_candidates=[
                RejectedCandidate(name=r["name"], rejected_by=r["rejected_by"], score=r["score"])
                for r in gen_res["rejected"]
            ],
            llm_error=gen_res.get("llm_error", False),
            llm_error_message=gen_res.get("llm_error_message", ""),
            validation_available=validation_available,
            validation_required=False,
            flagged_words=[]
        )

    # ------------------------------------------------------------------
    # Step 4: No blocking issues found (No match >= 90%) -> Allowed
    # ------------------------------------------------------------------
    return TradeNameResponse(
        trade_name=request.trade_name,
        category=request.category,
        status="ALLOWED",
        allowed=True,
        is_exact_duplicate=False,
        duplicate_message="",
        similar_found=False,
        total_matches=0,
        similar_names=[],
        message="✅ No issues found. Trade name can continue.",
        suggestions=[],
        rejected_candidates=[],
        llm_error=False,
        llm_error_message="",
        validation_available=validation_available,
        validation_required=False,
        flagged_words=[]
    )
