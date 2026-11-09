import difflib
import math
import re
import statistics
from typing import Annotated, Literal

from pydantic import Field

try:
    from mcp.server.mcpserver import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer
    from mcp.server.fastmcp.exceptions import ToolError

OZ_ML, DASH_OZ, BOTTLE_OZ = 29.5735, 1 / 32, 25.36


BOOK = {
    "Carpano Antica Formula": (16.5, 16.0, 0.6, "wine"), "Dolin Blanc": (16.0, 13.0, 0.6, "wine"),
    "Dolin Dry": (17.5, 3.0, 0.6, "wine"), "Dolin Rouge": (16.0, 13.0, 0.6, "wine"),
    "Generic dry vermouth": (17.5, 3.0, 0.6, "wine"), "Generic sweet vermouth": (16.5, 16.0, 0.6, "wine"),
    "Lillet Blanc": (17.0, 9.5, 0.6, "wine"), "Martinelli": (16.0, 16.0, 0.6, "wine"),
    "Amaro CioCiaro": (30.0, 16.0, 0, "liqueur"), "Amer Picon": (15.0, 20.0, 0, "liqueur"),
    "Aperol": (11.0, 24.0, 0, "liqueur"), "Benedictine": (40.0, 24.5, 0, "liqueur"),
    "Campari": (24.0, 24.0, 0, "liqueur"), "Green Chartreuse": (55.0, 25.0, 0, "liqueur"),
    "Yellow Chartreuse": (40.0, 31.2, 0, "liqueur"), "Cointreau": (40.0, 25.0, 0, "liqueur"),
    "White creme de cacao": (24.0, 39.5, 0, "liqueur"), "Creme de violette": (20.0, 37.5, 0, "liqueur"),
    "Drambuie": (40.0, 30.0, 0, "liqueur"), "Fernet Branca": (39.0, 8.0, 0, "liqueur"),
    "Luxardo Maraschino": (32.0, 35.0, 0, "liqueur"),
    "Angostura bitters": (44.7, 4.2, 0, "bitters"), "Peychauds bitters": (35.0, 5.0, 0, "bitters"),
    "Ashmeads Kernel apple juice": (0, 14.7, 1.25, "juice"), "Concord grape juice": (0, 18.0, 0.5, "juice"),
    "Cranberry juice": (0, 13.3, 3.6, "juice"), "Granny Smith apple juice": (0, 13.0, 0.93, "juice"),
    "Grapefruit juice": (0, 10.4, 2.4, "juice"), "Honeycrisp apple juice": (0, 13.8, 0.66, "juice"),
    "Orange juice": (0, 12.4, 0.8, "juice"), "Strawberry juice": (0, 8.0, 1.5, "juice"),
    "Wickson apple juice": (0, 14.7, 1.25, "juice"),
    "Champagne acid": (0, 0, 6.0, "acid"), "Lemon juice": (0, 1.6, 6.0, "acid"),
    "Lime acid orange": (0, 0, 6.0, "acid"), "Lime juice": (0, 1.6, 6.0, "acid"),
    "Orange juice lime strength": (0, 12.4, 6.0, "acid"), "Sour orange juice": (0, 12.3, 4.5, "acid"),
    "70 Brix caramel syrup": (0, 61.5, 0, "syrup"), "Butter syrup": (0, 42.1, 0, "syrup"),
    "Coriander syrup": (0, 61.5, 0, "syrup"), "Demerara syrup": (0, 61.5, 0, "syrup"),
    "Djer syrup": (0, 61.5, 0, "syrup"), "Honey syrup": (0, 61.5, 0, "syrup"), "Maple syrup": (0, 87.5, 0, "syrup"),
    "Any nut orgeat": (0, 61.5, 0, "syrup"), "Commercial orgeat": (0, 85.5, 0, "syrup"),
    "Quinine simple syrup": (0, 61.5, 0, "syrup"), "Simple syrup": (0, 61.5, 0, "syrup"),
    "Rich simple syrup": (0, 88.7, 0, "syrup"),
    "Cabernet sauvignon": (14.5, 0.2, 0.55, "wine"), "Coconut water": (0, 6.0, 0, "juice"),
    "Espresso": (0, 0, 1.5, "other"),
}
ADDED = {
    "Pineapple juice": (0, 6.0, 0.9, "juice"),
    "Agave syrup": (0, 61.5, 0, "syrup"),
    "Grenadine": (0, 61.5, 0, "syrup"),
    "Grand Marnier": (40, 21.4, 0, "liqueur"), "St Germain": (20, 37, 0, "liqueur"),
    "Cherry liqueur": (24, 36, 0, "liqueur"), "Amaretto": (24, 41, 0, "liqueur"),
    "Coffee liqueur": (20, 49.1, 0, "liqueur"), "Amaro Averna": (29, 16, 0, "liqueur"),
    "Suze": (20, 16, 0, "liqueur"), "Cream of coconut": (0, 44, 0, "syrup"),
    "Tonic water": (0, 9, 0, "topper"),
    "Soda water": (0, 0, 0, "topper"),
    "Egg white": (0, 0, 0, "egg"), "Whole egg": (0, 0, 0, "egg"), "Cream": (0, 0, 0, "egg"),
}
TABLE = {**BOOK, **ADDED}
ALIASES = {"lime": "Lime juice", "lemon": "Lemon juice", "angostura": "Angostura bitters",
           "peychauds": "Peychauds bitters", "maraschino": "Luxardo Maraschino", "triple sec": "Cointreau",
           "chartreuse": "Green Chartreuse", "fernet": "Fernet Branca", "averna": "Amaro Averna",
           "kahlua": "Coffee liqueur", "club soda": "Soda water", "demerara": "Demerara syrup", "egg": "Whole egg",
           "sweet vermouth": "Generic sweet vermouth", "dry vermouth": "Generic dry vermouth",
           "orgeat": "Any nut orgeat", "heavy cream": "Cream", "grapefruit": "Grapefruit juice",
           "cranberry": "Cranberry juice", "orange": "Orange juice", "honey": "Honey syrup"}


