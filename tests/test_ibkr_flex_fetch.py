"""Tests for brokers/ibkr_flex_fetch.py."""

import io
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from brokers.ibkr_flex_fetch import (
    FlexFetchError,
    _get_statement,
    _http_get,
    _parse_xml,
    _send_request,
    fetch_flex_report,
)


# ── XML helpers ────────────────────────────────────────────────────────────────

def _xml_success(ref_code: str = "REFCODE123") -> bytes:
    return (
        f"<?xml version='1.0'?>"
        f"<FlexStatementResponse>"
        f"  <Status>Success</Status>"
        f"  <ReferenceCode>{ref_code}</ReferenceCode>"
        f"</FlexStatementResponse>"
    ).encode()


def _xml_error(code: str, msg: str) -> bytes:
    return (
        f"<?xml version='1.0'?>"
        f"<FlexStatementResponse>"
        f"  <Status>Fail</Status>"
        f"  <ErrorCode>{code}</ErrorCode>"
        f"  <ErrorMessage>{msg}</ErrorMessage>"
        f"</FlexStatementResponse>"
    ).encode()


def _xml_generating() -> bytes:
    return _xml_error("1019", "Statement generation in progress. Please try again shortly.")


def _fake_urlopen(content: bytes):
    """Return a context-manager mock that yields a readable response."""
    resp = MagicMock()
    resp.read.return_value = content
    resp.__enter__ = lambda s: resp
    resp.__exit__ = MagicMock(return_value=False)
    return resp


CSV_BYTES = b"BOS,Activity\nHEADER,...\nDATA,...\nEOS,Activity\n"


# ── _parse_xml ─────────────────────────────────────────────────────────────────

def test_parse_xml_valid():
    root = _parse_xml(b"<Root><Child>hello</Child></Root>")
    assert root.findtext("Child") == "hello"


def test_parse_xml_invalid_raises():
    with pytest.raises(FlexFetchError, match="invalid XML"):
        _parse_xml(b"not xml at all", context="TestCtx")


# ── _http_get ──────────────────────────────────────────────────────────────────

def test_http_get_success():
    with patch("urllib.request.urlopen", return_value=_fake_urlopen(b"data")) as mock_open:
        result = _http_get("https://example.com/test")
    assert result == b"data"
    mock_open.assert_called_once()


def test_http_get_network_error():
    import urllib.error
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
        with pytest.raises(FlexFetchError, match="HTTP error"):
            _http_get("https://example.com/test")


# ── _send_request ──────────────────────────────────────────────────────────────

def test_send_request_success():
    with patch("urllib.request.urlopen", return_value=_fake_urlopen(_xml_success("REF99"))):
        ref = _send_request("mytoken", 12345)
    assert ref == "REF99"


def test_send_request_retries_on_1019_then_succeeds():
    side_effects = [
        _fake_urlopen(_xml_generating()),
        _fake_urlopen(_xml_generating()),
        _fake_urlopen(_xml_success("REFAFTER")),
    ]
    with patch("urllib.request.urlopen", side_effect=side_effects):
        with patch("time.sleep"):  # don't actually sleep in tests
            ref = _send_request("tok", 42)
    assert ref == "REFAFTER"


def test_send_request_auth_error_raises():
    err_xml = _xml_error("1003", "Authorization failed")
    with patch("urllib.request.urlopen", return_value=_fake_urlopen(err_xml)):
        with pytest.raises(FlexFetchError, match="1003"):
            _send_request("bad_token", 99)


def test_send_request_no_ref_code_raises():
    xml = (
        b"<?xml version='1.0'?>"
        b"<FlexStatementResponse>"
        b"  <Status>Success</Status>"
        b"  <ReferenceCode></ReferenceCode>"
        b"</FlexStatementResponse>"
    )
    with patch("urllib.request.urlopen", return_value=_fake_urlopen(xml)):
        with pytest.raises(FlexFetchError, match="no ReferenceCode"):
            _send_request("tok", 1)


def test_send_request_exhausts_retries():
    with patch("urllib.request.urlopen", return_value=_fake_urlopen(_xml_generating())):
        with patch("time.sleep"):
            with pytest.raises(FlexFetchError, match="not ready after"):
                _send_request("tok", 1)


# ── _get_statement ─────────────────────────────────────────────────────────────

