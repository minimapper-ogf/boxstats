import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from string import Template

# --- CONFIGURATION ---
localtesting = 0
# Frontend web root
OUTPUT_DIR = Path("/var/www/boxstats/site")
# Application root for data and logic
APP_ROOT = Path("/opt/boxstats")
if localtesting:
    APP_ROOT = Path(__file__).resolve().parent
    OUTPUT_DIR = APP_ROOT / "site"

DATA_DIR = APP_ROOT / "data"
TEMPLATES_DIR = APP_ROOT / "templates"
ORGS_FILE = APP_ROOT / "orgs.json"
ASSETS_DIR = OUTPUT_DIR / "assets"

TEMPLATE_FILES = {
    "base": TEMPLATES_DIR / "base.html",
    "index": TEMPLATES_DIR / "index.html",
    "detail": TEMPLATES_DIR / "detail.html",
    "add_org": TEMPLATES_DIR / "add_org.html",
    "about": TEMPLATES_DIR / "about.html",
}

CHART_FIELDS = [
    "UsersNow",
    "Favourited",
    "Collections",
    "VotesUp",
    "VotesDown",
    "LikePercentage",
    "TotalUsers",
    "TotalSeconds",
    "TotalSessions",
    "FileCount",
    "TotalSize",
    "ErrorRate",
]

def ensure_dirs():
    """Creates the frontend directory structure if it doesn't exist."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "orgs").mkdir(parents=True, exist_ok=True)

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None

def load_template(name):
    path = TEMPLATE_FILES[name]
    with open(path, "r", encoding="utf-8") as fh:
        return Template(fh.read())

def write_file(path, content):
    """Writes content to the specified path, ensuring parent directories exist."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)

def slugify(value):
    value = str(value).strip().lower()
    value = re.sub(r"[^a-z0-9_]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_")

def page_route_org(org_name):
    return f"/orgs/{slugify(org_name)}/"

def page_route_game(org_name, game_name):
    return f"/orgs/{slugify(org_name)}/{slugify(game_name)}/"

def format_size(value):
    if value is None:
        return "0 MB"
    value = float(value)
    if value >= 1024 ** 3:
        return f"{value / 1024 ** 3:.2f} GB"
    return f"{value / 1024 ** 2:.2f} MB"


def seconds_to_hours(value):
    return float(value) / 3600 if value is not None else 0.0


def safe_html(text):
    if text is None:
        return ""
    return str(text)


def build_org_game_list(org):
    games = org.get("games", [])
    if not games:
        return ""

    rows = []
    for game in sorted(games, key=lambda item: (-item.get("users", 0), item["title"].lower())):
        rows.append(
            f"""
        <li class=\"org-game-card\">
          <a href=\"{game['file']}\">
            <div class=\"org-game-preview\"><img src=\"{game['preview']}\" alt=\"{game['title']} preview\" /></div>
            <div class=\"org-game-info\">
              <strong>{game['title']}</strong>
              <div class=\"org-game-meta\">
                <span>Players: {game['users']}</span>
                <span>Favorites: {game['favourites']}</span>
                <span>Likes: {game['likes']}</span>
                <span>Dislikes: {game['dislikes']}</span>
              </div>
            </div>
          </a>
        </li>
            """
        )

    return """
    <section class=\"org-games-section\">
      <div class=\"section-heading\">
        <h2>Org games</h2>
        <p>A complete list of games published by this organization.</p>
      </div>
      <ul class=\"org-games-list\">""" + "\n".join(rows) + "</ul>\n    </section>"