def norm(name):
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", name.lower().replace("'", "").replace("’", "")).split())


INDEX = {norm(k): k for k in TABLE} | {norm(k): v for k, v in ALIASES.items()}
FITS = {"stirred": lambda a: -1.21 * a**2 + 1.246 * a + 0.145,
        "shaken": lambda a: -1.567 * a**2 + 1.742 * a + 0.203,
        "built": lambda a: 0.24, "none": lambda a: 0.0}
LINE = re.compile(r"^\s*(?P<amt>\d+\s+\d+/\d+|\d+/\d+|\d*\.?\d+)\s*(?P<unit>oz|ounces?|dash(?:es)?)\.?\s+"
                  r"(?P<name>.+?)\s*(?:(?P<abv>\d+(?:\.\d+)?)\s*%\s*(?:abv)?)?\s*$", re.I)


def parse(recipe):
    lines = [l for l in re.split(r"[;,\n]", recipe or "") if l.strip()]
    if not 1 <= len(lines) <= 12:
        raise ValueError("recipe needs 1-12 lines like '2 oz rye 50%; 0.75 oz lemon juice'")
    items = []
    for line in lines:
        m = LINE.match(line)
        if not m:
            raise ValueError(f"cannot read '{line.strip()}'; use '<amount> oz <name>' or '<amount> oz <spirit> <ABV>%'")
        parts = [p.partition("/") for p in m["amt"].split()]
        if any(d and float(d) == 0 for _, _, d in parts):
            raise ValueError(f"zero denominator in '{line.strip()}'")
        qty = sum(float(n) / float(d) if d else float(n) for n, _, d in parts)
        dash = m["unit"].lower().startswith("dash")
        if not 0 < qty <= (12 if dash else 8):
            raise ValueError(f"amount out of range in '{line.strip()}' (max 8 oz or 12 dashes)")
        known = INDEX.get(norm(m["name"]))
        if m["abv"]:
            if known and any(TABLE[known][1:3]):
                raise ValueError(f"'{m['name']}' is in the table with sugar/acid; drop the % to use it")
            if not 1 <= float(m["abv"]) <= 96:
                raise ValueError(f"ABV out of range in '{line.strip()}'")
            name, (abv, sugar, acid, kind) = m["name"].strip(), (float(m["abv"]), 0.0, 0.0, "spirit")
        elif known:
            name, (abv, sugar, acid, kind) = known, TABLE[known]
        else:
            close = [INDEX[c] for c in difflib.get_close_matches(norm(m["name"]), list(INDEX), n=3, cutoff=0.6)]
            raise ValueError(f"'{m['name']}' is not in the table" + (f"; closest: {close}" if close else "")
                             + ". Write spirits with their ABV, e.g. '2 oz rye 50%'.")
        items.append({"name": name, "oz": qty * DASH_OZ if dash else qty, "abv": abv,
                      "sugar": sugar, "acid": acid, "kind": kind})
    if sum(i["oz"] for i in items) > 12:
        raise ValueError("total volume exceeds 12 oz")
    return items


