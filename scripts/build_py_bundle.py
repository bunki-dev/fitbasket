"""Zip the Python package for the in-browser (Pyodide) build: web/public/py/fitbasket.zip.

Server-only modules (FastAPI, MCP, CLI) are left out; they can't run in the browser.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "fitbasket"
OUT = ROOT / "web" / "public" / "py" / "fitbasket.zip"
SERVER_ONLY = {"api.py", "mcp_server.py", "cli.py"}


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(SRC.rglob("*")):
            if path.is_dir() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            if path.parent == SRC and path.name in SERVER_ONLY:
                continue
            zf.write(path, Path("fitbasket") / path.relative_to(SRC))
            count += 1
    print(f"Wrote {OUT.relative_to(ROOT)} ({count} files, {OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
