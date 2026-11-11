#!/usr/bin/env python3
"""Turn raw GitHub data (.context/raw/*.json) into analytics and inject it into index.html.

Reads:  .context/raw/repos.json, .context/raw/owners.json
Writes: index.html  (replaces the JSON inside <script id="robo-data">...</script>)
Run with:  python3 -I tools/build.py
"""
import json
import re
import sys
import datetime
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / ".context" / "raw"
HTML = ROOT / "index.html"

# ---------------------------------------------------------------- location -> country
# Freeform GitHub "location" strings -> canonical country. Best-effort, hub-focused.
COUNTRY_ALIASES = {
    "usa": "United States", "u.s.a.": "United States", "u.s.": "United States",
    "us": "United States", "united states": "United States",
    "united states of america": "United States", "america": "United States",
    "uk": "United Kingdom", "u.k.": "United Kingdom", "england": "United Kingdom",
    "scotland": "United Kingdom", "wales": "United Kingdom", "great britain": "United Kingdom",
    "britain": "United Kingdom", "united kingdom": "United Kingdom",
    "deutschland": "Germany", "germany": "Germany",
    "schweiz": "Switzerland", "suisse": "Switzerland", "switzerland": "Switzerland",
    "nederland": "Netherlands", "the netherlands": "Netherlands", "netherlands": "Netherlands",
    "holland": "Netherlands",
    "españa": "Spain", "espana": "Spain", "spain": "Spain",
    "italia": "Italy", "italy": "Italy",
    "france": "France", "日本": "Japan", "japan": "Japan", "nippon": "Japan",
    "中国": "China", "china": "China", "prc": "China", "p.r.china": "China",
    "p.r. china": "China", "中国大陆": "China",
    "대한민국": "South Korea", "korea": "South Korea", "south korea": "South Korea",
    "republic of korea": "South Korea",
    "india": "India", "bharat": "India",
    "canada": "Canada", "australia": "Australia", "brasil": "Brazil", "brazil": "Brazil",
    "россия": "Russia", "russia": "Russia", "russian federation": "Russia",
    "polska": "Poland", "poland": "Poland", "sverige": "Sweden", "sweden": "Sweden",
    "norge": "Norway", "norway": "Norway", "suomi": "Finland", "finland": "Finland",
    "danmark": "Denmark", "denmark": "Denmark", "österreich": "Austria", "austria": "Austria",
    "belgium": "Belgium", "belgique": "Belgium", "belgie": "Belgium",
    "türkiye": "Turkey", "turkey": "Turkey", "turkiye": "Turkey",
    "singapore": "Singapore", "taiwan": "Taiwan", "台灣": "Taiwan", "台湾": "Taiwan",
    "hong kong": "Hong Kong", "香港": "Hong Kong",
    "ireland": "Ireland", "éire": "Ireland", "portugal": "Portugal",
    "greece": "Greece", "czech republic": "Czechia", "czechia": "Czechia",
    "israel": "Israel", "ישראל": "Israel", "mexico": "Mexico", "méxico": "Mexico",
    "argentina": "Argentina", "chile": "Chile", "colombia": "Colombia",
    "new zealand": "New Zealand", "iran": "Iran", "ukraine": "Ukraine", "україна": "Ukraine",
    "hungary": "Hungary", "romania": "Romania", "indonesia": "Indonesia",
    "vietnam": "Vietnam", "viet nam": "Vietnam", "thailand": "Thailand",
    "malaysia": "Malaysia", "philippines": "Philippines", "pakistan": "Pakistan",
    "south africa": "South Africa", "egypt": "Egypt", "saudi arabia": "Saudi Arabia",
    "united arab emirates": "UAE", "uae": "UAE", "slovenia": "Slovenia",
    "slovakia": "Slovakia", "croatia": "Croatia", "serbia": "Serbia",
    "bulgaria": "Bulgaria", "estonia": "Estonia", "latvia": "Latvia", "lithuania": "Lithuania",
    "luxembourg": "Luxembourg",
}
# City / region / state tokens -> country (common tech hubs).
CITY_TO_COUNTRY = {
    # US
    "san francisco": "United States", "sf": "United States", "bay area": "United States",
    "silicon valley": "United States", "mountain view": "United States", "palo alto": "United States",
    "new york": "United States", "nyc": "United States", "boston": "United States",
    "cambridge, ma": "United States", "seattle": "United States", "los angeles": "United States",
    "san diego": "United States", "pittsburgh": "United States", "austin": "United States",
    "chicago": "United States", "atlanta": "United States", "denver": "United States",
    "detroit": "United States", "ann arbor": "United States", "berkeley": "United States",
    "pasadena": "United States", "menlo park": "United States", "redmond": "United States",
    "sunnyvale": "United States", "santa clara": "United States", "washington, dc": "United States",
    "philadelphia": "United States", "houston": "United States", "dallas": "United States",
    "portland": "United States", "madison": "United States", "ithaca": "United States",
    # Europe
    "london": "United Kingdom", "oxford": "United Kingdom", "edinburgh": "United Kingdom",
    "manchester": "United Kingdom", "bristol": "United Kingdom",
    "zurich": "Switzerland", "zürich": "Switzerland", "lausanne": "Switzerland",
    "geneva": "Switzerland", "eth zurich": "Switzerland", "epfl": "Switzerland",
    "munich": "Germany", "münchen": "Germany", "berlin": "Germany", "hamburg": "Germany",
    "stuttgart": "Germany", "karlsruhe": "Germany", "aachen": "Germany", "bonn": "Germany",
    "freiburg": "Germany", "darmstadt": "Germany", "tübingen": "Germany", "bremen": "Germany",
    "paris": "France", "toulouse": "France", "grenoble": "France", "lyon": "France",
    "amsterdam": "Netherlands", "delft": "Netherlands", "eindhoven": "Netherlands",
    "rotterdam": "Netherlands", "utrecht": "Netherlands", "enschede": "Netherlands",
    "madrid": "Spain", "barcelona": "Spain", "valencia": "Spain", "zaragoza": "Spain",
    "milan": "Italy", "milano": "Italy", "rome": "Italy", "roma": "Italy", "turin": "Italy",
    "torino": "Italy", "bologna": "Italy", "genoa": "Italy", "genova": "Italy", "pisa": "Italy",
    "stockholm": "Sweden", "gothenburg": "Sweden", "lund": "Sweden",
    "oslo": "Norway", "trondheim": "Norway", "helsinki": "Finland", "espoo": "Finland",
    "copenhagen": "Denmark", "vienna": "Austria", "wien": "Austria", "graz": "Austria",
    "brussels": "Belgium", "leuven": "Belgium", "ghent": "Belgium", "gent": "Belgium",
    "lisbon": "Portugal", "porto": "Portugal", "warsaw": "Poland", "krakow": "Poland",
    "kraków": "Poland", "wroclaw": "Poland", "prague": "Czechia", "praha": "Czechia",
    "budapest": "Hungary", "athens": "Greece", "dublin": "Ireland",
    # Asia
    "tokyo": "Japan", "osaka": "Japan", "kyoto": "Japan", "nagoya": "Japan",
    "yokohama": "Japan", "tsukuba": "Japan",
    "beijing": "China", "shanghai": "China", "shenzhen": "China", "guangzhou": "China",
    "hangzhou": "China", "nanjing": "China", "wuhan": "China", "chengdu": "China",
    "xi'an": "China", "harbin": "China", "tianjin": "China", "hefei": "China",
    "seoul": "South Korea", "daejeon": "South Korea", "busan": "South Korea",
    "bangalore": "India", "bengaluru": "India", "mumbai": "India", "delhi": "India",
    "new delhi": "India", "hyderabad": "India", "chennai": "India", "pune": "India",
    "kolkata": "India", "kanpur": "India", "bombay": "India",
    "singapore": "Singapore", "taipei": "Taiwan", "hsinchu": "Taiwan",
    "tel aviv": "Israel", "haifa": "Israel", "jerusalem": "Israel",
    "tehran": "Iran", "istanbul": "Turkey", "ankara": "Turkey",
    # Americas / Oceania
    "toronto": "Canada", "montreal": "Canada", "montréal": "Canada", "vancouver": "Canada",
    "waterloo": "Canada", "edmonton": "Canada", "ottawa": "Canada",
    "sydney": "Australia", "melbourne": "Australia", "brisbane": "Australia",
    "perth": "Australia", "canberra": "Australia", "adelaide": "Australia",
    "auckland": "New Zealand", "wellington": "New Zealand",
    "sao paulo": "Brazil", "são paulo": "Brazil", "rio de janeiro": "Brazil",
    "buenos aires": "Argentina", "santiago": "Chile", "bogota": "Colombia",
    "mexico city": "Mexico", "ciudad de méxico": "Mexico",
}
US_STATES = {
    "al","ak","az","ar","ca","co","ct","de","fl","ga","hi","id","il","in","ia","ks","ky",
    "la","me","md","ma","mi","mn","ms","mo","mt","ne","nv","nh","nj","nm","ny","nc","nd",
    "oh","ok","or","pa","ri","sc","sd","tn","tx","ut","vt","va","wa","wv","wi","wy",
}

