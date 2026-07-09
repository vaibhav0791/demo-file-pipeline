from __future__ import annotations
from typing import Optional, Set


# Replace later with curated DB/API.
KNOWN_POSITIVE_TARGETS: Set[str] = {
    "TP53", "BRCA1", "EGFR", "PIK3CA"
}


def get_target_label(gene_symbol: str) -> Optional[int]:
    if not gene_symbol:
        return None
    g = gene_symbol.strip().upper()
    return 1 if g in KNOWN_POSITIVE_TARGETS else 0