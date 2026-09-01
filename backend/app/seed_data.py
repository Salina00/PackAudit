import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal, engine, Base
from backend.app.models.models import RuleDefinition, ManufacturerCache

# 12 Legal Metrology Rules + 6 FSSAI Food Rules + 7 Apparel & Textile Rules = 25 Rules
RULE_DEFINITIONS_DATA = [
    # ------------------ Legal Metrology General Rules (1 - 12) ------------------
    {
        "rule_id": "check_1",
        "rule_citation": "Rule 18 Exemption Pre-Check",
        "description": "Checks if the product is exempt under Rule 18 (institutional/industrial use, net qty <= 10g/10ml, agricultural produce > 50kg, or export-only).",
        "check_type": "exemption",
        "validation_logic": {
            "max_qty_exempt_g_ml": 10.0,
            "max_agricultural_produce_kg": 50.0
        },
        "severity": "CRITICAL",
        "fix_suggestion": "Ensure statutory exemption eligibility criteria (net qty ≤ 10g/ml, agricultural produce > 50kg, or industrial/export use) are clearly documented on packaging."
    },
    {
        "rule_id": "check_2",
        "rule_citation": "Rule 6(1)(a)",
        "description": "Every package must bear the name and complete address of the manufacturer, packer, or importer.",
        "check_type": "presence",
        "validation_logic": {
            "required_fields": ["manufacturer_name", "manufacturer_address"]
        },
        "severity": "CRITICAL",
        "fix_suggestion": "Include the full legal name and complete postal address of the manufacturer/packer with a valid 6-digit PIN code."
    },
    {
        "rule_id": "check_3",
        "rule_citation": "Rule 6(1)(b)",
        "description": "The common or generic name of the commodity contained in the package must be declared.",
        "check_type": "presence",
        "validation_logic": {
            "required_fields": ["generic_name"]
        },
        "severity": "MAJOR",
        "fix_suggestion": "Declare the common or generic name of the packaged commodity prominently on the Principal Display Panel."
    },
    {
        "rule_id": "check_4",
        "rule_citation": "Rule 6(1)(c)",
        "description": "The net quantity, in terms of standard unit of weight, measure or number, must be declared.",
        "check_type": "measurement",
        "validation_logic": {
            "allowed_units": ["g", "grm", "gram", "grams", "kg", "kg.", "kilogram", "kilograms", "ml", "ml.", "milliliter", "milliliters", "l", "l.", "liter", "liters", "litre", "litres", "m", "meter", "meters", "pcs", "units", "u", "n", "pair", "pairs", "piece", "pieces"]
        },
        "severity": "CRITICAL",
        "fix_suggestion": "Declare net quantity using statutory metric unit symbols ('g', 'kg', 'ml', 'l', 'pcs', 'N') without non-standard abbreviations like 'gms' or 'ltrs'."
    },
    {
        "rule_id": "check_5",
        "rule_citation": "Rule 6(1)(d)",
        "description": "The month and year in which the commodity is manufactured or pre-packed or imported must be declared.",
        "check_type": "regex",
        "validation_logic": {
            "regex_pattern": r"(?i)\b(?:0[1-9]|1[0-2])[/\-\.](?:19|20)?\d{2}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(?:19|20)?\d{2}\b"
        },
        "severity": "MAJOR",
        "fix_suggestion": "Declare the month and year of manufacturing or pre-packing in standard format (e.g. '08/2026' or 'Aug 2026')."
    },
    {
        "rule_id": "check_6",
        "rule_citation": "Rule 6(1)(e)",
        "description": "The Maximum Retail Price (MRP) must be declared clearly, including the phrase 'inclusive of all taxes' or 'incl. of all taxes'.",
        "check_type": "regex",
        "validation_logic": {
            "regex_pattern": r"(?i)\b(?:m\.?r\.?p\.?|max\.?(?:imum)?\s*retail\s*price)\s*(?:rs\.?|₹)?\s*\d+(?:\.\d{2})?",
            "required_phrases": ["inclusive of all taxes", "incl. of all taxes", "incl.of all taxes", "incl of all taxes"]
        },
        "severity": "CRITICAL",
        "fix_suggestion": "Add the mandatory statutory suffix 'inclusive of all taxes' or 'incl. of all taxes' immediately adjacent to the MRP declaration."
    },
    {
        "rule_id": "check_7",
        "rule_citation": "Rule 6(1)(g)",
        "description": "Every package must bear the name, address, telephone number, and email address of the consumer care contact.",
        "check_type": "presence",
        "validation_logic": {
            "required_fields": ["consumer_care_name", "consumer_care_phone", "consumer_care_email", "consumer_care_address"]
        },
        "severity": "MAJOR",
        "fix_suggestion": "Declare complete consumer care contact details including contact officer/cell name, postal address, working phone number, and valid email ID."
    },
    {
        "rule_id": "check_8",
        "rule_citation": "Rule 6(1)(f)",
        "description": "For imported commodities and general goods, the country of origin must be declared.",
        "check_type": "presence",
        "validation_logic": {
            "required_fields": ["country_of_origin"]
        },
        "severity": "MAJOR",
        "fix_suggestion": "Declare the Country of Origin clearly on the packaging (e.g., 'Country of Origin: India' or 'Made in India')."
    },
    {
        "rule_id": "check_9",
        "rule_citation": "Rule 6(1)(a) Importer",
        "description": "For imported commodities, the name and address of the importer must be declared.",
        "check_type": "presence",
        "validation_logic": {
            "required_fields": ["importer_name", "importer_address"]
        },
        "severity": "CRITICAL",
        "fix_suggestion": "For imported commodities, declare the registered company name and complete postal address of the Indian importer."
    },
    {
        "rule_id": "check_10",
        "rule_citation": "Rule 6(3) / Font Height",
        "description": "Minimum font height of declarations must conform to the Principal Display Panel (PDP) area regulations.",
        "check_type": "measurement",
        "validation_logic": {
            "pdp_font_rules": [
                {"max_area_cm2": 50, "min_height_mm": 1.0},
                {"max_area_cm2": 100, "min_height_mm": 1.5},
                {"max_area_cm2": 500, "min_height_mm": 2.0},
                {"max_area_cm2": 1000, "min_height_mm": 3.0},
                {"max_area_cm2": 999999, "min_height_mm": 4.0}
            ]
        },
        "severity": "MINOR",
        "fix_suggestion": "Increase letter and numeral font height to meet the minimum statutory height (e.g. min 2.0 mm for PDP area > 100 cm²) based on package surface area."
    },
    {
        "rule_id": "check_11",
        "rule_citation": "Rule 8 / Standard Sizes",
        "description": "Pre-packaged commodity net quantity must conform to the prescribed standard sizes for defined categories.",
        "check_type": "measurement",
        "validation_logic": {
            "standard_sizes": {
                "tea": [25, 50, 75, 100, 125, 150, 200, 250, 500, 1000],
                "biscuits": [25, 50, 75, 100, 150, 200, 250, 300, 400],
                "edible_oil": [50, 100, 200, 250, 500, 1000, 2000, 3000, 5000],
                "soap": [25, 50, 75, 100, 125, 150],
                "water": [100, 150, 200, 250, 300, 500, 750, 1000, 1500, 2000, 5000]
            }
        },
        "severity": "MAJOR",
        "fix_suggestion": "Pack the commodity in one of the prescribed standard net quantity sizes specified under the Second Schedule of Legal Metrology Rules."
    },
    {
        "rule_id": "check_12",
        "rule_citation": "Rule 23 E-Commerce",
        "description": "For e-commerce sales, digital listing declarations must display all mandatory statutory fields.",
        "check_type": "presence",
        "validation_logic": {
            "fields_to_compare": ["mrp", "net_quantity", "manufacturer_name", "country_of_origin"]
        },
        "severity": "MAJOR",
        "fix_suggestion": "Ensure the digital marketplace listing displays all mandatory statutory declarations (MRP, Net Quantity, Country of Origin, Manufacturer details, Consumer care) matching physical label."
    },

    # ------------------ FSSAI Food & Beverage Rules (FSSAI 2020) ------------------
    {
        "rule_id": "fssai_check_1",
        "rule_citation": "FSSAI Sec 31 / License 3-Tier",
        "description": "Every food package must display a valid 14-digit FSSAI License/Registration number verified through mathematical syntax, FoSCoS portal, and state registry cache.",
        "check_type": "presence",
        "validation_logic": {
            "syntax_pattern": r"^[12][0-3][0-9]\d{11}$"
        },
        "severity": "CRITICAL",
        "fix_suggestion": "Obtain and declare a valid 14-digit FSSAI license/registration number with the official FSSAI logo on the Principal Display Panel."
    },
    {
        "rule_id": "fssai_check_2",
        "rule_citation": "FSSAI 2020 Reg 5(3) / Nutrition",
        "description": "Nutritional Information per 100g/100ml and per serving declaring Energy, Protein, Carbohydrates, Total/Added Sugars, Fat, Saturated/Trans Fat, and Sodium with mathematical consistency.",
        "check_type": "measurement",
        "validation_logic": {
            "mandatory_nutrients": ["energy", "protein", "carbohydrates", "total_fat", "saturated_fat", "trans_fat", "sodium"]
        },
        "severity": "CRITICAL",
        "fix_suggestion": "Include a structured Nutritional Information table declaring all 8 mandatory nutrients per 100g/100ml and per serving."
    },
    {
        "rule_id": "fssai_check_3",
        "rule_citation": "FSSAI 2020 Reg 5(4) / Veg Logo",
        "description": "Mandatory Vegetarian (green circle in green square) or Non-Vegetarian (brown triangle in brown square) logo conforming to PDP surface area millimeter dimensions.",
        "check_type": "measurement",
        "validation_logic": {
            "pdp_sizing_mm": {"<=100": 6.0, "<=500": 8.0, "<=2500": 10.0, ">2500": 16.0}
        },
        "severity": "MAJOR",
        "fix_suggestion": "Display the compliant Veg (green circle in green square) or Non-Veg (brown triangle in brown square) symbol meeting minimum PDP millimeter dimensions."
    },
    {
        "rule_id": "fssai_check_4",
        "rule_citation": "FSSAI 2020 Reg 5(1) / Ingredients",
        "description": "List of Ingredients in strictly descending order of weight or volume at manufacture with Quantitative Ingredient Declaration (QUID) monotonicity.",
        "check_type": "presence",
        "validation_logic": {
            "descending_order_enforced": True
        },
        "severity": "MAJOR",
        "fix_suggestion": "List all ingredients in strictly descending order of incoming weight/volume, ensuring declared percentages descend monotonically."
    },
    {
        "rule_id": "fssai_check_5",
        "rule_citation": "FSSAI 2020 Reg 5(2) / Allergens",
        "description": "Mandatory separate allergen declaration ('Contains: ...') for 8 statutory allergen classes (gluten, crustaceans, milk, eggs, fish, nuts, soy, sulphites).",
        "check_type": "presence",
        "validation_logic": {
            "allergen_classes": ["gluten", "crustaceans", "milk", "eggs", "fish", "nuts", "soy", "sulphites"]
        },
        "severity": "CRITICAL",
        "fix_suggestion": "Add a separate allergen advisory statement immediately adjacent to ingredients (e.g. 'Contains: Wheat (Gluten), Milk, Tree Nuts')."
    },
    {
        "rule_id": "fssai_check_6",
        "rule_citation": "FSSAI 2020 Reg 5(10) / Expiry Date",
        "description": "Mandatory Expiry Date or Use By date declaration. 'Best Before' date is optional and cannot substitute for an explicit Expiry Date.",
        "check_type": "regex",
        "validation_logic": {
            "mandatory_keywords": ["expiry", "use by", "exp"]
        },
        "severity": "CRITICAL",
        "fix_suggestion": "Declare an explicit 'Expiry Date' or 'Use By' date on the package (e.g. 'Expiry: 31/12/2026'). 'Best Before' is not a legal substitute."
    },

    # ------------------ Apparel & Textile Rules (National Standards + LM 2011) ------------------
    {
        "rule_id": "apparel_check_1",
        "rule_citation": "Textile Rule / Fiber 100% Math",
        "description": "Mandatory declaration of fiber/fabric names with exact percentage values mathematically totaling 100%.",
        "check_type": "measurement",
        "validation_logic": {
            "exact_sum": 100.0
        },
        "severity": "CRITICAL",
        "fix_suggestion": "Declare all component fibers and fabrics with percentage values that sum exactly to 100% (e.g. '60% Cotton, 40% Polyester')."
    },
    {
        "rule_id": "apparel_check_2",
        "rule_citation": "Rule 6(1)(c) / Size & Metric",
        "description": "Garment size must declare physical metric dimensions in centimeters (cm) or meters (m); international letter size (S/M/L/XL) alone is legally insufficient.",
        "check_type": "measurement",
        "validation_logic": {
            "metric_pairing_required": True
        },
        "severity": "CRITICAL",
        "fix_suggestion": "Pair international letter sizes (S/M/L/XL) with physical metric measurements in centimeters (e.g. 'Size: L (Chest 102 cm, Length 76 cm)')."
    },
    {
        "rule_id": "apparel_check_3",
        "rule_citation": "Rule 6(1)(e) / MRP & Tax Suffix",
        "description": "Maximum Retail Price in INR/Rupees explicitly accompanied by mandatory 'inclusive of all taxes' suffix with OCR typo tolerance.",
        "check_type": "regex",
        "validation_logic": {
            "required_phrases": ["inclusive of all taxes", "incl. of all taxes"]
        },
        "severity": "CRITICAL",
        "fix_suggestion": "Include the mandatory statutory suffix 'inclusive of all taxes' or 'incl. of all taxes' immediately adjacent to the MRP declaration."
    },
    {
        "rule_id": "apparel_check_4",
        "rule_citation": "Rule 6(1)(b) / Apparel Taxonomy",
        "description": "Common or generic apparel commodity name must match recognized national Department of Consumer Affairs taxonomy (>=80% similarity).",
        "check_type": "presence",
        "validation_logic": {
            "taxonomy_threshold": 80
        },
        "severity": "MAJOR",
        "fix_suggestion": "Declare the statutory generic apparel commodity name (e.g. 'Men's T-Shirt', 'Formal Trousers', 'Cotton Saree') separate from brand name."
    },
    {
        "rule_id": "apparel_check_5",
        "rule_citation": "Rule 6(1)(f) / Consumer Care 3-Way",
        "description": "All 3 mandatory consumer care channels must be present: working telephone helpline, valid email, and physical postal address with 6-digit PIN code.",
        "check_type": "presence",
        "validation_logic": {
            "required_channels": ["phone", "email", "address"]
        },
        "severity": "CRITICAL",
        "fix_suggestion": "Provide all 3 statutory consumer care channels: working telephone number (or 1800 toll-free), valid email ID, and postal address with 6-digit PIN code."
    },
    {
        "rule_id": "apparel_check_6",
        "rule_citation": "Rule 6(1)(d) / Contextual MFD",
        "description": "Month and year of manufacture or pre-packing declared in explicit statutory context (MFD / MFG / PKD / Packed).",
        "check_type": "regex",
        "validation_logic": {
            "context_keywords": ["mfd", "mfg", "pkd", "packed", "manufactured"]
        },
        "severity": "MAJOR",
        "fix_suggestion": "Declare the manufacturing or packing date in explicit statutory context (e.g. 'MFD: 08/2026' or 'PKD: Aug 2026')."
    },
    {
        "rule_id": "apparel_check_7",
        "rule_citation": "Rule 6(1)(f) / Country of Origin",
        "description": "Explicit Country of Origin declaration ('Country of Origin: ...' or 'Made in ...') separate from general manufacturer address mentions.",
        "check_type": "presence",
        "validation_logic": {
            "explicit_context_required": True
        },
        "severity": "CRITICAL",
        "fix_suggestion": "Include an explicit Country of Origin declaration (e.g. 'Country of Origin: India' or 'Made in India') on the garment label."
    }
]

