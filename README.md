# Export Livestock to CSV / Excel — README

Export all livestock from a **Farming Simulator 2025** save into clean CSV files or an Excel workbook — complete with **genetics, health, pregnancy details, birthdays & countries (auto-mapped via Realistic Livestock)**, and rich **summary stats**.

---

## ✨ What it does

* Reads **only** your save’s `placeables.xml` (no game files modified).
* Exports:

  * **Animals** table (one row per animal).
  * **Fetuses** table (one row per fetus, linked to its mother).
  * **Summary** (by shed/species/breed: counts, % pregnant, average genetics/health/age).
* Adds derived fields: **age\_days**, **age\_years**, **preg\_due\_date**.
* Detects **country name / ISO code** from the **Realistic Livestock** mod’s `AREA_CODES`.
* Respects **modsDirectoryOverride** in `gameSettings.xml`.
* Optional filters (**species**, **FarmID**) and **batch mode** for **all saves**.
* Writes **Excel (.xlsx)** with 3 sheets if `openpyxl` is installed; otherwise CSVs.

---

## ✅ Requirements

* **Python 3.8+**
* Optional (for `.xlsx`): `openpyxl`

  ```powershell
  python -m pip install --upgrade openpyxl
  ```

---

## 🗺️ Where to put it & how it finds things

Place the script in your FS25 documents folder, e.g.:

```
E:\Users\<You>\OneDrive\Documents\My Games\FarmingSimulator2025\
  ├─ gameSettings.xml
  ├─ mods\ (or a custom mods dir via modsDirectoryOverride)
  ├─ savegame1\
  │   └─ placeables.xml
  └─ export_livestock_to_csv.py   ← put the script here
```

**Country mapping** is auto-loaded from the Realistic Livestock mod:

* Reads `gameSettings.xml` → `<modsDirectoryOverride active="true" directory="...">`.
* Scans that folder (or default `./mods`) for a folder/zip named like `FS25_RealisticLivestock`.
* Parses `src/RealisticLivestock.lua` to build the country **ID → (name, ISO)** map.

You can also point straight to the mod with `--rl "C:\path\to\FS25_RealisticLivestock.zip"` or provide your own JSON map via `--country-map`.

---

## 🚀 Quick start

From your FS25 folder:

```powershell
# Excel output (requires openpyxl), verbose logs
py .\export_livestock_to_csv.py --save savegame1 --verbose --xlsx
```

Example run (your output may vary):

```
PS *USER_SAVE_LOCATION*\Documents\My Games\FarmingSimulator2025> py .\export_livestock_to_csv.py --save savegame1 --verbose --xlsx
[info] modsDirectoryOverride active -> *USER_SAVE_LOCATION*\Documents\My Games\FS25 Mod Sources\New_Map_Test
[info] scanning mods dir: *USER_SAVE_LOCATION*\Documents\My Games\FS25 Mod Sources\New_Map_Test
[info] reading RL lua from zip: *USER_SAVE_LOCATION*\Documents\My Games\FS25 Mod Sources\New_Map_Test\FS25_RealisticLivestock.zip -> src/RealisticLivestock.lua
[info] parsed: animals=73, fetuses=56
[ok] savegame1: wrote *USER_SAVE_LOCATION*\Documents\My Games\FarmingSimulator2025\savegame1\savegame1_livestock.xlsx
```

If `openpyxl` is missing, the script automatically writes three CSVs instead.

---

## 🧰 Command reference

```
py export_livestock_to_csv.py [--save SAVE | --all-saves]
                              [--xlsx [PATH_OR_DIR]] [--out ANIMALS_CSV]
                              [--summary-out SUMMARY_CSV]
                              [--species cows,sheep,pigs] [--farmid N]
                              [--rl RL_PATH] [--country-map JSON] [--verbose]
```

**Primary:**

* `--save SAVE`
  Save folder or path (default: `savegame1`).
* `--all-saves`
  Process every `savegame*` under the current folder.

**Outputs:**

