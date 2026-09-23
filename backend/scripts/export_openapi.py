"""Write the API schema to docs/openapi.json for the frontend.

  uv run python -m scripts.export_openapi

Generate TypeScript types from it with:  npx openapi-typescript docs/openapi.json -o src/api.d.ts
"""

import json
from pathlib import Path

from app.main import app

OUT = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"


def main() -> None:
    OUT.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