# 50 National Consumer Brands Data Cache
MANUFACTURER_CACHE_DATA = [
    {"company_name": "Hindustan Unilever Limited", "aliases": ["HUL", "Unilever"], "registered_pincodes": ["400099", "400020"], "verified_addresses": ["Unilever House, B. D. Sawant Marg, Chakala, Andheri East, Mumbai 400099"]},
    {"company_name": "ITC Limited", "aliases": ["ITC"], "registered_pincodes": ["700071"], "verified_addresses": ["Virginia House, 37 J.L. Nehru Road, Kolkata 700071"]},
    {"company_name": "Nestle India Limited", "aliases": ["Nestle"], "registered_pincodes": ["122002"], "verified_addresses": ["100 / 101, World Trade Centre, Barakhamba Lane, New Delhi 110001", "Nestle House, Jacaranda Marg, M Block, DLF City Phase II, Gurugram 122002"]},
    {"company_name": "Britannia Industries Limited", "aliases": ["Britannia"], "registered_pincodes": ["560048", "700017"], "verified_addresses": ["5/1A, Hungerford Street, Kolkata 700017", "Prestige Shantiniketan, Whitefield, Bangalore 560048"]},
    {"company_name": "Dabur India Limited", "aliases": ["Dabur"], "registered_pincodes": ["201010", "110002"], "verified_addresses": ["8/3, Asaf Ali Road, New Delhi 110002", "Kaushambi, Sahibabad, Ghaziabad 201010"]},
    {"company_name": "Marico Limited", "aliases": ["Marico", "Parachute"], "registered_pincodes": ["400098"], "verified_addresses": ["7th Floor, Grande Palladium, 175, CST Road, Kalina, Santacruz East, Mumbai 400098"]},
    {"company_name": "Tata Consumer Products Limited", "aliases": ["Tata Tea", "Tata Salt", "TCPL"], "registered_pincodes": ["700020", "560001"], "verified_addresses": ["1, Bishop Lefroy Road, Kolkata 700020"]},
    {"company_name": "Parle Products Private Limited", "aliases": ["Parle", "Parle-G"], "registered_pincodes": ["400057"], "verified_addresses": ["North Level Crossing, Vile Parle East, Mumbai 400057"]},
    {"company_name": "Raymond Limited", "aliases": ["Raymond", "Park Avenue", "ColorPlus", "Parx"], "registered_pincodes": ["400606", "400001"], "verified_addresses": ["Plot No. 156/H No. 2, Village Zadgaon, Ratnagiri, Maharashtra 415612", "Jekegram, Pokhran Road No. 1, Thane West 400606"]},
    {"company_name": "Aditya Birla Fashion and Retail Limited", "aliases": ["ABFRL", "Louis Philippe", "Van Heusen", "Allen Solly", "Peter England"], "registered_pincodes": ["560068", "400025"], "verified_addresses": ["Piramal Agastya Corporate Park, Building 'A', 4th and 5th Floor, Unit No. 401, 403, 501, 502, L.B.S. Road, Kurla West, Mumbai 400070"]},
    {"company_name": "Arvind Limited", "aliases": ["Arvind", "Flying Machine", "US Polo"], "registered_pincodes": ["380025"], "verified_addresses": ["Naroda Road, Ahmedabad, Gujarat 380025"]},
    {"company_name": "Page Industries Limited (Jockey)", "aliases": ["Jockey", "Page"], "registered_pincodes": ["560008"], "verified_addresses": ["Umiya Business Bay - Tower 1, 7th Floor, Cessna Business Park, Kadubeesanahalli, Bangalore 560103"]},
    {"company_name": "Amul (GCMMF)", "aliases": ["Amul", "GCMMF"], "registered_pincodes": ["388001"], "verified_addresses": ["Amul Dairy Road, Anand 388001, Gujarat"]}
]

