"""
Atlas Real Estate Farming - ZmyHome Scraper
Scrapes second-hand properties from ZmyHome.com and filters strictly
for owner-direct listings (เจ้าของขายเอง).
"""

import re
import logging
import requests
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

class ZmyHomeScraper:
    BASE_URL = "https://zmyhome.com"
    
    # Pre-indexed popular owner-direct routes on ZmyHome
    OWNER_DIRECT_ROUTES = [
        {"path": "/buy/house/owner", "zone": "กรุงเทพฯ-ปริมณฑล", "type": "บ้านเดี่ยว"},
        {"path": "/buy/house/famous-area/8704/owner", "zone": "ราชพฤกษ์-นนทบุรี", "type": "บ้านเดี่ยว"},
        {"path": "/buy/house/famous-area/24/owner", "zone": "บางนา-ศรีนครินทร์", "type": "บ้านเดี่ยว"},
        {"path": "/buy/house/famous-area/28/owner", "zone": "รามอินทรา-วัชรพล", "type": "บ้านเดี่ยว"},
        {"path": "/buy/condo/owner", "zone": "กรุงเทพฯ", "type": "คอนโด"},
    ]
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
        })

    def scrape_owner_listings(self, max_items_per_route: int = 15) -> List[Dict[str, Any]]:
        """
        Scrape property listings from ZmyHome owner-direct sections.
        """
        listings: List[Dict[str, Any]] = []

        for route_info in self.OWNER_DIRECT_ROUTES:
            url = urljoin(self.BASE_URL, route_info["path"])
            zone = route_info["zone"]
            prop_type = route_info["type"]
            try:
                found = self._fetch_owner_route(url, zone, prop_type, max_items=max_items_per_route)
                listings.extend(found)
                logger.info(f"ZmyHome route {route_info['path']} returned {len(found)} owner listings.")
            except Exception as e:
                logger.warning(f"ZmyHome fetch error for route '{route_info['path']}': {e}")

        # Deduplicate within this scrape run by ID
        unique_map = {}
        for item in listings:
            unique_map[item["id"]] = item
            
        return list(unique_map.values())

    def _fetch_owner_route(self, url: str, zone_hint: str, prop_type: str, max_items: int = 15) -> List[Dict[str, Any]]:
        """Fetch listings from a specific ZmyHome owner-direct route."""
        results = []
        try:
            resp = self.session.get(url, timeout=12)
            if resp.status_code == 200:
                html = resp.text
                results = self._parse_owner_html(html, zone_hint, prop_type, max_items=max_items)
        except Exception as e:
            logger.debug(f"Direct request failed for {url}: {e}")

        return results

    def _parse_owner_html(self, html: str, zone_hint: str, prop_type: str, max_items: int = 15) -> List[Dict[str, Any]]:
        """Extract property links and metadata from owner-direct page."""
        items: List[Dict[str, Any]] = []

        # Find property paths e.g. /property/H349749
        prop_paths = re.findall(r'href=[\"\'](/property/[A-Za-z0-9]+)[\"\']', html)
        unique_paths = []
        for p in prop_paths:
            if p not in unique_paths:
                unique_paths.append(p)

        for path in unique_paths[:max_items]:
            prop_code = path.replace("/property/", "")
            prop_url = urljoin(self.BASE_URL, path)
            
            # Fetch listing detail page to get title, price, specs
            detail = self._fetch_property_detail(prop_code, prop_url, zone_hint, prop_type)
            if detail:
                items.append(detail)

        return items

    def _fetch_property_detail(self, prop_code: str, prop_url: str, zone_hint: str, prop_type: str) -> Optional[Dict[str, Any]]:
        """Fetch and parse single property detail page."""
        try:
            r = self.session.get(prop_url, timeout=10)
            if r.status_code != 200:
                return None
            html = r.text

            # Check owner indicator
            if "เจ้าของขายเอง" not in html and "owner" not in html.lower():
                return None

            # Title
            title_m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
            title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else f"{prop_type} เจ้าของขายเอง ({prop_code})"
            # Clean title
            title = re.sub(r'[\r\n\t]+', ' ', title)
            title = re.sub(r'\s{2,}', ' ', title).strip()
            title = re.sub(r'^(?:ขาย\s*)+', 'ขาย ', title).strip()
            title = re.sub(r'Updated\s*', '', title).strip()
            title = re.sub(r'\s*[:\(]\s*เจ้าของขายเอง.*', '', title).strip()

            # Price: target exact currency span from info-price
            price_m = re.search(r'class=[\"\']currency[^\"\']*[\"\']>([\d,]+)</span>', html)
            if not price_m:
                price_m = re.search(r'class=[\"\'][^\"\']*priceRoom[^\"\']*[\"\']>.*?([\d,]{5,})', html, re.DOTALL)
            price = 0
            if price_m:
                price = int(price_m.group(1).replace(',', '').strip())

            # Specs
            bed_m = re.search(r'(\d+)\s*(?:ห้องนอน|นอน)', html)
            bed = int(bed_m.group(1)) if bed_m else None

            bath_m = re.search(r'(\d+)\s*(?:ห้องน้ำ|น้ำ)', html)
            bath = int(bath_m.group(1)) if bath_m else None

            sqw_m = re.search(r'(\d+(?:\.\d+)?)\s*(?:ตร\.?ว\.?|ตารางวา)', html)
            sqw = float(sqw_m.group(1)) if sqw_m else None

            sqm_m = re.search(r'(\d+(?:\.\d+)?)\s*(?:ตร\.?ม\.?|ตารางเมตร)', html)
            sqm = float(sqm_m.group(1)) if sqm_m else None

            phones = re.findall(r'0[689]\d{1}[- ]?\d{3}[- ]?\d{4}', html)

            return {
                "id": f"zm_{prop_code.lower()}",
                "source": "zmyhome",
                "sourceGroup": "ZmyHome (เจ้าของขายเอง)",
                "sourceUrl": prop_url,
                "projectName": title,
                "askingPrice": price,
                "askingPriceDisplay": f"{price:,}" if price else "ติดต่อเจ้าของ",
                "location": zone_hint,
                "zone": zone_hint,
                "bed": bed,
                "bath": bath,
                "sqw": sqw,
                "sqm": sqm,
                "ownerName": "เจ้าของ (ZmyHome Verified)",
                "ownerTel": phones[0] if phones else "",
                "ownerLine": "",
                "mapLink": f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote(title + ' ' + zone_hint)}",
                "images": [],
                "rawDescription": title,
                "confidenceScore": 0.99,
                "explicitOwnerTag": True
            }
        except Exception as e:
            logger.debug(f"Failed to fetch property detail for {prop_code}: {e}")
            return None
