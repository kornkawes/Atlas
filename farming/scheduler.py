"""
Atlas Real Estate Farming - Automation Scheduler
Runs the farming engine twice daily at 06:00 and 18:00 (Asia/Bangkok).
Supports:
  - Immediate execution: python farming/scheduler.py --run-now
  - Background loop:     python farming/scheduler.py --daemon
  - Register Windows Task Scheduler: python farming/scheduler.py --install-tasks
"""

import os
import sys
import json
import time
import argparse
import logging
import subprocess
from datetime import datetime

# Ensure repository root is in sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from farming.engine import FarmingEngine

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s [%(name)s]: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("AtlasFarmingScheduler")

SCHEDULE_HOURS = [6, 18]  # 06:00 and 18:00

def run_cycle(zones=None, min_price=None, max_price=None):
    logger.info("Triggering Farming Cycle...")
    engine = FarmingEngine()
    result = engine.run_farming_cycle(target_zones=zones, min_price=min_price, max_price=max_price)
    logger.info(f"Cycle result: {result}")
    return result

from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

class CriteriaSyncHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress routine HTTP request noise in console

    def _send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors()
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/api/criteria"):
            criteria_file = os.path.join(REPO_ROOT, "farming", "data", "user_criteria.json")
            data = {}
            if os.path.exists(criteria_file):
                try:
                    with open(criteria_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    pass
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path.startswith("/api/criteria"):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                criteria_file = os.path.join(REPO_ROOT, "farming", "data", "user_criteria.json")
                os.makedirs(os.path.dirname(criteria_file), exist_ok=True)
                with open(criteria_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logger.info(f"Updated seller target zones via API: {data.get('target_zones')}")
                self.send_response(200)
                self._send_cors()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "saved": data}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self._send_cors()
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

def start_sync_server(port=8765):
    try:
        server = HTTPServer(("0.0.0.0", port), CriteriaSyncHandler)
        logger.info(f"Atlas Criteria Sync Server active at http://127.0.0.1:{port}/api/criteria")
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
    except Exception as e:
        logger.warning(f"Could not start criteria sync server on port {port}: {e}")

def daemon_loop():
    start_sync_server(8765)
    logger.info(f"Starting Atlas Farming Daemon. Scheduled times: {SCHEDULE_HOURS[0]:02d}:00 and {SCHEDULE_HOURS[1]:02d}:00")
    last_run_hour = None
    
    while True:
        now = datetime.now()
        current_hour = now.hour
        current_minute = now.minute

        # Check if current time matches scheduled hours (at minute 0-2) and hasn't run this hour yet
        if current_hour in SCHEDULE_HOURS and current_minute < 5:
            if last_run_hour != current_hour:
                logger.info(f"Alarm triggered for {current_hour:02d}:{current_minute:02d}!")
                logger.info(f"Alarm triggered for {current_hour:02d}:{current_minute:02d}! Reading current seller criteria...")
                try:
                    run_cycle()
                    last_run_hour = current_hour
                except Exception as e:
                    logger.error(f"Error during scheduled farming cycle: {e}")
        else:
            # Reset last_run_hour once we leave the trigger window
            if last_run_hour == current_hour:
                last_run_hour = None

        time.sleep(30)

def install_windows_tasks():
    """
    Registers two Windows Task Scheduler tasks:
    1. Atlas_Farming_Morning at 06:00
    2. Atlas_Farming_Evening at 18:00
    """
    python_exe = sys.executable
    engine_script = os.path.join(REPO_ROOT, "farming", "engine.py")

    tasks = [
        {"name": "Atlas_Farming_Morning", "time": "06:00"},
        {"name": "Atlas_Farming_Evening", "time": "18:00"},
    ]

    for t in tasks:
        cmd = [
            "schtasks", "/Create",
            "/SC", "DAILY",
            "/TN", t["name"],
            "/TR", f'"{python_exe}" "{engine_script}"',
            "/ST", t["time"],
            "/F"
        ]
        try:
            logger.info(f"Registering task {t['name']} at {t['time']}...")
            res = subprocess.run(" ".join(cmd), shell=True, capture_output=True, text=True)
            if res.returncode == 0:
                logger.info(f"Task {t['name']} registered successfully: {res.stdout.strip()}")
            else:
                logger.warning(f"Registration output: {res.stderr.strip() or res.stdout.strip()}")
        except Exception as e:
            logger.error(f"Failed to register task {t['name']}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Atlas Farming Scheduler")
    parser.add_argument("--run-now", action="store_true", help="Run one farming cycle immediately and exit")
    parser.add_argument("--daemon", action="store_true", help="Run continuously as background daemon")
    parser.add_argument("--install-tasks", action="store_true", help="Register Windows Task Scheduler jobs for 06:00 and 18:00")
    parser.add_argument("--zones", type=str, help="Comma-separated zone keywords (e.g. ไทรน้อย,บางบัวทอง)")
    parser.add_argument("--set-zones", type=str, help="Save target zones permanently into user_criteria.json")
    parser.add_argument("--min-price", type=int, help="Minimum asking price in Baht (e.g. 3000000)")
    parser.add_argument("--max-price", type=int, help="Maximum asking price in Baht (e.g. 10000000)")
    
    args = parser.parse_args()

    if args.set_zones:
        zones_list = [z.strip() for z in args.set_zones.split(",") if z.strip()]
        criteria_file = os.path.join(REPO_ROOT, "farming", "data", "user_criteria.json")
        os.makedirs(os.path.dirname(criteria_file), exist_ok=True)
        cur = {}
        if os.path.exists(criteria_file):
            try:
                with open(criteria_file, "r", encoding="utf-8") as f:
                    cur = json.load(f)
            except Exception:
                pass
        cur["target_zones"] = zones_list
        cur["last_updated_at"] = datetime.now().isoformat()
        with open(criteria_file, "w", encoding="utf-8") as f:
            json.dump(cur, f, ensure_ascii=False, indent=2)
        print(f"[OK] Saved target zones permanently: {zones_list}")
        sys.exit(0)

    zones = [z.strip() for z in args.zones.split(",")] if args.zones else None

    if args.install_tasks:
        install_windows_tasks()
    elif args.daemon:
        daemon_loop()
    else:
        # Default behavior: run cycle now
        run_cycle(zones=zones, min_price=args.min_price, max_price=args.max_price)
