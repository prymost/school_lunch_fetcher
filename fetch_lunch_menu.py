"""
fetch_lunch_menu.py

Step 1 of the lunch-automation pipeline: fetch a month of lunch menu data
from LINQ Connect (formerly Titan / family.titank12.com) and print it out
in a clean, readable form so we can see exactly what nutrition data is
actually available before deciding how to score "most nutritious."

This does NOT touch your calendar. It's read-only, safe to run as many
times as you want.

--- How to get your buildingId / districtId (one-time, ~2 minutes) ---
1. Go to https://linqconnect.com
2. Search for and select your school district, then your child's school.
3. Open your browser's DevTools (F12) -> Network tab.
4. Click on the menu / reload the page.
5. Find a request to "FamilyMenu" and look at its query string —
   it will have `buildingId=...` and `districtId=...` (both are GUIDs
   like 12345678-abcd-ef01-2345-6789abcdef01).
6. Add those to a local `.env` file (see .env.example) or pass them as CLI args.

Usage:
    python3 fetch_lunch_menu.py --building-id <ID> --district-id <ID> [--month 9 --year 2026]
    # Or if configured in .env:
    python3 fetch_lunch_menu.py [--month 9 --year 2026]

If --month/--year are omitted, it defaults to *next* calendar month,
which is when you'd actually run this in production (menu for next
month is posted at the end of this month).
"""

import argparse
import calendar
import datetime
import json
import os
from pathlib import Path
import sys
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError


def load_env_file():
    """Load environment variables from a local .env file if present."""
    env_paths = [Path(".env"), Path(__file__).resolve().parent / ".env"]
    for env_path in env_paths:
        if env_path.is_file():
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k and k not in os.environ:
                                os.environ[k] = v
                break
            except Exception:
                pass

API_URL = "https://api.linqconnect.com/api/FamilyMenu"

NUTRIENT_MAP = {
    "Calories": "cal",
    "Cal": "cal",
    "Total Fat": "fat",
    "Fat": "fat",
    "Saturated Fat": "sfat",
    "Sfat": "sfat",
    "Trans Fat": "trans",
    "Trans": "trans",
    "Sodium": "na",
    "Na": "na",
    "Dietary Fiber": "fib",
    "TDF": "fib",
    "Total Sugars": "sug",
    "Sug": "sug",
    "Added Sugars": "asug",
    "ASug": "asug",
    "Protein": "pro",
    "Pro": "pro",
}

NUTRIENT_ORDER = [
    "cal",
    "fat",
    "sfat",
    "trans",
    "na",
    "fib",
    "sug",
    "asug",
    "pro",
]

SCHEMA_HEADER = """# Keys schema:
# cal: Calories (kcal)
# fat: Total Fat (g)
# sfat: Saturated Fat (g)
# trans: Trans Fat (g)
# na: Sodium (mg)
# fib: Dietary Fiber (g)
# sug: Total Sugars (g)
# asug: Added Sugars (g)
# pro: Protein (g)"""


def next_month_range(today=None):
    today = today or datetime.date.today()
    year = today.year + (1 if today.month == 12 else 0)
    month = 1 if today.month == 12 else today.month + 1
    last_day = calendar.monthrange(year, month)[1]
    start = datetime.date(year, month, 1)
    end = datetime.date(year, month, last_day)
    return start, end


