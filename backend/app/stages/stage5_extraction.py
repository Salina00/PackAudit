import re
from typing import Dict, Any, List, Optional, Tuple

# Global spaCy model cache
_nlp = None

def get_spacy_nlp():
    """
    Lazy-loads the spaCy English model with fallback.
    """
    global _nlp
    if _nlp is None:
        try:
            import spacy
            print("Loading spaCy NLP model ('en_core_web_sm')...")
            _nlp = spacy.load("en_core_web_sm")
        except Exception as e:
            print(f"Failed to load spaCy model: {e}. Attempting to load dynamic spacy runner...")
            # We can download it dynamically if pip finished but model is missing
            try:
                import os
                os.system("python -m spacy download en_core_web_sm --quiet")
                import spacy
                _nlp = spacy.load("en_core_web_sm")
            except Exception as ex:
                print(f"Dynamic spacy download failed: {ex}. Falling back to heuristic NER.")
                _nlp = "FAILED"
    return _nlp

# Pre-compiled regex patterns for structured fields
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
PHONE_REGEX = re.compile(r"\b(?:\+91[\-\s]?)?\(?[0-9]{3,5}\)?[\-\s]?[0-9]{3,4}[\-\s]?[0-9]{3,4}\b|\b1800[\-\s]?[0-9]{3,4}[\-\s]?[0-9]{3,4}\b")
PINCODE_REGEX = re.compile(r"\b[1-9][0-9]{2}\s?[0-9]{3}\b") # Indian 6-digit pin codes

def extract_mrp(text: str) -> Tuple[Optional[str], float]:
    """
    Extracts the MRP string and float value.
    """
    # Matches patterns like MRP ₹30.00, M.R.P. Rs. 420, Rs 50, Maximum Retail Price Rs. 150
    mrp_match = re.search(r"(?i)(?:m\.?r\.?p\.?|max\.?(?:imum)?\s*retail\s*price)\s*(?:rs\.?|₹)?\s*(\d+(?:\.\d{2})?)", text)
    if mrp_match:
        val_str = mrp_match.group(1)
        return f"Rs. {val_str}", 0.95
        
    # Alternate search for bare price if prefaced by Rs or ₹
    price_match = re.search(r"(?i)\b(?:rs\.?|₹)\s*(\d+(?:\.\d{2})?)\b", text)
    if price_match:
        val_str = price_match.group(1)
        return f"Rs. {val_str}", 0.80
        
    return None, 0.0

def extract_net_quantity(text: str) -> Tuple[Optional[str], float]:
    """
    Extracts net quantity (e.g. 1 kg, 150 g, 200 ml, 1 L).
    """
    # Matches: Net Qty: 150g, Net Vol: 200 ml, Quantity: 1 kg, Net Volume 100 ml, or bare digits before units
    qty_match = re.search(
        r"(?i)(?:net\s*(?:qty|quantity|vol|volume|weight)?|quantity|qty|volume)\s*(?:is)?\s*:?\s*(\d+(?:\.\d+)?)\s*(g|grm|gram|grams|kg|kg\.|kilogram|kilograms|ml|ml\.|milliliter|milliliters|l|l\.|liter|liters|litre|litres|m|meter|meters|pcs|units|u)\b", 
        text
    )
    if qty_match:
        val = qty_match.group(1)
        unit = qty_match.group(2)
        return f"{val} {unit}", 0.95
        
    # Heuristic: search for any numeric value followed by metric units directly in text
    bare_qty = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:g|grm|gram|grams|kg|ml|l|litre|litres|pcs|units)\b", text, re.IGNORECASE)
    if bare_qty:
        return f"{bare_qty.group(1)} {bare_qty.group(2)}", 0.75
        
    return None, 0.0

def extract_mfg_date(text: str) -> Tuple[Optional[str], float]:
    """
    Extracts manufacturing/packing/import date (MM/YYYY or Month YYYY).
    """
    # Matches PKD: 08/2026, MFD: Aug 2026, MFG DATE: 08-2026
    date_match = re.search(
        r"(?i)(?:pkg|pkd|mfd|mfg|packed|manufactured|mfg\s*date|import\s*date)\s*:?\s*([A-Za-z]{3}\s+\d{4}|\d{2}[/\-\.]\d{4}|\d{2}[/\-\.]\d{2})\b",
        text
    )
    if date_match:
        return date_match.group(1), 0.95
        
    # Heuristic: match any standalone date format MM/YYYY or MM/YY
    bare_date = re.search(r"\b(0[1-9]|1[0-2])[/\-\.](20\d{2}|\d{2})\b", text)
    if bare_date:
        return bare_date.group(0), 0.75
        
    # Match Month YYYY (e.g. August 2026, Aug 2026)
    month_year = re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(20\d{2})\b", text, re.IGNORECASE)
    if month_year:
        return month_year.group(0), 0.85
        
    return None, 0.0