def build_game_pages(games, base_template, detail_template):
    game_entries = []

    for game in games:
        title = game["metadata"].get("Title") or f"{game['org']} / {game['game']}"
        summary = game["metadata"].get("Summary") or game["metadata"].get("Description") or ""
        preview = (
            game["metadata"].get("Thumb")
            or game["metadata"].get("Thumbnails", {}).get("Thumb")
            or game["metadata"].get("Thumbnails", {}).get("Wide")
            or ""
        )
        latest = game["latest"]
        if not latest:
            continue

        page_url = page_route_game(game['org'], game['game'])
        # Uses hardcoded /var/www/boxstats/site/...
        page_path = OUTPUT_DIR / "orgs" / slugify(game['org']) / slugify(game['game']) / "index.html"
        stats = build_timeline(game["history"])

        # Fully preserved page_data dictionary
        page_data = {
            "kind": "game",
            "pageTitle": title,
            "subtitle": summary,
            "org": game["org"],
            "game": game["game"],
            "preview": preview,
            "latest": {
                "UsersNow": latest.get("UsersNow", 0),
                "Favourited": latest.get("Favourited", 0),
                "Collections": latest.get("Collections", 0),
                "VotesUp": latest.get("VotesUp", 0),
                "VotesDown": latest.get("VotesDown", 0),
                "LikePercentage": latest.get("LikePercentage", 0.0),
                "TotalUsers": latest.get("TotalUsers", 0),
                "TotalSeconds": latest.get("TotalSeconds", 0),
                "TotalSessions": latest.get("TotalSessions", 0),
                "FileCount": latest.get("FileCount", 0),
                "TotalSize": latest.get("TotalSize", 0),
                "ErrorRate": latest.get("ErrorRate", 0.0),
                "LastUpdate": latest.get("Time") or latest.get("ScriptTimestamp") or "",
            },
            "timeline": stats,
            "links": {
                "home": "/index.html",
                "org": page_route_org(game['org']),
            },
        }

        content = detail_template.substitute(
            page_title=title,
            page_subtitle=summary,
            description_html=safe_html(game["metadata"].get("Description", "")),
            preview_image=preview,
            page_tag=game["org"],
            index_url="/index.html",
            org_url=page_data["links"]["org"],
            action_button=f'<a class="button button-soft" href="{page_data["links"]["org"]}">View Org</a>',
            org_games_section="",
            page_data_json=json.dumps(page_data, indent=2),
        )

        full_page = base_template.substitute(
            title=f"{title} — Boxstats",
            description=f"Stats and charts for {title}",
            content=content,
            inline_script="",
            updated=game["hist_latest_time"],
        )

        write_file(page_path, full_page)

        # Fully preserved game_entries dictionary
        game_entries.append(
            {
                "name": title,
                "file": page_url,
                "org": game["org"],
                "game": game["game"],
                "latest": latest,
                "metadata": game["metadata"],
                "preview": preview,
                "hist_latest_time": game.get("hist_latest_time", latest.get("Time", "")),
            }
        )

    return game_entries


def build_org_pages(orgs, base_template, detail_template):
    org_entries = []

    for org in orgs:
        title = org["metadata"].get("Title") or org["org"]
        summary = org["metadata"].get("Description") or ""
        preview = org["metadata"].get("Thumb") or ""
        latest = org["latest"]
        if not latest:
            continue

        page_url = page_route_org(org['org'])
        page_path = OUTPUT_DIR / "orgs" / slugify(org['org']) / "index.html"
        stats = build_timeline(org["history"])

        page_data = {
            "kind": "org",
            "pageTitle": title,
            "subtitle": summary,
            "org": org["org"],
            "preview": preview,
            "latest": {
                "UsersNow": latest.get("UsersNow", 0),
                "Favourited": latest.get("Favourited", 0),
                "Collections": latest.get("Collections", 0),
                "GameCount": len(org.get("games", [])),
                "VotesUp": latest.get("VotesUp", 0),
                "VotesDown": latest.get("VotesDown", 0),
                "LikePercentage": latest.get("LikePercentage", 0.0),
                "TotalUsers": latest.get("TotalUsers", 0),
                "TotalSeconds": latest.get("TotalSeconds", 0),
                "TotalSessions": latest.get("TotalSessions", 0),
                "FileCount": latest.get("FileCount", 0),
                "TotalSize": latest.get("TotalSize", 0),
                "ErrorRate": latest.get("ErrorRate", 0.0),
                "LastUpdate": latest.get("Time") or "",
            },
            "timeline": stats,
            "links": {
                "home": "index.html",
            },
        }

        content = detail_template.substitute(
            page_title=title,
            page_subtitle=summary,
            description_html=safe_html(org["metadata"].get("Description", "")),
            preview_image=preview,
            page_tag=f"Org: {org['org']}",
            index_url="/index.html",
            org_url="/index.html",
            action_button="",
            org_games_section=build_org_game_list(org),
            page_data_json=json.dumps(page_data, indent=2),
        )

        full_page = base_template.substitute(
            title=f"{title} — Boxstats",
            description=f"Organization stats for {title}",
            content=content,
            inline_script="",
            updated=org["hist_latest_time"],
        )

        write_file(page_path, full_page)

        org_entries.append(
            {
                "org": org["org"],
                "name": title,
                "file": page_url,
                "preview": preview,
            }
        )

    return org_entries


