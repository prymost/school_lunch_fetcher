# School Lunch Fetcher & Monthly Planning Pipeline

A streamlined workflow and toolset to fetch, evaluate, and schedule elementary school lunches. 

The goal of this system is to pick **exactly 2 days per week** for elementary school hot lunch—selecting meals that are nutritious, whole-food based, and kid-appropriate—while packing homemade lunch on the other 3 days. Selected days are exported directly into an **iCalendar (`.ics`)** file ready for Google Calendar.

---

## Table of Contents
1. [Core Purpose & Methodology](#core-purpose--methodology)
2. [Nutritional & Kid-Behavior Rules](#nutritional--kid-behavior-rules)
3. [Step-by-Step Monthly Workflow](#step-by-step-monthly-workflow)
4. [Calendar Integration Specifications](#calendar-integration-specifications)
5. [CLI Tool Reference (`fetch_lunch_menu.py`)](#cli-tool-reference-fetch_lunch_menupy)
6. [Repository Files](#repository-files)
7. [Future Automation Roadmap](#future-automation-roadmap)

---

## Core Purpose & Methodology

School menus often cycle between whole foods, snacks masquerading as meals, and ultra-processed comfort foods. Rather than letting kids eat cafeteria food every day or guessing which days to pack lunch, this pipeline establishes a consistent monthly process:

1. **Extract**: Fetch complete nutritional data from LINQ Connect at the end of each month for the upcoming month.
2. **Filter & Select**: Apply whole-food and kid-behavior heuristics to pick the top 2 days per week.
3. **Schedule**: Export full-day events into an `.ics` file with standard naming (`🥪 <Meal Name>`) and import directly into Google Calendar.

---

## Nutritional & Kid-Behavior Rules

When evaluating menu options for an elementary schooler, we apply two strict layers of criteria:

### Layer 1: Dietary & Ingredient Standards
- **Exclude Ultra-Processed Foods:** Pizza (e.g., Pepperoni/Cheese pizza) is ultra-processed and disqualified.
- **Exclude Snacks Masquerading as Meals:** Nachos (e.g., Bean & Cheese Nacho Dippers) and yogurt packs are treated as snacks, not whole-food meals.
- **Exclude or Deprioritize Cured/Mystery Meats:** Hot dogs, cured salami plates, and plant-based processed nuggets/waffles are deprioritized.
- **Prioritize Whole Foods:**
  - Whole poultry and meats (e.g., chicken breasts/sandwiches, bone-in teriyaki wings, shredded beef birria).
  - Traditional staple dishes (e.g., bean & cheese pupusas made from corn masa).
  - Whole grains and vegetables (steamed rice, broccoli).
  - Lower sodium (< 700 mg target), low saturated fat (< 5g target), low added sugars, and high fiber/protein.

### Layer 2: Elementary Kid Psychology (The "Cafeteria Trap")
- **The Hot Dog Trap:** In an elementary school cafeteria line, if a healthy option (like cold tomato-mozzarella salad) is paired against a tempting junk option (like a warm hot dog), **kids will almost always pick the hot dog**. Sending a child on that day functionally means sending them for a hot dog.
- **Win-Win Days:** Pick days where **both** available cafeteria choices are acceptable warm meals (e.g., Pasta Alfredo or Beef Birria Quesadilla).
- **Kid-Favorite & Nutritious:** Pick days where the option the child will naturally gravitate toward is genuinely wholesome and packed with protein (e.g., Orange Chicken with Rice & Broccoli, Breaded Chicken Sandwich, Teriyaki Wings with Rice).

---

## Step-by-Step Monthly Workflow

Run this workflow near the end of each month (e.g., around the 25th–28th) when the upcoming month's menu is published:

### Step 1: Fetch the Upcoming Menu
```bash
# Setup: Copy .env.example to .env and configure your school's IDs once
cp .env.example .env

# Fetch next calendar month (default behavior)
python3 fetch_lunch_menu.py -o upcoming_menu.yaml

# Or fetch a specific month/year (e.g., October 2026)
python3 fetch_lunch_menu.py --month 10 --year 2026 -o october_menu.yaml
```

### Step 2: Evaluate & Select 2 Days Per Week
Feed the YAML output or review the days against the rules:
1. Divide the month into school weeks (Monday–Friday).
2. Disqualify Friday pizza days and snack days (nachos/yogurt).
3. Disqualify days where the kid will pick a hot dog or processed meat over a salad.
4. Select the two highest-scoring, kid-reliable days for each week.

### Step 3: Generate the Google Calendar `.ics` File
Create an `.ics` file (RFC 5545) containing an all-day event for each selected day:
- **Event Title:** Must start with a sandwich emoji `🥪 ` followed by the chosen entree name (e.g., `🥪 Breaded Chicken Sandwich`).
- **All-Day Event:** Uses `DTSTART;VALUE=DATE:YYYYMMDD` and `DTEND;VALUE=DATE:YYYYMMDD` (exclusive end date).
- **Event Description:** Contains calories, protein, fat, sodium, fiber, and the alternate menu option available in the cafeteria.

### Step 4: Import into Google Calendar
1. Open [Google Calendar](https://calendar.google.com).
2. Go to **Settings (⚙️)** → **Import & export**.
3. Under **Import**, select the generated `.ics` file and choose your target calendar.

---

## Calendar Integration Specifications

### Naming & Format Convention
- **Summary format:** `🥪 <Selected Meal Name>`
- **Example:** `🥪 Orange Chicken with Rice & Broccoli`
- **Transparency:** `TRANSP:TRANSPARENT` (all-day event that does not block scheduling availability).

### Sample `.ics` Event Block
```ics
BEGIN:VEVENT
UID:school-lunch-20261019@lunchfetcher
DTSTAMP:20261012T204100Z
DTSTART;VALUE=DATE:20261019
DTEND;VALUE=DATE:20261020
SUMMARY:🥪 Breaded Chicken Sandwich
DESCRIPTION:School Lunch Selection:\n- Breaded Chicken Sandwich (330 kcal, 9g fat, 2g sat fat, 598mg sodium, 6g fiber, 24g protein)\nAlternate option available: Spaghetti w/ Marinara
TRANSP:TRANSPARENT
END:VEVENT
```

---

## CLI Tool Reference (`fetch_lunch_menu.py`)

The script connects to LINQ Connect’s API and converts raw nutritional data into clean, token-efficient YAML.

| Argument | Default | Description |
|---|---|---|
| `--building-id` | `LINQ_BUILDING_ID` env | LINQ Connect building ID for the school. |
| `--district-id` | `LINQ_DISTRICT_ID` env | LINQ Connect district ID. |
| `--month` | Next month (`1-12`) | Calendar month to fetch. |
| `--year` | Next month's year | Year for the requested month. |
| `--max-mains` | `2` | Number of entrees to display per day (`0` for all). |
| `-o`, `--output` | `stdout` | Write output directly to a YAML file. |
| `--raw` | `False` | Output the raw JSON response. |

You can store your district and building IDs locally in a `.env` file (copied from `.env.example`), so you don't need to specify them on every command line invocation.

### Schema Abbreviations
The YAML output uses abbreviated keys to stay token-efficient for LLM evaluation:
- `cal`: Calories (kcal)
- `fat`: Total Fat (g)
- `sfat`: Saturated Fat (g)
- `trans`: Trans Fat (g)
- `na`: Sodium (mg)
- `fib`: Dietary Fiber (g)
- `sug`: Total Sugars (g)
- `asug`: Added Sugars (g)
- `pro`: Protein (g)

---

## Repository Files

- [`fetch_lunch_menu.py`](fetch_lunch_menu.py): Main script fetching menu data from LINQ Connect.
- [`.env.example`](.env.example): Example environment configuration file for district and building GUIDs.
- [`.gitignore`](.gitignore): Specifies untracked files (bytecode, `.env`, `.ics`, and generated `.yaml` files).
- [`README.md`](README.md): This documentation and process guide.

---

## Future Automation Roadmap

When moving to complete end-to-end automation, the target workflow is:
1. **Recurring Monthly Trigger:** Run on the 25th of every month (via cron, a GitHub Action, or an AI assistant).
2. **Automated Evaluator:** A Python script or agent prompt that runs `fetch_lunch_menu.py`, parses the output using the rules above, and auto-generates the month's `.ics` file.
3. **Direct Calendar Sync:** Use the Google Calendar API (or email delivery) to import the events into the family calendar without manual file uploading.
