"""Tests for core/config.py — scan_account_ids and load_config."""

import pytest
from pathlib import Path
import yaml

from core.config import scan_account_ids, load_config, DEFAULTS


# ── scan_account_ids ──────────────────────────────────────────────────────────

def test_scan_empty_users_dir(tmp_path):
    assert scan_account_ids(tmp_path) == {}


def test_scan_missing_users_dir(tmp_path):
    assert scan_account_ids(tmp_path / "nonexistent") == {}


def test_scan_scalar_account_id(tmp_path):
    person = tmp_path / "jessie"
    person.mkdir()
    (person / "config.local.yaml").write_text("account_id: U11111111\n")
    assert scan_account_ids(tmp_path) == {"U11111111": "jessie"}


def test_scan_list_account_id(tmp_path):
    person = tmp_path / "matthias"
    person.mkdir()
    (person / "config.local.yaml").write_text(
        "account_id:\n  - U22222222\n  - '18801362'\n"
    )
    result = scan_account_ids(tmp_path)
    assert result == {"U22222222": "matthias", "18801362": "matthias"}


def test_scan_multiple_persons(tmp_path):
    for name, aid in [("jessie", "U11111111"), ("matthias", "U22222222")]:
        d = tmp_path / name
        d.mkdir()
        (d / "config.local.yaml").write_text(f"account_id: {aid}\n")
    result = scan_account_ids(tmp_path)
    assert result == {"U11111111": "jessie", "U22222222": "matthias"}


def test_scan_person_without_account_id(tmp_path):
    person = tmp_path / "nobody"
    person.mkdir()
    (person / "config.local.yaml").write_text("at_residency_start_year: 2024\n")
    assert scan_account_ids(tmp_path) == {}


def test_scan_person_without_config_file(tmp_path):
    (tmp_path / "ghost").mkdir()
    assert scan_account_ids(tmp_path) == {}


def test_scan_ignores_files_at_root(tmp_path):
    (tmp_path / "config.local.yaml").write_text("account_id: SHOULDNOTAPPEAR\n")
    assert scan_account_ids(tmp_path) == {}


# ── load_config ───────────────────────────────────────────────────────────────

def test_load_config_defaults_when_no_file(tmp_path):
    config = load_config(str(tmp_path / "missing.yaml"))
    assert config["kest_rate"] == 0.275


def test_load_config_merges_universal(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("kest_rate: 0.30\n")
    config = load_config(str(cfg_file))
    assert config["kest_rate"] == 0.30
    assert "wht_treaty_rates" in config  # defaults still present


def test_load_config_merges_person_overrides(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("kest_rate: 0.275\n")
    users_dir = tmp_path / "users"
    person_dir = users_dir / "matthias"
    person_dir.mkdir(parents=True)
    (person_dir / "config.local.yaml").write_text(
        "at_residency_start_year: 2024\nfreedom_dashboard:\n  portfolio_eur: 150000\n"
    )
    config = load_config(str(cfg_file), person="matthias", users_dir=users_dir)
    assert config["at_residency_start_year"] == 2024
    assert config["freedom_dashboard"]["portfolio_eur"] == 150000
    assert config["kest_rate"] == 0.275  # universal default preserved


def test_load_config_no_person_skips_user_config(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("kest_rate: 0.275\n")
    users_dir = tmp_path / "users"
    person_dir = users_dir / "matthias"
    person_dir.mkdir(parents=True)
    (person_dir / "config.local.yaml").write_text("at_residency_start_year: 2024\n")
    config = load_config(str(cfg_file), person=None, users_dir=users_dir)
    assert "at_residency_start_year" not in config


def test_load_config_deep_merge_nested_dicts(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("output:\n  excel: false\n")
    users_dir = tmp_path / "users"
    person_dir = users_dir / "jessie"
    person_dir.mkdir(parents=True)
    (person_dir / "config.local.yaml").write_text("output:\n  csv: false\n")
    config = load_config(str(cfg_file), person="jessie", users_dir=users_dir)
    assert config["output"]["excel"] is False   # from config.yaml
    assert config["output"]["csv"] is False     # from person config
    assert config["output"]["tax_summary"] is True  # from DEFAULTS


def test_load_config_cache_dirs_updated():
    config = load_config("config.yaml")
    assert "fx_cache" in config["fx_cache_dir"]
    assert "price_cache" in config["price_cache_dir"]
    assert "data/" not in config["fx_cache_dir"]
    assert "data/" not in config["price_cache_dir"]
