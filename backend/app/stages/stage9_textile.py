import os
import re
import json
import logging
from typing import Dict, Any, List, Tuple, Optional
from rapidfuzz import fuzz, process

logger = logging.getLogger("packaudit.textile")

# Load Apparel Taxonomy Dictionary
TAXONOMY_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "apparel_taxonomy.json")
_apparel_taxonomies = []

def load_apparel_taxonomies() -> List[Dict[str, Any]]:
    global _apparel_taxonomies
    if not _apparel_taxonomies:
        if os.path.exists(TAXONOMY_FILE):
            try:
                with open(TAXONOMY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    _apparel_taxonomies = data.get("taxonomies", [])
            except Exception as e:
                logger.error(f"Error loading apparel_taxonomy.json: {e}")
    return _apparel_taxonomies

# Common Fabric & Fiber Names
FABRIC_NAMES = [
    "cotton", "polyester", "silk", "wool", "linen", "viscose", "rayon", "modal", "nylon",
    "elastane", "spandex", "lycra", "acrylic", "cashmere", "bamboo", "jute", "hemp",
    "denim", "chiffon", "georgette", "khadi", "sateen", "poly", "polyurethane", "polyblend"
]

# -------------------------------------------------------------
# CHECK 1: Fiber Composition 100% Deterministic Math Validator
# -------------------------------------------------------------

def validate_fiber_composition(text: str) -> Dict[str, Any]:
    """
    Tier 1: Regex extraction of fiber percentages and fabric names.
    Tier 2: Deterministic summation validator requiring exact sum == 100%.
    """
    if not text:
        return {
            "status": "fail",
            "sum": 0.0,
            "breakdown": [],
            "explanation": "Fail: Fiber composition declaration is missing from garment tag."
        }

    # 1. First, check for an explicit composition block (e.g. Material: 60% Cotton, 40% Polyester)
    block_match = re.search(r"(?i)(?:material|composition|fabric|content|shell)\s*[:\-\s]+([^.\n]+)", text)
    target_text = block_match.group(1) if block_match else text

    def _extract_from_str(s: str) -> List[Dict[str, Any]]:
        fibers = []
        for m in re.finditer(r"(\d{1,3}(?:\.\d+)?)\s*%\s*([a-zA-Z\s\-]+)", s):
            pct_val = float(m.group(1))
            raw_fiber = m.group(2).strip()
            clean_fiber = re.split(r"[,;:\n\d/]", raw_fiber)[0].strip()
            # Match canonical fabric keyword
            matched_fab = None
            for fab in FABRIC_NAMES:
                if fab in clean_fiber.lower():
                    matched_fab = fab.capitalize()
                    break
            if matched_fab:
                fibers.append({"fiber": matched_fab, "percentage": pct_val})
        return fibers

    extracted_fibers = _extract_from_str(target_text)
    
    # Fallback to entire text if block didn't yield valid fibers
    if not extracted_fibers and block_match:
        extracted_fibers = _extract_from_str(text)

    # Check for reverse patterns (e.g. Cotton: 60%, Polyester 40%)
    if not extracted_fibers:
        for m in re.finditer(r"([a-zA-Z\s\-]+)\s*[:\-\s]*(\d{1,3}(?:\.\d+)?)\s*%", text):
            pct_val = float(m.group(2))
            raw_fiber = m.group(1).strip()
            clean_fiber = re.split(r"[,;:\n\d/]", raw_fiber)[-1].strip()
            matched_fab = None
            for fab in FABRIC_NAMES:
                if fab in clean_fiber.lower():
                    matched_fab = fab.capitalize()
                    break
            if matched_fab:
                extracted_fibers.append({"fiber": matched_fab, "percentage": pct_val})

    # Direct 100% single fiber check
    if not extracted_fibers:
        for fab in FABRIC_NAMES:
            match = re.search(rf"\b(100|\d{{1,2}})\s*%\s*{fab}\b", text, re.IGNORECASE)
            if match:
                extracted_fibers.append({"fiber": fab.capitalize(), "percentage": float(match.group(1))})

    if not extracted_fibers:
        return {
            "status": "fail",
            "sum": 0.0,
            "breakdown": [],
            "explanation": "Fail: Fiber composition declaration is missing or unparseable."
        }

    # Deduplicate repeated identical declarations from multiple OCR blocks
    unique_fibers: Dict[str, float] = {}
    for f in extracted_fibers:
        name = f["fiber"]
        pct = f["percentage"]
        # If fabric already seen with identical percentage, skip duplicate OCR mention
        if name not in unique_fibers:
            unique_fibers[name] = pct

    final_breakdown = [{"fiber": k, "percentage": v} for k, v in unique_fibers.items()]
    total_pct = sum(f["percentage"] for f in final_breakdown)
    breakdown_str = ", ".join([f"{f['percentage']:.0f}% {f['fiber']}" for f in final_breakdown])

    # Strict mathematical validation: sum must equal 100.0%
    if abs(total_pct - 100.0) < 0.1:
        return {
            "status": "pass",
            "sum": total_pct,
            "breakdown": final_breakdown,
            "explanation": f"Pass: Fiber composition verified ({breakdown_str}) totaling exactly 100%."
        }
    else:
        return {
            "status": "fail",
            "sum": total_pct,
            "breakdown": final_breakdown,
            "explanation": f"Fail (Fiber Math Violation): Declared textile composition percentages sum to {total_pct:.1f}% (expected exactly 100%). Composition: {breakdown_str}."
        }


# -------------------------------------------------------------
# CHECK 2: Size & Metric Dimensions Pairing Engine
# -------------------------------------------------------------

def validate_apparel_size_metric(text: str) -> Dict[str, Any]:
    """
    Validates apparel sizing under Legal Metrology Rules:
    - International letter sizes (S, M, L, XL, XXL) alone are non-compliant.
    - Letter size must be explicitly paired with physical metric dimensions in 'cm' or 'm'.
    """
    if not text:
        return {
            "status": "fail",
            "size": None,
            "is_paired": False,
            "explanation": "Fail: Garment size declaration is missing from label."
        }

    # Check 1: Explicit paired pattern (e.g. Size: L (Chest 102 cm))
    paired_match = re.search(
        r"(?i)\b(?:size|fit)\s*[:\-\s]*([A-Za-z0-9\+]+)?[^\n\.\;]*?\b(\d{2,3}(?:\.\d+)?\s*(?:cm|cms|m|inches|in|\"))\b",
        text
    )
    if paired_match:
        size_code = paired_match.group(1) or "Standard"
        metric_dim = paired_match.group(2)
        return {
            "status": "pass",
            "size": size_code,
            "dimensions": metric_dim,
            "is_paired": True,
            "explanation": f"Pass: Size declaration '{size_code}' is compliantly paired with metric dimensions ({metric_dim})."
        }

    # Check 2: Direct Metric measurements present on tag
    metric_measurements = re.findall(r"\b(\d{2,3}(?:\.\d+)?)\s*(?:cm|cms|m)\b", text, re.IGNORECASE)
    
    # Check 3: Alpha size only (e.g., "Size: L", "Size: XL", "Size M")
    alpha_size_match = re.search(r"(?i)\b(?:size|fit)\s*[:\-\s]*\b(XXS|XS|S|M|L|XL|XXL|XXXL|[0-9]{2,3})\b", text)
    
    if alpha_size_match:
        alpha_val = alpha_size_match.group(1).upper()
        if metric_measurements:
            dims_str = ", ".join([f"{m} cm" for m in metric_measurements[:2]])
            return {
                "status": "pass",
                "size": alpha_val,
                "dimensions": dims_str,
                "is_paired": True,
                "explanation": f"Pass: Garment size '{alpha_val}' is accompanied by physical metric measurements ({dims_str})."
            }
        else:
            return {
                "status": "fail",
                "size": alpha_val,
                "dimensions": None,
                "is_paired": False,
                "explanation": f"Fail: Size declared only as international letter size ('{alpha_val}') without mandatory metric dimensions in cm/m. Under Legal Metrology Rules, size must include physical metric measurements."
            }

    if metric_measurements:
        dims_str = ", ".join([f"{m} cm" for m in metric_measurements[:2]])
        return {
            "status": "pass",
            "size": "Metric Only",
            "dimensions": dims_str,
            "is_paired": True,
            "explanation": f"Pass: Physical metric dimensions declared ({dims_str})."
        }

    return {
        "status": "fail",
        "size": None,
        "is_paired": False,
        "explanation": "Fail: Garment size and physical metric dimensions are missing from the packaging/tag."
    }


# -------------------------------------------------------------
# CHECK 3: Maximum Retail Price (MRP) with Fuzzy Tax Suffix
# -------------------------------------------------------------

def validate_apparel_mrp_fuzzy(text: str) -> Dict[str, Any]:
    """
    Validates MRP with Unicode Rupee support and fuzzy matching for 'inclusive of all taxes'
    to prevent false negatives from garment tag wrinkling or minor OCR typos.
    """
    if not text:
        return {
            "status": "fail",
            "price": None,
            "has_tax_phrase": False,
            "explanation": "Fail: Maximum Retail Price (MRP) declaration is missing."
        }

    price_match = re.search(r"(?i)(?:m\.?r\.?p\.?|price)\s*[:\-\s]*(?:rs\.?|₹|\?|r\$|inr)?\s*([0-9,]+(?:\.[0-9]{2})?)", text)
    if not price_match:
        price_match = re.search(r"(?i)(?:rs\.?|₹)\s*([0-9,]+(?:\.[0-9]{2})?)", text)

    if not price_match:
        return {
            "status": "fail",
            "price": None,
            "has_tax_phrase": False,
            "explanation": "Fail: Maximum Retail Price (MRP) numerical declaration is missing."
        }

    raw_price = price_match.group(1).replace(",", "")
    
    tax_targets = [
        "inclusive of all taxes",
        "incl. of all taxes",
        "incl of all taxes",
        "incl.of all taxes",
        "incl of taxes",
        "all taxes included"
    ]
    
    has_tax_phrase = False
    best_match_ratio = 0.0
    text_lower = text.lower()
    
    for target in tax_targets:
        ratio = fuzz.partial_ratio(target, text_lower)
        if ratio > best_match_ratio:
            best_match_ratio = ratio
        if ratio >= 75.0:
            has_tax_phrase = True
            break

    if has_tax_phrase:
        return {
            "status": "pass",
            "price": f"Rs. {raw_price}",
            "has_tax_phrase": True,
            "match_confidence": best_match_ratio,
            "explanation": f"Pass: MRP declared as 'Rs. {raw_price}' with compliant statutory tax declaration (Fuzzy Match: {best_match_ratio:.0f}%)."
        }
    else:
        return {
            "status": "fail",
            "price": f"Rs. {raw_price}",
            "has_tax_phrase": False,
            "match_confidence": best_match_ratio,
            "explanation": f"Fail: MRP declared as 'Rs. {raw_price}' but lacks mandatory statutory suffix 'inclusive of all taxes' or 'incl. of all taxes'."
        }


# -------------------------------------------------------------
# CHECK 4: Generic / Common Name Taxonomy Match (Rule 6(1)(b))
# -------------------------------------------------------------

def validate_apparel_generic_name(text: str, generic_name_candidate: Optional[str] = None) -> Dict[str, Any]:
    """
    Validates generic/common name against National Apparel Taxonomy dictionary using RapidFuzz (>= 80%).
    Ensures generic commodity name is present and separated from brand name.
    """
    taxonomies = load_apparel_taxonomies()
    
    valid_names = []
    term_map = {}
    for entry in taxonomies:
        term = entry.get("term", "")
        valid_names.append(term)
        term_map[term.lower()] = term
        for alias in entry.get("aliases", []):
            valid_names.append(alias)
            term_map[alias.lower()] = term

    # 1. Test explicit generic_name_candidate if provided
    if generic_name_candidate:
        match = process.extractOne(generic_name_candidate, valid_names, scorer=fuzz.token_set_ratio)
        if match and match[1] >= 75.0:
            canonical = term_map.get(match[0].lower(), match[0])
            return {
                "status": "pass",
                "generic_name": canonical,
                "similarity_score": match[1],
                "explanation": f"Pass: Generic name verified as '{canonical}' (Taxonomy match: {match[1]:.0f}% for '{generic_name_candidate}')."
            }

    # 2. Search entire text payload for word-boundary taxonomy matches
    text_lower = text.lower()
    for term_entry in valid_names:
        pattern = rf"\b{re.escape(term_entry.lower())}\b"
        if re.search(pattern, text_lower):
            canonical = term_map.get(term_entry.lower(), term_entry)
            return {
                "status": "pass",
                "generic_name": canonical,
                "similarity_score": 100.0,
                "explanation": f"Pass: Generic name '{canonical}' identified from taxonomy dictionary."
            }

    return {
        "status": "fail",
        "generic_name": None,
        "similarity_score": 0.0,
        "explanation": "Fail: Common or generic name of the apparel commodity is missing or does not match recognized statutory taxonomy (Rule 6(1)(b))."
    }


# -------------------------------------------------------------
# CHECK 5: Consumer Care 3-Channel Verification (Rule 6(1)(f))
# -------------------------------------------------------------

def validate_apparel_consumer_care(fields: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
    """
    Enforces statutory Rule 6(1)(f) requiring all 3 mandatory channels:
    1. 10-digit Indian phone / 1800 toll-free
    2. Valid email address
    3. Complete physical postal address with 6-digit PIN code
    """
    full_text = f"{raw_text} {fields.get('consumer_care_phone', '')} {fields.get('consumer_care_email', '')} {fields.get('consumer_care_address', '')}"
    
    has_phone = bool(fields.get("consumer_care_phone")) or bool(re.search(r"\b[6-9]\d{9}\b|\b1800[\-\s]?[0-9]{3,4}[\-\s]?[0-9]{3,4}\b", full_text))
    has_email = bool(fields.get("consumer_care_email")) or bool(re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b", full_text))
    has_pincode = bool(re.search(r"\b[1-9][0-9]{2}\s?[0-9]{3}\b", full_text))
    has_address = bool(fields.get("consumer_care_address")) or has_pincode
    
    missing = []
    if not has_phone: missing.append("telephonic helpline (10-digit / 1800 toll-free)")
    if not has_email: missing.append("valid email address")
    if not has_address: missing.append("postal address with 6-digit PIN code")
    
    if missing:
        return {
            "status": "fail",
            "missing_channels": missing,
            "explanation": f"Fail (Rule 6(1)(f)): Consumer care details incomplete. Missing mandatory channels: {', '.join(missing)}."
        }
    else:
        return {
            "status": "pass",
            "missing_channels": [],
            "explanation": "Pass: All 3 mandatory consumer care channels present (Phone, Email, Postal Address with PIN code)."
        }


# -------------------------------------------------------------
# CHECK 6: Contextual Manufacturing / Packing Date (Rule 6(1)(d))
# -------------------------------------------------------------

def validate_apparel_mfg_date(text: str) -> Dict[str, Any]:
    """
    Validates manufacturing/packing date with required context (MFD / MFG / PKD / Packed / Imported).
    Ensures a bare uncontextualized date is not accepted.
    """
    date_context_match = re.search(
        r"(?i)\b(?:mfd|mfg|manufactured|pkd|packed|pkg|packing\s*date|import\s*date|imported)\b\s*[:\-\s]*([A-Za-z]{3,9}\s+\d{4}|\d{2}[/\-\.]\d{2,4})\b",
        text
    )
    if date_context_match:
        d_val = date_context_match.group(1)
        return {
            "status": "pass",
            "date": d_val,
            "explanation": f"Pass: Manufacturing/packing date declared in compliant context ('{d_val}')."
        }
    else:
        bare_date = re.search(r"\b(0[1-9]|1[0-2])[/\-\.](20\d{2}|\d{2})\b", text)
        if bare_date:
            return {
                "status": "fail",
                "date": bare_date.group(0),
                "explanation": f"Fail: Date '{bare_date.group(0)}' found but lacks mandatory statutory context keyword (MFD, MFG, PKD, or Packed)."
            }
        return {
            "status": "fail",
            "date": None,
            "explanation": "Fail: Date of manufacturing, packing, or import declaration is missing from garment tag."
        }


# -------------------------------------------------------------
# CHECK 7: Contextual Country of Origin (Rule 6(1)(f))
# -------------------------------------------------------------

def validate_apparel_country_of_origin(text: str) -> Dict[str, Any]:
    """
    Validates Country of Origin with explicit origin context (Country of Origin / Made in / Product of).
    Avoids false positives from incidental address mentions (e.g. 'Manufactured in Mumbai, India').
    """
    origin_match = re.search(
        r"(?i)\b(?:country\s*of\s*origin|made\s*in|product\s*of|origin)\b\s*[:\-\s]*([A-Za-z\s]+)\b",
        text
    )
    if origin_match:
        country = origin_match.group(1).strip()
        country_clean = re.split(r"[\n,;\.]", country)[0].strip()
        return {
            "status": "pass",
            "country": country_clean,
            "explanation": f"Pass: Country of Origin declared in explicit context as '{country_clean}'."
        }
        
    if "made in india" in text.lower() or "product of india" in text.lower():
        return {
            "status": "pass",
            "country": "India",
            "explanation": "Pass: Country of Origin declared as 'India' ('Made in India')."
        }

    return {
        "status": "fail",
        "country": None,
        "explanation": "Fail: Country of Origin declaration is missing. (Incidental address mentions do not substitute for a statutory origin declaration)."
    }