def profile(recipe, method):
    items = parse(recipe)
    iced = [i for i in items if i["kind"] != "topper"]
    v_mix = sum(i["oz"] for i in iced)
    if v_mix == 0:
        raise ValueError("recipe has nothing to mix with ice")
    a = sum(i["oz"] * i["abv"] for i in iced) / 100 / v_mix
    d = FITS[method](a)
    v = v_mix * (1 + d) + sum(i["oz"] for i in items if i["kind"] == "topper")
    tot = lambda f: sum(i["oz"] * i[f] for i in items)
    warnings = []
    if method in ("stirred", "shaken") and not 0.17 <= a <= 0.48:
        warnings.append(f"pre-ice ABV {a:.0%} is outside 17-48%, the span of the book's measured drinks")
    return {"items": items, "v_mix": v_mix, "a": a, "d": d, "v": v, "abv": tot("abv") / v,
            "sugar": tot("sugar") / v, "acid": tot("acid") / v, "warnings": warnings}


def classify(items):
    kinds = {i["kind"] for i in items}
    if "egg" in kinds:
        return "flip"
    if "topper" in kinds:
        return "highball"
    if any(i["acid"] >= 2 for i in items):
        sugar_from = lambda k: sum(i["oz"] * i["sugar"] for i in items if i["kind"] == k)
        return "sidecar" if sugar_from("liqueur") > sugar_from("syrup") else "daiquiri"
    return "martini" if "wine" in kinds else "old fashioned"


BOOK_DRINKS = [
    ("Old-Fashioned", "built", 32.1, 7.6, 0, "old fashioned"), ("Widow's Kiss", "stirred", 32.3, 3.7, 0, "old fashioned"),
    ("Improved Whiskey Cocktail", "stirred", 29.3, 6.5, 0, "old fashioned"), ("Rusty Nail", "stirred", 28.8, 4.1, 0, "old fashioned"),
    ("De La Louisiane", "stirred", 29.3, 4.5, 0.06, "martini"), ("Manhattan (rye)", "stirred", 27.2, 3.4, 0.12, "martini"),
    ("Bijou", "stirred", 27.1, 9.3, 0.14, "martini"), ("Brooklyn", "stirred", 26.3, 4.2, 0.06, "martini"),
    ("Vieux Carre", "stirred", 25.9, 4.1, 0.10, "martini"), ("Old Pal", "stirred", 25.7, 4.0, 0.09, "martini"),
    ("Rob Roy", "stirred", 25.5, 2.5, 0.09, "martini"), ("Bobby Burns", "stirred", 24.9, 4.2, 0.10, "martini"),
    ("Manhattan (bourbon)", "stirred", 24.6, 3.7, 0.14, "martini"), ("Martinez", "stirred", 22.5, 6.6, 0.13, "martini"),
    ("Hanky Panky", "stirred", 22.4, 5.6, 0.20, "martini"), ("Blackthorn", "stirred", 21.1, 6.3, 0.10, "martini"),
    ("Negroni", "stirred", 20.7, 9.4, 0.14, "martini"),
    ("Blinker", "shaken", 21.4, 4.1, 0.39, "daiquiri"), ("Champs-Elysees", "shaken", 19.7, 5.2, 0.80, "daiquiri"),
    ("Jack Rose", "shaken", 18.2, 8.5, 0.81, "daiquiri"), ("Fresh Lime Gimlet", "shaken", 17.3, 8.7, 0.82, "daiquiri"),
    ("Bee's Knees", "shaken", 17.2, 8.7, 0.83, "daiquiri"), ("Southside", "shaken", 17.2, 8.7, 0.83, "daiquiri"),
    ("Gold Rush", "shaken", 17.2, 8.7, 0.83, "daiquiri"), ("Brown Derby", "shaken", 16.6, 7.6, 0.44, "daiquiri"),
    ("Classic Daiquiri", "shaken", 15.0, 8.9, 0.85, "daiquiri"), ("Honeysuckle", "shaken", 15.0, 8.9, 0.85, "daiquiri"),
    ("Daiquiri (more lime)", "shaken", 14.7, 8.7, 0.94, "daiquiri"),
    ("Pegu Club", "shaken", 21.0, 4.2, 0.78, "sidecar"), ("Brandy Crusta", "shaken", 20.2, 4.7, 0.57, "sidecar"),
    ("Between the Sheets", "shaken", 20.1, 4.5, 0.57, "sidecar"), ("Last Word", "shaken", 20.0, 9.6, 0.94, "sidecar"),
    ("Sidecar", "shaken", 18.9, 6.0, 0.76, "sidecar"), ("Aviation", "shaken", 18.7, 5.1, 0.81, "sidecar"),
    ("Margarita", "shaken", 18.5, 6.0, 0.76, "sidecar"), ("Corpse Reviver #2", "shaken", 17.4, 5.7, 1.03, "sidecar"),
    ("20th-Century", "shaken", 17.3, 6.5, 0.85, "sidecar"), ("Cosmopolitan", "shaken", 16.6, 5.5, 1.05, "sidecar"),
    ("Hemingway Daiquiri", "shaken", 16.5, 4.1, 0.98, "sidecar"),
    ("Alexander", "shaken", 16.4, 3.1, 0, "flip"), ("Whiskey Sour", "egg white", 15.2, 7.1, 0.53, "flip"),
    ("Clover Club", "egg white", 13.6, 6.7, 0.49, "flip"), ("Pink Lady", "egg white", 12.4, 9.0, 0.64, "flip"),
    ("Pisco Sour", "egg white", 12.1, 7.2, 0.68, "flip"),
    ("Chartruth", "carbonated", 18.0, 8.3, 1.21, "highball"), ("Gin and Juice (agar)", "carbonated", 16.9, 5.0, 1.16, "highball"),
    ("Gin and Juice (centrifuge)", "carbonated", 15.8, 7.2, 0.91, "highball"),
    ("Carbonated Negroni", "carbonated", 16.0, 7.3, 0.38, "highball"), ("Gin and Tonic (dry)", "carbonated", 15.4, 4.9, 0.41, "highball"),
    ("Carbonated Whiskey Sour", "carbonated", 15.2, 7.2, 0.44, "highball"), ("Carbonated Margarita", "carbonated", 14.2, 7.1, 0.44, "highball"),
]

