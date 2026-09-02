import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # DB configuration
    DATABASE_URL: str = Field(
        default="postgresql://postgres:SalinaTamboli@db.bjlfxcjsyqichrqjdyts.supabase.co:5432/postgres",
        description="Database URL for PostgreSQL connection"
    )
    
    # App directories
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    UPLOAD_DIR: str = os.path.join(BASE_DIR, "static", "uploads")
    REPORT_DIR: str = os.path.join(BASE_DIR, "static", "reports")
    
    # AI authentication thresholds
    AUTHENTICITY_THRESHOLD: float = 70.0  # Pass threshold in percentage
    
    # Nominatim Geocoding API config
    NOMINATIM_USER_AGENT: str = "PackAudit Legal Metrology Compliance Checker (prototype)"
    
    model_config = SettingsConfigDict(
        env_file=(
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "backend", ".env"),
            ".env"
        ),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Ensure directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.REPORT_DIR, exist_ok=True)
