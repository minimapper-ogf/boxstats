import requests
import json
import os
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# --- CONFIGURATION ---
localtesting = 0
BASE_DIR = Path("/opt/boxstats")
if localtesting:
    BASE_DIR = Path(__file__).resolve().parent
ORGS_FILE = BASE_DIR / 'orgs.json'
QUALIFIED_FILE = BASE_DIR / 'qualified_games.json'
LOG_FILE = BASE_DIR / 'tracker.log'
DATA_DIR = BASE_DIR / 'data'
GENERATE_SCRIPT = BASE_DIR / 'generate_site.py'

HEADERS = {"User-Agent": "boxstats/v1"}
FAVOURITE_THRESHOLD = 50

# --- LOG BUFFERING ---
log_buffer = []

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_message = f"[{timestamp}] {message}"
    print(formatted_message)
    log_buffer.append(formatted_message)

def flush_logs():
    now = datetime.now()
    cutoff = now - timedelta(hours=24)
    existing_content = []
    if LOG_FILE.exists():
        with open(LOG_FILE, 'r') as f:
            for line in f:
                try:
                    ts_str = line[1:20]
                    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    if ts > cutoff:
                        existing_content.append(line.strip())
                except:
                    continue
    final_logs = existing_content + log_buffer
    with open(LOG_FILE, 'w') as f:
        f.write("\n".join(final_logs) + "\n")
    log_buffer.clear()

def load_json(path, default):
    path = Path(path)
    if path.exists():
        with open(path, 'r') as f:
            try: return json.load(f)
            except json.JSONDecodeError: return default
    return default

def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)

def calculate_like_percentage(up, down):
    total = up + down
    return round((up / total) * 100, 3) if total > 0 else 0.0

def prune_history(history, days_to_keep):
    """Removes entries older than X days based on the 'Time' key."""
    cutoff = datetime.now() - timedelta(days=days_to_keep)
    pruned = []
    for entry in history:
        try:
            # Handle ISO format: 2026-04-28T20:50:00
            entry_time = datetime.fromisoformat(entry['Time'])
            if entry_time > cutoff:
                pruned.append(entry)
        except (ValueError, KeyError):
            continue
    return pruned

