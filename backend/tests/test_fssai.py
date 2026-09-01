import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.app.stages.stage8_fssai import (
    validate_fssai_syntax,
    check_fssai_3tier,
    validate_nutrition_table,
    validate_veg_nonveg_logo,
    validate_ingredients_descending_order,
    validate_allergen_declaration,
    validate_expiry_date_declaration
)
from backend.app.stages.stage6_rules import run_compliance_checks
from backend.app.core.database import SessionLocal

def test_fssai_all_checks():
    db = SessionLocal()
    try:
        print("\n=======================================================")
        print("TEST 1: FSSAI License 3-Tier Verification")
        print("=======================================================")
        
        # 1a. Tier 3 Cache Hit (Britannia verified license)
        res_cache = check_fssai_3tier("10012011000167")
        print("Britannia License (10012011000167):", res_cache["status"], "->", res_cache["explanation"])
        assert res_cache["status"] == "pass"
        assert res_cache["tier_reached"] == 3
        assert "Britannia Industries Limited" in res_cache["explanation"]
        
        # 1b. Tier 1 Valid Syntax (State 07 Delhi, 2023 License)
        res_syntax = check_fssai_3tier("10723011000999")
        print("Valid Decoded License (10723011000999):", res_syntax["status"], "->", res_syntax["explanation"])
        assert res_syntax["status"] == "pass"
        assert res_syntax["tier_reached"] == 1
        assert "Delhi" in res_syntax["explanation"]
        
        # 1c. Invalid Syntax - Wrong Starting Digit (3)
        res_inv1 = check_fssai_3tier("30723011000999")
        print("Invalid Digit 1 (30723011000999):", res_inv1["status"], "->", res_inv1["explanation"])
        assert res_inv1["status"] == "fail"
        
        # 1d. Invalid Syntax - Wrong State Code (99)
        res_inv2 = check_fssai_3tier("19923011000999")
        print("Invalid State Code (19923011000999):", res_inv2["status"], "->", res_inv2["explanation"])
        assert res_inv2["status"] == "fail"
        
        # 1e. Invalid Length (10 digits)
        res_inv3 = check_fssai_3tier("1072301100")
        print("Short Length (1072301100):", res_inv3["status"], "->", res_inv3["explanation"])
        assert res_inv3["status"] == "fail"

        print("\n=======================================================")
        print("TEST 2: Nutrition Information Table & Calculations")
        print("=======================================================")
        
        nut_compliant = {
            "energy": 460.0,
            "protein": 7.5,
            "carbohydrates": 68.0,
            "total_sugars": 22.0,
            "added_sugars": 19.5,
            "total_fat": 17.5,
            "saturated_fat": 8.0,
            "trans_fat": 0.05,
            "sodium": 280.0
        }
        res_nut1 = validate_nutrition_table(nut_compliant)
        print("Compliant Nutrition:", res_nut1["status"], "->", res_nut1["explanation"])
        assert res_nut1["status"] == "pass"
        
        nut_bad_fat = {
            "energy": 450.0,
            "protein": 6.0,
            "carbohydrates": 60.0,
            "total_fat": 10.0,
            "saturated_fat": 15.0,
            "trans_fat": 0.1,
            "sodium": 100.0
        }
        res_nut2 = validate_nutrition_table(nut_bad_fat)
        print("Bad Fat Breakdown:", res_nut2["status"], "->", res_nut2["explanation"])
        assert res_nut2["status"] == "fail"
        assert "Saturated fat" in res_nut2["explanation"]
        
        nut_bad_sugars = {
            "energy": 400.0,
            "protein": 5.0,
            "carbohydrates": 40.0,
            "added_sugars": 55.0,
            "total_fat": 12.0,
            "saturated_fat": 5.0,
            "trans_fat": 0.0,
            "sodium": 50.0
        }
        res_nut3 = validate_nutrition_table(nut_bad_sugars)
        print("Bad Sugar Breakdown:", res_nut3["status"], "->", res_nut3["explanation"])
        assert res_nut3["status"] == "fail"
        assert "Added sugars" in res_nut3["explanation"]

        print("\n=======================================================")
        print("TEST 3: Veg / Non-Veg Logo & Geometric Sizing")
        print("=======================================================")
        
        res_veg1 = validate_veg_nonveg_logo({"type": "veg", "color": "green", "inner_shape": "circle", "square_size_mm": 8.5}, pdp_area_cm2=150.0)
        print("Compliant Veg Logo:", res_veg1["status"], "->", res_veg1["explanation"])
        assert res_veg1["status"] == "pass"
        
        res_veg2 = validate_veg_nonveg_logo({"type": "veg", "color": "green", "inner_shape": "circle", "square_size_mm": 4.0}, pdp_area_cm2=150.0)
        print("Undersized Logo:", res_veg2["status"], "->", res_veg2["explanation"])
        assert res_veg2["status"] == "fail"
        assert "below statutory minimum" in res_veg2["explanation"]

        print("\n=======================================================")
        print("TEST 4: Ingredients List Descending Order (QUID)")
        print("=======================================================")
        
        ing_valid = "Refined Wheat Flour (65%), Sugar (20%), Refined Palm Oil (12%), Invert Sugar Syrup (2%), Iodised Salt"
        res_ing1 = validate_ingredients_descending_order(ing_valid)
        print("Descending Ingredients:", res_ing1["status"], "->", res_ing1["explanation"])
        assert res_ing1["status"] == "pass"
        
        ing_invalid = "Refined Wheat Flour (40%), Sugar (45%), Palm Oil (10%)"
        res_ing2 = validate_ingredients_descending_order(ing_invalid)
        print("Violating Order Ingredients:", res_ing2["status"], "->", res_ing2["explanation"])
        assert res_ing2["status"] == "fail"
        assert "Descending Order Violation" in res_ing2["explanation"]

        print("\n=======================================================")
        print("TEST 5: Mandatory Allergen Declaration")
        print("=======================================================")
        
        ing_text = "Wheat Flour, Sugar, Milk Solids, Butter, Emulsifier (Soy Lecithin)"
        allergen_stmt = "Contains: Wheat (Gluten), Milk, Soy."
        res_all1 = validate_allergen_declaration(ing_text, allergen_stmt)
        print("Compliant Allergen:", res_all1["status"], "->", res_all1["explanation"])
        assert res_all1["status"] == "pass"
        
        ing_text_missing = "Wheat Flour, Sugar, Peanut Butter, Cashew Nuts"
        res_all2 = validate_allergen_declaration(ing_text_missing, None)
        print("Missing Allergen Warning:", res_all2["status"], "->", res_all2["explanation"])
        assert res_all2["status"] == "fail"
        assert "lacks a separate 'Contains:'" in res_all2["explanation"]

        print("\n=======================================================")
        print("TEST 6: Expiry Date vs 'Best Before' Mandate")
        print("=======================================================")
        
        res_exp1 = validate_expiry_date_declaration(mfg_date="08/2026", expiry_date="02/2027", best_before_date="Best before 6 months")
        print("Compliant Expiry Date:", res_exp1["status"], "->", res_exp1["explanation"])
        assert res_exp1["status"] == "pass"
        
        res_exp2 = validate_expiry_date_declaration(mfg_date="08/2026", expiry_date=None, best_before_date="Best before 6 months from manufacture")
        print("Best Before Only Violation:", res_exp2["status"], "->", res_exp2["explanation"])
        assert res_exp2["status"] == "fail"
        assert "Best Before' is optional and cannot substitute" in res_exp2["explanation"]

        print("\n=======================================================")
        print("TEST 7: Full 25-Rule Pipeline Evaluation (Food Product)")
        print("=======================================================")
        
        sample_food_package = {
            "generic_name": "Butter Cookies",
            "mrp": "Rs. 75.00 (inclusive of all taxes)",
            "net_quantity": "200 g",
            "mfg_date": "08/2026",
            "country_of_origin": "India",
            "manufacturer_name": "Britannia Industries Limited",
            "manufacturer_address": "5/1A, Hungerford Street, Kolkata 700017",
            "consumer_care_email": "care@britannia.com",
            "consumer_care_phone": "1800 425 4449",
            "consumer_care_name": "Britannia Consumer Cell",
            "consumer_care_address": "Prestige Shantiniketan, Whitefield, Bangalore 560048",
            "is_imported": False,
            "fssai_license_no": "10012011000167",
            "nutrition_table": {
                "energy": 490.0,
                "protein": 7.0,
                "carbohydrates": 65.0,
                "total_sugars": 22.0,
                "added_sugars": 18.0,
                "total_fat": 22.0,
                "saturated_fat": 10.0,
                "trans_fat": 0.1,
                "sodium": 320.0
            },
            "ingredients_text": "Refined Wheat Flour (60%), Sugar (20%), Butter (15%), Salt",
            "allergen_statement": "Contains: Wheat (Gluten), Milk.",
            "veg_nonveg": "veg",
            "expiry_date": "02/2027",
            "best_before_date": "Best before 6 months"
        }
        
        all_results = run_compliance_checks(sample_food_package, "photo", 1.5, db)
        print(f"Total Evaluated Rules: {len(all_results)} (12 Legal Metrology + 6 FSSAI + 7 Apparel Exempt)")
        assert len(all_results) == 25
        
        fails = [c for c in all_results if c["status"] == "fail"]
        print(f"Total Fails on Compliant Food Product: {len(fails)}")
        assert len(fails) == 0, f"Expected 0 fails, got: {fails}"
        
        print("\nALL 6 FSSAI CHECKS + FULL 25-RULE PIPELINE PASSED WITH 100% ACCURACY!")
        
    finally:
        db.close()

if __name__ == "__main__":
    test_fssai_all_checks()
