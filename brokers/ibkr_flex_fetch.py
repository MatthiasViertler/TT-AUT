"""
IBKR Flex Web Service report fetcher.

Downloads an Activity Statement from IBKR's Flex Web Service using a saved
Flex Query token + query ID. No browser interaction required.

Setup in users/{person}/config.local.yaml:
  ibkr_flex:
    token: "your_flex_token"   # IB Client Portal → Settings → Flex Web Service
    query_id: 123456           # The numeric ID of your saved Flex Query

Usage:
  python main.py --person matthias --year 2025 --fetch-ibkr

The fetched report is saved to users/{person}/data/IB/{person}_ibkr_flex_{YYYY-MM-DD}.csv
using today's date. Files accumulate over time: each fetch extends the history
window by one query period. The pipeline's raw_id deduplication handles any
overlapping transactions across files transparently.
"""

import logging
import time
import urllib.error
import urllib.request
from pathlib import Path
from xml.etree import ElementTree

log = logging.getLogger(__name__)

_SEND_URL = (
    "https://gdcdyn.interactivebrokers.com"
    "/Universal/servlet/FlexStatementService.SendRequest"
)
_GET_URL = (
    "https://gdcdyn.interactivebrokers.com"
    "/Universal/servlet/FlexStatementService.GetStatement"
)
_MAX_RETRIES = 10
_RETRY_DELAY_S = 5

# Error code returned by IBKR when the report is still being generated
_ERR_GENERATING = "1019"


class FlexFetchError(RuntimeError):
    """Raised when the IBKR Flex Web Service returns an error."""


def fetch_flex_report(
    token: str,
    query_id: str | int,
    save_path: Path,
    overwrite: bool = False,
) -> Path:
    """Fetch an IBKR Flex report and save it to *save_path*.

    Skips the download when *save_path* already exists and *overwrite* is False.
    Returns *save_path*.
    """
    if save_path.exists() and not overwrite:
        log.info("[ibkr-flex] Using cached report: %s", save_path)
        print(
            f"  [ibkr-flex] Using cached report: {save_path.name}"
            "  (pass --force-fetch-ibkr to re-download)"
        )
        return save_path

    print("  [ibkr-flex] Fetching report from IBKR Flex Web Service…")
    ref_code = _send_request(token, query_id)
    content = _get_statement(token, ref_code)

    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(content)
    print(f"  [ibkr-flex] Saved: {save_path}  ({len(content):,} bytes)")
    log.info("[ibkr-flex] Saved %d bytes to %s", len(content), save_path)
    return save_path


def _send_request(token: str, query_id: str | int) -> str:
    """Request statement generation; return the reference code."""
    url = f"{_SEND_URL}?t={token}&q={query_id}&v=3"

    for attempt in range(1, _MAX_RETRIES + 1):
        xml_bytes = _http_get(url)
        root = _parse_xml(xml_bytes, context="SendRequest")
        status = root.findtext("Status", "").strip()

        if status == "Success":
            ref_code = root.findtext("ReferenceCode", "").strip()
            if not ref_code:
                raise FlexFetchError(
                    "IBKR Flex: Success status but no ReferenceCode in response"
                )
            log.info("[ibkr-flex] Reference code: %s", ref_code)
            return ref_code

        error_code = root.findtext("ErrorCode", "").strip()
        error_msg = root.findtext("ErrorMessage", "").strip()

        if error_code == _ERR_GENERATING:
            print(f"  [ibkr-flex] Statement generating… (attempt {attempt}/{_MAX_RETRIES})")
            time.sleep(_RETRY_DELAY_S)
            continue

        if error_code == "1001":
            raise FlexFetchError(
                "IBKR cooldown active (error 1001) — wait ~10 minutes, then re-run with --force-fetch-ibkr"
            )

        raise FlexFetchError(
            f"IBKR Flex SendRequest error {error_code}: {error_msg}"
        )

    raise FlexFetchError(
        f"IBKR Flex: statement not ready after {_MAX_RETRIES} attempts"
    )


def _get_statement(token: str, ref_code: str) -> bytes:
    """Retrieve the generated statement bytes."""
    url = f"{_GET_URL}?q={ref_code}&t={token}&v=3"

    for attempt in range(1, _MAX_RETRIES + 1):
        content = _http_get(url)
        stripped = content.lstrip()

        # XML response → status message or error; anything else → actual report
        if stripped.startswith((b"<?xml", b"<Flex")):
            root = _parse_xml(content, context="GetStatement")
            error_code = root.findtext("ErrorCode", "").strip()
            error_msg = root.findtext("ErrorMessage", "").strip()

            if error_code == _ERR_GENERATING:
                print(
                    f"  [ibkr-flex] Waiting for statement… (attempt {attempt}/{_MAX_RETRIES})"
                )
                time.sleep(_RETRY_DELAY_S)
                continue

            raise FlexFetchError(
                f"IBKR Flex GetStatement error {error_code}: {error_msg}"
            )

        return content

    raise FlexFetchError(
        f"IBKR Flex: statement still not available after {_MAX_RETRIES} retries"
    )


def _http_get(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.read()
    except urllib.error.URLError as e:
        raise FlexFetchError(f"IBKR Flex HTTP error: {e}") from e


def _parse_xml(data: bytes, context: str = "") -> ElementTree.Element:
    try:
        return ElementTree.fromstring(data)
    except ElementTree.ParseError as e:
        raise FlexFetchError(
            f"IBKR Flex {context}: invalid XML in response: {e}"
        ) from e
