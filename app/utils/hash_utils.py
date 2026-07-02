import hashlib
import json
from typing import Any

def canonical_dumps(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def sha256_hash(data: Any) -> str:
    payload = canonical_dumps(data).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()