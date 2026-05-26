from __future__ import annotations

import base64

from fastapi import HTTPException


def encode_id(path: str) -> str:
    return base64.urlsafe_b64encode(path.encode("utf-8")).decode("ascii").rstrip("=")


def decode_id(run_id: str) -> str:
    try:
        padded = run_id + "=" * (-len(run_id) % 4)
        return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except Exception as ex:
        raise HTTPException(status_code=400, detail="Invalid run id") from ex
