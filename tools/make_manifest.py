"""Write MANIFEST.md: size and SHA-256 of every file in the repository (except MANIFEST.md and .git)."""
import datetime, hashlib, os
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = []
for d, dirs, files in os.walk(H):
    dirs[:] = sorted(x for x in dirs if x not in (".git", "__pycache__"))
    for f in sorted(files):
        if f in (".DS_Store",): continue
        p = os.path.join(d, f); r = os.path.relpath(p, H)
        if r == "MANIFEST.md": continue
        rows.append((r, os.path.getsize(p), hashlib.sha256(open(p, "rb").read()).hexdigest()))
rows.sort()
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
with open(os.path.join(H, "MANIFEST.md"), "w") as f:
    f.write(f"# Manifest\n\nGenerated {now} by `tools/make_manifest.py`.\n\n## Files in this repository ({len(rows)})\n\n| file | bytes | sha256 |\n|---|---|---|\n")
    for r, n, h in rows: f.write(f"| `{r}` | {n:,} | `{h}` |\n")
print(len(rows), "files")
