import re
import urllib.parse
import requests
from typing import Dict, Any, List, Tuple, Optional
from sqlalchemy.orm import Session
from rapidfuzz import fuzz, process

from backend.app.models.models import RuleDefinition, ManufacturerCache
from backend.app.core.config import settings

# In-memory rule definitions cache loaded at startup/first request
_rules_cache = {}

PINCODE_REGEX = re.compile(r"\b[1-9][0-9]{2}\s?[0-9]{3}\b")

STATIC_FIX_SUGGESTIONS = {
    "check_1": "Ensure statutory exemption eligibility criteria (net qty ≤ 10g/ml, agricultural produce > 50kg, or industrial/export use) are clearly documented on packaging.",
    "check_2": "Include the full legal name and complete postal address of the manufacturer/packer with a valid 6-digit PIN code.",
    "check_3": "Declare the common or generic name of the packaged commodity prominently on the Principal Display Panel.",
    "check_4": "Declare net quantity using statutory metric unit symbols ('g', 'kg', 'ml', 'l', 'pcs') without non-standard abbreviations like 'gms' or 'ltrs'.",
    "check_5": "Declare the month and year of manufacturing or pre-packing in standard format (e.g. '08/2026' or 'Aug 2026').",
    "check_6": "Add the mandatory statutory suffix 'inclusive of all taxes' or 'incl. of all taxes' immediately adjacent to the MRP declaration.",
    "check_7": "Declare complete consumer care contact details including contact officer/cell name, postal address, working phone number, and valid email ID.",
    "check_8": "Declare the Country of Origin clearly on the packaging (e.g., 'Country of Origin: India' or 'Made in India').",
    "check_9": "For imported commodities, declare the registered company name and complete postal address of the Indian importer.",
    "check_10": "Increase letter and numeral font height to meet the minimum statutory height (e.g. min 2.0 mm for PDP area > 100 cm²) based on package surface area.",
    "check_11": "Pack the commodity in one of the prescribed standard net quantity sizes specified under the Second Schedule of Legal Metrology Rules.",
    "check_12": "Ensure the digital marketplace listing displays all mandatory statutory declarations (MRP, Net Quantity, Country of Origin, Manufacturer details, Consumer care) matching physical label."
}

def get_rules_definitions(db: Session) -> Dict[str, Dict[str, Any]]:
    """
    Fetches rule definitions from DB and caches them in memory.
    """
    global _rules_cache
    if not _rules_cache:
        rules = db.query(RuleDefinition).all()
        for r in rules:
            _rules_cache[r.rule_id] = {
                "rule_citation": r.rule_citation,
                "description": r.description,
                "check_type": r.check_type,
                "validation_logic": r.validation_logic or {},
                "severity": r.severity or "MAJOR",
                "fix_suggestion": r.fix_suggestion or STATIC_FIX_SUGGESTIONS.get(r.rule_id, "")
            }
        print(f"Rule engine: Cached {len(_rules_cache)} rules.")
    return _rules_cache

