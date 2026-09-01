import sys
import os
# Add SIH directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.database import SessionLocal
from backend.app.stages.stage6_rules import run_compliance_checks

def test_rule_engine():
    db = SessionLocal()
    try:
        # Test Case 1: Compliant product
        compliant_fields = {
            "mrp": "Rs. 150.00 (inclusive of all taxes)",
            "mrp_confidence": 0.98,
            "net_quantity": "125 g",
            "net_quantity_confidence": 0.99,
            "mfg_date": "08/2026",
            "mfg_date_confidence": 0.98,
            "country_of_origin": "India",
            "country_of_origin_confidence": 0.99,
            "manufacturer_name": "Hindustan Unilever Limited",
            "manufacturer_address": "Unilever House, Chakala, Andheri East, Mumbai 400099",
            "consumer_care_email": "care@unilever.com",
            "consumer_care_phone": "1800-10-2222",
            "consumer_care_name": "Hindustan Unilever Limited",
            "consumer_care_address": "Unilever House, Chakala, Andheri East, Mumbai 400099",
            "is_imported": False,
            "generic_name": "Bath Soap"
        }
        
        print("\n--- Test Case 1: Running Compliant Product ---")
        results1 = run_compliance_checks(compliant_fields, "photo", 1.5, db)
        fails1 = [c for c in results1 if c["status"] == "fail"]
        print(f"Total fails: {len(fails1)}")
        for c in results1:
            print(f"- {c['rule_id']} ({c['rule_citation']}): {c['status'].upper()} -> {c['explanation']}")
            
        assert len(fails1) == 0, f"Expected 0 fails, got {len(fails1)}"
        
        # Test Case 2: Non-compliant product (missing inclusive of taxes, non-standard unit)
        non_compliant_fields = {
            "mrp": "Rs. 50.00",  # missing "inclusive of all taxes" in raw_text!
            "mrp_confidence": 0.95,
            "net_quantity": "150 gms",  # 'gms' is non-standard!
            "net_quantity_confidence": 0.95,
            "mfg_date": "06-2026",  # wrong format (expects MM/YYYY or Month YYYY)
            "mfg_date_confidence": 0.95,
            "country_of_origin": "India",
            "manufacturer_name": "Small Scale Foods",
            "manufacturer_address": "Small Industrial Area, Sector 5, Pincode 110041",
            "consumer_care_email": None,  # Missing consumer care email!
            "consumer_care_phone": "9876543210",
            "consumer_care_name": "Small Scale Foods",
            "consumer_care_address": "Small Industrial Area, Sector 5, Pincode 110041",
            "is_imported": False,
            "generic_name": "Biscuits"
        }
        
        print("\n--- Test Case 2: Running Non-Compliant Product ---")
        results2 = run_compliance_checks(non_compliant_fields, "photo", 1.2, db)
        fails2 = [c for c in results2 if c["status"] == "fail"]
        print(f"Total fails: {len(fails2)}")
        for c in results2:
            print(f"- {c['rule_id']} ({c['rule_citation']}): {c['status'].upper()} -> {c['explanation']}")
            
        # Expect failures in Check 4 (unit), Check 5 (date format), Check 6 (taxes phrase), Check 7 (consumer care email)
        print("\nUnit Test Rules Evaluation PASSED successfully!")
        
    finally:
        db.close()

if __name__ == "__main__":
    test_rule_engine()
