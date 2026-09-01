import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.app.stages.stage6_rules import run_compliance_checks
from backend.app.core.database import SessionLocal

def test_category_routing():
    db = SessionLocal()
    try:
        print("\n=======================================================")
        print("TEST 1: Category 'food' (Food & Beverage Mode)")
        print("=======================================================")
        
        food_sample = {
            "generic_name": "Premium Tea",
            "mrp": "Rs. 250.00 (inclusive of all taxes)",
            "net_quantity": "500 g",
            "mfg_date": "08/2026",
            "country_of_origin": "India",
            "manufacturer_name": "Tata Consumer Products Limited",
            "manufacturer_address": "1, Bishop Lefroy Road, Kolkata 700020",
            "consumer_care_email": "care@tataconsumer.com",
            "consumer_care_phone": "1800 22 2444",
            "consumer_care_name": "Tata Care",
            "consumer_care_address": "Kolkata 700020",
            "fssai_license_no": "10014031001025",
            "nutrition_table": {"energy": 100, "protein": 2, "carbohydrates": 20, "total_fat": 0.5},
            "ingredients_text": "Tea Leaves (100%)",
            "veg_nonveg": "veg",
            "expiry_date": "08/2027"
        }
        
        food_results = run_compliance_checks(food_sample, "photo", 1.5, db, target_category="food")
        print(f"Total Evaluated Rules (Food Mode): {len(food_results)}")
        assert len(food_results) == 25
        
        # FSSAI checks should be active (pass/fail, not exempt)
        fssai_active = [c for c in food_results if c["rule_id"].startswith("fssai_") and c["status"] != "exempt"]
        print(f"Active FSSAI checks count: {len(fssai_active)}")
        assert len(fssai_active) == 6
        
        # Apparel checks should all be exempt
        apparel_exempt = [c for c in food_results if c["rule_id"].startswith("apparel_") and c["status"] == "exempt"]
        print(f"Exempt Apparel checks count: {len(apparel_exempt)}")
        assert len(apparel_exempt) == 7

        print("\n=======================================================")
        print("TEST 2: Category 'apparel' (Apparel & Textile Mode)")
        print("=======================================================")
        
        apparel_sample = {
            "generic_name": "Men's Cotton Shirt",
            "mrp": "Rs. 1299.00 (inclusive of all taxes)",
            "net_quantity": "1 N",
            "mfg_date": "08/2026",
            "country_of_origin": "India",
            "manufacturer_name": "Raymond Limited",
            "manufacturer_address": "Plot No. 156, Village Zadgaon, Ratnagiri 415612",
            "consumer_care_email": "care@raymond.in",
            "consumer_care_phone": "1800 222 000",
            "consumer_care_name": "Raymond Care",
            "consumer_care_address": "Thane West 400606",
            "fiber_composition": "100% Cotton",
            "apparel_size": "Size: L (Chest 102 cm, Length 76 cm)"
        }
        
        apparel_results = run_compliance_checks(apparel_sample, "photo", 1.5, db, target_category="apparel")
        print(f"Total Evaluated Rules (Apparel Mode): {len(apparel_results)}")
        assert len(apparel_results) == 25
        
        # Apparel checks should be active
        apparel_active = [c for c in apparel_results if c["rule_id"].startswith("apparel_") and c["status"] != "exempt"]
        print(f"Active Apparel checks count: {len(apparel_active)}")
        assert len(apparel_active) == 7
        
        # FSSAI checks should all be exempt
        fssai_exempt = [c for c in apparel_results if c["rule_id"].startswith("fssai_") and c["status"] == "exempt"]
        print(f"Exempt FSSAI checks count: {len(fssai_exempt)}")
        assert len(fssai_exempt) == 6

        print("\n=======================================================")
        print("TEST 3: Category 'general' (General Retail Mode)")
        print("=======================================================")
        
        general_sample = {
            "generic_name": "LED Lighting Bulb",
            "mrp": "Rs. 150.00 (inclusive of all taxes)",
            "net_quantity": "1 N",
            "mfg_date": "08/2026",
            "country_of_origin": "India",
            "manufacturer_name": "Wipro Consumer Care and Lighting",
            "manufacturer_address": "Doddakannelli, Sarjapur Road, Bangalore 560035",
            "consumer_care_email": "care@wipro.com",
            "consumer_care_phone": "1800 425 1969",
            "consumer_care_name": "Wipro Care",
            "consumer_care_address": "Bangalore 560035"
        }
        
        general_results = run_compliance_checks(general_sample, "photo", 1.5, db, target_category="general")
        print(f"Total Evaluated Rules (General Mode): {len(general_results)}")
        assert len(general_results) == 25
        
        # Both FSSAI and Apparel checks should be exempt
        fssai_exempt_gen = [c for c in general_results if c["rule_id"].startswith("fssai_") and c["status"] == "exempt"]
        apparel_exempt_gen = [c for c in general_results if c["rule_id"].startswith("apparel_") and c["status"] == "exempt"]
        print(f"General Mode: Exempt FSSAI: {len(fssai_exempt_gen)} / 6, Exempt Apparel: {len(apparel_exempt_gen)} / 7")
        assert len(fssai_exempt_gen) == 6
        assert len(apparel_exempt_gen) == 7
        
        # Legal Metrology rules (check_1 to check_12) should all be active
        lm_checks = [c for c in general_results if not c["rule_id"].startswith("fssai_") and not c["rule_id"].startswith("apparel_")]
        assert len(lm_checks) == 12
        
        print("\n3-CATEGORY COMPLIANCE ROUTING TEST PASSED WITH 100% ACCURACY!")
        
    finally:
        db.close()

if __name__ == "__main__":
    test_category_routing()