def run_tracker():
    start_time = datetime.now()
    rounded_time = start_time.replace(second=0, microsecond=0)
    if start_time.second >= 30:
        rounded_time += timedelta(minutes=1)

    timestamp = rounded_time.isoformat()
    is_midnight = rounded_time.hour == 0

    log(f"--- Starting Tracker Run for {timestamp} ---")

    orgs = load_json(ORGS_FILE, [])
    qualified_list = load_json(QUALIFIED_FILE, [])
    initial_qualified_count = len(qualified_list)

    valid_orgs = []
    orgs_modified = False

    for org_name in orgs:
        ident = org_name['org'] if isinstance(org_name, dict) else org_name

        time.sleep(1)
        log(f"Fetching Org: {ident}...")
        url = f"https://services.facepunch.com/sbox/package/find?q=org:{ident}"

        try:
            response = requests.get(url, headers=HEADERS, timeout=15)

            if response.status_code != 200:
                log(f"  [WARN] API returned {response.status_code} for {ident}. Skipping.")
                valid_orgs.append(org_name)
                continue

            data = response.json()
            packages_list = data.get('Packages', [])

            if not packages_list:
                log(f"  [PURGE] Org '{ident}' confirmed empty by API. Removing.")
                orgs_modified = True
                continue

            # Org is confirmed valid
            valid_orgs.append(org_name)
            packages = [p for p in packages_list if p.get('TypeName') == 'game']

        except Exception as e:
            log(f"  [ERROR] Connection error for {ident}: {e}. Keeping in list.")
            valid_orgs.append(org_name)
            continue

        if packages:
            first_pkg = packages[0]
            org_info = first_pkg.get('Org', {})
            org_metadata = {
                "Ident": org_info.get('Ident', ident),
                "Title": org_info.get('Title', ""),
                "Description": org_info.get('Description', ""),
                "Thumb": org_info.get('Thumb', ""),
                "LastUpdate": timestamp
            }
            save_json(DATA_DIR / ident / "metadata.json", org_metadata)

        org_total_stats = {"UsersNow": 0, "Favourited": 0, "Collections": 0, "VotesUp": 0, "VotesDown": 0}

        for pkg in packages:
            game_ident = pkg.get('Ident')
            full_id = f"{ident}.{game_ident}"
            game_path = DATA_DIR / ident / game_ident

            favs = pkg.get('Favourited', 0)
            if favs >= FAVOURITE_THRESHOLD and full_id not in qualified_list:
                qualified_list.append(full_id)
                log(f"  [PROMOTED] {full_id} reached {favs} favorites!")

            deep_data = {
                "Description": "",
                "Thumbnails": {"Thumb": None, "Wide": None, "Tall": None, "Video": None},
                "TotalUsers": 0, "TotalSeconds": 0, "TotalSessions": 0,
                "FileCount": 0, "TotalSize": 0, "ErrorRate": 0.0
            }

            if full_id in qualified_list:
                try:
                    log(f"    Deep Fetch: {full_id}...")
                    d_res = requests.get(f"https://services.facepunch.com/sbox/package/get/{full_id}", headers=HEADERS, timeout=10).json()
                    p_data = d_res if 'UsageStats' in d_res else d_res.get('Package', {})
                    u_stats = p_data.get('UsageStats', {}).get('Total', {})
                    version = p_data.get('Version', {})

                    deep_data.update({
                        "Description": p_data.get('Description', ""),
                        "Thumbnails": {
                            "Thumb": p_data.get('Thumb'), "Wide": p_data.get('ThumbWide'),
                            "Tall": p_data.get('ThumbTall'), "Video": p_data.get('VideoThumb')
                        },
                        "TotalUsers": u_stats.get('Users', 0), "TotalSeconds": u_stats.get('Seconds', 0),
                        "TotalSessions": u_stats.get('Sessions', 0), "FileCount": version.get('FileCount', 0),
                        "TotalSize": version.get('TotalSize', 0), "ErrorRate": p_data.get('ErrorRate', 0.0)
                    })
                except Exception as e:
                    log(f"      [WARN] Deep fetch failed for {full_id}: {e}")

            up, down = pkg.get('VotesUp', 0), pkg.get('VotesDown', 0)
            like_pct = calculate_like_percentage(up, down)

            game_metadata = {
                "Title": pkg.get('Title'), "Summary": pkg.get('Summary'),
                "Description": deep_data["Description"], "Created": pkg.get('Created'),
                "Tags": pkg.get('Tags'), "Thumbnails": deep_data["Thumbnails"],
                "LatestStats": {
                    "Players": pkg.get('UsageStats', {}).get('UsersNow', 0),
                    "Favourites": favs, "Likes": up, "Dislikes": down, "LikePercentage": like_pct,
                    "TotalUsers": deep_data["TotalUsers"], "TotalSeconds": deep_data["TotalSeconds"],
                    "TotalSessions": deep_data["TotalSessions"], "FileCount": deep_data["FileCount"],
                    "TotalSize": deep_data["TotalSize"], "ErrorRate": round(deep_data["ErrorRate"], 6),
                    "ScriptTimestamp": timestamp, "LastUpdateFromAPI": pkg.get('Updated')
                }
            }
            save_json(game_path / "metadata.json", game_metadata)

            stats_10m = {
                "Time": timestamp, "UsersNow": pkg.get('UsageStats', {}).get('UsersNow', 0),
                "Favourited": favs, "Collections": pkg.get('Collections', 0),
                "VotesUp": up, "VotesDown": down, "LikePercentage": like_pct,
                "TotalUsers": deep_data["TotalUsers"], "TotalSeconds": deep_data["TotalSeconds"],
                "TotalSessions": deep_data["TotalSessions"], "FileCount": deep_data["FileCount"],
                "TotalSize": deep_data["TotalSize"], "ErrorRate": round(deep_data["ErrorRate"], 6)
            }

            history_10m = load_json(game_path / "10m.json", [])
            history_10m.append(stats_10m)

            # --- PRUNING LOGIC (GAME) ---
            keep_days = 14 if favs >= FAVOURITE_THRESHOLD else 7
            history_10m = prune_history(history_10m, keep_days)
            save_json(game_path / "10m.json", history_10m)

            for key in ["UsersNow", "Favourited", "Collections", "VotesUp", "VotesDown"]:
                org_total_stats[key] += stats_10m.get(key, 0)

            if is_midnight:
                history_1d = load_json(game_path / "1d.json", [])
                if not history_1d or history_1d[-1]['Time'][:10] != timestamp[:10]:
                    daily_peak = max([h['UsersNow'] for h in history_10m[-144:]]) if history_10m else stats_10m['UsersNow']
                    stats_1d = stats_10m.copy()
                    stats_1d['UsersNow'] = daily_peak
                    history_1d.append(stats_1d)
                    save_json(game_path / "1d.json", history_1d)

        # --- ORG AGGREGATION ---
        org_path = DATA_DIR / ident
        org_like_pct = calculate_like_percentage(org_total_stats["VotesUp"], org_total_stats["VotesDown"])
        org_h10m = load_json(org_path / "10m.json", [])
        org_h10m.append({"Time": timestamp, **org_total_stats, "LikePercentage": org_like_pct})

        # --- PRUNING LOGIC (ORG) ---
        # Orgs follow the same logic based on aggregate favorites
        org_keep_days = 14 if org_total_stats["Favourited"] >= FAVOURITE_THRESHOLD else 7
        org_h10m = prune_history(org_h10m, org_keep_days)
        save_json(org_path / "10m.json", org_h10m)

        if is_midnight:
            org_h1d = load_json(org_path / "1d.json", [])
            if not org_h1d or org_h1d[-1]['Time'][:10] != timestamp[:10]:
                peak = max([h['UsersNow'] for h in org_h10m[-144:]]) if org_h10m else org_total_stats['UsersNow']
                org_h1d.append({"Time": timestamp, **org_total_stats, "UsersNow": peak, "LikePercentage": org_like_pct})
                save_json(org_path / "1d.json", org_h1d)

    if orgs_modified:
        save_json(ORGS_FILE, valid_orgs)
        log(f"Orgs list updated. Removed {len(orgs) - len(valid_orgs)}.")

    if len(qualified_list) > initial_qualified_count:
        save_json(QUALIFIED_FILE, qualified_list)
        log(f"Qualified list updated: {len(qualified_list)}.")

    try:
        log("Triggering frontend build...")
        subprocess.run(["python3", str(GENERATE_SCRIPT)], check=True, cwd=str(BASE_DIR))
        log("Frontend build successful.")
    except Exception as e:
        log(f"  [ERROR] Frontend generation failed: {e}")

    duration = (datetime.now() - start_time).total_seconds()
    log(f"--- Run Complete. Duration: {duration:.2f}s ---")
    flush_logs()

if __name__ == "__main__":
    run_tracker()
