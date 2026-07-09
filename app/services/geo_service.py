from __future__ import annotations

from typing import Optional, Dict, Any, List, Tuple
import io
import re
import requests
import pandas as pd

NCBI_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
GEO_SEARCH_DB = "gds"

# simple in-memory cache per process
_GEO_CACHE: Dict[str, List[Dict[str, Any]]] = {}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _gene_norm(x: Any) -> str:
    return str(x).strip().upper() if x is not None else ""


def _to_float(v: Any) -> Optional[float]:
    try:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return float(v)
    except Exception:
        return None


def _to_int(v: Any) -> Optional[int]:
    try:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return int(v)
    except Exception:
        return None


def _esearch_gds_ids(disease: str, retmax: int = 10) -> List[str]:
    term = f'("{disease}"[All Fields]) AND "Homo sapiens"[Organism]'
    r = requests.get(
        f"{NCBI_EUTILS}/esearch.fcgi",
        params={"db": GEO_SEARCH_DB, "term": term, "retmode": "json", "retmax": retmax},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    return data.get("esearchresult", {}).get("idlist", [])


def _esummary_gds(ids: List[str]) -> List[Dict[str, Any]]:
    if not ids:
        return []
    r = requests.get(
        f"{NCBI_EUTILS}/esummary.fcgi",
        params={"db": GEO_SEARCH_DB, "id": ",".join(ids), "retmode": "json"},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    out = []
    for gid in ids:
        item = data.get("result", {}).get(gid, {})
        if item:
            out.append(item)
    return out


def _guess_sep(content: bytes) -> str:
    head = content[:5000].decode("utf-8", errors="ignore")
    if "\t" in head:
        return "\t"
    if "," in head:
        return ","
    return "\t"


def _detect_columns(df: pd.DataFrame) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    cols = {c: _norm(str(c)) for c in df.columns}

    gene_col = next((c for c, n in cols.items() if n in {"gene", "gene symbol", "genesymbol", "symbol", "hgnc_symbol"}), None)

    logfc_col = next(
        (c for c, n in cols.items() if "logfc" in n or n in {"log2 fold change", "log2fc", "log fold change"}),
        None
    )

    adjp_col = next(
        (c for c, n in cols.items() if n in {"adj.p.val", "adj p val", "padj", "fdr", "qvalue", "q-value"}),
        None
    )

    avgexpr_col = next(
        (c for c, n in cols.items() if n in {"aveexpr", "average expression", "baseMean".lower()} or "avg" in n),
        None
    )

    return gene_col, logfc_col, adjp_col, avgexpr_col


def _try_parse_table_bytes(content: bytes, source: str) -> Optional[Dict[str, Any]]:
    sep = _guess_sep(content)
    try:
        df = pd.read_csv(io.BytesIO(content), sep=sep)
    except Exception:
        return None

    if df is None or df.empty or len(df.columns) < 3:
        return None

    gene_col, logfc_col, adjp_col, avgexpr_col = _detect_columns(df)
    if not gene_col or not logfc_col or not adjp_col:
        return None

    # normalize in-place for fast lookup
    df["_gene_norm"] = df[gene_col].astype(str).str.strip().str.upper()

    return {
        "df": df,
        "gene_col": gene_col,
        "logfc_col": logfc_col,
        "adjp_col": adjp_col,
        "avgexpr_col": avgexpr_col,
        "source": source,
    }


def _fetch_candidate_tables_for_gse(gse: str) -> List[Dict[str, Any]]:
    """
    Tries common GEO file locations. Best-effort only.
    """
    out = []
    # Common supplementary page pattern
    supp_url = f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={gse}"
    try:
        html = requests.get(supp_url, timeout=30).text
    except Exception:
        return out

    # find candidate downloadable text/csv/tsv links
    links = set(re.findall(r'href="([^"]+)"', html))
    candidates = []
    for link in links:
        low = link.lower()
        if any(ext in low for ext in [".txt", ".tsv", ".csv"]):
            if low.startswith("/"):
                link = "https://www.ncbi.nlm.nih.gov" + link
            elif low.startswith("ftp://"):
                link = link.replace("ftp://", "https://")
            candidates.append(link)

    for url in candidates[:20]:
        try:
            r = requests.get(url, timeout=45)
            if r.status_code != 200 or len(r.content) < 200:
                continue
            parsed = _try_parse_table_bytes(r.content, source=f"GEO:{gse}")
            if parsed:
                out.append(parsed)
        except Exception:
            continue

    return out


def _build_disease_cache(disease_id: str) -> List[Dict[str, Any]]:
    ids = _esearch_gds_ids(disease_id, retmax=12)
    summaries = _esummary_gds(ids)

    # prefer series-like entries that mention GSE
    gses = []
    for s in summaries:
        acc = str(s.get("accession", "")).upper()
        if acc.startswith("GSE"):
            gses.append(acc)

    parsed_tables = []
    for gse in gses[:6]:
        parsed_tables.extend(_fetch_candidate_tables_for_gse(gse))

    return parsed_tables


def get_geo_metrics_for_gene(disease_id: str, gene_symbol: str) -> Optional[Dict[str, Any]]:
    """
    Fully automatic GEO retrieval.
    Real-only policy: returns None if no trustworthy DE table hit is found.
    """
    disease_key = _norm(disease_id)
    gene_key = _gene_norm(gene_symbol)

    if not disease_key or not gene_key:
        return None

    if disease_key not in _GEO_CACHE:
        try:
            _GEO_CACHE[disease_key] = _build_disease_cache(disease_key)
        except Exception:
            _GEO_CACHE[disease_key] = []

    for item in _GEO_CACHE[disease_key]:
        df = item["df"]
        hit = df.loc[df["_gene_norm"] == gene_key]
        if hit.empty:
            continue

        row = hit.iloc[0]
        logfc = _to_float(row.get(item["logfc_col"]))
        adjp = _to_float(row.get(item["adjp_col"]))
        avg = _to_float(row.get(item["avgexpr_col"])) if item.get("avgexpr_col") else None

        # strict validity
        if logfc is None or adjp is None:
            continue
        if not (0.0 <= adjp <= 1.0):
            continue

        return {
            "logfc": logfc,
            "adj_p_value": adjp,
            "average_expression": avg,
            "tissue": None,          # optional unless derivable
            "sample_size": None,     # optional unless derivable
            "source": item["source"],
        }

    return None