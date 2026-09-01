"""
UniProt ID Mapping connector.

Uses the UniProt REST ID Mapping API to map STRING protein IDs
to UniProt Accession IDs (e.g. ENSP00000394624 → P35372).

API flow:
  1. POST /idmapping/run        → submit job
  2. GET  /idmapping/status/{id} → poll until done
  3. GET  /idmapping/results/{id}→ retrieve mapped IDs
"""
import time
import logging
import httpx
from typing import Any

logger = logging.getLogger(__name__)

UNIPROT_API_BASE = "https://rest.uniprot.org"
POLL_INTERVAL_SEC = 3.0
MAX_POLL_ATTEMPTS = 30       # ~90 seconds max wait


def _strip_species_prefix(string_id: str) -> str:
    """Remove '9606.' (or any species prefix) from a STRING ID."""
    if "." in string_id:
        return string_id.split(".", 1)[1]
    return string_id


def submit_id_mapping(
    string_ids: list[str],
    from_db: str = "Ensembl_Protein",
    to_db: str = "UniProtKB",
) -> str:
    """
    Submit a batch ID mapping job to UniProt.
    Returns the jobId for polling.
    """
    # Strip species prefix from all IDs
    cleaned_ids = [_strip_species_prefix(sid) for sid in string_ids]

    url = f"{UNIPROT_API_BASE}/idmapping/run"
    data = {
        "from": from_db,
        "to": to_db,
        "ids": ",".join(cleaned_ids),
    }

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        resp = client.post(url, data=data)
        resp.raise_for_status()
        result = resp.json()

    job_id = result.get("jobId", "")
    if not job_id:
        raise RuntimeError(f"UniProt ID mapping returned no jobId: {result}")

    logger.info("UniProt ID mapping job submitted: %s (%d IDs)", job_id, len(cleaned_ids))
    return job_id


def poll_mapping_status(job_id: str) -> bool:
    """
    Poll UniProt until the mapping job is complete.
    Returns True when done, raises on timeout.
    """
    url = f"{UNIPROT_API_BASE}/idmapping/status/{job_id}"

    for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()

            # UniProt redirects (303) to the results URL when done.
            # If we followed a redirect and got results, we're done.
            if "/results/" in str(resp.url):
                logger.info("UniProt mapping job %s complete via redirect (attempt %d)", job_id, attempt)
                return True

            data = resp.json()

        if "results" in data or "failedIds" in data:
            logger.info("UniProt mapping job %s complete (attempt %d)", job_id, attempt)
            return True

        if data.get("jobStatus") == "RUNNING":
            logger.debug("Job %s still running (attempt %d/%d)", job_id, attempt, MAX_POLL_ATTEMPTS)
            time.sleep(POLL_INTERVAL_SEC)
            continue

        # Unexpected status
        time.sleep(POLL_INTERVAL_SEC)

    raise TimeoutError(
        f"UniProt ID mapping job {job_id} did not complete "
        f"after {MAX_POLL_ATTEMPTS * POLL_INTERVAL_SEC}s"
    )


def fetch_mapping_results(job_id: str) -> list[dict[str, Any]]:
    """
    Fetch the completed mapping results.
    Returns list of {from, to} dicts.
    """
    url = f"{UNIPROT_API_BASE}/idmapping/results/{job_id}"

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()

    return data.get("results", [])


def map_string_to_uniprot(
    string_ids: list[str],
) -> dict[str, str]:
    """
    High-level function: takes a list of full STRING IDs
    (e.g. '9606.ENSP00000394624') and returns a dict mapping
    each full STRING ID → UniProt accession.

    Example:
        {'9606.ENSP00000394624': 'P35372', ...}
    """
    if not string_ids:
        return {}

    # Deduplicate
    unique_ids = list(set(string_ids))

    # Build lookup: cleaned_id → original full STRING ID
    cleaned_to_full: dict[str, str] = {}
    for sid in unique_ids:
        cleaned = _strip_species_prefix(sid)
        cleaned_to_full[cleaned] = sid

    # Submit, poll, fetch
    job_id = submit_id_mapping(unique_ids)
    poll_mapping_status(job_id)
    results = fetch_mapping_results(job_id)

    # Build mapping: full_string_id → uniprot_accession
    mapping: dict[str, str] = {}
    for entry in results:
        from_id = entry.get("from", "")
        to_entry = entry.get("to", {})

        # UniProt returns the accession in to.primaryAccession
        if isinstance(to_entry, dict):
            uniprot_acc = to_entry.get("primaryAccession", "")
        else:
            uniprot_acc = str(to_entry)

        if from_id and uniprot_acc:
            # Map back to the full STRING ID
            full_sid = cleaned_to_full.get(from_id, from_id)
            mapping[full_sid] = uniprot_acc

    logger.info(
        "UniProt mapping complete: %d/%d IDs mapped",
        len(mapping), len(unique_ids),
    )
    return mapping
