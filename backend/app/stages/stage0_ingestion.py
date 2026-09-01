import os
import sys
import pdfplumber
import fitz  # PyMuPDF
from typing import Dict, Any

from backend.app.core.database import SessionLocal
from backend.app.models.models import RuleDefinition
from backend.app.seed_data import seed

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extracts text from a Legal Metrology amendment PDF.
    Tries pdfplumber first, falls back to PyMuPDF (fitz) if layout breaks.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found at: {pdf_path}")
        
    text = ""
    # Try pdfplumber first
    try:
        print(f"Attempting to extract text from {pdf_path} using pdfplumber...")
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        if text.strip():
            print("Successfully extracted text using pdfplumber.")
            return text
    except Exception as e:
        print(f"pdfplumber extraction failed: {e}. Falling back to PyMuPDF...")
        
    # Fallback to PyMuPDF
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            extracted = page.get_text()
            if extracted:
                text += extracted + "\n"
        print("Successfully extracted text using PyMuPDF (fitz).")
        return text
    except Exception as e:
        print(f"PyMuPDF extraction failed: {e}")
        raise e

def load_and_cache_rules() -> Dict[str, Any]:
    """
    Fetches rule definitions from the PostgreSQL database
    and returns them cached in a dictionary keyed by rule_id.
    """
    db = SessionLocal()
    try:
        rules = db.query(RuleDefinition).all()
        # Cache rules in memory
        cached_rules = {}
        for rule in rules:
            cached_rules[rule.rule_id] = {
                "rule_id": rule.rule_id,
                "rule_citation": rule.rule_citation,
                "description": rule.description,
                "check_type": rule.check_type,
                "validation_logic": rule.validation_logic,
                "severity": rule.severity
            }
        return cached_rules
    finally:
        db.close()

def run_stage0_ingestion():
    """
    Executes the ingestion process, setting up the tables and seeding the database.
    """
    print("Executing Stage 0: Rule dataset ingestion...")
    seed()
    print("Stage 0 Completed successfully!")

if __name__ == "__main__":
    run_stage0_ingestion()
