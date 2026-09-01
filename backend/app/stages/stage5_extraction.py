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
PHONE_REGEX = re.compile(r"\b(?:\+91[\-\s]?)?\(?[0-9]{3,5}\)?[\-\s]?[0-9]{3,4}[\-\s]?[0-9]{3,4}\b|\b1800[\-\s]?[0-9]{3,4}[\-\s]?[0-9]{3,4}\b")
PINCODE_REGEX = re.compile(r"\b[1-9][0-9]{2}\s?[0-9]{3}\b") # Indian 6-digit pin codes
FSSAI_REGEX = re.compile(r"(?i)(?:fssai|lic\.?\s*(?:no\.?|number)?|licence|license)\s*[:\-\s]*([0-9]{14})\b|\b(1[0-9]{13}|2[0-9]{13})\b")

def extract_mrp(text: str) -> Tuple[Optional[str], float]:
    """
    Extracts the MRP string and float value.
    """
    mrp_match = re.search(r"(?i)(?:m\.?r\.?p\.?|max\.?(?:imum)?\s*retail\s*price)\s*(?:rs\.?|₹)?\s*(\d+(?:\.\d{2})?)", text)
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
    Extracts net quantity (e.g. 1 kg, 150 g, 200 ml, 1 L).
    """
    qty_match = re.search(
        r"(?i)(?:net\s*(?:qty|quantity|vol|volume|weight)?|quantity|qty|volume)\s*(?:is)?\s*:?\s*(\d+(?:\.\d+)?)\s*(g|grm|gram|grams|kg|kg\.|kilogram|kilograms|ml|ml\.|milliliter|milliliters|l|l\.|liter|liters|litre|litres|m|meter|meters|pcs|units|u)\b", 
        text
    )
    if qty_match:
        val = qty_match.group(1)
        unit = qty_match.group(2)
        return f"{val} {unit}", 0.95
        
    bare_qty = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:g|grm|gram|grams|kg|ml|l|litre|litres|pcs|units)\b", text, re.IGNORECASE)
    if bare_qty:
        return f"{bare_qty.group(1)} {bare_qty.group(2)}", 0.75
        
    return None, 0.0

def extract_mfg_date(text: str) -> Tuple[Optional[str], float]:
    """
    Extracts manufacturing/packing/import date (MM/YYYY or Month YYYY).
    """
    date_match = re.search(
        r"(?i)(?:pkg|pkd|mfd|mfg|packed|manufactured|mfg\s*date|import\s*date)\s*:?\s*([A-Za-z]{3}\s+\d{4}|\d{2}[/\-\.]\d{4}|\d{2}[/\-\.]\d{2})\b",
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
            except ValueError:
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
    expiry_match = re.search(r"(?i)(?:expiry|exp\.?|use\s*by|use\s*before)\s*[:\-\s]*([0-9]{1,2}[/\-\.][0-9]{2,4}|[A-Za-z]{3,9}\s+[0-9]{2,4})", text)
    expiry_date = expiry_match.group(1).strip() if expiry_match else None
    
    best_before_match = re.search(r"(?i)best\s*before\s*[:\-\s]*([0-9]{1,2}\s*(?:months?|days?|years?)|[0-9]{1,2}[/\-\.][0-9]{2,4}|[A-Za-z]{3,9}\s+[0-9]{2,4})", text)
    best_before_date = best_before_match.group(1).strip() if best_before_match else None
    
    return expiry_date, best_before_date

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
    
    if nlp == "FAILED" or nlp is None:
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
                
        if mfd_by_lines:
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
    
    if orgs:
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
    Stage 5: High-level extraction pipeline combining Legal Metrology and FSSAI Food Declarations.
    """
    text_lines = [r.get("text", "").strip() for r in ocr_regions if r.get("text", "").strip()]
    
    # Generic Name detection
    generic_name = None
    if text_lines:
        for line in text_lines[:4]:
            if len(line) > 3 and not any(k in line.lower() for k in ["mrp", "net qty", "fssai", "batch", "pkd", "mfd", "rs.", "₹"]):
                generic_name = line
                break
        if not generic_name:
            generic_name = text_lines[0]
            
    fields = {
        "generic_name": generic_name,
        "generic_name_confidence": 0.90 if generic_name else 0.0,
        
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
        "importer_address": None,
        
        # FSSAI Food & Beverage Declarations
        "fssai_license_no": None,
        "fssai_confidence": 0.0,
        "nutrition_table": {},
        "ingredients_text": None,
        "allergen_statement": None,
        "veg_nonveg": "veg",
        "expiry_date": None,
        "best_before_date": None
    }
    
    # 1. Parse structured fields via Regex
    fields["mrp"], fields["mrp_confidence"] = extract_mrp(raw_text)
    fields["net_quantity"], fields["net_quantity_confidence"] = extract_net_quantity(raw_text)
    fields["mfg_date"], fields["mfg_date_confidence"] = extract_mfg_date(raw_text)
    fields["country_of_origin"], fields["country_of_origin_confidence"] = extract_country_of_origin(raw_text)
    fields["fssai_license_no"], fields["fssai_confidence"] = extract_fssai_number(raw_text)
    
    # Extract FSSAI Food & Beverage fields
    fields["ingredients_text"], fields["allergen_statement"] = extract_ingredients_and_allergens(raw_text)
    fields["nutrition_table"] = extract_nutrition_facts(raw_text)
    fields["expiry_date"], fields["best_before_date"] = extract_dates_breakdown(raw_text)
    
    # Veg / Non-Veg detection from text keywords
    raw_lower = raw_text.lower()
    if any(k in raw_lower for k in ["non-veg", "non veg", "chicken", "meat", "egg", "fish", "mutton", "prawn", "pork", "beef"]):
        fields["veg_nonveg"] = "non_veg"
    else:
        fields["veg_nonveg"] = "veg"
    
    if any(k in raw_lower for k in ["imported", "importer", "import date", "luxury imports"]):
        fields["is_imported"] = True
        
    # 2. Extract manufacturer, importer, and consumer care details
    entities = parse_entities_with_nlp(text_lines)
    fields["manufacturer_name"] = entities.get("manufacturer_name")
    fields["manufacturer_address"] = entities.get("manufacturer_address")
    fields["importer_name"] = entities.get("importer_name")
    fields["importer_address"] = entities.get("importer_address")
    
    # 3. Consumer Care extraction
    emails = EMAIL_REGEX.findall(raw_text)
    if emails:
        fields["consumer_care_email"] = emails[0]
    phones = PHONE_REGEX.findall(raw_text)
    if phones:
        fields["consumer_care_phone"] = phones[0]
        
    for idx, line in enumerate(text_lines):
        if any(k in line.lower() for k in ["consumer care", "customer care", "complaints", "helpline", "feedback"]):
            care_parts = []
            for i in range(idx, min(idx + 3, len(text_lines))):
                l = text_lines[i]
                if not any(k in l.lower() for k in ["mrp", "quantity", "pkd"]):
                    care_parts.append(l)
            if care_parts:
                fields["consumer_care_address"] = " ".join(care_parts).strip()
            break
            
    if fields["consumer_care_email"] or fields["consumer_care_phone"]:
        fields["consumer_care_name"] = fields["manufacturer_name"] or "Consumer Cell"
        if not fields["consumer_care_address"]:
            fields["consumer_care_address"] = fields["manufacturer_address"]
            
    return fields
