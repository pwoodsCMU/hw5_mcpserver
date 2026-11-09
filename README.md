# cocktail-preplanner

An MCP server for planning cocktails on paper before mixing them, so fewer test drinks get poured out. It estimates strength, balance, cost, the nearest classic, and freezer stability from a written recipe.

## Files

| File | Purpose |
| --- | --- |
| `cocktail_mcp_server.py` | The MCP server (stdio transport), with five tools |
| `requirements.txt` | Python dependency (`mcp`) |
| `record_calls.py` | Calls each tool through the MCP Inspector CLI and writes a Markdown log |
| `mcp_inspector_log.md` | Recorded calls and responses, including invalid inputs |

## Setup

Requires Python 3.10+.

```bash
pip install -r requirements.txt
python cocktail_mcp_server.py
```

The server waits on stdin/stdout for an MCP client and prints nothing on its own. It works with `mcp` 1.x and 2.x.

**Claude Desktop.** Add the server to `claude_desktop_config.json` and restart Claude Desktop:

```json
{
  "mcpServers": {
    "cocktail-preplanner": {
      "command": "python",
      "args": ["C:\\path\\to\\cocktail_mcp_server.py"]
    }
  }
}
```

**MCP Inspector.** Requires Node.js; tested with Node 22 and Inspector 2.14.0.

```bash
npx @modelcontextprotocol/inspector python cocktail_mcp_server.py      # browser UI
python record_calls.py python cocktail_mcp_server.py mcp_inspector_log.md   # regenerate the log
```

## Recipe format

Every tool takes `recipe`: one drink written as a single string.

```
2 oz rye 50%; 1 oz sweet vermouth; 2 dash angostura
```

