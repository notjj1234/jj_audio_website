import json
from pathlib import Path

p = Path(__file__).with_name("asar-inventory.json")
data = json.loads(p.read_text(encoding="utf-8"))
prefixes = ("out/", "native/", "build/", "resources/")
rows = []
for f in data["files"]:
    path = f["path"]
    if path.startswith(prefixes) or "/" not in path:
        flag = "U" if f["unpacked"] else "A"
        rows.append(f"{f['size']}\t{flag}\t{path}")
out = Path(__file__).with_name("shell-files.txt")
out.write_text("\n".join(rows) + "\n", encoding="utf-8")
print(f"wrote {len(rows)} rows to {out}")
print("\n".join(rows))
