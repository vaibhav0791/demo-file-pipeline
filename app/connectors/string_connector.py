import httpx
import time
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── STRING DB API base ──────────────────────────────────────────────
STRING_API_BASE = "https://string-db.org/api"
SPECIES_HUMAN = 9606
MAX_BATCH_SIZE = 80          # hard cap from pipeline requirements
REQUEST_DELAY_SEC = 1.0      # polite delay between requests
MAX_RETRIES = 3
BACKOFF_FACTOR = 2.0         # exponential back-off multiplier


def _request_with_retry(
    method: str,
    url: str,
    *,
    params: dict | None = None,
    data: dict | None = None,
    timeout: float = 30.0,
) -> Any:
    """
    HTTP helper with exponential back-off and retry logic.
    Handles 429 (rate-limit) and 5xx errors gracefully.
    """
    delay = REQUEST_DELAY_SEC
    last_exc: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                if method == "GET":
                    resp = client.get(url, params=params)
                else:
                    resp = client.post(url, data=data)

                # Rate-limited → back off
                if resp.status_code == 429:
                    logger.warning(
                        "STRING API rate-limited (429). "
                        "Attempt %d/%d — sleeping %.1fs",
                        attempt, MAX_RETRIES, delay,
                    )
                    time.sleep(delay)
                    delay *= BACKOFF_FACTOR
                    continue

                resp.raise_for_status()
                return resp.json()

        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            last_exc = exc
            logger.warning(
                "STRING API error on attempt %d/%d: %s — retrying in %.1fs",
                attempt, MAX_RETRIES, exc, delay,
            )
            time.sleep(delay)
            delay *= BACKOFF_FACTOR

    raise RuntimeError(
        f"STRING API request failed after {MAX_RETRIES} attempts: {last_exc}"
    )


# ── Public API ──────────────────────────────────────────────────────

def map_identifiers_to_string_ids(
    identifiers: list[str],
    species: int = SPECIES_HUMAN,
) -> list[dict[str, Any]]:
    """
    Map gene symbols / UniProt accessions to STRING IDs.
    Returns a list of dicts with keys like:
      queryItem, stringId, preferredName, annotation …
    """
    if len(identifiers) > MAX_BATCH_SIZE:
        raise ValueError(
            f"Batch size {len(identifiers)} exceeds the "
            f"maximum of {MAX_BATCH_SIZE} proteins per request."
        )

    url = f"{STRING_API_BASE}/json/get_string_ids"
    data = {
        "identifiers": "\r".join(identifiers),
        "species": species,
        "limit": 1,           # best hit per identifier
    }

    time.sleep(REQUEST_DELAY_SEC)      # polite pre-request delay
    return _request_with_retry("POST", url, data=data)


def fetch_interaction_partners(
    string_id: str,
    *,
    species: int = SPECIES_HUMAN,
    limit: int = 50,
    required_score: int = 400,
) -> list[dict[str, Any]]:
    """
    Fetch interaction partners for a single STRING protein ID.
    Returns list of interaction dicts (preferredName_A/B, score, …).
    """
    url = f"{STRING_API_BASE}/json/interaction_partners"
    data = {
        "identifiers": string_id,
        "species": species,
        "limit": limit,
        "required_score": required_score,
    }

    time.sleep(REQUEST_DELAY_SEC)
    return _request_with_retry("POST", url, data=data)


def fetch_network(
    string_ids: list[str],
    *,
    species: int = SPECIES_HUMAN,
    required_score: int = 400,
) -> list[dict[str, Any]]:
    """
    Fetch the full interaction network among a set of STRING IDs.
    Useful for building the networkx graph for centrality computation.
    """
    if len(string_ids) > MAX_BATCH_SIZE:
        raise ValueError(
            f"Batch size {len(string_ids)} exceeds the "
            f"maximum of {MAX_BATCH_SIZE} proteins."
        )

    url = f"{STRING_API_BASE}/json/network"
    data = {
        "identifiers": "\r".join(string_ids),
        "species": species,
        "required_score": required_score,
    }

    time.sleep(REQUEST_DELAY_SEC)
    return _request_with_retry("POST", url, data=data)
