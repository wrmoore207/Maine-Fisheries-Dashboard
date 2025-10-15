from __future__ import annotations
from pathlib import Path
from datetime import datetime
import hashlib
import shutil

from src.config import SNAP_DIR
from src.io import list_processed

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_dir = SNAP_DIR / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_lines = ["file,bytes,sha256"]
    for p in list_processed():
        dest = out_dir / p.name
        shutil.copy2(p, dest)
        manifest_lines.append(f"{p.name},{dest.stat().st_size},{_sha256(dest)}")

    (out_dir / "MANIFEST.csv").write_text("\n".join(manifest_lines), encoding="utf-8")
    print(f"Wrote snapshot -> {out_dir}")

if __name__ == "__main__":
    main()
