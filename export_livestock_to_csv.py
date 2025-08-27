#!/usr/bin/env python3
# Export livestock (genetics, pregnancy, weight, parent IDs, FarmID, birthday/country)
# Reads ONLY: <save>/placeables.xml
# Country mapping sources (priority):
#   1) --country-map JSON (explicit override)
#   2) RealisticLivestock mod: parse src/RealisticLivestock.lua -> AREA_CODES
#      - auto-detected via gameSettings.xml modsDirectoryOverride or default ./mods
#      - or pass --rl to point directly at the RL mod folder/zip
#   3) Otherwise: "Unknown (<raw>)"
#
# Run from .../My Games/FarmingSimulator2025:
#   python export_livestock_to_csv.py -s savegame1 --verbose
#   python export_livestock_to_csv.py -s savegame1 --rl "D:\Mods\FS25_RealisticLivestock.zip"
#   python export_livestock_to_csv.py -s savegame1 --country-map country_map.json

import argparse, csv, json, os, sys, zipfile, re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

COLUMNS = [
    "purchase_date", "current_shed", "breed", "country", "country_name", "country_iso",
    "FarmID", "unique_id", "name", "sex", "age", "purchase_price",
    "birthday_day", "birthday_month", "birthday_year",
    "is_parent", "is_pregnant", "preg_day", "preg_month", "preg_year", "preg_duration", "preg_fetus_count",
    "animal_health", "animal_gen_metabolism", "animal_gen_quality", "animal_gen_health",
    "animal_gen_fertility", "animal_gen_productivity",
    "weight", "mother_id", "father_id",
    "fetus_sexes", "fetus_breeds", "fetus_health", "fetus_mother_ids", "fetus_father_ids",
    "fetus_gen_metabolism", "fetus_gen_quality", "fetus_gen_health", "fetus_gen_fertility", "fetus_gen_productivity",
]

# ---------- tiny XML helpers ----------
def _basename_or(val: str, fallback: str = "") -> str:
    try: return os.path.basename(val) if val else fallback
    except Exception: return fallback

def _get_attr(elem: Optional[ET.Element], name: str, default: str = "") -> str:
    return elem.get(name, default) if elem is not None else default

def _child(elem: Optional[ET.Element], name: str) -> Optional[ET.Element]:
    return elem.find(name) if elem is not None else None

def _genetics(elem: Optional[ET.Element]) -> Dict[str, str]:
    g = _child(elem, "genetics")
    return {
        "metabolism": _get_attr(g, "metabolism"),
        "quality": _get_attr(g, "quality"),
        "health": _get_attr(g, "health"),
        "fertility": _get_attr(g, "fertility"),
        "productivity": _get_attr(g, "productivity"),
    }

# ---------- RL country mapping ----------
def _str_to_bool(s: str) -> bool:
    return str(s).strip().lower() in ("1", "true", "yes", "on")

def find_mods_dir(fs_root: str, verbose: bool = False) -> str:
    """Use gameSettings.xml modsDirectoryOverride when active; else ./mods next to gameSettings.xml."""
    settings_path = os.path.join(fs_root, "gameSettings.xml")
    default_dir = os.path.join(fs_root, "mods")
    if not os.path.isfile(settings_path):
        if verbose: print(f"[info] gameSettings.xml not found; using default mods dir: {default_dir}")
        return default_dir
    try:
        root = ET.parse(settings_path).getroot()
    except Exception as e:
        if verbose: print(f"[warn] could not parse gameSettings.xml: {e}")
        return default_dir
    node = root.find("modsDirectoryOverride")
    if node is None:
        for child in root:
            if child.tag.lower() == "modsdirectoryoverride":
                node = child; break
    if node is None:
        if verbose: print(f"[info] modsDirectoryOverride not present; using default mods dir: {default_dir}")
        return default_dir
    active = node.get("active") or ""
    directory = node.get("directory") or ""
    if not directory:
        dc = node.find("directory")
        if dc is not None and dc.text: directory = dc.text.strip()
    if _str_to_bool(active) and directory:
        directory = os.path.expanduser(os.path.expandvars(directory))
        if verbose: print(f"[info] modsDirectoryOverride active -> {directory}")
        return directory
    if verbose: print(f"[info] modsDirectoryOverride inactive; using default mods dir: {default_dir}")
    return default_dir

