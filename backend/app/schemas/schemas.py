from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class RuleDefinitionResponse(BaseModel):
    rule_id: str
    rule_citation: str
    description: str
    check_type: str
    validation_logic: Optional[Dict[str, Any]] = None
    severity: str
    fix_suggestion: Optional[str] = None

    class Config:
        from_attributes = True

class ExtractedFieldResponse(BaseModel):
    field_name: str
    field_value: Optional[str] = None
    ocr_confidence: float

    class Config:
        from_attributes = True

class RuleCheckResponse(BaseModel):
    rule_id: str
    rule_citation: str
    description: Optional[str] = None
    status: str
    explanation: Optional[str] = None
    severity: Optional[str] = "MAJOR"
    fix_suggestion: Optional[str] = None

    class Config:
        from_attributes = True

class ScanSummaryResponse(BaseModel):
    id: str
    created_at: datetime
    input_type: str
    authenticity_score: float
    object_classification: str
    image_path: Optional[str] = None

    class Config:
        from_attributes = True

# Alias for backward compatibility
ScanResponse = ScanSummaryResponse

class ScanDetailResponse(BaseModel):
    id: str
    created_at: datetime
    input_type: str
    image_path: Optional[str] = None
    authenticity_score: float
    object_classification: str
    fields: List[ExtractedFieldResponse]
    checks: List[RuleCheckResponse]
    authenticity_report: Optional[Dict[str, Any]] = None
    report_pdf_url: Optional[str] = None

    class Config:
        from_attributes = True