def build_timeline(history):
    if not history:
        return []
    return [
        {
            "Time": entry.get("Time", ""),
            "UsersNow": entry.get("UsersNow", 0),
            "Favourited": entry.get("Favourited", 0),
            "Collections": entry.get("Collections", 0),
            "VotesUp": entry.get("VotesUp", 0),
            "VotesDown": entry.get("VotesDown", 0),
            "LikePercentage": entry.get("LikePercentage", 0.0),
            "TotalUsers": entry.get("TotalUsers", 0),
            "TotalSeconds": entry.get("TotalSeconds", 0),
            "TotalSessions": entry.get("TotalSessions", 0),
            "FileCount": entry.get("FileCount", 0),
            "TotalSize": entry.get("TotalSize", 0),
            "ErrorRate": entry.get("ErrorRate", 0.0),
        }
        for entry in history
    ]


def scan_data():
    games = []
    orgs = []
    org_lookup = {}

    for org_dir in sorted(DATA_DIR.iterdir()):
        if not org_dir.is_dir():
            continue

        org_meta_path = org_dir / "metadata.json"
        org_history_path = org_dir / "10m.json"
        org_meta = load_json(org_meta_path)
        org_history = load_json(org_history_path) or []
        latest_org = org_history[-1] if org_history else {}
        if org_meta and org_history:
            org_entry = {"org": org_dir.name, "metadata": org_meta, "history": org_history, "latest": latest_org, "hist_latest_time": latest_org.get("Time", ""), "games": []}
            orgs.append(org_entry)
            org_lookup[org_dir.name] = org_entry

        for game_dir in sorted(org_dir.iterdir()):
            if not game_dir.is_dir():
                continue
            game_meta_path = game_dir / "metadata.json"
            game_history_path = game_dir / "10m.json"
            game_meta = load_json(game_meta_path)
            game_history = load_json(game_history_path) or []
            if not game_meta or not game_history:
                continue
            latest_game = game_history[-1]
            game_entry = {
                "org": org_dir.name,
                "game": game_dir.name,
                "metadata": game_meta,
                "history": game_history,
                "latest": latest_game,
                "hist_latest_time": latest_game.get("Time", ""),
            }
            games.append(game_entry)
            if org_dir.name in org_lookup:
                game_preview = (
                game_meta.get("Thumb")
                or game_meta.get("Thumbnails", {}).get("Thumb")
                or game_meta.get("Thumbnails", {}).get("Wide")
                or ""
            )
            org_lookup[org_dir.name]["games"].append(
                {
                    "title": game_meta.get("Title", game_dir.name),
                    "file": page_route_game(org_dir.name, game_dir.name),
                    "preview": game_preview,
                    "users": latest_game.get("UsersNow", 0),
                    "likes": latest_game.get("VotesUp", 0),
                    "dislikes": latest_game.get("VotesDown", 0),
                    "favourites": latest_game.get("Favourited", 0),
                }
            )
    return games, orgs


def build_home_timeline(games):
    all_timestamps = set()
    game_histories = []

    for game in games:
        history = game.get("history", [])
        if not history:
            continue
        sorted_history = sorted((entry for entry in history if entry.get("Time")), key=lambda value: value["Time"])
        game_histories.append(sorted_history)
        all_timestamps.update(entry["Time"] for entry in sorted_history)

    timeline = []
    for timestamp in sorted(all_timestamps):
        total_players = 0
        total_games = 0

        for sorted_history in game_histories:
            last_users = None
            for entry in sorted_history:
                if entry["Time"] <= timestamp:
                    last_users = entry.get("UsersNow", 0)
                else:
                    break
            if last_users is not None:
                total_players += last_users
                total_games += 1

        timeline.append({"Time": timestamp, "Players": total_players, "Games": total_games})

    return timeline