def _brace_body(text: str, header: str) -> Optional[str]:
    """Return the text inside the top-level braces after 'header' (brace-matched)."""
    i = text.find(header)
    if i < 0: return None
    j = text.find("{", i)
    if j < 0: return None
    depth = 0
    for k in range(j, len(text)):
        c = text[k]
        if c == "{": depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[j+1:k]
    return None

def _parse_area_codes_from_lua(lua_text: str) -> Tuple[Dict[str,str], Dict[str,str]]:
    """Return (id->country_name, id->iso_code) by parsing AREA_CODES = { ... }."""
    body = _brace_body(lua_text, "AREA_CODES")
    if not body: return {}, {}
    name_map, iso_map = {}, {}
    for entry in re.finditer(r'\[\s*(\d+)\s*\]\s*=\s*{(.*?)}', body, flags=re.S):
        idx = entry.group(1)
        sub = entry.group(2)
        m_code = re.search(r'\["code"\]\s*=\s*"([^"]*)"', sub)
        m_name = re.search(r'\["country"\]\s*=\s*"([^"]*)"', sub)
        if m_name: name_map[idx] = m_name.group(1)
        if m_code: iso_map[idx]  = m_code.group(1)
    return name_map, iso_map

def _looks_like_rl_mod(name: str) -> bool:
    n = name.lower()
    return ("realistic" in n and "livestock" in n) or n.startswith("fs25_realisticlivestock")

def _load_area_codes_from_rl_path(path: str, verbose: bool=False) -> Tuple[Dict[str,str], Dict[str,str]]:
    """Load AREA_CODES from a specific RL mod folder or zip."""
    if os.path.isdir(path):
        # Look for **/RealisticLivestock.lua (case-insensitive)
        for root, _dirs, files in os.walk(path):
            for fn in files:
                if fn.lower() == "realisticlivestock.lua":
                    lua_path = os.path.join(root, fn)
                    if verbose: print(f"[info] reading RL lua: {lua_path}")
                    try:
                        with open(lua_path, "r", encoding="utf-8", errors="ignore") as fh:
                            txt = fh.read()
                        return _parse_area_codes_from_lua(txt)
                    except Exception as e:
                        if verbose: print(f"[warn] failed to read RL lua: {e}")
    elif os.path.isfile(path) and path.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(path, "r") as zf:
                # any path ending with /RealisticLivestock.lua (case-insensitive)
                cands = [n for n in zf.namelist() if n.lower().endswith("/realisticlivestock.lua") or n.lower()== "realisticlivestock.lua"]
                for n in cands:
                    if verbose: print(f"[info] reading RL lua from zip: {path} -> {n}")
                    txt = zf.read(n).decode("utf-8", errors="ignore")
                    return _parse_area_codes_from_lua(txt)
        except Exception as e:
            if verbose: print(f"[warn] failed to inspect zip {path}: {e}")
    return {}, {}

def load_area_codes_from_rl(mods_dir: str, verbose: bool=False) -> Tuple[Dict[str,str], Dict[str,str], List[str]]:
    """
    Search mods_dir for RL (folder or zip) and parse AREA_CODES.
    Returns (name_map, iso_map, checked_paths) for debug visibility.
    """
    checked = []
    if not os.path.isdir(mods_dir):
        return {}, {}, checked

    # 1) Prefer obvious RL-named entries
    entries = os.listdir(mods_dir)
    rl_candidates = [e for e in entries if _looks_like_rl_mod(e)]
    scan_order = rl_candidates + [e for e in entries if e not in rl_candidates]

    for entry in scan_order:
        p = os.path.join(mods_dir, entry)
        checked.append(p)
        names, isos = _load_area_codes_from_rl_path(p, verbose=verbose)
        if names:
            return names, isos, checked

    # 2) As a last resort, brute-force look inside every zip for the lua
    for entry in entries:
        p = os.path.join(mods_dir, entry)
        if os.path.isfile(p) and p.lower().endswith(".zip"):
            checked.append(p)
            try:
                with zipfile.ZipFile(p, "r") as zf:
                    lua_members = [n for n in zf.namelist() if n.lower().endswith("/realisticlivestock.lua") or n.lower()=="realisticlivestock.lua"]
                    if lua_members:
                        txt = zf.read(lua_members[0]).decode("utf-8", errors="ignore")
                        names, isos = _parse_area_codes_from_lua(txt)
                        if names:
                            return names, isos, checked
            except Exception:
                pass

    return {}, {}, checked