SOURS = {"daiquiri", "sidecar"}


def family_range(fam):

    rows = [d for d in BOOK_DRINKS if d[5] == fam]
    span = lambda col, pad: (round(max(0, min(r[col] for r in rows) - pad), 3), round(max(r[col] for r in rows) + pad, 3))
    out = {"abv": span(2, 0.05), "sugar": span(3, 0.05), "acid": span(4, 0.005),
           "median_sugar": statistics.median(r[3] for r in rows)}
    if fam in SOURS:
        out["ratio"] = (min((r[3] - .05) / (r[4] + .005) for r in rows), max((r[3] + .05) / (r[4] - .005) for r in rows))
        out["median_ratio"] = statistics.median(r[3] / r[4] for r in rows)
    return out


RANGES = {fam: family_range(fam) for fam in ["old fashioned", "martini", "daiquiri", "sidecar", "highball", "flip"]}
SPREAD = [statistics.pstdev(r[col] for r in BOOK_DRINKS) for col in (2, 3, 4)]


def band(x, rng):
    return "within" if rng[0] <= x <= rng[1] else ("below" if x < rng[0] else "above")


def family_of(p, family):
    return (classify(p["items"]), "auto-detected") if family == "auto" else (family, "set by user")


def abv_metrics(recipe, method, family="auto"):
    p = profile(recipe, method)
    fam, how = family_of(p, family)
    rng = RANGES[fam]["abv"]
    return {"final_abv_pct": round(p["abv"], 1), "family": f"{fam} ({how})",
            "strength_vs_family": f"{band(p['abv'], rng)} the {fam} range of {rng[0]}-{rng[1]}%",
            "final_volume_oz": round(p["v"], 2), "pre_ice_abv_pct": round(100 * p["a"], 1),
            "water_added_oz": round(p["d"] * p["v_mix"], 2), "warnings": p["warnings"]}