def to_country(loc):
    if not loc:
        return None
    raw = loc.strip().lower()
    raw = raw.replace("．", ".").replace("，", ",")
    # whole-string alias
    if raw in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[raw]
    # split on commas/pipes/slashes and inspect tokens, last-first (country usually last)
    parts = [p.strip() for p in re.split(r"[,/|·•\-]| and ", raw) if p.strip()]
    for p in reversed(parts):
        if p in COUNTRY_ALIASES:
            return COUNTRY_ALIASES[p]
        if p in CITY_TO_COUNTRY:
            return CITY_TO_COUNTRY[p]
        if p in US_STATES:
            return "United States"
    # substring sweeps as fallback
    for key, val in COUNTRY_ALIASES.items():
        if re.search(r"\b" + re.escape(key) + r"\b", raw):
            return val
    for key, val in CITY_TO_COUNTRY.items():
        if key in raw:
            return val
    return None

# ---------------------------------------------------------------- category from topics
CATEGORY_RULES = [
    ("SLAM & Perception", {"slam","visual-slam","lidar","point-cloud","pointcloud","perception",
                           "sensor-fusion","visual-odometry","vio","mapping","localization",
                           "occupancy-grid","3d-reconstruction"}),
    ("Aerial & Drones",   {"drone","uav","quadcopter","px4","ardupilot","flight-controller",
                           "multirotor","fpv","betaflight","mavlink","aerial-robotics"}),
    ("Autonomous Driving",{"autonomous-driving","self-driving-car","self-driving","autonomous-vehicles",
                           "adas","autonomous-car","lane-detection","carla","apollo","autoware"}),
    ("Manipulation",      {"manipulation","robot-arm","grasping","grasp","moveit","pick-and-place",
                           "dexterous","robotic-arm","end-effector"}),
    ("Legged & Humanoid", {"humanoid","humanoid-robot","quadruped","legged-robots","legged",
                           "biped","bipedal","hexapod","locomotion","walking-robot"}),
    ("Simulation",        {"simulation","gazebo","mujoco","physics-engine","pybullet","isaac-sim",
                           "isaac-gym","webots","simulator","digital-twin"}),
    ("Learning & Control",{"reinforcement-learning","robot-learning","imitation-learning",
                           "embodied-ai","deep-learning","machine-learning","rl","control-systems",
                           "model-predictive-control","mpc","optimal-control","policy-learning"}),
    ("Navigation",        {"navigation","path-planning","motion-planning","trajectory-optimization",
                           "obstacle-avoidance","nav2","global-planner"}),
    ("Framework & Middleware",{"ros","ros2","robot-operating-system","ros-noetic","middleware",
                           "rclcpp","rclpy","robotics-framework","dds"}),
]
CAT_ORDER = [c for c, _ in CATEGORY_RULES] + ["Robotics (general)"]