def _load_country_map_json(path: Optional[str]) -> Dict[str, str]:
    if not path: return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return {str(k): str(v) for k, v in data.items()}
    except Exception as e:
        print(f"[warn] failed to read country map '{path}': {e}", file=sys.stderr)
        return {}

def _country_lookup(code_raw: str, name_map: Dict[str,str], iso_map: Dict[str,str], json_map: Dict[str,str]) -> Tuple[str,str]:
    if not code_raw: return "", ""
    # JSON override:
    if code_raw in json_map: return json_map[code_raw], ""
    try:
        as_int = str(int(float(code_raw)))
        if as_int in json_map: return json_map[as_int], ""
    except Exception:
        pass
    # RL mapping:
    key = None
    try: key = str(int(float(code_raw)))
    except Exception: key = code_raw
    name = name_map.get(key, "")
    iso  = iso_map.get(key, "")
    if not name and code_raw in name_map:
        name = name_map[code_raw]; iso = iso_map.get(code_raw, iso)
    return (name or f"Unknown ({code_raw})", iso)

# ---------- placeables parsing ----------
def parse_placeables(placeables_path: str, country_name_map: Dict[str,str], country_iso_map: Dict[str,str], json_override: Dict[str,str]) -> List[Dict[str, str]]:
    try:
        tree = ET.parse(placeables_path)
    except Exception as e:
        print(f"[error] Failed to parse {placeables_path}: {e}", file=sys.stderr)
        return []
    root = tree.getroot()
    rows: List[Dict[str, str]] = []

    for plc in root.findall("placeable"):
        shed_file = plc.get("filename", "")
        current_shed = _basename_or(shed_file, plc.get("uniqueId", "Husbandry"))

        ha = plc.find("husbandryAnimals")
        if ha is None: continue
        clusters = ha.find("clusters")
        if clusters is None: continue

        for animal in clusters.findall("animal"):
            row = {k: "" for k in COLUMNS}

            # core
            row["current_shed"] = current_shed
            row["breed"]        = _get_attr(animal, "subType")
            row["sex"]          = _get_attr(animal, "gender")
            row["age"]          = _get_attr(animal, "age")
            row["FarmID"]       = _get_attr(animal, "farmId")
            row["unique_id"]    = _get_attr(animal, "id")
            row["name"]         = _get_attr(animal, "name")
            row["is_parent"]    = _get_attr(animal, "isParent")
            row["is_pregnant"]  = _get_attr(animal, "isPregnant")

            # animal health + genetics
            row["animal_health"] = _get_attr(animal, "health")
            agen = _genetics(animal)
            row["animal_gen_metabolism"]   = agen["metabolism"]
            row["animal_gen_quality"]      = agen["quality"]
            row["animal_gen_health"]       = agen["health"]
            row["animal_gen_fertility"]    = agen["fertility"]
            row["animal_gen_productivity"] = agen["productivity"]

            # body & parentage
            row["weight"]     = _get_attr(animal, "weight")
            row["mother_id"]  = _get_attr(animal, "motherId")
            row["father_id"]  = _get_attr(animal, "fatherId")

            # birthday & country
            bday = _child(animal, "birthday")
            if bday is not None:
                row["birthday_day"]   = _get_attr(bday, "day")
                row["birthday_month"] = _get_attr(bday, "month")
                row["birthday_year"]  = _get_attr(bday, "year")
                row["country"]        = _get_attr(bday, "country")
                cname, ciso           = _country_lookup(row["country"], country_name_map, country_iso_map, json_override)
                row["country_name"]   = cname
                row["country_iso"]    = ciso

            # pregnancy
            preg = _child(animal, "pregnancy")
            if preg is not None:
                row["preg_day"]      = _get_attr(preg, "day")
                row["preg_month"]    = _get_attr(preg, "month")
                row["preg_year"]     = _get_attr(preg, "year")
                row["preg_duration"] = _get_attr(preg, "duration")

                f_sex, f_breed, f_health = [], [], []
                f_mids, f_fids = [], []
                f_gm, f_gq, f_gh, f_gf, f_gp = [], [], [], [], []

                pregnancies = _child(preg, "pregnancies")
                if pregnancies is not None:
                    for fetus in pregnancies.findall("pregnancy"):
                        f_sex.append(_get_attr(fetus, "gender"))
                        f_breed.append(_get_attr(fetus, "subType"))
                        f_health.append(_get_attr(fetus, "health"))
                        f_mids.append(_get_attr(fetus, "motherId"))
                        f_fids.append(_get_attr(fetus, "fatherId"))
                        fg = _genetics(fetus)
                        f_gm.append(fg["metabolism"]); f_gq.append(fg["quality"]); f_gh.append(fg["health"])
                        f_gf.append(fg["fertility"]);   f_gp.append(fg["productivity"])

                row["preg_fetus_count"]      = str(len(f_sex))
                row["fetus_sexes"]           = "|".join(f_sex)
                row["fetus_breeds"]          = "|".join(f_breed)
                row["fetus_health"]          = "|".join(f_health)
                row["fetus_mother_ids"]      = "|".join(f_mids)
                row["fetus_father_ids"]      = "|".join(f_fids)
                row["fetus_gen_metabolism"]  = "|".join(f_gm)
                row["fetus_gen_quality"]     = "|".join(f_gq)
                row["fetus_gen_health"]      = "|".join(f_gh)
                row["fetus_gen_fertility"]   = "|".join(f_gf)
                row["fetus_gen_productivity"]= "|".join(f_gp)

            rows.append(row)
    return rows