def extract_country_of_origin(text: str) -> Tuple[str, float]:
    """
    Extracts Country of Origin.
    """
    match = re.search(r"(?i)(?:country\s*of\s*origin|made\s*in|product\s*of)\s*:?\s*([A-Za-z\s]+)\b", text)
    if match:
        country = match.group(1).strip()
        # Clean up trailing spaces or punctuation
        country = re.split(r"[\n,;\.]", country)[0].strip()
        return country, 0.95
        
    # Heuristic check
    if "made in india" in text.lower() or "product of india" in text.lower():
        return "India", 0.90
        
    return "India", 0.50 # Default assumption for Indian legal Metrology if not found

def parse_entities_with_nlp(text_lines: List[str]) -> Dict[str, Any]:
    """
    Runs NER on text lines to separate organizations, locations, and contact info.
    Falls back to regex-based heuristics if spaCy model is unavailable.
    """
    nlp = get_spacy_nlp()
    
    extracted = {
        "manufacturer_name": None,
        "manufacturer_address": None,
        "importer_name": None,
        "importer_address": None,
        "consumer_care_name": None,
        "consumer_care_address": None
    }
    
    joined_text = "\n".join(text_lines)
    
    # 1. Fallback heuristic parsing
    if nlp == "FAILED" or nlp is None:
        # Loop over lines to identify manufacture and import lines
        mfd_by_lines = []
        imp_by_lines = []
        care_lines = []
        
        for line in text_lines:
            line_l = line.lower()
            if "mfd by" in line_l or "manufactured by" in line_l or "mfd. by" in line_l or "packed by" in line_l:
                mfd_by_lines.append(line)
            elif "imported by" in line_l or "importer" in line_l or "distributed by" in line_l:
                imp_by_lines.append(line)
            elif "consumer" in line_l or "care" in line_l or "complaint" in line_l or "helpline" in line_l:
                care_lines.append(line)
                
        # Simple extraction based on line splitting
        if mfd_by_lines:
            line = mfd_by_lines[0]
            parts = re.split(r"(?i)mfd\s*by:?|manufactured\s*by:?", line)
            if len(parts) > 1 and parts[1].strip():
                extracted["manufacturer_name"] = parts[1].split(",")[0].strip()
                
            # Address search: combine subsequent lines containing pincodes or address markers
            addr_parts = []
            for l in text_lines:
                if any(k in l.lower() for k in ["road", "street", "marg", "nagar", "industrial", "floor", "building", "plot", "kolkata", "mumbai", "bangalore", "delhi", "chennai", "pincode"]):
                    if not any(k in l.lower() for k in ["mrp", "net qty", "pkd", "Helpline"]):
                        addr_parts.append(l)
            if addr_parts:
                extracted["manufacturer_address"] = ", ".join(addr_parts[:2])
                
        if imp_by_lines:
            line = imp_by_lines[0]
            parts = re.split(r"(?i)imported\s*by:?|importer:?", line)
            if len(parts) > 1 and parts[1].strip():
                extracted["importer_name"] = parts[1].split(",")[0].strip()
                
        return extracted
        
    # 2. Real spaCy NLP Execution
    try:
        # Run spaCy NER
        doc = nlp(joined_text)
        orgs = [ent.text for ent in doc.ents if ent.label_ == "ORG"]
        locs = [ent.text for ent in doc.ents if ent.label_ in ["GPE", "LOC", "FAC"]]
        
        # Look for "Mfd by" line to extract name
        mfd_by_index = -1
        for idx, line in enumerate(text_lines):
            if any(k in line.lower() for k in ["mfd by", "manufactured by", "packed by"]):
                mfd_by_index = idx
                break
                
        if mfd_by_index != -1:
            mfd_line = text_lines[mfd_by_index]
            # Match ORG names appearing near or in this line
            mfd_doc = nlp(mfd_line)
            mfd_orgs = [ent.text for ent in mfd_doc.ents if ent.label_ == "ORG"]
            if mfd_orgs:
                extracted["manufacturer_name"] = mfd_orgs[0]
            else:
                # Clean up "Mfd by: " text
                clean = re.sub(r"(?i)mfd\s*by:?|manufactured\s*by:?|packed\s*by:?", "", mfd_line).strip()
                extracted["manufacturer_name"] = clean.split(",")[0].strip()
                
            # Collect following 1-2 lines for address, or search for pincode in following lines
            addr_lines = []
            for i in range(mfd_by_index, min(mfd_by_index + 3, len(text_lines))):
                line = text_lines[i]
                if not any(k in line.lower() for k in ["mrp", "quantity", "pkd", "consumer"]):
                    addr_lines.append(line)
            if addr_lines:
                extracted["manufacturer_address"] = " ".join(addr_lines).replace("Mfd by:", "").strip()
                
        # Look for Importer details
        imp_index = -1
        for idx, line in enumerate(text_lines):
            if any(k in line.lower() for k in ["imported by", "importer", "distributed by"]):
                imp_index = idx
                break
                
        if imp_index != -1:
            imp_line = text_lines[imp_index]
            imp_doc = nlp(imp_line)
            imp_orgs = [ent.text for ent in imp_doc.ents if ent.label_ == "ORG"]
            if imp_orgs:
                extracted["importer_name"] = imp_orgs[0]
            else:
                clean = re.sub(r"(?i)imported\s*by:?|importer:?|distributed\s*by:?", "", imp_line).strip()
                extracted["importer_name"] = clean.split(",")[0].strip()
                
            addr_lines = []
            for i in range(imp_index, min(imp_index + 3, len(text_lines))):
                line = text_lines[i]
                if not any(k in line.lower() for k in ["mrp", "quantity", "pkd", "consumer"]):
                    addr_lines.append(line)
            if addr_lines:
                extracted["importer_address"] = " ".join(addr_lines).replace("Imported by:", "").strip()
                
    except Exception as e:
        print(f"spaCy parsing runtime exception: {e}")
        
    return extracted

