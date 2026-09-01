import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.app.stages.stage9_textile import (
    validate_fiber_composition,
    validate_apparel_size_metric,
    validate_apparel_mrp_fuzzy,
    validate_apparel_generic_name,
    validate_apparel_consumer_care,
    validate_apparel_mfg_date,
    validate_apparel_country_of_origin
)
from backend.app.stages.stage6_rules import run_compliance_checks
from backend.app.core.database import SessionLocal

def test_apparel_all_checks():
    db = SessionLocal()
    try:
        print("\n=======================================================")
        print("TEST 1: Fiber Composition 100% Deterministic Math Validator")
        print("=======================================================")
        
        # 1a. Compliant dual blend (60% Cotton, 40% Polyester = 100%)
        res_fib1 = validate_fiber_composition("Material: 60% Cotton, 40% Polyester")
        print("Dual Blend (60+40):", res_fib1["status"], "->", res_fib1["explanation"])
        assert res_fib1["status"] == "pass"
        assert res_fib1["sum"] == 100.0
        
        # 1b. Compliant 100% single fiber
        res_fib2 = validate_fiber_composition("100% Pure Silk Fabric")
        print("100% Single Fiber:", res_fib2["status"], "->", res_fib2["explanation"])
        assert res_fib2["status"] == "pass"
        assert res_fib2["sum"] == 100.0
        
        # 1c. Math Violation: Under-sum (70% Cotton + 20% Polyester = 90%)
        res_fib3 = validate_fiber_composition("Composition: 70% Cotton, 20% Polyester")
        print("Under-sum (70+20=90%):", res_fib3["status"], "->", res_fib3["explanation"])
        assert res_fib3["status"] == "fail"
        assert "Fiber Math Violation" in res_fib3["explanation"]
        assert res_fib3["sum"] == 90.0
        
        # 1d. Math Violation: Over-sum (55% Cotton + 50% Polyester = 105%)
        res_fib4 = validate_fiber_composition("Content: 55% Cotton, 50% Polyester")
        print("Over-sum (55+50=105%):", res_fib4["status"], "->", res_fib4["explanation"])
        assert res_fib4["status"] == "fail"
        assert "Fiber Math Violation" in res_fib4["explanation"]

        print("\n=======================================================")
        print("TEST 2: Size & Metric Dimensions Pairing Engine")
        print("=======================================================")
        
        # 2a. Compliant Letter Size + Physical Dimensions in cm
        res_sz1 = validate_apparel_size_metric("Size: L (Chest 102 cm, Length 76 cm)")
        print("Letter + Metric (L, 102 cm):", res_sz1["status"], "->", res_sz1["explanation"])
        assert res_sz1["status"] == "pass"
        assert res_sz1["is_paired"] is True
        
        # 2b. Compliant Numeric Size + Physical Dimensions
        res_sz2 = validate_apparel_size_metric("Size: 32 (Waist 81 cm)")
        print("Numeric + Metric (32, 81 cm):", res_sz2["status"], "->", res_sz2["explanation"])
        assert res_sz2["status"] == "pass"
        
        # 2c. Non-Compliant Letter Size Alone (Size: XL without cm measurements)
        res_sz3 = validate_apparel_size_metric("Size: XL. Made in India.")
        print("Letter Size Only (XL):", res_sz3["status"], "->", res_sz3["explanation"])
        assert res_sz3["status"] == "fail"
        assert "without mandatory metric dimensions" in res_sz3["explanation"]

        print("\n=======================================================")
        print("TEST 3: MRP & Fuzzy Tax Suffix Matcher")
        print("=======================================================")
        
        # 3a. Standard Rupee symbol with explicit tax phrase
        res_mrp1 = validate_apparel_mrp_fuzzy("MRP: ₹1,299.00 (inclusive of all taxes)")
        print("Standard MRP ₹1299:", res_mrp1["status"], "->", res_mrp1["explanation"])
        assert res_mrp1["status"] == "pass"
        
        # 3b. Wrinkled tag OCR typo (inlc. of all faxes)
        res_mrp2 = validate_apparel_mrp_fuzzy("MRP: Rs. 899.00 inlc. of all faxes")
        print("Wrinkled Tag Fuzzy Match:", res_mrp2["status"], "->", res_mrp2["explanation"])
        assert res_mrp2["status"] == "pass"
        
        # 3c. Missing tax phrase
        res_mrp3 = validate_apparel_mrp_fuzzy("MRP: ₹799.00 only")
        print("Missing Tax Suffix:", res_mrp3["status"], "->", res_mrp3["explanation"])
        assert res_mrp3["status"] == "fail"

        print("\n=======================================================")
        print("TEST 4: Generic Name Taxonomy Match (Rule 6(1)(b))")
        print("=======================================================")
        
        # 4a. Recognized taxonomy term (Shirt)
        res_gen1 = validate_apparel_generic_name("Raymond Men's Cotton Formal Shirt", "Formal Shirt")
        print("Taxonomy Match (Shirt):", res_gen1["status"], "->", res_gen1["explanation"])
        assert res_gen1["status"] == "pass"
        assert res_gen1["generic_name"] == "Shirt"
        
        # 4b. Recognized taxonomy term (T-Shirt)
        res_gen2 = validate_apparel_generic_name("Graphic Print Crew Neck Tee", "Graphic Tee")
        print("Taxonomy Match (Tee -> T-Shirt):", res_gen2["status"], "->", res_gen2["explanation"])
        assert res_gen2["status"] == "pass"
        assert res_gen2["generic_name"] == "T-Shirt"
        
        # 4c. Unrecognized generic name (Brand only)
        res_gen3 = validate_apparel_generic_name("XYZ Brand Supreme Edition 2026", "XYZ Supreme")
        print("Brand Name Only:", res_gen3["status"], "->", res_gen3["explanation"])
        assert res_gen3["status"] == "fail"

        print("\n=======================================================")
        print("TEST 5: Consumer Care 3-Channel Verification (Rule 6(1)(f))")
        print("=======================================================")
        
        # 5a. All 3 channels present
        fields_cc_full = {
            "consumer_care_phone": "1800 222 555",
            "consumer_care_email": "care@raymond.in",
            "consumer_care_address": "Jekegram, Pokhran Road, Thane 400606"
        }
        res_cc1 = validate_apparel_consumer_care(fields_cc_full, "")
        print("Full 3-Channel Care:", res_cc1["status"], "->", res_cc1["explanation"])
        assert res_cc1["status"] == "pass"
        
        # 5b. Missing email channel
        fields_cc_partial = {
            "consumer_care_phone": "9876543210",
            "consumer_care_email": None,
            "consumer_care_address": "Thane, Mumbai 400606"
        }
        res_cc2 = validate_apparel_consumer_care(fields_cc_partial, "")
        print("Missing Email Channel:", res_cc2["status"], "->", res_cc2["explanation"])
        assert res_cc2["status"] == "fail"
        assert "valid email address" in res_cc2["explanation"]

        print("\n=======================================================")
        print("TEST 6: Contextual Manufacturing / Packing Date")
        print("=======================================================")
        
        # 6a. Contextual date (MFD: 08/2026)
        res_mfg1 = validate_apparel_mfg_date("MFD: 08/2026. Made in India.")
        print("Contextual MFD (MFD: 08/2026):", res_mfg1["status"], "->", res_mfg1["explanation"])
        assert res_mfg1["status"] == "pass"
        
        # 6b. Bare uncontextualized date
        res_mfg2 = validate_apparel_mfg_date("08/2026. Batch 402.")
        print("Bare Date (08/2026 without MFD/PKD):", res_mfg2["status"], "->", res_mfg2["explanation"])
        assert res_mfg2["status"] == "fail"

        print("\n=======================================================")
        print("TEST 7: Contextual Country of Origin")
        print("=======================================================")
        
        # 7a. Explicit origin declaration
        res_co1 = validate_apparel_country_of_origin("Country of Origin: India")
        print("Explicit Origin:", res_co1["status"], "->", res_co1["explanation"])
        assert res_co1["status"] == "pass"
        
        # 7b. Address mention only (Anti-Halo test)
        res_co2 = validate_apparel_country_of_origin("Manufactured by ABC Corp, Mumbai, India")
        print("Address Mention Only:", res_co2["status"], "->", res_co2["explanation"])
        assert res_co2["status"] == "fail"

        print("\n=======================================================")
        print("TEST 8: Full 25-Rule Pipeline Evaluation (Apparel Product)")
        print("=======================================================")
        
        sample_apparel_item = {
            "generic_name": "Men's Cotton Shirt",
            "mrp": "Rs. 1499.00 (inclusive of all taxes)",
            "net_quantity": "1 N",
            "mfg_date": "08/2026",
            "country_of_origin": "India",
            "manufacturer_name": "Raymond Limited",
            "manufacturer_address": "Plot No. 156, Village Zadgaon, Ratnagiri 415612",
            "consumer_care_email": "care@raymond.in",
            "consumer_care_phone": "1800 222 000",
            "consumer_care_name": "Raymond Customer Cell",
            "consumer_care_address": "Jekegram, Pokhran Road No. 1, Thane West 400606",
            "is_imported": False,
            "fiber_composition": "100% Cotton",
            "apparel_size": "Size: L (Chest 102 cm, Length 76 cm)"
        }
        
        # Build raw_text containing all labels
        raw_text_payload = (
            "Raymond Men's Cotton Formal Shirt\n"
            "Material: 100% Cotton\n"
            "Size: L (Chest 102 cm, Length 76 cm)\n"
            "Net Quantity: 1 N\n"
            "MRP: Rs. 1499.00 (inclusive of all taxes)\n"
            "MFD: 08/2026\n"
            "Country of Origin: India\n"
            "Manufactured by: Raymond Limited, Plot No. 156, Village Zadgaon, Ratnagiri 415612\n"
            "Consumer Care: 1800 222 000, care@raymond.in, Thane West 400606"
        )
        sample_apparel_item["raw_text"] = raw_text_payload
        
        all_results = run_compliance_checks(sample_apparel_item, "photo", 1.5, db)
        print(f"Total Evaluated Rules: {len(all_results)} (12 Legal Metrology + 6 FSSAI Exempt + 7 Apparel)")
        assert len(all_results) == 25
        
        # Food rules should be exempt
        food_rules = [c for c in all_results if c["rule_id"].startswith("fssai_")]
        assert len(food_rules) == 6
        for fr in food_rules:
            assert fr["status"] == "exempt"
            
        # Apparel rules should all pass
        apparel_rules = [c for c in all_results if c["rule_id"].startswith("apparel_")]
        assert len(apparel_rules) == 7
        for ar in apparel_rules:
            assert ar["status"] == "pass", f"Apparel rule {ar['rule_id']} failed: {ar['explanation']}"
            
        fails = [c for c in all_results if c["status"] == "fail"]
        print(f"Total Fails on Compliant Apparel Product: {len(fails)}")
        assert len(fails) == 0, f"Expected 0 fails, got: {fails}"
        
        print("\nALL 7 APPAREL CHECKS + FULL 25-RULE PIPELINE PASSED WITH 100% ACCURACY!")
        
    finally:
        db.close()

if __name__ == "__main__":
    test_apparel_all_checks()