# ---------- CLI ----------
def resolve_save_dir(save_arg: str) -> str:
    cand = os.path.abspath(save_arg)
    if os.path.isdir(cand): return cand
    return os.path.join(os.getcwd(), save_arg)

def main():
    ap = argparse.ArgumentParser(description="Export livestock (genetics, pregnancy, weight, parent IDs, FarmID, birthday/country) from a FS2025 save.")
    ap.add_argument("-s", "--save", default="savegame1", help="Savegame folder name or path (default: savegame1).")
    ap.add_argument("-o", "--out", default=None, help="Output CSV path (default: <save>/livestock.csv)")
    ap.add_argument("--country-map", default=None, help="Optional JSON mapping for country codes to names (overrides RL).")
    ap.add_argument("--rl", default=None, help="Path to the RealisticLivestock mod (folder or .zip). If omitted, auto-detect in mods dir.")
    ap.add_argument("--verbose", action="store_true", help="Print discovery info.")
    args = ap.parse_args()

    fs_root  = os.getcwd()
    save_dir = resolve_save_dir(args.save)
    placeables_path = os.path.join(save_dir, "placeables.xml")
    if not os.path.isfile(placeables_path):
        print(f"[error] placeables.xml not found at: {placeables_path}", file=sys.stderr); sys.exit(1)

    # 1) JSON override
    json_override = _load_country_map_json(args.country_map)

    # 2) RL AREA_CODES (either explicit --rl or auto)
    name_map, iso_map, checked = {}, {}, []
    if not json_override:
        if args.rl:
            if args.verbose: print(f"[info] using RL path: {args.rl}")
            name_map, iso_map = _load_area_codes_from_rl_path(args.rl, verbose=args.verbose)
            checked = [args.rl]
        else:
            mods_dir = find_mods_dir(fs_root, verbose=args.verbose)
            if args.verbose: print(f"[info] scanning mods dir: {mods_dir}")
            name_map, iso_map, checked = load_area_codes_from_rl(mods_dir, verbose=args.verbose)
        if args.verbose:
            if name_map:
                print(f"[info] RL AREA_CODES found ({len(name_map)} entries).")
            else:
                print("[warn] RealisticLivestock.lua with AREA_CODES not found.")
                if checked:
                    print("[info] paths checked:")
                    for p in checked:
                        print("  -", p)

    rows = parse_placeables(placeables_path, name_map, iso_map, json_override)

    out_csv = args.out or os.path.join(save_dir, "livestock.csv")
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exported {len(rows)} animals from {os.path.basename(save_dir)} → {out_csv}")

if __name__ == "__main__":
    main()