def extract_fields_from_ocr(ocr_regions: List[Dict[str, Any]], raw_text: str) -> Dict[str, Any]:
    """
    Stage 5: Structuring raw text into named fields.
    Takes OCR bounding boxes and raw text, parses using rules + NLP,
    and returns a structured JSON object of fields with confidence scores.
    """
    text_lines = [r["text"] for r in ocr_regions]
    
    # Base extracted structure
    fields = {
        "mrp": None,
        "mrp_confidence": 0.0,
        
        "net_quantity": None,
        "net_quantity_confidence": 0.0,
        
        "mfg_date": None,
        "mfg_date_confidence": 0.0,
        
        "country_of_origin": "India",
        "country_of_origin_confidence": 0.50,
        
        "manufacturer_name": None,
        "manufacturer_address": None,
        
        "consumer_care_name": None,
        "consumer_care_phone": None,
        "consumer_care_email": None,
        "consumer_care_address": None,
        
        "is_imported": False,
        "importer_name": None,
        "importer_address": None
    }
    
    # 1. Parse structured fields via Regex
    fields["mrp"], fields["mrp_confidence"] = extract_mrp(raw_text)
    fields["net_quantity"], fields["net_quantity_confidence"] = extract_net_quantity(raw_text)
    fields["mfg_date"], fields["mfg_date_confidence"] = extract_mfg_date(raw_text)
    fields["country_of_origin"], fields["country_of_origin_confidence"] = extract_country_of_origin(raw_text)
    
    # Identify if product is imported
    if any(k in raw_text.lower() for k in ["imported", "importer", "import date", "luxury imports"]):
        fields["is_imported"] = True
        
    # 2. Extract manufacturer, importer, and consumer care details
    entities = parse_entities_with_nlp(text_lines)
    fields["manufacturer_name"] = entities.get("manufacturer_name")
    fields["manufacturer_address"] = entities.get("manufacturer_address")
    fields["importer_name"] = entities.get("importer_name")
    fields["importer_address"] = entities.get("importer_address")
    
    # 3. Consumer Care extraction (specific regexes for phone and email)
    emails = EMAIL_REGEX.findall(raw_text)
    if emails:
        fields["consumer_care_email"] = emails[0]
    phones = PHONE_REGEX.findall(raw_text)
    if phones:
        fields["consumer_care_phone"] = phones[0]
        
    # Find consumer care physical contact block
    for idx, line in enumerate(text_lines):
        if any(k in line.lower() for k in ["consumer care", "customer care", "complaints", "helpline", "feedback"]):
            # Extract following lines for consumer care address
            care_parts = []
            for i in range(idx, min(idx + 3, len(text_lines))):
                l = text_lines[i]
                if not any(k in l.lower() for k in ["mrp", "quantity", "pkd"]):
                    care_parts.append(l)
            if care_parts:
                fields["consumer_care_address"] = " ".join(care_parts).strip()
            break
            
    # Set default values for consumer care name if not found
    if fields["consumer_care_email"] or fields["consumer_care_phone"]:
        fields["consumer_care_name"] = fields["manufacturer_name"] or "Consumer Cell"
        if not fields["consumer_care_address"]:
            fields["consumer_care_address"] = fields["manufacturer_address"]
            
    return fields