* `--xlsx` *(optional value)*

  * `--xlsx` (no value): writes `<save>/<save>_livestock.xlsx`.
  * `--xlsx D:\Reports\` (dir): writes workbook(s) into that folder.
  * Falls back to CSVs if `openpyxl` not installed.
* `--out ANIMALS_CSV`
  Path for Animals CSV (default: `<save>/livestock.csv`).
* `--summary-out SUMMARY_CSV`
  Path for Summary CSV (default: `<save>/livestock_summary.csv`).
  *(Fetuses CSV path is derived from Animals CSV: `*_fetuses.csv`.)*

**Country mapping:**

* `--rl PATH`
  Path to the Realistic Livestock mod **folder or .zip**; skips auto-discovery.
* `--country-map JSON`
  Custom JSON map of `country_id -> country_name` (overrides RL map).
  Example:

  ```json
  { "1": "United States", "14": "United Kingdom" }
  ```

**Filters:**

* `--species cows,sheep,pigs`
  Only include those species. (Heuristic: animal/type, placeable `type`, or shed filename.)
* `--farmid N`
  Include animals where `FarmID == N`.

**Misc:**

* `--verbose`
  Print discovery & parse details (mods folder used, RL detection, counts).

---

## 📄 What gets exported

### Animals sheet / `livestock.csv`

| Column                           | Description                                                           |
| -------------------------------- | --------------------------------------------------------------------- |
| placeable\_id                    | ID/uniqueId of the shed’s `<placeable>`                               |
| current\_shed                    | Basename of placeable `filename` (e.g. `cowBarnF2A1.xml`) or fallback |
| shed\_type                       | `<placeable><type>` or the filename stem                              |
| species                          | Inferred (cows, sheep, pigs, chickens, goats, horses)                 |
| breed                            | Animal `@subType`                                                     |
| FarmID                           | Animal `@farmId`                                                      |
| unique\_id                       | Animal `@id`                                                          |
| name                             | Animal `@name` (if present)                                           |
| sex                              | Animal `@gender`                                                      |
| age                              | Months (as stored)                                                    |
| age\_days                        | Approx. `age * 30` (integer)                                          |
| age\_years                       | `age / 12` (2 decimals)                                               |
| weight                           | Animal `@weight` (as stored)                                          |
| animal\_health                   | Animal `@health`                                                      |
| animal\_gen\_\*                  | From `<genetics metabolism/quality/health/fertility/productivity>`    |
| birthday\_day/month/year         | From `<birthday ...>`                                                 |
| country                          | Raw country ID from `<birthday country="...">`                        |
| country\_name / country\_iso     | Mapped via RL `AREA_CODES` or your `--country-map`                    |
| is\_parent                       | Animal `@isParent`                                                    |
| is\_pregnant                     | Animal `@isPregnant`                                                  |
| preg\_day/month/year             | From `<pregnancy ...>`                                                |
| preg\_duration                   | Duration (days)                                                       |
| preg\_due\_date                  | `preg_date + duration` (ISO date)                                     |
| preg\_fetus\_count               | Number of fetuses in this pregnancy                                   |
| purchase\_date / purchase\_price | **Not stored** in `placeables.xml` (left blank)                       |

### Fetuses sheet / `livestock_fetuses.csv`

| Column                                          | Description                   |
| ----------------------------------------------- | ----------------------------- |
| mother\_unique\_id                              | Links fetus row to its mother |
| current\_shed / shed\_type / species            | As above (copied from mom)    |
| mother\_breed                                   | Mom’s breed                   |
| fetus\_index                                    | 1..N within that pregnancy    |
| sex / breed                                     | Fetus attributes              |
| health                                          | Fetus `@health`               |
| gen\_\*                                         | Fetus `<genetics ...>`        |
| due\_date                                       | Same as mom’s `preg_due_date` |
| preg\_\*                                        | Copied from mom               |
| FarmID / country / country\_name / country\_iso | Copied from mom               |

### Summary sheet / `livestock_summary.csv`

Aggregated by **current\_shed × species × breed**:

* `animals_count`, `pregnant_count`, `total_fetuses`
* `avg_age_months`, `avg_age_years`
* `avg_health`
* `avg_gen_metabolism`, `avg_gen_quality`, `avg_gen_health`, `avg_gen_fertility`, `avg_gen_productivity`

---

## 🧪 Examples

**All saves → Excel per save (default file name in each save folder):**

```powershell
py .\export_livestock_to_csv.py --all-saves --xlsx --verbose
```

**Only cows on FarmID 2 → Excel into a specific reports folder:**

```powershell
py .\export_livestock_to_csv.py --all-saves --species cows --farmid 2 --xlsx "E:\Reports\FS25\" --verbose
```

**Force RL mapping from a specific file (skip auto):**

```powershell
py .\export_livestock_to_csv.py --save savegame1 --rl "E:\Mods\FS25_RealisticLivestock.zip" --xlsx --verbose
```

**Use a custom JSON country map (overrides RL):**

```powershell
py .\export_livestock_to_csv.py --save savegame1 --country-map ".\country_map.json" --xlsx
```

---

## 🔎 How key fields are derived

* **species** — looks at `animal@type` / `animal@animalType`, then `<placeable><type>`, then shed filename (e.g., `cowBarn…` → cows).
* **age\_days** — months × **30** (consistent, simple approximation).
* **age\_years** — months ÷ **12** (two decimals).
* **preg\_due\_date** — `date(preg_year,preg_month,preg_day) + duration_days`. If any part is missing/invalid, it’s blank.
* **country\_name / country\_iso** — from the Realistic Livestock mod’s `AREA_CODES` (Lua) or an explicit `--country-map` JSON. If neither is available, shows `Unknown (<id>)`.

---

## 🛠️ Troubleshooting

* **“openpyxl not installed; writing CSVs instead.”**
  Install it:

  ```powershell
  python -m pip install --upgrade openpyxl
  ```
* **“RealisticLivestock.lua with AREA\_CODES not found.”**

  * Check `gameSettings.xml` → mods folder path.
  * Ensure RL is in that folder.
  * Run with `--rl "path\to\FS25_RealisticLivestock.zip"` to bypass scanning.
* **Country still shows “Unknown (X)”.**

  * Your animals’ `<birthday country="X">` value isn’t in RL’s list.
  * Provide your own map: `--country-map my_map.json`.
* **No animals exported / empty CSV.**

  * Ensure animals live under: `/placeables/placeable/husbandryAnimals/clusters/animal`.
  * Confirm you are targeting the correct save folder with `--save`.
* **Permission / path errors.**

  * Close the workbook if it’s already open in Excel.
  * Use full paths and quote paths with spaces.
  * Make sure you’re running from the FS25 folder.

---

## 📦 Output layout

* **Excel** (if `--xlsx` and `openpyxl` available):
  `<save>/<save>_livestock.xlsx` (sheets: **Animals**, **Fetuses**, **Summary**)
  or into your specified directory/file.
* **CSV fallback** (or when you choose CSV):

  * `<save>/livestock.csv`
  * `<save>/livestock_fetuses.csv`
  * `<save>/livestock_summary.csv`

---

## 🧩 Notes & limits

* `purchase_date` and `purchase_price` aren’t stored in `placeables.xml`; columns are kept for consistency but left blank.
* Species detection is heuristic; feel free to suggest additional keywords to tighten it for your map/mod set.
* Calculations use simple, locale-safe numeric formatting (strings); adjust as needed if you plan further analytics.

---