def balance_metrics(recipe, method, family="auto"):
    p = profile(recipe, method)
    fam, how = family_of(p, family)
    r, items, fix = RANGES[fam], p["items"], None
    sugar_t, acid_t = p["sugar"] * p["v"], p["acid"] * p["v"]
    if fam in SOURS:
        if not p["acid"]:
            raise ValueError(f"the {fam} family is judged on sugar:acid, but this recipe has no acid")
        ratio = p["sugar"] / p["acid"]
        sweet_sour, strength = band(ratio, r["ratio"]), band(p["acid"], r["acid"])
        notes = [{"below": "too sour", "above": "too sweet", "within": "sugar:acid within range"}[sweet_sour],
                 {"below": "acid is weak", "above": "acid is strong", "within": "acid within range"}[strength]]
        aim, citrus = r["median_ratio"], max(items, key=lambda i: i["acid"])
        if sweet_sour == "below":
            fix = f"add {(aim * acid_t - sugar_t) / 61.5:.2f} oz simple syrup (family median sugar:acid {aim:.1f})"
        elif sweet_sour == "above":
            fix = (f"add {(sugar_t - aim * acid_t) / (aim * citrus['acid'] - citrus['sugar']):.2f} oz "
                   f"{citrus['name']} (family median sugar:acid {aim:.1f})")
        balanced = sweet_sour == strength == "within"
        reference = {"sugar_to_acid": [round(x, 1) for x in r["ratio"]], "acid_pct": r["acid"]}
    else:
        sweet = band(p["sugar"], r["sugar"])
        notes = [{"below": "drier than the range", "above": "sweeter than the range", "within": "sugar within range"}[sweet]]
        if sweet != "within":
            change = (r["median_sugar"] - p["sugar"]) * p["v"] / 61.5
            fix = (f"add about {change:.2f} oz simple syrup" if change > 0 else
                   f"cut sweetness by the sugar in about {-change:.2f} oz simple syrup") + " (family median)"
        balanced = sweet == "within"
        reference = {"sugar_g_per_100ml": r["sugar"]}
    return {"verdict": ("balanced" if balanced else "not balanced") + f" for the {fam} family: " + "; ".join(notes),
            "family": f"{fam} ({how})", "suggested_change": fix, "sugar_g_per_100ml": round(p["sugar"], 2),
            "acid_pct": round(p["acid"], 2), "family_range": reference, "warnings": p["warnings"]}


def cost_metrics(recipe, prices, drinks=1):
    per_oz = {}
    for part in [s for s in re.split(r"[;\n,]", prices or "") if s.strip()]:
        m = re.match(r"^\s*(.+?)\s*=\s*\$?\s*(\d*\.?\d+)\s*(?:/\s*(\d*\.?\d+)\s*(?:oz)?)?\s*$", part, re.I)
        if not m or float(m[2]) <= 0 or (m[3] and float(m[3]) <= 0):
            raise ValueError(f"cannot read price '{part.strip()}'; use 'name=price' or 'name=price/oz_per_unit'")
        per_oz[norm(m[1])] = float(m[2]) / (float(m[3]) if m[3] else BOTTLE_OZ)
    lines, unpriced, each = [], [], 0.0
    for i in parse(recipe):
        words = set(norm(i["name"]).split())
        rate = next((usd for key, usd in per_oz.items()
                     if INDEX.get(key) == i["name"] or key == norm(i["name"]) or set(key.split()) <= words), None)
        line = {"ingredient": i["name"], "oz_per_drink": round(i["oz"], 3), "oz_total": round(drinks * i["oz"], 3)}
        if rate is None:
            unpriced.append(i["name"])
        else:
            each += i["oz"] * rate
            line |= {"usd_per_drink": round(i["oz"] * rate, 2), "usd_total": round(drinks * i["oz"] * rate, 2)}
        lines.append(line)
    each = round(each, 2)
    return {"drinks": drinks, "cost_per_drink_usd": each, "total_cost_usd": round(drinks * each, 2),
            "ingredients": lines, "unpriced_ingredients": unpriced}


def closest_metrics(recipe, method, count=3):
    p = profile(recipe, method)
    mine = (p["abv"], p["sugar"], p["acid"])
    dist = lambda d: math.sqrt(sum(((x - y) / s) ** 2 for x, y, s in zip(mine, d[2:5], SPREAD)))
    return {"drink": {"abv_pct": round(mine[0], 1), "sugar_g_per_100ml": round(mine[1], 2), "acid_pct": round(mine[2], 2)},
            "closest": [{"name": d[0], "book_style": d[1], "family": d[5], "abv_pct": d[2], "sugar_g_per_100ml": d[3],
                         "acid_pct": d[4], "distance": round(dist(d), 2)} for d in sorted(BOOK_DRINKS, key=dist)[:count]],
            "distance_note": "Euclidean distance with each axis divided by its spread across the book's drinks",
            "warnings": p["warnings"]}