- Lines are separated by `;`, `,`, or newlines.
- Amounts can be decimals (`0.75`), fractions (`3/4`), or mixed numbers (`1 1/2`).
- Units are `oz` (US fl oz) or `dash`. One dash is taken as 1/32 oz.
- **Unsweetened spirits** are written with their ABV inline (`2 oz rye 50%`) and are treated as having no sugar or acid.
- **All other ingredients** are looked up by name in the ingredient table (see [Data](#data)). Case and punctuation are ignored, and common aliases such as `lime`, `angostura`, and `sweet vermouth` are accepted.
- **Limits:** 1–12 lines; each line > 0 and ≤ 8 oz or ≤ 12 dashes; ≤ 12 oz total; inline ABV 1–96%.

Several tools also take `method`, which sets how much water ice adds:

| `method` | Dilution model (water added ÷ pre-ice volume, with $a$ = pre-ice ABV as a fraction) |
| --- | --- |
| `stirred` | $-1.21a^2 + 1.246a + 0.145$ |
| `shaken` | $-1.567a^2 + 1.742a + 0.203$ |
| `built` | 0.24 |
| `none` | 0 |

Carbonated toppers (soda, tonic) are added after the ice step and are not diluted.

## Invalid-input behavior (all tools)

Every failure comes back as a tool result with `isError: true` and a readable message, so a model can fix its input and retry. There are two kinds:

- **Schema violations**: a wrong type, a value outside an enum, or a number out of bounds. The MCP SDK rejects these before the tool runs and returns a validation message naming the field. Example: `freezer_temp_c: Input should be greater than or equal to -40`.
- **Recipe errors**: raised by the tool itself.

| Cause | Message (abridged) |
| --- | --- |
| Line can't be parsed | `cannot read '<line>'; use '<amount> oz <name>' …` |
| Unknown ingredient | `'<name>' is not in the table; closest: [...]. Write spirits with their ABV …` |
| ABV written on a sweetened ingredient | `'campari' is in the table with sugar/acid; drop the % to use it` |
| Amount, ABV, line count, or total volume out of range | `amount out of range …`, `ABV out of range …`, `recipe needs 1-12 lines …`, `total volume exceeds 12 oz` |
| Fraction with a zero denominator | `zero denominator in '<line>'` |
| Recipe contains only carbonated toppers | `recipe has nothing to mix with ice` |

**Warnings** do not fail the call; they are returned in a `warnings` list. The only one: for `shaken` or `stirred`, a pre-ice ABV outside 17–48%, the span of the measured drinks the dilution fits were built from.

## Tools

### `estimate_abv`

Final strength after ice dilution, and whether it falls in the ABV range of the drink's cocktail family.

| Input | Type | Units / valid values | Default |
| --- | --- | --- | --- |
| `recipe` | string | see [Recipe format](#recipe-format) | required |
| `method` | enum | `shaken`, `stirred`, `built`, `none` | required |
| `family` | enum | `auto`, `old fashioned`, `martini`, `daiquiri`, `sidecar`, `highball`, `flip` | `auto` |

| Result field | Type | Units |
| --- | --- | --- |
| `final_abv_pct` | number | % ABV |
| `family` | string | family and whether it was auto-detected or set by the user |
| `strength_vs_family` | string | `within` / `below` / `above` the family range, with the range |
| `final_volume_oz` | number | oz |
| `pre_ice_abv_pct` | number | % ABV |
| `water_added_oz` | number | oz |
| `warnings` | list of strings | |

### `check_balance`

Sweetness and sourness after dilution, judged against the family's range, with a suggested fix.

- The daiquiri and sidecar families are judged on sugar:acid ratio and acid strength.
- The other families are judged on sugar alone.

| Input | Type | Units / valid values | Default |
| --- | --- | --- | --- |
| `recipe` | string | see [Recipe format](#recipe-format) | required |
| `method` | enum | `shaken`, `stirred`, `built`, `none` | required |
| `family` | enum | as in `estimate_abv` | `auto` |

| Result field | Type | Units |
| --- | --- | --- |
| `verdict` | string | `balanced` / `not balanced for the <family> family: …` |
| `family` | string | as in `estimate_abv` |
| `suggested_change` | string or null | simple syrup or citrus to add (oz); null when balanced |
| `sugar_g_per_100ml` | number | g per 100 mL of finished drink |
| `acid_pct` | number | % titratable acid |
| `family_range` | object | `sugar_to_acid` and `acid_pct` ranges (sour families) or `sugar_g_per_100ml` range |
| `warnings` | list of strings | |

**Additional error:** forcing a sour family (`daiquiri` or `sidecar`) on a recipe with no acid.

### `estimate_cost`

Ingredient cost per drink, plus totals and ingredient volumes for a batch.

| Input | Type | Units / valid values | Default |
| --- | --- | --- | --- |
| `recipe` | string | one drink; see [Recipe format](#recipe-format) | required |
| `prices` | string | `name=USD` per 750 mL bottle, or `name=USD/oz_per_unit`; separated by `;`. Example: `gin=30; lime juice=0.40/0.75` | required |
| `drinks` | integer | 1–100 | 1 |

| Result field | Type | Units |
| --- | --- | --- |
| `drinks` | integer | count |
| `cost_per_drink_usd` | number | USD |
| `total_cost_usd` | number | USD (`cost_per_drink_usd` × `drinks`) |
| `ingredients` | list of objects | `ingredient`, `oz_per_drink`, `oz_total`, and for priced items `usd_per_drink`, `usd_total` |
| `unpriced_ingredients` | list of strings | ingredients that had no price |

Price names match an ingredient by exact name, alias, or words contained in its name (`rye` matches `rye 50%`). Ingredients without a price are not an error: they are listed and left out of the totals.

**Additional error:** a price entry that can't be read, or a price or unit size ≤ 0.

### `closest_classic`

The classic cocktails from *Liquid Intelligence* whose measured finished ABV, sugar, and acid are nearest to the drink's.

| Input | Type | Units / valid values | Default |
| --- | --- | --- | --- |
| `recipe` | string | see [Recipe format](#recipe-format) | required |
| `method` | enum | `shaken`, `stirred`, `built`, `none` | required |
| `count` | integer | 1–10 | 3 |

| Result field | Type | Units |
| --- | --- | --- |
| `drink` | object | `abv_pct` (%), `sugar_g_per_100ml`, `acid_pct` (%) of the input drink |
| `closest` | list of objects | `name`, `book_style`, `family`, `abv_pct`, `sugar_g_per_100ml`, `acid_pct`, `distance` (dimensionless) |
| `distance_note` | string | how distance is computed |
| `warnings` | list of strings | |

Distance is Euclidean in (ABV, sugar, acid). Each axis is divided by that quantity's standard deviation across the 51 reference drinks, so no single axis dominates.

### `check_freezing`

Estimated freezing point of the finished drink, and whether it stays liquid at a given freezer temperature. Intended for bottled, freezer-stored cocktails:

- use `stirred` to include pre-dilution water;
- use `none` for an undiluted batch.

| Input | Type | Units / valid values | Default |
| --- | --- | --- | --- |
| `recipe` | string | see [Recipe format](#recipe-format) | required |
| `method` | enum | `shaken`, `stirred`, `built`, `none` | required |
| `freezer_temp_c` | number | °C, −40 to 10 | −18 |

| Result field | Type | Units |
| --- | --- | --- |
| `verdict` | string | `stays liquid` (adds a slush warning within 2 °C) / `will start to freeze (ice crystals form)` |
| `freezing_point_c` | number | °C |
| `freezer_temp_c` | number | °C |
| `margin_c` | number | °C (freezer temperature − freezing point; negative means it freezes) |
| `final_abv_pct` | number | % ABV |
| `sugar_g_per_100ml` | number | g per 100 mL |
| `final_volume_oz` | number | oz |
| `model` | string | model statement and its limitation |
| `warnings` | list of strings | |

**Model.** Blagden's law: ΔT = K<sub>f</sub> · m, with K<sub>f</sub> = 1.86 °C·kg/mol.

- **Solutes:** ethanol (0.789 g/mL, 46.07 g/mol) and sucrose (342.3 g/mol), both dissolved in the drink's water.
- **Water mass:** total volume minus the ethanol volume minus 0.63 mL per gram of sugar.
- **Ignored:** acids.

**Limitations.**

- Against the [Engineering ToolBox](https://engineeringtoolbox.com/ethanol-water-d_989.html) ethanol–water table, the model predicts freezing 0.5–1.8 °C warmer than measured at 10–40% ABV. A `stays liquid` verdict is therefore conservative.
- Sugars other than sucrose (for example honey) lower the freezing point more than modeled.

## Models

### Cocktail families

When `family` is `auto`, a drink is assigned to the first family whose rule it matches. The six families are the root cocktails of *Cocktail Codex*.

| Order | Family | Rule |
| --- | --- | --- |
| 1 | flip | contains egg or cream |
| 2 | highball | contains a carbonated topper |
| 3 | sidecar | contains citrus (acid ≥ 2%), and more sugar comes from liqueur than from syrup |
| 4 | daiquiri | contains citrus, and more sugar comes from syrup |
| 5 | martini | contains vermouth or another wine |
| 6 | old fashioned | anything else |

### Family ranges

Each family's range is the min–max of the measured finished values of its members among 51 drinks in *Liquid Intelligence* ("Specifications for Cocktail Balance at a Glance"). The range is widened only by half the book's last printed digit, so the book's own drinks pass.

The suggested change in `check_balance` targets the family median:

- **Sour families:** the change is exact within the model, because dilution doesn't change the sugar:acid ratio.
- **Other families:** the change is approximate, because it ignores the extra dilution the change itself causes.

### Shaken-fit sign

The book prints the shaken dilution fit with a positive $a^2$ term. That version exceeds the book's own stated 51–60% dilution for shaken drinks, so this server uses McDonald's corrected negative sign.

## Data

Each table row is `name: (ABV %, sugar g/100 mL, titratable acid %, kind)`. The `kind` field drives family detection and must be one of `syrup`, `juice`, `acid`, `liqueur`, `wine`, `bitters`, `topper`, `egg`, or `other`.

- **`BOOK`**: *Liquid Intelligence*, "Cocktail Ingredient Percentages". Arnold's modified spirits are omitted. Rich simple syrup is set to 88.7, from the book's 887 g of sugar per liter.
- **`ADDED`**: ingredients the book's table lacks, mostly from the Cocktail Chemistry table. Three are assumptions:
  - grenadine at simple-syrup strength (61.5);
  - egg, egg white, and cream with no sugar or acid;
  - tonic at 9 g/100 mL; the book gives 9–12 for sodas.
- **`BOOK_DRINKS`**: the measured drinks behind the family ranges. Blood and Sand, the blended drinks, and the uncharted Cosmopolitan TC are excluded. Three acid values garbled in the source copy (Brandy Crusta, Between the Sheets, egg-white Whiskey Sour) were recomputed from start acid and volumes.

To add an ingredient, add a row to `ADDED`.

## References

- Arnold, D. (2014). *Liquid Intelligence: The Art and Science of the Perfect Cocktail*. W. W. Norton.
- Day, A., Fauchald, N., & Kaplan, D. (2018). *Cocktail Codex: Fundamentals, Formulas, Evolutions*. Ten Speed Press.
- McDonald, M. (2020). [Between the Sheets](https://mikemcdonald.co/blog/2020/05/06/between-the-sheets/) (shaken dilution sign correction).
- Cocktail Chemistry. [Ingredient table](https://www.cocktailchemistrylab.com/calculator-ingredients).
- Engineering ToolBox. [Ethanol–water freezing points](https://engineeringtoolbox.com/ethanol-water-d_989.html).