def build_index_page(base_template, index_template, games, orgs):
    game_rows = []
    game_table_data = []
    for game in sorted(games, key=lambda item: (-item["latest"].get("UsersNow", 0), item["org"], item["game"])):
        title = game["metadata"].get("Title", game["game"])
        preview = (
            game["metadata"].get("Thumb")
            or game["metadata"].get("Thumbnails", {}).get("Thumb")
            or game["metadata"].get("Thumbnails", {}).get("Wide")
            or ""
        )
        game_rows.append(title)
        game_table_data.append(
            {
                "title": title,
                "org": game["org"],
                "file": game["file"],
                "preview": preview,
                "UsersNow": game["latest"].get("UsersNow", 0),
                "Favourited": game["latest"].get("Favourited", 0),
                "VotesUp": game["latest"].get("VotesUp", 0),
                "VotesDown": game["latest"].get("VotesDown", 0),
                "LikePercentage": game["latest"].get("LikePercentage", 0.0),
                "Created": game["metadata"].get("Created", ""),
                "TotalSize": game["latest"].get("TotalSize", 0),
                "ErrorRate": game["latest"].get("ErrorRate", 0.0),
            }
        )
    org_rows = []
    for org in sorted(orgs, key=lambda item: item["org"]):
        org_rows.append(
            """
            <article class=\"list-card\">
                <a class=\"list-link\" href=\"{file}\">
                    <div class=\"list-preview\"><img src=\"{preview}\" alt=\"{title} preview\"></div>
                    <div class=\"list-text\">
                        <strong>{title}</strong>
                        <span>org</span>
                    </div>
                </a>
            </article>
            """.format(
                file=org["file"],
                preview=org.get("preview", ""),
                title=org.get("name", org["org"]),
            )
        )

    total_players = sum(game["latest"].get("UsersNow", 0) for game in games)
    total_favourites = sum(game["latest"].get("Favourited", 0) for game in games)
    total_collections = sum(game["latest"].get("Collections", 0) for game in games)
    total_sessions = sum(game["latest"].get("TotalSessions", 0) for game in games)
    last_updated = max((game["hist_latest_time"] for game in games), default="")
    home_timeline = build_home_timeline(games)

    content = index_template.substitute(
        total_games=len(games),
        total_orgs=len(orgs),
        total_players=total_players,
        total_favourites=total_favourites,
        total_collections=total_collections,
        total_sessions=total_sessions,
        games_tracked=len(games),
        orgs_tracked=len(orgs),
        last_updated=last_updated,
        game_list="",
        org_list="\n".join(org_rows),
        home_page_data_json=json.dumps({
            "timeline": home_timeline,
            "stats": {
                "games": len(games),
                "players": total_players,
                "orgs": len(orgs),
                "favorites": total_favourites,
                "collections": total_collections,
                "sessions": total_sessions,
                "lastUpdated": last_updated,
            },
        }, indent=2),
        game_table_data_json=json.dumps(game_table_data, indent=2),
    )
    page = base_template.substitute(
        title="Home - Boxstats",
        description="Dashboard of tracked games and historic player counts.",
        content=content,
        inline_script="",
        updated=datetime.now(timezone.utc).isoformat(),
    )
    write_file(OUTPUT_DIR / "index.html", page)


def copy_assets():
    """Copies CSS/JS from /opt/boxstats/assets to /var/www/boxstats/site/assets."""
    source_css = APP_ROOT / "assets" / "style.css"
    source_js = APP_ROOT / "assets" / "site.js"
    if source_css.exists():
        write_file(ASSETS_DIR / "style.css", source_css.read_text(encoding="utf-8"))
    if source_js.exists():
        write_file(ASSETS_DIR / "site.js", source_js.read_text(encoding="utf-8"))


def build_add_org_page(base_template, add_org_template):
    content = add_org_template.substitute()
    full_page = base_template.substitute(
        title="Add Org — BoxTrack",
        description="Add a new organization to orgs.json.",
        content=content,
        inline_script="",
        updated=datetime.now(timezone.utc).isoformat(),
    )
    write_file(OUTPUT_DIR / "add_org" / "index.html", full_page)


def build_about_page(base_template, about_template):
    content = about_template.substitute()
    full_page = base_template.substitute(
        title="About — Boxstats",
        description="About the Boxstats dashboard.",
        content=content,
        inline_script="",
        updated=datetime.now(timezone.utc).isoformat(),
    )
    write_file(OUTPUT_DIR / "about" / "index.html", full_page)


def generate_site():
    ensure_dirs()
    copy_assets()
    games, orgs = scan_data()
    # load_template uses TEMPLATE_FILES which now points to /opt/boxstats/templates
    base_template = load_template("base")
    index_template = load_template("index")
    detail_template = load_template("detail")
    add_org_template = load_template("add_org")
    about_template = load_template("about")

    org_entries = build_org_pages(orgs, base_template, detail_template)
    game_entries = build_game_pages(games, base_template, detail_template)
    build_index_page(base_template, index_template, game_entries, org_entries)
    build_add_org_page(base_template, add_org_template)
    build_about_page(base_template, about_template)
    print(f"Site generated successfully in {OUTPUT_DIR}")

if __name__ == "__main__":
    generate_site()
