import os
import re
import uuid
import urllib.parse
import logging
import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional, Tuple

from backend.app.core.config import settings

logger = logging.getLogger("packaudit.scraper")
logger.setLevel(logging.INFO)

class InvalidProductUrlException(Exception):
    """Raised when the URL is not a valid product page."""
    pass

class ScrapeBlockedException(Exception):
    """Raised when the platform blocks the request or serves a CAPTCHA."""
    pass

class ScrapeFailedException(Exception):
    """Raised when scraping fails due to missing selectors or unreadable page."""
    pass

def save_uploaded_file(file_bytes: bytes, filename: str) -> str:
    """
    Saves raw uploaded image bytes to the static upload directory
    with a unique UUID prefix to prevent collisions.
    Returns the absolute path to the saved file.
    """
    ext = os.path.splitext(filename)[1]
    if not ext:
        ext = ".jpg"  # default
        
    unique_filename = f"{uuid.uuid4()}{ext}"
    target_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
    
    with open(target_path, "wb") as f:
        f.write(file_bytes)
        
    return target_path

def validate_product_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validates whether the provided URL matches expected e-commerce product page patterns.
    Rejects search, category, cart, wishlist, or store URLs with clear actionable messages.
    """
    if not url or not isinstance(url, str):
        return False, "Please enter a valid URL."
        
    url_clean = url.strip()
    if not (url_clean.startswith("http://") or url_clean.startswith("https://")):
        return False, "URL must start with http:// or https://"
        
    try:
        parsed = urllib.parse.urlparse(url_clean)
    except Exception:
        return False, "Could not parse URL format."
        
    domain = (parsed.netloc or "").lower()
    path = (parsed.path or "").lower()
    query = (parsed.query or "").lower()
    
    if not domain:
        return False, "Invalid URL: missing domain name."
        
    # 1. Amazon validation
    if "amazon" in domain or "amzn" in domain:
        # Reject search / category / browse / cart / wishlist / store URLs
        search_indicators = [
            "/s", "/s?", "/search", "/b/", "/b?", "/browse", "/browse?",
            "/cart", "/gp/cart", "/wishlist", "/stores/", "/categories", "/deal", "/goldbox"
        ]
        if any(path.startswith(ind) or ind in path for ind in search_indicators):
            return False, "The provided URL is a search or category page, not a product page. Please provide a direct product link (e.g. amazon.in/dp/...) or upload a photo instead."
            
        # Product pattern checks
        is_amazon_product = (
            "/dp/" in path or
            "/gp/product/" in path or
            "/gp/aw/d/" in path or
            "/d/" in path or
            bool(re.search(r"/[A-Z0-9]{10}(?:[/?]|$)", path, re.IGNORECASE)) or
            "amzn.to" in domain or
            "amzn.in" in domain
        )
        if not is_amazon_product:
            return False, "The provided URL does not match an Amazon product detail page. Please ensure the link contains /dp/ or /gp/product/ (e.g. https://www.amazon.in/dp/B08...) or upload a photo instead."
            
        return True, None

    # 2. Flipkart validation
    if "flipkart" in domain or "fkrt" in domain:
        search_indicators = [
            "/search", "/viewcart", "/travel/", "/plus", "/account",
            "/grocery-supermart-store", "/offers-store", "/all-categories"
        ]
        if any(path.startswith(ind) or ind in path for ind in search_indicators):
            return False, "The provided URL is a Flipkart search or store page, not a product page. Please provide a direct product link or upload a photo instead."
            
        is_flipkart_product = (
            "/p/" in path or
            "/dl/" in path or
            "pid=" in query or
            "fkrt.it" in domain
        )
        if not is_flipkart_product:
            return False, "The provided URL does not appear to be a Flipkart product page. Please ensure the link contains /p/ or a product ID (pid=) or upload a photo instead."
            
        return True, None

    # 3. Generic / Other e-commerce domains
    if path in ["", "/"] or path.startswith("/search") or "search=" in query or "q=" in query:
        return False, "The provided URL is a homepage or search page. Please provide a direct product listing link or upload a photo instead."
        
    return True, None

def scrape_ecommerce_listing(url: str) -> Dict[str, Any]:
    """
    Scrapes an e-commerce product page and extracts statutory declarations defensively.
    Distinguishes clean scrape, partial scrape (missing fields), and blocked/CAPTCHA responses.
    """
    # 1. Validate URL first
    is_valid, validation_msg = validate_product_url(url)
    if not is_valid:
        raise InvalidProductUrlException(validation_msg or "Invalid product listing URL.")
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate",
        "Cache-Control": "max-age=0",
        "Upgrade-Insecure-Requests": "1"
    }
    
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    
    scraped_data: Dict[str, Any] = {
        "url": url,
        "source": "Amazon India" if "amazon" in domain else ("Flipkart" if "flipkart" in domain else domain),
        "raw_text": "",
        "fields": {}
    }
    
    # 2. Perform HTTP Request with diagnostic logging
    try:
        res = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
    except requests.exceptions.Timeout:
        logger.warning(f"Request timeout connecting to {url}")
        raise ScrapeBlockedException("This listing could not be read. Connection timed out. Platform may be rate-limiting requests. Try a direct product link, or upload a photo instead.")
    except requests.exceptions.RequestException as req_err:
        logger.warning(f"Request connection failure for {url}: {req_err}")
        raise ScrapeBlockedException("This listing could not be read. Could not connect to the platform. Try a direct product link, or upload a photo instead.")
        
    # Log status code and response sample for debugging
    status_code = res.status_code
    response_snippet = res.text[:400].replace("\n", " ").strip()
    logger.info(f"Scraper fetched {url} - Status: {status_code} - Body snippet: {response_snippet}")
    
    # Check for blocking status codes
    if status_code in [403, 429, 503]:
        logger.warning(f"Scraper blocked by {domain} (HTTP {status_code}). Snippet: {response_snippet}")
        raise ScrapeBlockedException("This listing could not be read. It may be blocked by the platform, or the URL may not be a product page. Try a direct product link, or upload a photo instead.")
    elif status_code != 200:
        logger.warning(f"Scraper received non-200 status ({status_code}) for {url}. Snippet: {response_snippet}")
        raise ScrapeFailedException("This listing could not be read. Platform returned an error page. Try a direct product link, or upload a photo instead.")
        
    # Check for CAPTCHA / Bot detection signatures in response body
    page_text_lower = res.text.lower()
    captcha_signatures = [
        "api-services-support@amazon.com",
        "type the characters you see in this image",
        "enter the characters you see below",
        "robot check",
        "validatecaptcha",
        "please verify you are a human",
        "access denied",
        "blockedsession"
    ]
    if any(sig in page_text_lower for sig in captcha_signatures):
        logger.warning(f"CAPTCHA signature detected for {url}. Snippet: {response_snippet}")
        raise ScrapeBlockedException("This listing could not be read. It may be blocked by the platform, or the URL may not be a product page. Try a direct product link, or upload a photo instead.")
        
    # 3. Parse HTML DOM defensively
    try:
        soup = BeautifulSoup(res.text, 'html.parser')
    except Exception as parse_err:
        logger.error(f"HTML parser error for {url}: {parse_err}")
        raise ScrapeFailedException("This listing could not be read. Page structure is unparseable. Try a direct product link, or upload a photo instead.")
        
    # Strip non-text elements
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
        
    scraped_data["raw_text"] = soup.get_text(separator=" ", strip=True)
    extracted_fields: Dict[str, Optional[str]] = {}
    
    # 4. Extract fields by platform
    if "amazon" in domain:
        # Title / Generic Name
        title_selectors = ["#productTitle", "#title", "h1.product-title-word-break", "span#productTitle"]
        for sel in title_selectors:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                extracted_fields["generic_name"] = el.get_text(strip=True)
                break
                
        # Price / MRP
        price_selectors = [
            ".a-price .a-offscreen",
            "span.priceToPay .a-offscreen",
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            "#corePrice_desktop .a-offscreen",
            "#corePriceDisplay_desktop_feature_div .a-offscreen",
            ".apexPriceToPay .a-offscreen"
        ]
        for sel in price_selectors:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                extracted_fields["mrp"] = el.get_text(strip=True)
                break
                
        # Structured specifications (Detail bullets / tables)
        detail_rows = soup.select("#detailBullets_feature_div li, #detailBullets_sidebar_table tr, #productDetails_techSpec_section_1 tr, #prodDetails tr, #productOverview_feature_div tr")
        for row in detail_rows:
            text = row.get_text(separator=" ", strip=True)
            text_l = text.lower()
            
            # Country of origin
            if ("country of origin" in text_l or "origin" in text_l) and "country_of_origin" not in extracted_fields:
                parts = text.split(":") if ":" in text else text.split("\n")
                if len(parts) > 1:
                    extracted_fields["country_of_origin"] = parts[1].strip()
                    
            # Manufacturer / Packer
            if ("manufacturer" in text_l or "packer" in text_l or "brand" in text_l) and "manufacturer_name" not in extracted_fields:
                parts = text.split(":") if ":" in text else text.split("\n")
                if len(parts) > 1:
                    val = parts[1].strip()
                    extracted_fields["manufacturer_name"] = val
                    extracted_fields["manufacturer_address"] = val # often includes address
                    
            # Net Quantity / Item Weight
            if ("net quantity" in text_l or "item weight" in text_l or "net content" in text_l or "weight" in text_l or "volume" in text_l) and "net_quantity" not in extracted_fields:
                parts = text.split(":") if ":" in text else text.split("\n")
                if len(parts) > 1:
                    extracted_fields["net_quantity"] = parts[1].strip()
                    
            # Date first available / Mfg date
            if ("date first available" in text_l or "manufacture" in text_l or "mfg" in text_l) and "mfg_date" not in extracted_fields:
                parts = text.split(":") if ":" in text else text.split("\n")
                if len(parts) > 1:
                    extracted_fields["mfg_date"] = parts[1].strip()

    elif "flipkart" in domain:
        # Title / Generic Name
        title_selectors = ["span.B_NuCI", "h1.VU-ZEz", "span._35KyD6", "h1._6EBuvT", "h1.C7fEHH"]
        for sel in title_selectors:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                extracted_fields["generic_name"] = el.get_text(strip=True)
                break
                
        # Price / MRP
        price_selectors = ["div._30jeq3._16Jk6d", "div._30jeq3", "div.Nx9bqj.CxhGGd", "div.Nx9bqj"]
        for sel in price_selectors:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                extracted_fields["mrp"] = el.get_text(strip=True)
                break
                
        # Specifications table
        spec_rows = soup.select("table._14cfVK tr, div._1UhVsV tr, div._3k-BhJ tr, div.G6XhRU")
        for row in spec_rows:
            text = row.get_text(separator=" ", strip=True)
            text_l = text.lower()
            
            if ("country of origin" in text_l or "origin" in text_l) and "country_of_origin" not in extracted_fields:
                parts = text.split(":") if ":" in text else text.split("\n")
                if len(parts) > 1:
                    extracted_fields["country_of_origin"] = parts[1].strip()
                    
            if ("manufacturer" in text_l or "packer" in text_l) and "manufacturer_name" not in extracted_fields:
                parts = text.split(":") if ":" in text else text.split("\n")
                if len(parts) > 1:
                    val = parts[1].strip()
                    extracted_fields["manufacturer_name"] = val
                    extracted_fields["manufacturer_address"] = val
                    
            if ("net quantity" in text_l or "weight" in text_l or "quantity" in text_l) and "net_quantity" not in extracted_fields:
                parts = text.split(":") if ":" in text else text.split("\n")
                if len(parts) > 1:
                    extracted_fields["net_quantity"] = parts[1].strip()

    # 5. Check if page returned zero product markers (completely blank/stripped page)
    if not extracted_fields.get("generic_name") and not extracted_fields.get("mrp"):
        logger.warning(f"No recognized product title or price found on {url}. Snippet: {response_snippet}")
        raise ScrapeFailedException("This listing could not be read. It may be blocked by the platform, or the URL may not be a product page. Try a direct product link, or upload a photo instead.")
        
    scraped_data["fields"] = extracted_fields
    logger.info(f"Successfully scraped {url}. Found fields: {list(extracted_fields.keys())}")
    return scraped_data
