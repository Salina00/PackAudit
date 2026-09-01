import sys
import os
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.app.stages.stage1_upload import (
    validate_product_url,
    scrape_ecommerce_listing,
    InvalidProductUrlException,
    ScrapeBlockedException,
    ScrapeFailedException
)
from backend.app.stages.stage6_rules import run_compliance_checks
from backend.app.stages.stage7_report import save_scan_results_to_db, generate_pdf_report
from backend.app.core.database import SessionLocal

def test_acceptance_criteria():
    db = SessionLocal()
    try:
        print("\n==========================================")
        print("TEST 1: URL Pattern Validation")
        print("==========================================")
        
        # Valid URLs
        valid_urls = [
            "https://www.amazon.in/Tata-Tea-Premium-Desh-Chai/dp/B00T78X046/",
            "https://amazon.in/gp/product/B08XYZ1234",
            "https://www.flipkart.com/britannia-good-day-cashew-cookies/p/itmf3j5678",
            "https://dl.flipkart.com/dl/p/itm12345?pid=CKY1234"
        ]
        for u in valid_urls:
            is_valid, msg = validate_product_url(u)
            print(f"URL: {u} -> Valid: {is_valid}")
            assert is_valid is True, f"Expected {u} to be valid, got: {msg}"
            
        # Invalid search/category/cart URLs
        invalid_urls = [
            ("https://www.amazon.in/s?k=tea", "search or category page"),
            ("https://www.amazon.in/gp/cart/view.html", "search or category page"),
            ("https://www.flipkart.com/search?q=biscuits", "Flipkart search or store page"),
            ("https://www.flipkart.com/viewcart", "Flipkart search or store page"),
            ("https://example.com/search?q=oil", "homepage or search page")
        ]
        for u, expected_msg_fragment in invalid_urls:
            is_valid, msg = validate_product_url(u)
            print(f"URL: {u} -> Valid: {is_valid}, Message: '{msg}'")
            assert is_valid is False, f"Expected {u} to be rejected"
            assert expected_msg_fragment.lower() in (msg or "").lower()
            
        print("\n==========================================")
        print("TEST 2: Complete Scrape -> Full Compliance Report")
        print("==========================================")
        
        # Mocking requests.get to return a valid HTML product page
        mock_html_complete = """
        <html>
            <body>
                <span id="productTitle"> Tata Tea Gold Leaf Tea </span>
                <span class="a-price"><span class="a-offscreen"> ₹450.00 </span></span>
                <table id="detailBullets_sidebar_table">
                    <tr><td>Country of Origin: India</td></tr>
                    <tr><td>Manufacturer: Tata Consumer Products Limited, 1 Bishop Lefroy Road, Kolkata 700020</td></tr>
                    <tr><td>Net Quantity: 500 g</td></tr>
                    <tr><td>Date First Available: 01/2026</td></tr>
                </table>
            </body>
        </html>
        """
        
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = mock_html_complete
            mock_get.return_value = mock_resp
            
            scraped = scrape_ecommerce_listing("https://www.amazon.in/dp/B00COMPLETE")
            fields = scraped["fields"]
            print(f"Scraped fields successfully: {fields}")
            assert fields["generic_name"] == "Tata Tea Gold Leaf Tea"
            assert fields["mrp"] == "₹450.00"
            assert fields["country_of_origin"] == "India"
            assert fields["net_quantity"] == "500 g"
            
            # Run compliance rules on complete scrape
            extracted_fields = {
                "generic_name": fields.get("generic_name"),
                "mrp": fields.get("mrp"),
                "net_quantity": fields.get("net_quantity"),
                "manufacturer_name": fields.get("manufacturer_name"),
                "manufacturer_address": fields.get("manufacturer_address"),
                "country_of_origin": fields.get("country_of_origin"),
                "consumer_care_email": "care@tataconsumer.com",
                "consumer_care_phone": "1800 22 2444",
                "consumer_care_name": fields.get("manufacturer_name"),
                "consumer_care_address": fields.get("manufacturer_address"),
                "mfg_date": fields.get("mfg_date"),
                "is_imported": False,
                "listing_fields": fields
            }
            results = run_compliance_checks(extracted_fields, "url", None, db)
            print(f"Complete listing compliance checks count: {len(results)}")
            # Verify no crashes and description exists in all checks
            for r in results:
                assert "description" in r
                assert "rule_citation" in r
                assert "status" in r
                print(f" - {r['rule_id']}: {r['status'].upper()} -> {r['explanation']}")
                
        print("\n==========================================")
        print("TEST 3: Partial Scrape (Missing declarations) -> Graceful Degradation")
        print("==========================================")
        
        # HTML with Title & Price only (Country of Origin and Net Quantity are missing)
        mock_html_partial = """
        <html>
            <body>
                <span id="productTitle"> Sample Unbranded Cookies </span>
                <span class="a-price"><span class="a-offscreen"> ₹50.00 </span></span>
            </body>
        </html>
        """
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = mock_html_partial
            mock_get.return_value = mock_resp
            
            scraped = scrape_ecommerce_listing("https://www.amazon.in/dp/B00PARTIAL")
            fields = scraped["fields"]
            print(f"Scraped partial fields: {fields}")
            assert fields.get("generic_name") == "Sample Unbranded Cookies"
            assert fields.get("country_of_origin") is None
            assert fields.get("net_quantity") is None
            
            # Feed partial fields to rule engine
            extracted_fields_partial = {
                "generic_name": fields.get("generic_name"),
                "mrp": fields.get("mrp"),
                "net_quantity": fields.get("net_quantity"),
                "manufacturer_name": fields.get("manufacturer_name"),
                "manufacturer_address": fields.get("manufacturer_address"),
                "country_of_origin": fields.get("country_of_origin"),
                "consumer_care_email": fields.get("consumer_care_email"),
                "consumer_care_phone": fields.get("consumer_care_phone"),
                "consumer_care_name": fields.get("consumer_care_name"),
                "consumer_care_address": fields.get("consumer_care_address"),
                "mfg_date": fields.get("mfg_date"),
                "is_imported": False,
                "listing_fields": fields
            }
            
            results_partial = run_compliance_checks(extracted_fields_partial, "url", None, db)
            print(f"Partial listing checks count: {len(results_partial)}")
            
            # Check 8 (Country of origin) must fail gracefully
            check_8 = next(c for c in results_partial if c["rule_id"] == "check_8")
            assert check_8["status"] == "fail"
            print(f"Check 8 status: {check_8['status']} ({check_8['explanation']})")
            
            # Check 4 (Net Quantity) must fail gracefully
            check_4 = next(c for c in results_partial if c["rule_id"] == "check_4")
            assert check_4["status"] == "fail"
            print(f"Check 4 status: {check_4['status']} ({check_4['explanation']})")
            
            # Check 12 (Rule 23 E-Commerce) must fail because mandatory declarations are missing on digital listing
            check_12 = next(c for c in results_partial if c["rule_id"] == "check_12")
            assert check_12["status"] == "fail"
            print(f"Check 12 status: {check_12['status']} ({check_12['explanation']})")
            
        print("\n==========================================")
        print("TEST 4: Blocked / CAPTCHA Page -> Clear Actionable Message")
        print("==========================================")
        
        mock_captcha_html = """
        <html>
            <head><title>Robot Check</title></head>
            <body>
                <p>Type the characters you see in this image to continue.</p>
                <form action="/errors/validateCaptcha"></form>
            </body>
        </html>
        """
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 503
            mock_resp.text = mock_captcha_html
            mock_get.return_value = mock_resp
            
            try:
                scrape_ecommerce_listing("https://www.amazon.in/dp/B00BLOCKED")
                assert False, "Expected ScrapeBlockedException"
            except ScrapeBlockedException as e:
                print(f"Blocked exception caught cleanly: '{str(e)}'")
                assert "This listing could not be read" in str(e)
                assert "upload a photo instead" in str(e)
                
        print("\n==========================================")
        print("ALL ACCEPTANCE CHECKS PASSED SUCCESSFULLY!")
        print("==========================================")
        
    finally:
        db.close()

if __name__ == "__main__":
    test_acceptance_criteria()
