import httpx
from typing import Any

UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb/search"

def fetch_uniprot_by_gene(gene_symbol: str, size: int = 20) -> list[dict[str, Any]]:
    """
    Fetch UniProtKB entries by human gene symbol.
    """
    query = f'(gene:{gene_symbol}) AND (organism_id:9606)'
    params = {
        "query": query,
        "format": "json",
        "size": size,
    }

    with httpx.Client(timeout=30.0) as client:
        resp = client.get(UNIPROT_BASE, params=params)
        resp.raise_for_status()
        data = resp.json()

    return data.get("results", [])