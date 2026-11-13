"""Start the single-origin app and demo at http://127.0.0.1:8765."""

from __future__ import annotations

import uvicorn

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8765, workers=1)