def seed_database():
    """
    Creates tables if not created, and populates 25 rule definitions and brand caches.
    """
    db: Session = SessionLocal()
    try:
        print("Initializing Database tables...")
        Base.metadata.create_all(bind=engine)
        
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE rule_definitions ADD COLUMN IF NOT EXISTS fix_suggestion VARCHAR;"))
            conn.commit()
        
        print(f"Seeding {len(RULE_DEFINITIONS_DATA)} Rule Definitions (12 Legal Metrology + 6 FSSAI Food + 7 Apparel & Textile)...")
        for r_data in RULE_DEFINITIONS_DATA:
            existing = db.query(RuleDefinition).filter(RuleDefinition.rule_id == r_data["rule_id"]).first()
            if not existing:
                rule_def = RuleDefinition(
                    rule_id=r_data["rule_id"],
                    rule_citation=r_data["rule_citation"],
                    description=r_data["description"],
                    check_type=r_data["check_type"],
                    validation_logic=r_data["validation_logic"],
                    severity=r_data["severity"],
                    fix_suggestion=r_data.get("fix_suggestion")
                )
                db.add(rule_def)
            else:
                existing.rule_citation = r_data["rule_citation"]
                existing.description = r_data["description"]
                existing.check_type = r_data["check_type"]
                existing.validation_logic = r_data["validation_logic"]
                existing.severity = r_data["severity"]
                existing.fix_suggestion = r_data.get("fix_suggestion")
                
        db.commit()
        
        print("Seeding Manufacturer & Brand Cache...")
        for m_data in MANUFACTURER_CACHE_DATA:
            existing_mfg = db.query(ManufacturerCache).filter(ManufacturerCache.company_name == m_data["company_name"]).first()
            if not existing_mfg:
                mfg = ManufacturerCache(
                    company_name=m_data["company_name"],
                    aliases=m_data["aliases"],
                    registered_pincodes=m_data["registered_pincodes"],
                    verified_addresses=m_data["verified_addresses"]
                )
                db.add(mfg)
            else:
                existing_mfg.aliases = m_data["aliases"]
                existing_mfg.registered_pincodes = m_data["registered_pincodes"]
                existing_mfg.verified_addresses = m_data["verified_addresses"]
                
        db.commit()
        print("Database seeding completed successfully (25 Rules + Brands Cached)!")
    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
