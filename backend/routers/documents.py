from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import Optional

from services.ocr_processor import convert_upload_to_images
from services.ai_extractor import extract_from_documents, merge_extractions

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/analyze")
async def analyze_documents(
    screenshot: Optional[UploadFile] = File(None),
    site_plan: Optional[UploadFile] = File(None),
    social_media_url: Optional[str] = Form(None),
):
    """
    Accept uploaded documents, run AI extraction, return field-level results.
    """
    uploaded_documents = []

    for upload, document_type in [
        (screenshot, "Social Media Page Screenshot"),
        (site_plan, "Valid Site Plan"),
    ]:
        if upload and upload.filename:
            content = await upload.read()
            if content:
                # Site plans only need page 1 since all key information is on the first page
                max_pages = 1 if document_type == "Valid Site Plan" else None
                imgs = convert_upload_to_images(content, upload.filename, max_pages=max_pages)
                uploaded_documents.append((document_type, imgs))

    if not uploaded_documents:
        raise HTTPException(
            status_code=400,
            detail="At least one document must be uploaded (screenshot or site plan).",
        )

    results = []
    issues = []
    for document_type, images in uploaded_documents:
        result = await extract_from_documents(images, document_type)
        results.append(result["extraction"])
        if not result["is_relevant"]:
            message = result["message"] or (
                f"The uploaded file does not appear to be a {document_type.lower()}."
            )
            issues.append(f"{document_type}: {message}")

    if issues:
        return {
            "success": False,
            "document_validation": {"is_valid": False, "issues": issues},
        }

    result = results[0]
    for additional_result in results[1:]:
        result = merge_extractions(result, additional_result)

    # If social_media_account is empty but social_media_url was provided in the form, derive handle
    if social_media_url and not result.get("social_media_account", {}).get("value"):
        import re
        clean_url = social_media_url.strip()
        match = re.search(
            r"(?:instagram\.com|tiktok\.com|facebook\.com|x\.com|twitter\.com)/@?([a-zA-Z0-9._-]+)",
            clean_url,
        )
        if match:
            handle = f"@{match.group(1)}"
        elif clean_url.startswith("@"):
            handle = clean_url
        elif "/" not in clean_url:
            handle = f"@{clean_url}"
        else:
            handle = clean_url

        result["social_media_account"] = {
            "value": handle,
            "confidence": 0.95,
            "status": "auto_filled",
        }

    return {
        "success": True,
        "extraction": result,
        "social_media_url": social_media_url,
        "document_validation": {"is_valid": True, "issues": []},
    }
