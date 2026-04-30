from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import json
import os
import sys

# --- SERVER PATH CONFIGURATION ---
localtesting = 0
# The code logic, orgs.json, and templates live here:
ROOT_DIR = Path("/opt/boxstats")
# The publicly accessible HTML files live here:
SITE_DIR = Path("/var/www/boxstats/site")
if localtesting:
    ROOT_DIR = Path(__file__).resolve().parent
    SITE_DIR = ROOT_DIR / "site"
ORGS_FILE = ROOT_DIR / "orgs.json"

# Add ROOT_DIR to sys.path so we can import generate_site even if
# this script is started from a different location
sys.path.append(str(ROOT_DIR))
import generate_site

class DashboardRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Explicitly tell the handler to serve files from the public site directory
        super().__init__(*args, directory=str(SITE_DIR), **kwargs)

    def do_GET(self):
        if self.path.startswith("/api/orgs"):
            return self.send_orgs_json()
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/add_org":
            return self.handle_add_org()
        self.send_error(404, "Not Found")

    def send_orgs_json(self):
        if not ORGS_FILE.exists():
            return self.send_error(404, "orgs.json not found")

        with ORGS_FILE.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        payload = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def handle_add_org(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return self.send_json_error("Request body required", 400)

        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            return self.send_json_error("Request body must be valid JSON", 400)

        org_name = str(payload.get("org", "")).strip()
        if not org_name:
            return self.send_json_error("Organization name is required", 400)

        org_slug = org_name.lower().replace(" ", "_")
        orgs = self.load_orgs()

        normalized_orgs = [self.normalize_org_item(item) for item in orgs]
        if any(item["org"] == org_slug for item in normalized_orgs):
            return self.send_json_error("Organization already exists", 409)

        # Append the new org
        if orgs and all(isinstance(item, dict) for item in orgs):
            orgs.append({"org": org_slug, "name": org_name, "metadata": {"Description": "Added via Dashboard"}})
        else:
            orgs.append(org_slug)

        self.write_orgs(orgs)

        # Trigger site regeneration in the correct context
        current_dir = Path.cwd()
        try:
            os.chdir(ROOT_DIR)
            generate_site.generate_site()
            print(f"Site regenerated at {SITE_DIR}")
        finally:
            os.chdir(current_dir)

        self.send_response(201)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"success": True, "org": org_slug}).encode("utf-8"))

    def load_orgs(self):
        if not ORGS_FILE.exists(): return []
        with ORGS_FILE.open("r", encoding="utf-8") as h:
            data = json.load(h)
        return data if isinstance(data, list) else data.get("orgs", [])

    def write_orgs(self, orgs):
        with ORGS_FILE.open("w", encoding="utf-8") as h:
            json.dump(orgs, h, indent=2)

    def normalize_org_item(self, item):
        return item if isinstance(item, dict) else {"org": str(item)}

    def send_json_error(self, message, status=400):
        payload = json.dumps({"error": message}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(payload)

def run(server_class=HTTPServer, handler_class=DashboardRequestHandler, port=8010):
    # Ensure directories exist
    SITE_DIR.mkdir(parents=True, exist_ok=True)

    server_address = ("", port)
    httpd = server_class(server_address, handler_class)
    print(f"Running BoxStats Service...")
    print(f"Logic Root: {ROOT_DIR}")
    print(f"Serving Content From: {SITE_DIR}")
    print(f"Listening on port: {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
