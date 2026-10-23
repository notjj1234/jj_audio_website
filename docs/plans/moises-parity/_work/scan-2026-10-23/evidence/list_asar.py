import json, struct
from pathlib import Path
asar = Path(r"C:\Users\orall\AppData\Local\Programs\moises-desktop\resources\app.asar")
data = asar.read_bytes()
payload_size = struct.unpack_from("<I", data, 0)[0]
header_pickle_size = struct.unpack_from("<I", data, 4)[0]
print(f"size_pickle_payload={payload_size} header_pickle_size={header_pickle_size} file={len(data)}")
hs = 8
h_payload = struct.unpack_from("<I", data, hs)[0]
str_len = struct.unpack_from("<I", data, hs+4)[0]
print(f"header_payload={h_payload} str_len={str_len}")
raw = data[hs+8:hs+8+str_len]
header = json.loads(raw)
base = 8 + header_pickle_size
files = []
def walk(node, prefix):
    if "files" in node:
        for name, child in node["files"].items():
            walk(child, f"{prefix}{name}/" if "files" in child else f"{prefix}{name}")
    else:
        files.append({
            "path": prefix,
            "size": node.get("size"),
            "offset": node.get("offset"),
            "unpacked": bool(node.get("unpacked")),
            "executable": bool(node.get("executable")),
        })
walk(header, "")
out = Path(r"C:\Users\orall\Documents\GitHub\jj_audio_website\docs\plans\moises-parity\_work\scan-2026-10-23\evidence\asar-inventory.json")
summary = {
    "asar_bytes": len(data),
    "header_pickle_size": header_pickle_size,
    "payload_base": base,
    "file_count": len(files),
    "total_listed_size": sum(f["size"] or 0 for f in files),
    "unpacked_count": sum(1 for f in files if f["unpacked"]),
}
# top-level dirs
from collections import Counter
tops = Counter(p["path"].split("/")[0] for p in files)
summary["top_level"] = dict(tops)
# largest 40
largest = sorted(files, key=lambda f: f["size"] or 0, reverse=True)[:40]
summary["largest"] = largest
# interesting names
keys = ("package.json","index.html","preload","main","renderer")
interesting = [f for f in files if f["path"].endswith("package.json") or "preload" in f["path"].lower() or f["path"].startswith("out/") or f["path"].endswith(".html")]
summary["interesting_count"] = len(interesting)
out.write_text(json.dumps({"summary": summary, "files": files}, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2)[:8000])
# extract package.json
for f in files:
    if f["path"] == "package.json" and f["offset"] is not None:
        start = base + int(f["offset"])
        blob = data[start:start+f["size"]]
        Path(r"C:\Users\orall\Documents\GitHub\jj_audio_website\docs\plans\moises-parity\_work\scan-2026-10-23\evidence\package.json").write_bytes(blob)
        print("--- package.json bytes", len(blob))
        print(blob[:4000].decode("utf-8", "replace"))
