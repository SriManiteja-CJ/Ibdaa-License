from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from routers import documents, license, llm_config, activity

app = FastAPI(
    title="UAQ Trade License – DED Smart Services API",
    description="AI-powered document extraction and trade license application submission.",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(documents.router)
app.include_router(license.router)
app.include_router(llm_config.router)
app.include_router(activity.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "UAQ DED Smart Services API"}