def to_category(topics, name, desc):
    t = set(x.lower() for x in (topics or []))
    hay = (name + " " + (desc or "")).lower()
    for cat, keys in CATEGORY_RULES:
        if t & keys:
            return cat
        for k in keys:
            if "-" in k and k.replace("-", " ") in hay:
                return cat
    # weak keyword fallback
    if "slam" in hay: return "SLAM & Perception"
    if "drone" in hay or "uav" in hay: return "Aerial & Drones"
    if "humanoid" in hay or "quadruped" in hay or "legged" in hay: return "Legged & Humanoid"
    if "ros" in t or "ros2" in t: return "Framework & Middleware"
    return "Robotics (general)"

ACCENTS = {
    "SLAM & Perception": "#3987e5", "Aerial & Drones": "#d95926",
    "Autonomous Driving": "#c98500", "Manipulation": "#d55181",
    "Legged & Humanoid": "#e66767", "Simulation": "#199e70",
    "Learning & Control": "#9085e9", "Navigation": "#008300",
    "Framework & Middleware": "#3987e5", "Robotics (general)": "#898781",
}

def year_of(iso):
    return int(iso[:4]) if iso else None

def main():
    repos = json.loads((RAW / "repos.json").read_text())
    owners = json.loads((RAW / "owners.json").read_text())
    loc_by_owner = {o["login"].lower(): (o.get("location") or None) for o in owners}
    name_by_owner = {o["login"].lower(): (o.get("name") or o["login"]) for o in owners}
    contrib_by_fn = {}
    cpath = RAW / "contributors.json"
    if cpath.exists():
        contrib_by_fn = {c["full_name"]: c.get("contributors") for c in json.loads(cpath.read_text())}

    out = []
    for r in repos:
        login = r["owner_login"].lower()
        loc = loc_by_owner.get(login)
        country = to_country(loc)
        cat = to_category(r.get("topics"), r["name"], r.get("description"))
        out.append({
            "full_name": r["full_name"], "url": r["html_url"], "name": r["name"],
            "owner": r["owner_login"], "owner_type": r.get("owner_type"),
            "owner_name": name_by_owner.get(login, r["owner_login"]),
            "desc": (r.get("description") or "").strip(),
            "stars": r.get("stars") or 0, "forks": r.get("forks") or 0,
            "issues": r.get("open_issues") or 0,
            "language": r.get("language") or "Other",
            "topics": r.get("topics") or [],
            "created": r.get("created_at"), "pushed": r.get("pushed_at"),
            "homepage": (r.get("homepage") or "").strip(),
            "license": r.get("license"),
            "country": country or "Unknown",
            "location": loc or "",
            "category": cat, "accent": ACCENTS.get(cat, "#898781"),
            "contributors": contrib_by_fn.get(r["full_name"]),
        })

    # -------- trending / momentum proxy (no star history available) ----------
    # star_rate (stars/day over lifetime) weighted by how recently the repo was pushed,
    # then converted to a percentile rank so colors spread evenly across [0,1].
    now = datetime.datetime.utcnow()
    def _days(iso):
        try:
            return max(1.0, (now - datetime.datetime.strptime(iso[:10], "%Y-%m-%d")).days)
        except Exception:
            return 3650.0
    raws = []
    for p in out:
        age = _days(p["created"])
        star_rate = p["stars"] / age
        push_recency = 2.718281828 ** (-_days(p["pushed"]) / 120.0)
        raws.append(star_rate * (0.35 + 0.65 * push_recency))
    order = sorted(range(len(out)), key=lambda i: raws[i])
    n = len(out)
    for rank, i in enumerate(order):
        out[i]["trending"] = round((rank / (n - 1)) if n > 1 else 1.0, 4)

    # -------- analytics aggregates
    years = [year_of(p["created"]) for p in out if p["created"]]
    y_min, y_max = min(years), max(years)
    per_year_count = defaultdict(int)
    per_year_stars = defaultdict(int)
    per_year_by_cat = defaultdict(lambda: defaultdict(int))
    for p in out:
        y = year_of(p["created"])
        if y is None:
            continue
        per_year_count[y] += 1
        per_year_stars[y] += p["stars"]
        per_year_by_cat[y][p["category"]] += 1

    timeline = []
    cum_c = cum_s = 0
    for y in range(y_min, y_max + 1):
        cum_c += per_year_count.get(y, 0)
        cum_s += per_year_stars.get(y, 0)
        timeline.append({
            "year": y, "new": per_year_count.get(y, 0), "cumRepos": cum_c,
            "newStars": per_year_stars.get(y, 0), "cumStars": cum_s,
            "byCat": dict(per_year_by_cat.get(y, {})),
        })

    def agg(key):
        c = defaultdict(lambda: {"count": 0, "stars": 0})
        for p in out:
            c[p[key]]["count"] += 1
            c[p[key]]["stars"] += p["stars"]
        rows = [{"label": k, **v} for k, v in c.items()]
        rows.sort(key=lambda x: -x["stars"])
        return rows

    by_country = agg("country")
    by_language = agg("language")
    by_category = agg("category")

    known_country = sum(1 for p in out if p["country"] != "Unknown")
    data = {
        "generated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "totals": {
            "repos": len(out),
            "stars": sum(p["stars"] for p in out),
            "forks": sum(p["forks"] for p in out),
            "countries": len([c for c in by_country if c["label"] != "Unknown"]),
            "languages": len(by_language),
            "knownCountryPct": round(100 * known_country / len(out)) if out else 0,
            "yearMin": y_min, "yearMax": y_max,
        },
        "catOrder": CAT_ORDER,
        "accents": ACCENTS,
        "timeline": timeline,
        "byCountry": by_country,
        "byLanguage": by_language,
        "byCategory": by_category,
        "repos": out,
    }

    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # Harden against breaking out of the <script> block. '<' and '>' only occur inside
    # string values here, and owner profile fields are attacker-controlled (e.g. a
    # literal "</script>" or "<!--"). Escaping them as </> keeps the blob valid
    # JSON (JSON.parse restores them) while making </script>, <script, <!-- inert in HTML.
    blob = blob.replace("<", "\\u003c").replace(">", "\\u003e")
    html = HTML.read_text()
    new_html, n = re.subn(
        r'(<script type="application/json" id="robo-data">).*?(</script>)',
        lambda m: m.group(1) + blob + m.group(2),
        html, count=1, flags=re.DOTALL)
    if n != 1:
        print("ERROR: data marker not found in index.html", file=sys.stderr)
        sys.exit(1)
    HTML.write_text(new_html)
    print(f"Injected {len(out)} repos | {data['totals']['stars']:,} stars | "
          f"{data['totals']['countries']} countries | years {y_min}-{y_max}")

if __name__ == "__main__":
    main()