def freezing_metrics(recipe, method, freezer_temp_c=-18.0):

    p = profile(recipe, method)
    ml = p["v"] * OZ_ML
    ethanol_ml, sugar_g = ml * p["abv"] / 100, ml * p["sugar"] / 100
    water_kg = (ml - ethanol_ml - 0.63 * sugar_g) / 1000
    molality = (0.789 * ethanol_ml / 46.07 + sugar_g / 342.3) / water_kg
    fp = -1.86 * molality
    margin = freezer_temp_c - fp
    verdict = "stays liquid" if margin >= 0 else "will start to freeze (ice crystals form)"
    if 0 <= margin < 2:
        verdict += "; within 2 C of freezing, so it may turn slushy"
    return {"verdict": verdict, "freezing_point_c": round(fp, 1), "freezer_temp_c": freezer_temp_c,
            "margin_c": round(margin, 1), "final_abv_pct": round(p["abv"], 1),
            "sugar_g_per_100ml": round(p["sugar"], 2), "final_volume_oz": round(p["v"], 2),
            "model": "ideal colligative estimate (Kf = 1.86 C kg/mol; ethanol and sucrose); acids ignored. "
                     "It underestimates depression at high ethanol, so the true freezing point is somewhat colder.",
            "warnings": p["warnings"]}


mcp = MCPServer(name="cocktail-preplanner", instructions=(
    "Tools for planning cocktails before mixing. Pass a recipe for one drink as '<amount> oz <ingredient>' lines "
    "joined by '; ', writing unsweetened spirits with their ABV (e.g. '2 oz rye 50%'). Report verdicts as returned. "
    "For a batch, set drinks in estimate_cost. For freezer-stored bottled cocktails, use method 'stirred' to include "
    "pre-dilution water, or 'none' for an undiluted batch."))

Recipe = Annotated[str, Field(description="One drink, e.g. '2 oz rye 50%; 1 oz sweet vermouth; 2 dash angostura'. "
                                          "US fl oz or dashes; 1-12 lines, <= 12 oz total.")]
Method = Annotated[Literal["shaken", "stirred", "built", "none"], Field(
    description="Ice technique: 'shaken'/'stirred' (Arnold dilution fits), 'built' (24% dilution), 'none' (no ice).")]
Family = Annotated[Literal["auto", "old fashioned", "martini", "daiquiri", "sidecar", "highball", "flip"], Field(
    description="Family whose Liquid Intelligence range is used; 'auto' detects it.")]


def run(fn, *args):
    try:
        return fn(*args)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def estimate_abv(recipe: Recipe, method: Method, family: Family = "auto") -> dict:
    """Final ABV (%) after ice dilution and whether it is inside the drink's family range."""
    return run(abv_metrics, recipe, method, family)


@mcp.tool()
def check_balance(recipe: Recipe, method: Method, family: Family = "auto") -> dict:
    """Sugar (g/100 mL) and acid (%) after dilution, judged against the family range, with a suggested fix."""
    return run(balance_metrics, recipe, method, family)


@mcp.tool()
def estimate_cost(recipe: Recipe,
                  prices: Annotated[str, Field(description="'name=USD' per 750 mL bottle or 'name=USD/oz_per_unit', "
                                                           "separated by ';', e.g. 'gin=30; lime juice=0.40/0.75'.")],
                  drinks: Annotated[int, Field(ge=1, le=100, description="How many drinks to make.")] = 1) -> dict:
    """Ingredient cost per drink and for a batch (USD), with per-ingredient volumes. Unpriced items are listed."""
    return run(cost_metrics, recipe, prices, drinks)


@mcp.tool()
def closest_classic(recipe: Recipe, method: Method,
                    count: Annotated[int, Field(ge=1, le=10, description="How many matches to return.")] = 3) -> dict:
    """The classic cocktails from Liquid Intelligence whose measured finished ABV, sugar, and acid are nearest this drink's."""
    return run(closest_metrics, recipe, method, count)


@mcp.tool()
def check_freezing(recipe: Recipe, method: Method,
                   freezer_temp_c: Annotated[float, Field(ge=-40, le=10, description="Freezer temperature in C; "
                                                                                     "home freezers are about -18.")] = -18.0) -> dict:
    """Estimated freezing point (C) of the finished drink and whether it stays liquid at the freezer temperature."""
    return run(freezing_metrics, recipe, method, freezer_temp_c)


if __name__ == "__main__":
    mcp.run()
