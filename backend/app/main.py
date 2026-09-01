import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import settings
from backend.app.api import scans, rules

app = FastAPI(
    title="PackAudit API",
    description="Legal Metrology Statutory Compliance Checker for Packaged Commodities in India",
    version="1.0.0"
)

# CORS Policy configuration (allowing local frontend origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure static directories exist
static_dir = os.path.join(settings.BASE_DIR, "static")
os.makedirs(os.path.join(static_dir, "uploads"), exist_ok=True)
os.makedirs(os.path.join(static_dir, "reports"), exist_ok=True)

# Mount uploads and reports to serve them statically
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Mount API Routers
app.include_router(scans.router)
app.include_router(rules.router)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "PackAudit Legal Metrology API",
        "version": "1.0.0",
        "docs_url": "/docs"
    }
