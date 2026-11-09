import datetime, json, shlex, subprocess, sys

PY, SERVER, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
BASE = ["npx", "-y", "@modelcontextprotocol/inspector@2.14.0", "--cli", PY, SERVER]

CALLS = [
    ("Original tool: check_balance", "check_balance",
     {"recipe": "2 oz bourbon 50%; 1 oz lemon juice; 0.5 oz simple syrup", "method": "shaken"}),
    ("Original tool: estimate_cost (batch of 2)", "estimate_cost",
     {"recipe": "0.75 oz gin 47%; 0.75 oz green chartreuse; 0.75 oz maraschino; 0.75 oz lime juice",
      "prices": "gin=30; green chartreuse=70; maraschino=35; lime juice=0.40/0.75", "drinks": 2}),
    ("New tool: closest_classic", "closest_classic",
     {"recipe": "2 oz bourbon 50%; 0.75 oz lemon juice; 0.75 oz honey syrup", "method": "shaken"}),
    ("New tool: check_freezing (pre-diluted martini)", "check_freezing",
     {"recipe": "2.5 oz gin 47%; 0.5 oz dry vermouth", "method": "stirred", "freezer_temp_c": -18}),
    ("New tool: check_freezing (same martini, undiluted)", "check_freezing",
     {"recipe": "2.5 oz gin 47%; 0.5 oz dry vermouth", "method": "none", "freezer_temp_c": -18}),
    ("Invalid input: unknown ingredient", "check_balance",
     {"recipe": "2 oz moonshine; 0.75 oz lime juice", "method": "shaken"}),
    ("Invalid input: argument outside the schema", "check_freezing",
     {"recipe": "2 oz vodka 40%", "method": "none", "freezer_temp_c": -60}),
]


def run(args):
    proc = subprocess.run(BASE + args, capture_output=True, text=True, timeout=180)
    return proc.returncode, proc.stdout.strip() or proc.stderr.strip()


def pretty(raw):
    try:
        res = json.loads(raw)
    except json.JSONDecodeError:
        return raw, None
    text = res.get("content", [{}])[0].get("text", "")
    try:
        text = json.dumps(json.loads(text), indent=2)
    except (json.JSONDecodeError, TypeError):
        pass
    return text, res.get("isError")


log = [f"# MCP Inspector call log: cocktail-preplanner",
       "",
       f"- Recorded: {datetime.datetime.now().astimezone():%Y-%m-%d %H:%M %Z}",
       "- Client: MCP Inspector CLI 2.14.0 (`@modelcontextprotocol/inspector`), stdio transport",
       f"- Server: `{SERVER.rsplit('/', 1)[-1]}` on the Python `mcp` SDK",
       ""]

code, raw = run(["--method", "tools/list"])
tools = json.loads(raw)["tools"]
log += ["## tools/list", "", "```", f"$ inspector --cli python {SERVER.rsplit('/', 1)[-1]} --method tools/list", "```", "",
        "| Tool | Parameters |", "| --- | --- |"]
log += [f"| `{t['name']}` | " + ", ".join(f"`{k}`" + ("" if k in t["inputSchema"].get("required", []) else " (optional)")
                                       for k in t["inputSchema"]["properties"]) + " |" for t in tools]
log.append("")

for title, tool, args in CALLS:
    cli = ["--method", "tools/call", "--tool-name", tool]
    for k, v in args.items():
        cli += ["--tool-arg", f"{k}={v}"]
    code, raw = run(cli)
    body, is_error = pretty(raw)
    shown = " ".join(shlex.quote(a) for a in cli)
    log += [f"## {title}", "", "```", f"$ inspector --cli python {SERVER.rsplit('/', 1)[-1]} {shown}", "```", "",
            f"**isError:** `{is_error}`", "", "```json" if body.lstrip().startswith("{") else "```", body, "```", ""]

open(OUT, "w").write("\n".join(log))
print("\n".join(log))
