import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal, engine, Base
from backend.app.models.models import RuleDefinition, ManufacturerCache

# 12 Legal Metrology Rules + 6 FSSAI Food Rules Data
RULE_DEFINITIONS_DATA = [
    # ------------------ Legal Metrology Rules (1 - 12) ------------------
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
            "allowed_units": ["g", "grm", "gram", "grams", "kg", "kg.", "kilogram", "kilograms", "ml", "ml.", "milliliter", "milliliters", "l", "l.", "liter", "liters", "litre", "litres", "m", "meter", "meters", "pcs", "units", "u"]
        },
        "severity": "CRITICAL",
        "fix_suggestion": "Declare net quantity using statutory metric unit symbols ('g', 'kg', 'ml', 'l', 'pcs') without non-standard abbreviations like 'gms' or 'ltrs'."
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
    {"company_name": "Godrej Consumer Products Limited", "aliases": ["GCPL", "Godrej"], "registered_pincodes": ["400079"], "verified_addresses": ["Godrej One, Pirojshanagar, Eastern Express Highway, Vikhroli East, Mumbai 400079"]},
    {"company_name": "Colgate-Palmolive (India) Limited", "aliases": ["Colgate"], "registered_pincodes": ["400076"], "verified_addresses": ["Colgate Research Centre, Main Street, Hiranandani Gardens, Powai, Mumbai 400076"]},
    {"company_name": "Amul (GCMMF)", "aliases": ["Amul", "GCMMF"], "registered_pincodes": ["388001"], "verified_addresses": ["Amul Dairy Road, Anand 388001, Gujarat"]},
    {"company_name": "Mother Dairy Fruit & Vegetable Pvt Ltd", "aliases": ["Mother Dairy"], "registered_pincodes": ["110092"], "verified_addresses": ["Patparganj, Delhi 110092"]},
    {"company_name": "Haldiram Snacks Private Limited", "aliases": ["Haldiram", "Haldirams"], "registered_pincodes": ["201307", "440008"], "verified_addresses": ["B-1/H-8, Mohan Co-operative Industrial Estate, Main Mathura Road, New Delhi 110044"]},
    {"company_name": "Bikaji Foods International Limited", "aliases": ["Bikaji"], "registered_pincodes": ["334006"], "verified_addresses": ["F 196-199, F 178 & E 188, Bichhwal Industrial Area, Bikaner 334006"]},
    {"company_name": "Balaji Wafers Private Limited", "aliases": ["Balaji"], "registered_pincodes": ["360024"], "verified_addresses": ["Vajdi (Vad), Kalawad Road, Tal. Lodhika, Dist. Rajkot 360024"]},
    {"company_name": "Patanjali Ayurved Limited", "aliases": ["Patanjali"], "registered_pincodes": ["249405"], "verified_addresses": ["Patanjali Food & Herbal Park, Padartha, Laksar Road, Haridwar 249405"]},
    {"company_name": "Emami Limited", "aliases": ["Emami", "BoroPlus", "Zandu"], "registered_pincodes": ["700107"], "verified_addresses": ["Emami Tower, 687 Anandapur, EM Bypass, Kolkata 700107"]},
    {"company_name": "Adani Wilmar Limited", "aliases": ["Fortune", "Adani Wilmar"], "registered_pincodes": ["380009"], "verified_addresses": ["Fortune House, Near Navrangpura Railway Crossing, Ahmedabad 380009"]},
    {"company_name": "PepsiCo India Holdings Private Limited", "aliases": ["PepsiCo", "Lays", "Kurkure", "Tropicana"], "registered_pincodes": ["122002"], "verified_addresses": ["Level 3-6, Pioneer Square, Sector 62, Near Golf Course Extension Road, Gurugram 122102"]},
    {"company_name": "Coca-Cola India Private Limited", "aliases": ["Coca-Cola", "Coke", "Thums Up"], "registered_pincodes": ["122016"], "verified_addresses": ["One Horizon Center, Golf Course Road, DLF Phase 5, Sector 43, Gurugram 122003"]},
    {"company_name": "Mondelez India Foods Private Limited", "aliases": ["Cadbury", "Mondelez", "Oreo"], "registered_pincodes": ["400018"], "verified_addresses": ["Unit No. 2001, 20th Floor, Tower-3, One International Center, Parel, Mumbai 400013"]},
    {"company_name": "Reckitt Benckiser (India) Private Limited", "aliases": ["Dettol", "Reckitt", "Harpic", "Lizol"], "registered_pincodes": ["122016"], "verified_addresses": ["DLF Cyber Park, 6th & 7th Floor, Tower C, 405 B, Udyog Vihar Phase III, Sector 20, Gurugram 122016"]},
    {"company_name": "Procter & Gamble Hygiene and Health Care Limited", "aliases": ["P&G", "Gillette", "Pampers", "Ariel", "Tide"], "registered_pincodes": ["400099"], "verified_addresses": ["P&G Plaza, Cardinal Gracias Road, Chakala, Andheri East, Mumbai 400099"]},
    {"company_name": "Johnson & Johnson Private Limited", "aliases": ["J&J", "Johnson & Johnson", "Johnsons"], "registered_pincodes": ["400080"], "verified_addresses": ["501 Arena Space, Behind Majas Bus Depot, Off JVLR, Jogeshwari East, Mumbai 400060"]},
    {"company_name": "GSK Consumer Healthcare (Haleon India)", "aliases": ["Sensodyne", "Crocin", "Eno", "Haleon"], "registered_pincodes": ["122002"], "verified_addresses": ["5th Floor, DLF Cyber City, Building 10, Tower C, DLF Phase 2, Gurugram 122002"]},
    {"company_name": "Wipro Consumer Care and Lighting", "aliases": ["Wipro", "Santoor", "Yardley"], "registered_pincodes": ["560035"], "verified_addresses": ["Doddakannelli, Sarjapur Road, Bangalore 560035"]},
    {"company_name": "CavinKare Private Limited", "aliases": ["CavinKare", "Chik", "Meera", "Nyle"], "registered_pincodes": ["600032"], "verified_addresses": ["Cavin Ville, No. 12, Cenotaph Road, Teynampet, Chennai 600018"]},
    {"company_name": "Jyothy Labs Limited", "aliases": ["Ujala", "Pril", "Margo", "Exo", "Jyothy"], "registered_pincodes": ["400059"], "verified_addresses": ["Ujala House, Ram Krishna Mandir Road, Kondivita, Andheri East, Mumbai 400059"]},
    {"company_name": "Himalaya Wellness Company", "aliases": ["Himalaya", "Himalaya Herbals"], "registered_pincodes": ["562123"], "verified_addresses": ["Makali, Bengaluru 562123, Karnataka"]},
    {"company_name": "Bisleri International Private Limited", "aliases": ["Bisleri"], "registered_pincodes": ["400099"], "verified_addresses": ["Western Express Highway, Andheri East, Mumbai 400099"]}
]

def seed_database():
    """
    Creates tables if not created, and populates initial rule definitions and brand caches.
    """
    db: Session = SessionLocal()
    try:
        print("Initializing Database tables...")
        Base.metadata.create_all(bind=engine)
        
        # Ensure new column fix_suggestion exists in PostgreSQL
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE rule_definitions ADD COLUMN IF NOT EXISTS fix_suggestion VARCHAR;"))
            conn.commit()
        
        print(f"Seeding {len(RULE_DEFINITIONS_DATA)} Rule Definitions (12 Legal Metrology + 6 FSSAI Food)...")
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
        
        print("Seeding Manufacturer Cache...")
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
        print("Database seeding completed successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