def fetch_menu(building_id: str, district_id: str, start: datetime.date, end: datetime.date) -> dict:
    params = f"buildingId={building_id}&districtId={district_id}&startDate={start.month}-{start.day}-{start.year}&endDate={end.month}-{end.day}-{end.year}"
    url = f"{API_URL}?{params}"
    # LINQ Connect's edge (Cloudflare or similar) rejects requests that don't
    # look like they came from a real browser hitting linqconnect.com.
    headers = {
        "Origin": "https://linqconnect.com",
        "Referer": "https://linqconnect.com/",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        print(f"HTTP error {e.code} fetching menu: {e.reason}", file=sys.stderr)
        raise
    except URLError as e:
        print(f"Network error fetching menu: {e.reason}", file=sys.stderr)
        raise


def format_recipe_yaml(recipe: dict) -> list[str]:
    name = recipe.get("RecipeName") or recipe.get("MenuMealName") or "Unknown"
    raw_nutrients = {}
    for n in recipe.get("Nutrients") or []:
        n_name = (n.get("Name") or "").strip()
        n_abbr = (n.get("Abbreviation") or "").strip()
        key = NUTRIENT_MAP.get(n_name) or NUTRIENT_MAP.get(n_abbr)
        if key:
            val = n.get("Value")
            if val is not None:
                try:
                    val = float(val)
                    if val.is_integer():
                        val = int(val)
                except (ValueError, TypeError):
                    pass
                raw_nutrients[key] = val

    lines = [f"    - name: {json.dumps(name)}"]
    for key in NUTRIENT_ORDER:
        if key in raw_nutrients:
            val = raw_nutrients[key]
            # Trans fat and added sugars are omitted when 0
            if key in ("trans", "asug") and val == 0:
                continue
            lines.append(f"      {key}: {val}")
    return lines


def format_menu_yaml(data: dict, max_mains: int = 2) -> str:
    """Format menu data as YAML matching the expected schema."""
    lines = [SCHEMA_HEADER]

    # Collect days and entries
    day_entries = []

    for session in data.get("FamilyMenuSessions", []):
        session_name = session.get("ServingSession") or "Lunch"
        for plan in session.get("MenuPlans", []):
            for day in plan.get("Days", []):
                date_raw = day.get("Date")
                if not date_raw:
                    continue
                try:
                    dt = datetime.datetime.strptime(date_raw, "%m/%d/%Y")
                    date_iso = dt.strftime("%Y-%m-%d")
                    day_name = dt.strftime("%A")
                except ValueError:
                    date_iso = date_raw
                    day_name = ""

                for meal in day.get("MenuMeals", []):
                    meal_name = meal.get("MenuMealName") or session_name

                    # Find entrees / mains category
                    mains_recipes = []
                    for cat in meal.get("RecipeCategories", []):
                        cat_name = (cat.get("CategoryName") or "").lower()
                        if "entree" in cat_name or "main" in cat_name:
                            recipes = cat.get("Recipes", [])
                            if max_mains > 0:
                                recipes = recipes[:max_mains]
                            mains_recipes.extend(recipes)

                    if mains_recipes:
                        day_entries.append((date_iso, day_name, session_name, meal_name, mains_recipes))

    # Sort chronologically by date
    day_entries.sort(key=lambda item: item[0])

    for date_iso, day_name, session_name, meal_name, recipes in day_entries:
        lines.append(f"- date: {json.dumps(date_iso)}")
        if day_name:
            lines.append(f"  day: {json.dumps(day_name)}")
        lines.append(f"  session: {json.dumps(session_name)}")
        lines.append(f"  meal: {json.dumps(meal_name)}")
        lines.append("  mains:")
        for recipe in recipes:
            lines.extend(format_recipe_yaml(recipe))

    return "\n".join(lines)


def filter_menu_data(data: dict) -> dict:
    """Ignore breakfast and field trip menus to focus output only on regular school lunch offerings."""
    filtered_sessions = []
    for session in data.get("FamilyMenuSessions", []):
        session_name = (session.get("ServingSession") or "").lower()
        if "lunch" in session_name:
            filtered_plans = []
            for plan in session.get("MenuPlans", []):
                plan_name = (plan.get("MenuPlanName") or "").lower()
                if "field trip" in plan_name:
                    continue
                if "k-8/elementary lunch" in plan_name:
                    filtered_plans.append(plan)
            # If no plan matched specific elementary lunch filter, keep all non-field-trip lunch plans
            if not filtered_plans:
                for plan in session.get("MenuPlans", []):
                    plan_name = (plan.get("MenuPlanName") or "").lower()
                    if "field trip" not in plan_name:
                        filtered_plans.append(plan)
            session["MenuPlans"] = filtered_plans
            filtered_sessions.append(session)
    data["FamilyMenuSessions"] = filtered_sessions
    return data


def main():
    load_env_file()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--building-id",
        default=os.environ.get("LINQ_BUILDING_ID"),
        help="LINQ Connect buildingId (GUID). Defaults to LINQ_BUILDING_ID from env/.env.",
    )
    parser.add_argument(
        "--district-id",
        default=os.environ.get("LINQ_DISTRICT_ID"),
        help="LINQ Connect districtId (GUID). Defaults to LINQ_DISTRICT_ID from env/.env.",
    )
    parser.add_argument("--month", type=int, help="Month number (1-12). Defaults to next month.")
    parser.add_argument("--year", type=int, help="Year, e.g. 2026. Defaults alongside --month.")
    parser.add_argument("--max-mains", type=int, default=2, help="Max mains per day (default 2; 0 for unlimited).")
    parser.add_argument("--output", "-o", help="File to write output to (default: stdout).")
    parser.add_argument("--raw", action="store_true", help="Dump the full raw JSON instead of the summary.")
    args = parser.parse_args()

    if not args.building_id or not args.district_id:
        parser.error(
            "Both --building-id and --district-id are required (pass via CLI or set "
            "LINQ_BUILDING_ID and LINQ_DISTRICT_ID in a local .env file or environment)."
        )

    if args.month and args.year:
        last_day = calendar.monthrange(args.year, args.month)[1]
        start = datetime.date(args.year, args.month, 1)
        end = datetime.date(args.year, args.month, last_day)
    elif args.month and not args.year:
        today = datetime.date.today()
        year = today.year if args.month >= today.month else today.year + 1
        last_day = calendar.monthrange(year, args.month)[1]
        start = datetime.date(year, args.month, 1)
        end = datetime.date(year, args.month, last_day)
    else:
        start, end = next_month_range()

    print(f"Fetching menu for {start.strftime('%B %Y')} ({start} to {end})...", file=sys.stderr)
    data = fetch_menu(args.building_id, args.district_id, start, end)

    data = filter_menu_data(data)

    if args.raw:
        output_text = json.dumps(data, indent=2)
    else:
        output_text = format_menu_yaml(data, max_mains=args.max_mains)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_text + "\n")
        print(f"Menu written to {args.output}", file=sys.stderr)
    else:
        print(output_text)


if __name__ == "__main__":
    main()