def test_get_statement_returns_csv():
    with patch("urllib.request.urlopen", return_value=_fake_urlopen(CSV_BYTES)):
        result = _get_statement("tok", "REF1")
    assert result == CSV_BYTES


def test_get_statement_retries_on_1019_then_returns_csv():
    side_effects = [
        _fake_urlopen(_xml_generating()),
        _fake_urlopen(CSV_BYTES),
    ]
    with patch("urllib.request.urlopen", side_effect=side_effects):
        with patch("time.sleep"):
            result = _get_statement("tok", "REF1")
    assert result == CSV_BYTES


def test_get_statement_error_raises():
    err_xml = _xml_error("1010", "Service unavailable")
    with patch("urllib.request.urlopen", return_value=_fake_urlopen(err_xml)):
        with pytest.raises(FlexFetchError, match="1010"):
            _get_statement("tok", "REF1")


def test_get_statement_exhausts_retries():
    with patch("urllib.request.urlopen", return_value=_fake_urlopen(_xml_generating())):
        with patch("time.sleep"):
            with pytest.raises(FlexFetchError, match="still not available"):
                _get_statement("tok", "REF1")


# ── fetch_flex_report ──────────────────────────────────────────────────────────

def test_fetch_saves_file(tmp_path):
    save_path = tmp_path / "report.csv"
    side_effects = [
        _fake_urlopen(_xml_success("REF1")),
        _fake_urlopen(CSV_BYTES),
    ]
    with patch("urllib.request.urlopen", side_effect=side_effects):
        result = fetch_flex_report("tok", 1, save_path)
    assert result == save_path
    assert save_path.read_bytes() == CSV_BYTES


def test_fetch_skips_if_exists_no_overwrite(tmp_path):
    save_path = tmp_path / "report.csv"
    save_path.write_bytes(b"old content")
    with patch("urllib.request.urlopen") as mock_open:
        result = fetch_flex_report("tok", 1, save_path, overwrite=False)
    mock_open.assert_not_called()
    assert result == save_path
    assert save_path.read_bytes() == b"old content"


def test_fetch_overwrites_if_force(tmp_path):
    save_path = tmp_path / "report.csv"
    save_path.write_bytes(b"old content")
    side_effects = [
        _fake_urlopen(_xml_success("REF2")),
        _fake_urlopen(CSV_BYTES),
    ]
    with patch("urllib.request.urlopen", side_effect=side_effects):
        result = fetch_flex_report("tok", 1, save_path, overwrite=True)
    assert save_path.read_bytes() == CSV_BYTES


def test_fetch_creates_parent_dirs(tmp_path):
    save_path = tmp_path / "a" / "b" / "report.csv"
    side_effects = [
        _fake_urlopen(_xml_success("REF3")),
        _fake_urlopen(CSV_BYTES),
    ]
    with patch("urllib.request.urlopen", side_effect=side_effects):
        fetch_flex_report("tok", 1, save_path)
    assert save_path.exists()


def test_fetch_propagates_flex_error(tmp_path):
    save_path = tmp_path / "report.csv"
    err_xml = _xml_error("1003", "Authorization failed")
    with patch("urllib.request.urlopen", return_value=_fake_urlopen(err_xml)):
        with pytest.raises(FlexFetchError, match="1003"):
            fetch_flex_report("tok", 1, save_path)


def test_fetch_does_not_save_on_error(tmp_path):
    save_path = tmp_path / "report.csv"
    err_xml = _xml_error("1003", "Authorization failed")
    with patch("urllib.request.urlopen", return_value=_fake_urlopen(err_xml)):
        with pytest.raises(FlexFetchError):
            fetch_flex_report("tok", 1, save_path)
    assert not save_path.exists()


def test_send_request_uses_correct_url():
    with patch("brokers.ibkr_flex_fetch._http_get", return_value=_xml_success("R1")) as mock_get:
        _send_request("mytoken", 42)
    url = mock_get.call_args[0][0]
    assert "t=mytoken" in url
    assert "q=42" in url
    assert "v=3" in url


def test_get_statement_uses_correct_url():
    with patch("brokers.ibkr_flex_fetch._http_get", return_value=CSV_BYTES) as mock_get:
        _get_statement("mytoken", "REFXYZ")
    url = mock_get.call_args[0][0]
    assert "q=REFXYZ" in url
    assert "t=mytoken" in url
    assert "v=3" in url
