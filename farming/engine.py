"""
Atlas Real Estate - Farming Engine
Coordinates multi-source scraping (ZmyHome + Facebook Groups),
filters out brokers, deduplicates listings, tracks price drops,
and syncs data to local storage and Google Sheets.
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

# Ensure repository root is in sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from farming.scrapers.zmyhome import ZmyHomeScraper
from farming.scrapers.facebook_groups import FacebookGroupScraper

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s [%(name)s]: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("AtlasFarmingEngine")

class FarmingEngine:
    def __init__(self, config_path: str = "farming/config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        self.data_path = self.config.get("storage", {}).get("local_data_file", "farming/data/farmed_listings.json")
        self.client_export_path = self.config.get("storage", {}).get("client_export_file", "farmed_listings.json")
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        
        self.zmyhome_scraper = ZmyHomeScraper(self.config)
        self.facebook_scraper = FacebookGroupScraper(self.config)
        
        self.db: Dict[str, Dict[str, Any]] = self._load_db()

    def _load_config(self) -> Dict[str, Any]:
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load config from {self.config_path}: {e}")
            return {}

    def _load_db(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, "r", encoding="utf-8") as f:
                    items = json.load(f)
                    if isinstance(items, list):
                        return {item["id"]: item for item in items if "id" in item}
                    elif isinstance(items, dict):
                        return items
            except Exception as e:
                logger.error(f"Failed to load existing db from {self.data_path}: {e}")
        return {}

    def save_db(self) -> None:
        """Saves current database to local storage and client export file."""
        items_list = list(self.db.values())
        
        # Sort by lastUpdatedAt or firstSeenAt descending
        items_list.sort(key=lambda x: x.get("lastUpdatedAt") or x.get("firstSeenAt") or "", reverse=True)
        
        # 1. Save to internal data path
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(items_list, f, ensure_ascii=False, indent=2)
            
        # 2. Save export for frontend PWA
        with open(self.client_export_path, "w", encoding="utf-8") as f:
            json.dump({
                "status": "success",
                "total": len(items_list),
                "lastRunAt": datetime.now().isoformat(),
                "data": items_list
            }, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Saved {len(items_list)} farmed listings to {self.data_path} & {self.client_export_path}")

    def _matches_criteria(self, item: Dict[str, Any], target_zones: Optional[List[str]] = None, min_price: Optional[int] = None, max_price: Optional[int] = None) -> bool:
        """
        Filters item based on target zone keywords and price range.
        """
        price = item.get("askingPrice") or 0
        if min_price is not None and price > 0 and price < min_price:
            return False
        if max_price is not None and price > 0 and price > max_price:
            return False

        if target_zones:
            haystack = f"{item.get('projectName', '')} {item.get('location', '')} {item.get('zone', '')} {item.get('rawDescription', '')}".lower()
            if not any(z.strip().lower() in haystack for z in target_zones if z.strip()):
                return False

        return True

    def run_farming_cycle(self, target_zones: Optional[List[str]] = None, min_price: Optional[int] = None, max_price: Optional[int] = None) -> Dict[str, Any]:
        """
        Executes one full farming cycle:
        1. Scrape ZmyHome owner listings
        2. Scrape Facebook Groups owner posts
        3. Filter candidates by target zones & price constraints
        4. Deduplicate and detect changes / price drops
        5. Save and report metrics
        """
        now = datetime.now().isoformat()
        logger.info(f"Starting Farming Cycle at {now}...")

        # Load criteria defaults from config if not explicitly passed
        if target_zones is None:
            target_zones = self.config.get("target_zones")
        if min_price is None:
            min_price = self.config.get("price_range", {}).get("min")
        if max_price is None:
            max_price = self.config.get("price_range", {}).get("max")
        
        logger.info(f"Active Criteria: Zones={target_zones}, MinPrice={min_price:,}฿, MaxPrice={max_price:,}฿" if min_price and max_price else f"Active Criteria: Zones={target_zones}")

        new_count = 0
        price_drop_count = 0
        price_increase_count = 0
        unchanged_count = 0

        # Step 1: Scrape from ZmyHome
        logger.info("Fetching owner listings from ZmyHome...")
        zm_items = self.zmyhome_scraper.scrape_owner_listings()
        logger.info(f"ZmyHome returned {len(zm_items)} candidate owner listings.")

        # Step 2: Scrape from Facebook Groups
        logger.info("Fetching owner posts from Facebook Groups...")
        fb_items = self.facebook_scraper.scrape_owner_posts()
        logger.info(f"Facebook Groups returned {len(fb_items)} candidate owner posts.")

        all_candidates = zm_items + fb_items
        logger.info(f"Total raw candidates: {len(all_candidates)}")

        # Step 3: Filter by Zone & Price criteria
        matched_candidates = []
        for c in all_candidates:
            if self._matches_criteria(c, target_zones, min_price, max_price):
                matched_candidates.append(c)
        logger.info(f"Candidates matching zone & price criteria: {len(matched_candidates)} of {len(all_candidates)}")

        # Step 4: Ingest, Deduplicate & Change Detection
        for item in matched_candidates:
            item_id = item["id"]
            price = item.get("askingPrice") or 0

            if item_id not in self.db:
                # NEW LISTING
                item["firstSeenAt"] = now
                item["lastUpdatedAt"] = now
                item["lastCheckedAt"] = now
                item["isNew"] = True
                item["isPriceDrop"] = False
                item["priceHistory"] = [{"date": now, "price": price}] if price else []
                item["status"] = "active"
                item["claimedBy"] = None
                
                self.db[item_id] = item
                new_count += 1
            else:
                # EXISTING LISTING - CHECK PRICE & STATUS
                existing = self.db[item_id]
                old_price = existing.get("askingPrice") or 0
                existing["lastCheckedAt"] = now
                existing["isNew"] = False

                if price > 0 and old_price > 0 and price != old_price:
                    # PRICE CHANGED!
                    delta = price - old_price
                    pct = round((delta / old_price) * 100, 1)
                    is_drop = delta < 0

                    existing["askingPrice"] = price
                    existing["askingPriceDisplay"] = f"{price:,}"
                    existing["lastUpdatedAt"] = now
                    
                    history = existing.get("priceHistory", [])
                    history.append({"date": now, "price": price, "delta": delta, "pct": pct})
                    existing["priceHistory"] = history
                    
                    existing["priceChange"] = {
                        "previousPrice": old_price,
                        "currentPrice": price,
                        "delta": delta,
                        "percentage": pct,
                        "isDrop": is_drop,
                        "changedAt": now
                    }
                    existing["isPriceDrop"] = is_drop

                    if is_drop:
                        price_drop_count += 1
                        logger.info(f"🔥 PRICE DROP on {item_id}: {old_price:,} -> {price:,} ({pct}%)")
                    else:
                        price_increase_count += 1
                else:
                    # Unchanged price, update non-empty fields if found
                    if not existing.get("ownerTel") and item.get("ownerTel"):
                        existing["ownerTel"] = item["ownerTel"]
                    if not existing.get("ownerLine") and item.get("ownerLine"):
                        existing["ownerLine"] = item["ownerLine"]
                    if not existing.get("sqw") and item.get("sqw"):
                        existing["sqw"] = item["sqw"]
                    if not existing.get("bed") and item.get("bed"):
                        existing["bed"] = item["bed"]
                    unchanged_count += 1

        # Step 5: Persist
        self.save_db()

        report = {
            "cycleCompletedAt": datetime.now().isoformat(),
            "criteria": {
                "targetZones": target_zones,
                "minPrice": min_price,
                "maxPrice": max_price
            },
            "totalInDatabase": len(self.db),
            "candidatesProcessed": len(matched_candidates),
            "newListings": new_count,
            "priceDrops": price_drop_count,
            "priceIncreases": price_increase_count,
            "unchanged": unchanged_count,
            "sources": {
                "zmyhome": len([i for i in self.db.values() if i.get("source") == "zmyhome"]),
                "facebook": len([i for i in self.db.values() if i.get("source") == "facebook"])
            }
        }
        
        logger.info(f"Farming Cycle Completed: +{new_count} new, {price_drop_count} price drops, {len(self.db)} total.")
        return report

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Atlas Farming Engine")
    parser.add_argument("--zones", type=str, help="Comma-separated zone keywords (e.g. ไทรน้อย,บางบัวทอง)")
    parser.add_argument("--min-price", type=int, help="Minimum asking price in Baht (e.g. 3000000)")
    parser.add_argument("--max-price", type=int, help="Maximum asking price in Baht (e.g. 10000000)")

    args = parser.parse_args()
    zones = [z.strip() for z in args.zones.split(",")] if args.zones else None

    engine = FarmingEngine()
    result = engine.run_farming_cycle(target_zones=zones, min_price=args.min_price, max_price=args.max_price)
    print(json.dumps(result, ensure_ascii=False, indent=2))
