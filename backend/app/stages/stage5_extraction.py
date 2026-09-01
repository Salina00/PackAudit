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
            print(f"Failed to load spaCy model: {e}. Falling back to heuristic NER.")
            _nlp = "FAILED"
    return _nlp

# Pre-compiled regex patterns for structured fields
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
PHONE_REGEX = re.compile(r"\b(?:\+91[\-\s]?)?\(?[0-9]{3,5}\)?[\-\s]?[0-9]{3,4}[\-\s]?[0-9]{3,4}\b|\b1800[\-\s]?[0-9]{3,4}[\-\s]?[0-9]{3,4}\b|\b[6-9]\d{9}\b")
PINCODE_REGEX = re.compile(r"\b[1-9][0-9]{2}\s?[0-9]{3}\b")
FSSAI_REGEX = re.compile(r"(?i)(?:fssai|lic\.?\s*(?:no\.?|number)?|licence|license)\s*[:\-\s]*([0-9]{14})\b|\b(1[0-9]{13}|2[0-9]{13})\b")

def extract_mrp(text: str) -> Tuple[Optional[str], float]:
    """
    Extracts the MRP string and float value.
    """
    mrp_match = re.search(r"(?i)(?:m\.?r\.?p\.?|max\.?(?:imum)?\s*retail\s*price)\s*(?:rs\.?|₹|\?|r\$)?\s*(\d+(?:\.\d{2})?)", text)
    if mrp_match:
        val_str = mrp_match.group(1)
        return f"Rs. {val_str}", 0.95
        
    price_match = re.search(r"(?i)\b(?:rs\.?|₹)\s*(\d+(?:\.\d{2})?)\b", text)
    if price_match:
        val_str = price_match.group(1)
        return f"Rs. {val_str}", 0.80
        
    return None, 0.0

def extract_net_quantity(text: str) -> Tuple[Optional[str], float]:
    """
    Extracts net quantity (e.g. 1 kg, 150 g, 69 g, 200 ml, 1 L, 1 N, 1 Pair, 1 Piece).
    """
    qty_match = re.search(
        r"(?i)(?:net\s*(?:qty|quantity|vol|volume|weight)?|quantity|qty|volume|net\s*wt\.?)\s*(?:is)?\s*:?\s*(\d+(?:\.\d+)?)\s*(g|grm|gram|grams|kg|kg\.|kilogram|kilograms|ml|ml\.|milliliter|milliliters|l|l\.|liter|liters|litre|litres|m|meter|meters|pcs|units|u|n|pair|pairs|piece|pieces)\b", 
        text
    )
    if qty_match:
        val = qty_match.group(1)
        unit = qty_match.group(2)
        return f"{val} {unit}", 0.95
        
    bare_qty = re.search(r"\b(\d+(?:\.\d+)?)\s*(g|grm|gram|grams|kg|ml|l|litre|litres|pcs|units|n|pair|pairs)\b", text, re.IGNORECASE)
    if bare_qty:
        groups = bare_qty.groups()
        if len(groups) >= 2:
            return f"{groups[0]} {groups[1]}", 0.75
        elif len(groups) == 1:
            return f"{groups[0]}", 0.65
        
    return None, 0.0

def extract_mfg_date(text: str) -> Tuple[Optional[str], float]:
    """
    Extracts manufacturing/packing/import date (DD/MM/YYYY, MM/YYYY, or Month YYYY).
    """
    date_match = re.search(
        r"(?i)(?:pkg|pkd|mfd|mfg|packed|manufactured|mfg\s*date|import\s*date)\s*:?\s*([A-Za-z]{3}\s+\d{4}|\d{1,2}[/\-\.]\d{2}[/\-\.]\d{2,4}|\d{2}[/\-\.]\d{4}|\d{2}[/\-\.]\d{2})\b",
        text
    )
    if date_match:
        return date_match.group(1), 0.95
        
    bare_date = re.search(r"\b(0[1-9]|1[0-2])[/\-\.](20\d{2}|\d{2})\b", text)
    if bare_date:
        return bare_date.group(0), 0.75
        
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
        country = re.split(r"[\n,;\.]", country)[0].strip()
        return country, 0.95
        
    if "made in india" in text.lower() or "product of india" in text.lower():
        return "India", 0.90
        
    return "India", 0.50

def extract_fssai_number(text: str) -> Tuple[Optional[str], float]:
    """
    Extracts 14-digit FSSAI License Number.
    """
    match = FSSAI_REGEX.search(text)
    if match:
        val = match.group(1) or match.group(2)
        if val and len(val) == 14:
            return val, 0.98
    return None, 0.0

