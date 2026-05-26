from __future__ import annotations

import json
from typing import Any

from inspect_ai._util.json import to_json_safe


def as_jsonable(value: Any) -> Any:
    return json.loads(to_json_safe(value, indent=None).decode("utf-8"))