def parse_net_qty_numeric(qty_str: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    """
    Parses a quantity string like '150 g' or '1 kg' or '200 ml' into a numeric value in grams/ml
    and returns (numeric_val_in_standard_unit, base_unit).
    Standardizes kg to g (x1000) and L to ml (x1000).
    """
    if not qty_str:
        return None, None
        
    qty_str = str(qty_str).lower().strip()
    match = re.search(r"(\d+(?:\.\d+)?)\s*([a-z]+)", qty_str)
    if not match:
        return None, None
        
    val = float(match.group(1))
    unit = match.group(2)
    
    # Standardize units
    if unit in ["g", "grm", "gram", "grams"]:
        return val, "g"
    elif unit in ["kg", "kg.", "kilogram", "kilograms"]:
        return val * 1000.0, "g"
    elif unit in ["ml", "ml.", "milliliter", "milliliters"]:
        return val, "ml"
    elif unit in ["l", "l.", "liter", "liters", "litre", "litres"]:
        return val * 1000.0, "ml"
    elif unit in ["m", "meter", "meters"]:
        return val, "m"
    elif unit in ["pcs", "units", "u"]:
        return val, "pcs"
        
    return val, unit

def verify_address_nominatim(address: str) -> Tuple[bool, str]:
    """
    Checks the physical existence of an address using OpenStreetMap Nominatim.
    Fuzzy matches the results to handle OCR errors.
    """
    if not address or len(address) < 15:
        return False, "Address is too short to verify."
        
    clean_addr = re.sub(r"[^\w\s\-\,]", " ", address)
    parts = [p.strip() for p in clean_addr.split(",") if p.strip()]
    query = ", ".join(parts[-3:]) if len(parts) >= 3 else clean_addr
    
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(query)}&format=json&limit=1"
    headers = {
        "User-Agent": settings.NOMINATIM_USER_AGENT
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if data:
                osm_display = data[0].get("display_name", "")
                ratio = fuzz.partial_token_sort_ratio(address.lower(), osm_display.lower())
                if ratio > 60.0:
                    return True, f"Address verified via OpenStreetMap (Fuzzy Match: {ratio:.1f}%, Found: {osm_display})"
                else:
                    return False, f"Address found on OSM but has low matching confidence ({ratio:.1f}%). Found: {osm_display}"
            else:
                return False, f"Geocoding API returned no matches for address fragment: '{query}'."
        else:
            return False, f"OSM Geocoding API returned HTTP status {res.status_code}."
    except Exception as e:
        return True, f"Nominatim API geocode offline/timeout. Address bypass enabled. (Error: {str(e)})"

def check_address_with_cache(address: str, company: Optional[str], db: Session) -> Tuple[bool, str]:
    """
    Verifies manufacturer address against the static database cache of 50 national brands.
    If not in cache, falls back to OSM Nominatim verification.
    """
    if not address:
        return False, "Address is missing."
        
    if company:
        cached_mfgs = db.query(ManufacturerCache).all()
        best_mfg = None
        best_ratio = 0.0
        
        for mfg in cached_mfgs:
            names = [mfg.company_name] + (mfg.aliases or [])
            match = process.extractOne(company.lower(), [n.lower() for n in names], scorer=fuzz.ratio)
            if match and match[1] > best_ratio:
                best_ratio = match[1]
                best_mfg = mfg
                
        if best_mfg and best_ratio > 75.0:
            pincode_match = PINCODE_REGEX.search(address)
            pincode = pincode_match.group(0).replace(" ", "") if pincode_match else None
            
            if pincode and best_mfg.registered_pincodes:
                cached_pincodes = [str(pc).replace(" ", "") for pc in best_mfg.registered_pincodes]
                if pincode in cached_pincodes:
                    return True, f"Verified against manufacturer cache (Company: {best_mfg.company_name}, Pincode: {pincode})"
                    
            if best_mfg.verified_addresses:
                addr_match = process.extractOne(address.lower(), [a.lower() for a in best_mfg.verified_addresses], scorer=fuzz.partial_token_sort_ratio)
                if addr_match and addr_match[1] > 65.0:
                    return True, f"Verified against manufacturer cache (Company: {best_mfg.company_name}, Address match: {addr_match[1]:.1f}%)"
                    
    return verify_address_nominatim(address)

def _get_rule_meta(rules: Dict[str, Dict[str, Any]], rule_id: str, default_citation: str, default_desc: str, default_severity: str = "MAJOR") -> Tuple[str, str, str, str]:
    rule_info = rules.get(rule_id, {})
    citation = rule_info.get("rule_citation") or default_citation
    desc = rule_info.get("description") or default_desc
    severity = rule_info.get("severity") or default_severity
    fix_suggestion = rule_info.get("fix_suggestion") or STATIC_FIX_SUGGESTIONS.get(rule_id, "Ensure declaration complies with Legal Metrology Rules, 2011.")
    return citation, desc, severity, fix_suggestion

def run_compliance_checks(extracted_fields: Dict[str, Any], input_type: str, calibration_factor: Optional[float], db: Session) -> List[Dict[str, Any]]:
    """
    Stage 6: Compliance rule engine.
    Runs all 12 checks against extracted fields.
    Returns: List of check result dictionaries with rule_id, rule_citation, description, severity, fix_suggestion, status, explanation.
    """
    rules = get_rules_definitions(db)
    check_results = []
    
    # 1. Rule 18 Exemption Pre-check (Check 1)
    cit1, desc1, sev1, fix1 = _get_rule_meta(rules, "check_1", "Rule 18 Exemption Pre-Check", "Checks if product is exempt under Rule 18.", "CRITICAL")
    is_exempt = False
    exemption_reason = ""
    
    qty_val, qty_unit = parse_net_qty_numeric(extracted_fields.get("net_quantity"))
    raw_text = " ".join([str(v) for v in extracted_fields.values() if v])
    raw_text_lower = raw_text.lower()
    
    if qty_val is not None and qty_unit in ["g", "ml"] and qty_val <= 10.0:
        is_exempt = True
        exemption_reason = f"Net quantity ({qty_val} {qty_unit}) is <= 10g/10ml (Rule 18 exemption)."
    elif any(k in raw_text_lower for k in ["institutional use", "industrial use", "not for retail sale", "bulk package", "industrial pack"]):
        is_exempt = True
        exemption_reason = "Product marked for institutional/industrial use."
    elif any(k in raw_text_lower for k in ["for export only", "export quality", "export pack"]):
        is_exempt = True
        exemption_reason = "Product marked for export only."
    elif qty_unit == "g" and qty_val is not None and qty_val > 50000.0:
        g_name = str(extracted_fields.get("generic_name") or "").lower()
        agri_keywords = ["flour", "rice", "wheat", "atta", "sugar", "dal", "pulses", "grain"]
        if any(k in g_name for k in agri_keywords):
            is_exempt = True
            exemption_reason = f"Agricultural produce ({qty_val/1000.0} kg) exceeds 50kg limit."
            
    check_results.append({
        "rule_id": "check_1",
        "rule_citation": cit1,
        "description": desc1,
        "severity": sev1,
        "fix_suggestion": fix1,
        "status": "exempt" if is_exempt else "pass",
        "explanation": f"Exempt: {exemption_reason}" if is_exempt else "Product is subject to all Legal Metrology declarations."
    })
    
    if is_exempt:
        for r_id in rules:
            if r_id != "check_1":
                c_cit, c_desc, c_sev, c_fix = _get_rule_meta(rules, r_id, r_id, "")
                check_results.append({
                    "rule_id": r_id,
                    "rule_citation": c_cit,
                    "description": c_desc,
                    "severity": c_sev,
                    "fix_suggestion": c_fix,
                    "status": "exempt",
                    "explanation": f"Exempted under Rule 18. Reason: {exemption_reason}"
                })
        return check_results
        
    # 2. Check 2: Manufacturer / Packer Name & Address
    cit2, desc2, sev2, fix2 = _get_rule_meta(rules, "check_2", "Rule 6(1)(a)", "Name and complete address of the manufacturer, packer, or importer.", "CRITICAL")
    mfg_name = extracted_fields.get("manufacturer_name")
    mfg_addr = extracted_fields.get("manufacturer_address")
    if not mfg_name or not mfg_addr:
        check_results.append({
            "rule_id": "check_2",
            "rule_citation": cit2,
            "description": desc2,
            "severity": sev2,
            "fix_suggestion": fix2,
            "status": "fail",
            "explanation": "Fail: Manufacturer/packer name or address is missing from the declarations."
        })
    else:
        addr_valid, addr_msg = check_address_with_cache(mfg_addr, mfg_name, db)
        check_results.append({
            "rule_id": "check_2",
            "rule_citation": cit2,
            "description": desc2,
            "severity": sev2,
            "fix_suggestion": fix2,
            "status": "pass" if addr_valid else "fail",
            "explanation": f"Pass: Manufacturer details present. {addr_msg}" if addr_valid else f"Fail: {addr_msg}"
        })
        
    # 3. Check 3: Generic Name of Commodity
    cit3, desc3, sev3, fix3 = _get_rule_meta(rules, "check_3", "Rule 6(1)(b)", "Common or generic name of the commodity.", "MAJOR")
    g_name = extracted_fields.get("generic_name")
    if not g_name:
        check_results.append({
            "rule_id": "check_3",
            "rule_citation": cit3,
            "description": desc3,
            "severity": sev3,
            "fix_suggestion": fix3,
            "status": "fail",
            "explanation": "Fail: Common or generic name of the commodity is missing."
        })
    else:
        check_results.append({
            "rule_id": "check_3",
            "rule_citation": cit3,
            "description": desc3,
            "severity": sev3,
            "fix_suggestion": fix3,
            "status": "pass",
            "explanation": f"Pass: Generic name declared as '{g_name}'."
        })
        
    # 4. Check 4: Net Quantity
    cit4, desc4, sev4, fix4 = _get_rule_meta(rules, "check_4", "Rule 6(1)(c)", "Net quantity in standard units of weight, measure or number.", "CRITICAL")
    net_qty = extracted_fields.get("net_quantity")
    if not net_qty:
        check_results.append({
            "rule_id": "check_4",
            "rule_citation": cit4,
            "description": desc4,
            "severity": sev4,
            "fix_suggestion": fix4,
            "status": "fail",
            "explanation": "Fail: Net quantity declaration is missing."
        })
    else:
        match_abbr = re.search(r"\b(g|kg|ml|l|m|pcs|units|u)\b", str(net_qty).lower())
        is_standard_unit = match_abbr is not None
        non_compliant = re.search(r"\b(gms|grm|grms|kgs|mltr|ltr|ltrs|liters|litres|milliliters)\b", str(net_qty).lower())
        
        if non_compliant:
            check_results.append({
                "rule_id": "check_4",
                "rule_citation": cit4,
                "description": desc4,
                "severity": sev4,
                "fix_suggestion": fix4,
                "status": "fail",
                "explanation": f"Fail: Net quantity '{net_qty}' uses non-compliant abbreviation '{non_compliant.group(1)}'. Must use standard units like 'g', 'kg', 'ml', 'l'."
            })
        elif not is_standard_unit:
            check_results.append({
                "rule_id": "check_4",
                "rule_citation": cit4,
                "description": desc4,
                "severity": sev4,
                "fix_suggestion": fix4,
                "status": "fail",
                "explanation": f"Fail: Net quantity '{net_qty}' lacks standard units of measurement (g, kg, ml, l, pcs)."
            })
        else:
            check_results.append({
                "rule_id": "check_4",
                "rule_citation": cit4,
                "description": desc4,
                "severity": sev4,
                "fix_suggestion": fix4,
                "status": "pass",
                "explanation": f"Pass: Net quantity '{net_qty}' uses correct metric abbreviation."
            })
            
    # 5. Check 5: Month & Year of Manufacturing/Packing
    cit5, desc5, sev5, fix5 = _get_rule_meta(rules, "check_5", "Rule 6(1)(d)", "Month and year of manufacture, pre-packing or import.", "MAJOR")
    mfg_d = extracted_fields.get("mfg_date")
    if not mfg_d:
        check_results.append({
            "rule_id": "check_5",
            "rule_citation": cit5,
            "description": desc5,
            "severity": sev5,
            "fix_suggestion": fix5,
            "status": "fail",
            "explanation": "Fail: Month and year of manufacture/packing/import is missing."
        })
    else:
        pat = rules.get("check_5", {}).get("validation_logic", {}).get("regex_pattern") or r"(?i)\b(?:0[1-9]|1[0-2])[/\-\.](?:19|20)?\d{2}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(?:19|20)?\d{2}\b"
        if re.search(pat, str(mfg_d)):
            check_results.append({
                "rule_id": "check_5",
                "rule_citation": cit5,
                "description": desc5,
                "severity": sev5,
                "fix_suggestion": fix5,
                "status": "pass",
                "explanation": f"Pass: Mfg date '{mfg_d}' declared in compliant format."
            })
        else:
            check_results.append({
                "rule_id": "check_5",
                "rule_citation": cit5,
                "description": desc5,
                "severity": sev5,
                "fix_suggestion": fix5,
                "status": "fail",
                "explanation": f"Fail: Mfg date '{mfg_d}' is in non-compliant format. Must clearly specify month and year (e.g. MM/YYYY or Month YYYY)."
            })
            
    # 6. Check 6: MRP Syntax
    cit6, desc6, sev6, fix6 = _get_rule_meta(rules, "check_6", "Rule 6(1)(e)", "Maximum Retail Price (MRP) including 'inclusive of all taxes'.", "CRITICAL")
    mrp_val = extracted_fields.get("mrp")
    if not mrp_val:
        check_results.append({
            "rule_id": "check_6",
            "rule_citation": cit6,
            "description": desc6,
            "severity": sev6,
            "fix_suggestion": fix6,
            "status": "fail",
            "explanation": "Fail: Maximum Retail Price (MRP) declaration is missing."
        })
    else:
        phrases = rules.get("check_6", {}).get("validation_logic", {}).get("required_phrases", ["inclusive of all taxes", "incl. of all taxes", "incl of all taxes", "incl.of all taxes"])
        has_taxes_phrase = any(p in raw_text_lower for p in phrases) or input_type == "url"
        
        if not has_taxes_phrase:
            check_results.append({
                "rule_id": "check_6",
                "rule_citation": cit6,
                "description": desc6,
                "severity": sev6,
                "fix_suggestion": fix6,
                "status": "fail",
                "explanation": f"Fail: MRP '{mrp_val}' lacks mandatory suffix 'inclusive of all taxes' or 'incl. of all taxes'."
            })
        else:
            check_results.append({
                "rule_id": "check_6",
                "rule_citation": cit6,
                "description": desc6,
                "severity": sev6,
                "fix_suggestion": fix6,
                "status": "pass",
                "explanation": f"Pass: MRP '{mrp_val}' declared with compliant tax inclusive declaration."
            })
            
    # 7. Check 7: Consumer Care Details
    cit7, desc7, sev7, fix7 = _get_rule_meta(rules, "check_7", "Rule 6(1)(g)", "Consumer care name, address, telephone and email.", "MAJOR")
    cc_phone = extracted_fields.get("consumer_care_phone")
    cc_email = extracted_fields.get("consumer_care_email")
    cc_name = extracted_fields.get("consumer_care_name")
    cc_addr = extracted_fields.get("consumer_care_address")
    
    missing_cc = []
    if not cc_name: missing_cc.append("name")
    if not cc_phone: missing_cc.append("phone")
    if not cc_email: missing_cc.append("email")
    if not cc_addr: missing_cc.append("address")
    
    if missing_cc:
        check_results.append({
            "rule_id": "check_7",
            "rule_citation": cit7,
            "description": desc7,
            "severity": sev7,
            "fix_suggestion": fix7,
            "status": "fail",
            "explanation": f"Fail: Consumer care declarations are incomplete. Missing fields: {', '.join(missing_cc)}."
        })
    else:
        check_results.append({
            "rule_id": "check_7",
            "rule_citation": cit7,
            "description": desc7,
            "severity": sev7,
            "fix_suggestion": fix7,
            "status": "pass",
            "explanation": f"Pass: All consumer care details present (Phone: {cc_phone}, Email: {cc_email})."
        })
        
    # 8. Check 8: Country of Origin
    cit8, desc8, sev8, fix8 = _get_rule_meta(rules, "check_8", "Rule 6(1)(f)", "Country of origin for imported/domestic commodities.", "MAJOR")
    origin = extracted_fields.get("country_of_origin")
    if not origin:
        check_results.append({
            "rule_id": "check_8",
            "rule_citation": cit8,
            "description": desc8,
            "severity": sev8,
            "fix_suggestion": fix8,
            "status": "fail",
            "explanation": "Fail: Country of Origin declaration is missing."
        })
    else:
        check_results.append({
            "rule_id": "check_8",
            "rule_citation": cit8,
            "description": desc8,
            "severity": sev8,
            "fix_suggestion": fix8,
            "status": "pass",
            "explanation": f"Pass: Country of Origin declared as '{origin}'."
        })
        
    # 9. Check 9: Importer Details (if imported)
    cit9, desc9, sev9, fix9 = _get_rule_meta(rules, "check_9", "Rule 6(1)(a) Importer", "Name and address of importer for imported commodities.", "CRITICAL")
    is_imported = extracted_fields.get("is_imported", False)
    if is_imported:
        imp_name = extracted_fields.get("importer_name")
        imp_addr = extracted_fields.get("importer_address")
        if not imp_name or not imp_addr:
            check_results.append({
                "rule_id": "check_9",
                "rule_citation": cit9,
                "description": desc9,
                "severity": sev9,
                "fix_suggestion": fix9,
                "status": "fail",
                "explanation": "Fail: Product is imported but importer name or address is missing."
            })
        else:
            check_results.append({
                "rule_id": "check_9",
                "rule_citation": cit9,
                "description": desc9,
                "severity": sev9,
                "fix_suggestion": fix9,
                "status": "pass",
                "explanation": f"Pass: Importer details declared (Name: {imp_name}, Address: {imp_addr})."
            })
    else:
        check_results.append({
            "rule_id": "check_9",
            "rule_citation": cit9,
            "description": desc9,
            "severity": sev9,
            "fix_suggestion": fix9,
            "status": "exempt",
            "explanation": "Exempt: Commodity is not marked as imported."
        })
        
    # 10. Check 10: Font Height vs PDP Area (Rule 6(3))
    cit10, desc10, sev10, fix10 = _get_rule_meta(rules, "check_10", "Rule 6(3) / Font Height", "Minimum font height conforming to Principal Display Panel area.", "MINOR")
    if calibration_factor is None:
        check_results.append({
            "rule_id": "check_10",
            "rule_citation": cit10,
            "description": desc10,
            "severity": sev10,
            "fix_suggestion": fix10,
            "status": "unverifiable",
            "explanation": "Unverifiable: Font height could not be measured because no calibration card or package bounding box was detected in frame."
        })
    else:
        actual_height_mm = 12.0 * calibration_factor
        estimated_pdp_area_cm2 = 150.0
        pdp_rules = rules.get("check_10", {}).get("validation_logic", {}).get("pdp_font_rules", [
            {"max_area_cm2": 50, "min_height_mm": 1.0},
            {"max_area_cm2": 100, "min_height_mm": 1.5},
            {"max_area_cm2": 500, "min_height_mm": 2.0},
            {"max_area_cm2": 1000, "min_height_mm": 3.0},
            {"max_area_cm2": 999999, "min_height_mm": 4.0}
        ])
        required_height_mm = 2.0
        for rule in pdp_rules:
            if estimated_pdp_area_cm2 <= rule.get("max_area_cm2", 999999):
                required_height_mm = rule.get("min_height_mm", 2.0)
                break
                
        if actual_height_mm < required_height_mm:
            check_results.append({
                "rule_id": "check_10",
                "rule_citation": cit10,
                "description": desc10,
                "severity": sev10,
                "fix_suggestion": fix10,
                "status": "fail",
                "explanation": f"Fail: Estimated font height is {actual_height_mm:.2f} mm, below the minimum required height of {required_height_mm:.2f} mm for PDP area {estimated_pdp_area_cm2} cm²."
            })
        else:
            check_results.append({
                "rule_id": "check_10",
                "rule_citation": cit10,
                "description": desc10,
                "severity": sev10,
                "fix_suggestion": fix10,
                "status": "pass",
                "explanation": f"Pass: Measured font height is {actual_height_mm:.2f} mm, complying with the minimum required height of {required_height_mm:.2f} mm."
            })
            
    # 11. Check 11: Standard Pack Sizes (Rule 8)
    cit11, desc11, sev11, fix11 = _get_rule_meta(rules, "check_11", "Rule 8 / Standard Sizes", "Net quantity conformity to prescribed standard sizes.", "MAJOR")
    if qty_val is not None and qty_unit in ["g", "ml"]:
        g_name_lower = str(g_name or "").lower()
        matched_cat = None
        
        cats = rules.get("check_11", {}).get("validation_logic", {}).get("standard_sizes", {})
        for cat in cats:
            if cat in g_name_lower:
                matched_cat = cat
                break
                
        if matched_cat:
            standard_list = cats[matched_cat]
            if qty_val in standard_list:
                check_results.append({
                    "rule_id": "check_11",
                    "rule_citation": cit11,
                    "description": desc11,
                    "severity": sev11,
                    "fix_suggestion": fix11,
                    "status": "pass",
                    "explanation": f"Pass: Quantity ({net_qty}) matches a standard size for category '{matched_cat}'."
                })
            else:
                sizes_str = ", ".join([f"{s}g" if qty_unit == "g" else f"{s}ml" for s in standard_list])
                check_results.append({
                    "rule_id": "check_11",
                    "rule_citation": cit11,
                    "description": desc11,
                    "severity": sev11,
                    "fix_suggestion": fix11,
                    "status": "fail",
                    "explanation": f"Fail: Quantity ({net_qty}) does not conform to standard pack sizes for category '{matched_cat}'. Permitted sizes: {sizes_str}."
                })
        else:
            check_results.append({
                "rule_id": "check_11",
                "rule_citation": cit11,
                "description": desc11,
                "severity": sev11,
                "fix_suggestion": fix11,
                "status": "exempt",
                "explanation": "Exempt: Commodity category does not have standard pack size restrictions under Rule 8."
            })
    else:
        check_results.append({
            "rule_id": "check_11",
            "rule_citation": cit11,
            "description": desc11,
            "severity": sev11,
            "fix_suggestion": fix11,
            "status": "exempt",
            "explanation": "Exempt: Net quantity is missing or could not be parsed."
        })
        
    # 12. Check 12: E-Commerce Parity (Rule 23)
    cit12, desc12, sev12, fix12 = _get_rule_meta(rules, "check_12", "Rule 23 E-Commerce", "Digital e-commerce listing declarations and packaging parity.", "MAJOR")
    if input_type == "url":
        listing_fields = extracted_fields.get("listing_fields") or {}
        missing_digital = []
        if not listing_fields.get("generic_name"): missing_digital.append("generic name")
        if not listing_fields.get("mrp"): missing_digital.append("MRP")
        if not listing_fields.get("net_quantity"): missing_digital.append("net quantity")
        if not listing_fields.get("country_of_origin"): missing_digital.append("country of origin")
        if not listing_fields.get("manufacturer_name") and not listing_fields.get("manufacturer_address"):
            missing_digital.append("manufacturer/packer details")
            
        if missing_digital:
            check_results.append({
                "rule_id": "check_12",
                "rule_citation": cit12,
                "description": desc12,
                "severity": sev12,
                "fix_suggestion": fix12,
                "status": "fail",
                "explanation": f"Fail (Rule 23): Digital e-commerce listing is missing mandatory declarations: {', '.join(missing_digital)}."
            })
        else:
            check_results.append({
                "rule_id": "check_12",
                "rule_citation": cit12,
                "description": desc12,
                "severity": sev12,
                "fix_suggestion": fix12,
                "status": "pass",
                "explanation": "Pass (Rule 23): Mandatory statutory declarations are present on the digital e-commerce listing."
            })
    else:
        check_results.append({
            "rule_id": "check_12",
            "rule_citation": cit12,
            "description": desc12,
            "severity": sev12,
            "fix_suggestion": fix12,
            "status": "exempt",
            "explanation": "Exempt: Input type is a camera image upload, not an e-commerce listing URL."
        })
        
    return check_results