def extract_ingredients_and_allergens(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extracts raw ingredient string and allergen advisory statement.
    """
    ing_match = re.search(r"(?i)ingredients?\s*[:\-\s]+([^.\n]+(?:\n[^.\n]+)*)", text)
    ingredients_text = ing_match.group(1).strip() if ing_match else None
    
    allergen_match = re.search(r"(?i)(?:contains|allergen\s*(?:info|information|advice|warning)?)\s*[:\-\s]+([^.\n]+)", text)
    allergen_text = allergen_match.group(1).strip() if allergen_match else None
    
    return ingredients_text, allergen_text

def extract_nutrition_facts(text: str) -> Dict[str, Any]:
    """
    Parses nutrition table lines into structured numeric values.
    """
    nutrition: Dict[str, Any] = {}
    
    def _find_val(pattern: str) -> Optional[float]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except (ValueError, IndexError):
                return None
        return None

    nutrition["energy"] = _find_val(r"(?:energy|calories)\s*[:\-\s]*([0-9]+(?:\.[0-9]+)?)\s*(?:kcal|cal|kj)?")
    nutrition["protein"] = _find_val(r"protein\s*[:\-\s]*([0-9]+(?:\.[0-9]+)?)\s*g?")
    nutrition["carbohydrates"] = _find_val(r"(?:carbohydrate|carbohydrates|total\s*carbs?)\s*[:\-\s]*([0-9]+(?:\.[0-9]+)?)\s*g?")
    nutrition["total_sugars"] = _find_val(r"(?:total\s*sugars?|sugars?)\s*[:\-\s]*([0-9]+(?:\.[0-9]+)?)\s*g?")
    nutrition["added_sugars"] = _find_val(r"added\s*sugars?\s*[:\-\s]*([0-9]+(?:\.[0-9]+)?)\s*g?")
    nutrition["total_fat"] = _find_val(r"(?:total\s*fat|fat)\s*[:\-\s]*([0-9]+(?:\.[0-9]+)?)\s*g?")
    nutrition["saturated_fat"] = _find_val(r"(?:saturated\s*fat|sat\s*fat)\s*[:\-\s]*([0-9]+(?:\.[0-9]+)?)\s*g?")
    nutrition["trans_fat"] = _find_val(r"trans\s*fat\s*[:\-\s]*([0-9]+(?:\.[0-9]+)?)\s*g?")
    nutrition["sodium"] = _find_val(r"sodium\s*[:\-\s]*([0-9]+(?:\.[0-9]+)?)\s*mg?")
    
    return {k: v for k, v in nutrition.items() if v is not None}

def extract_dates_breakdown(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extracts explicit Expiry Date vs Best Before date strings.
    """
    expiry_match = re.search(r"(?i)(?:expiry|exp\.?|use\s*by|use\s*before)\s*[:\-\s]*([0-9]{1,2}[/\-\.][0-9]{1,2}[/\-\.][0-9]{2,4}|[0-9]{1,2}[/\-\.][0-9]{2,4}|[A-Za-z]{3,9}\s+[0-9]{2,4})", text)
    expiry_date = expiry_match.group(1).strip() if expiry_match else None
    
    best_before_match = re.search(r"(?i)best\s*before\s*[:\-\s]*([0-9]{1,2}\s*(?:months?|days?|years?)|[0-9]{1,2}[/\-\.][0-9]{2,4}|[A-Za-z]{3,9}\s+[0-9]{2,4})", text)
    best_before_date = best_before_match.group(1).strip() if best_before_match else None
    
    return expiry_date, best_before_date

def extract_fiber_and_size(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extracts fiber composition string and garment size declaration.
    """
    fiber_match = re.search(r"(?i)(?:composition|fabric|material|content)?\s*[:\-\s]*((?:\d{1,3}%\s*[a-zA-Z\s\-]+(?:,\s*)?)+)", text)
    fiber_str = fiber_match.group(1).strip() if fiber_match else None
    
    size_match = re.search(r"(?i)\b(?:size|fit)\s*[:\-\s]*([A-Za-z0-9\+]+(?:\s*\([^\)]+\))?)", text)
    size_str = size_match.group(1).strip() if size_match else None
    
    return fiber_str, size_str

def parse_entities_with_nlp(text_lines: List[str]) -> Dict[str, Any]:
    """
    Runs NER on text lines to separate organizations, locations, and contact info.
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
    
    # Check for keywords first
    for line in text_lines:
        line_l = line.lower()
        if any(k in line_l for k in ["marketed by", "mfd by", "manufactured by", "mfd. by", "packed by", "itc limited"]):
            parts = line.split(":") if ":" in line else line.split("by")
            cand = parts[-1].strip()
            if len(cand) > 2:
                extracted["manufacturer_name"] = cand
                break
                
    if nlp == "FAILED" or nlp is None:
        mfd_by_lines = []
        imp_by_lines = []
        care_lines = []
        
        for line in text_lines:
            line_l = line.lower()
            if "mfd by" in line_l or "manufactured by" in line_l or "mfd. by" in line_l or "packed by" in line_l or "marketed by" in line_l:
                mfd_by_lines.append(line)
            elif "imported by" in line_l or "importer" in line_l or "distributed by" in line_l:
                imp_by_lines.append(line)
            elif "consumer" in line_l or "care" in line_l or "complaint" in line_l or "helpline" in line_l:
                care_lines.append(line)
                
        if mfd_by_lines and not extracted["manufacturer_name"]:
            parts = mfd_by_lines[0].split(":") if ":" in mfd_by_lines[0] else mfd_by_lines[0].split("by")
            extracted["manufacturer_name"] = parts[-1].strip()
            extracted["manufacturer_address"] = " ".join(mfd_by_lines).strip()
            
        if imp_by_lines:
            parts = imp_by_lines[0].split(":") if ":" in imp_by_lines[0] else imp_by_lines[0].split("by")
            extracted["importer_name"] = parts[-1].strip()
            extracted["importer_address"] = " ".join(imp_by_lines).strip()
            
        if care_lines:
            extracted["consumer_care_address"] = " ".join(care_lines).strip()
            
        return extracted
        
    doc = nlp(joined_text)
    orgs = [ent.text.strip() for ent in doc.ents if ent.label_ == "ORG"]
    locs = [ent.text.strip() for ent in doc.ents if ent.label_ in ["GPE", "LOC", "FAC"]]
    
    if orgs and not extracted["manufacturer_name"]:
        extracted["manufacturer_name"] = orgs[0]
        if len(orgs) > 1 and ("imported" in joined_text.lower() or "importer" in joined_text.lower()):
            extracted["importer_name"] = orgs[1]
            
    if locs:
        pincodes = PINCODE_REGEX.findall(joined_text)
        addr_parts = locs[:3]
        if pincodes:
            addr_parts.append(pincodes[0])
        extracted["manufacturer_address"] = ", ".join(addr_parts)
        
    return extracted

def extract_fields_from_ocr(ocr_regions: List[Dict[str, Any]], raw_text: str) -> Dict[str, Any]:
    """
    Stage 5: High-level extraction pipeline combining Legal Metrology, FSSAI Food, and Apparel Declarations.
    """
    text_lines = [r.get("text", "").strip() for r in ocr_regions if r.get("text", "").strip()]
    
    # Generic Name detection
    generic_name = None
    if text_lines:
        for line in text_lines[:6]:
            if len(line) > 3 and not any(k in line.lower() for k in ["mrp", "net wt", "net weight", "net qty", "fssai", "batch", "pkd", "mfd", "rs.", "₹", "size", "store in", "feedback"]):
                generic_name = line
                break
        if not generic_name:
            generic_name = text_lines[0]
            
    fields: Dict[str, Any] = {
        "generic_name": generic_name,
        "mrp": None,
        "mrp_confidence": 0.0,
        "net_quantity": None,
        "net_quantity_confidence": 0.0,
        "mfg_date": None,
        "mfg_date_confidence": 0.0,
        "country_of_origin": "India",
        "country_of_origin_confidence": 0.90,
        "manufacturer_name": None,
        "manufacturer_address": None,
        "importer_name": None,
        "importer_address": None,
        "consumer_care_email": None,
        "consumer_care_phone": None,
        "consumer_care_address": None,
        "fssai_license_no": None,
        "ingredients": None,
        "allergen_info": None,
        "nutrition_facts": {},
        "expiry_date": None,
        "best_before_date": None,
        "fiber_composition": None,
        "apparel_size": None,
        "batch_no": None
    }
    
    # Extract Batch Number
    batch_match = re.search(r"(?i)(?:batch\s*(?:no\.?|number)?|lot\s*(?:no\.?|number)?)\s*[:\-\s]*([A-Za-z0-9\-\./]+)", raw_text)
    if batch_match:
        fields["batch_no"] = batch_match.group(1).strip()
        
    # 1. Regex Extractions
    fields["mrp"], fields["mrp_confidence"] = extract_mrp(raw_text)
    fields["net_quantity"], fields["net_quantity_confidence"] = extract_net_quantity(raw_text)
    fields["mfg_date"], fields["mfg_date_confidence"] = extract_mfg_date(raw_text)
    fields["country_of_origin"], fields["country_of_origin_confidence"] = extract_country_of_origin(raw_text)
    fields["fssai_license_no"], _ = extract_fssai_number(raw_text)
    fields["ingredients"], fields["allergen_info"] = extract_ingredients_and_allergens(raw_text)
    fields["nutrition_facts"] = extract_nutrition_facts(raw_text)
    fields["expiry_date"], fields["best_before_date"] = extract_dates_breakdown(raw_text)
    fields["fiber_composition"], fields["apparel_size"] = extract_fiber_and_size(raw_text)
    
    # 2. Contact details extraction
    emails = EMAIL_REGEX.findall(raw_text)
    if emails:
        fields["consumer_care_email"] = emails[0]
        
    phones = PHONE_REGEX.findall(raw_text)
    if phones:
        fields["consumer_care_phone"] = phones[0]
        
    # 3. NLP Extraction for entities
    nlp_results = parse_entities_with_nlp(text_lines)
    fields["manufacturer_name"] = nlp_results.get("manufacturer_name")
    fields["manufacturer_address"] = nlp_results.get("manufacturer_address")
    fields["importer_name"] = nlp_results.get("importer_name")
    fields["importer_address"] = nlp_results.get("importer_address")
    fields["consumer_care_address"] = nlp_results.get("consumer_care_address")
    
    return fields
