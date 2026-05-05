"""Tests for output/anv_checklist.py."""

import pytest
from pathlib import Path
from output.anv_checklist import write_anv_checklist, _pendlerpauschale


# ── _pendlerpauschale ─────────────────────────────────────────────────────────

def test_pp_public_below_threshold():
    assert _pendlerpauschale(15, "public") == 0.0

def test_pp_public_20_40():
    assert _pendlerpauschale(25, "public") == 696.0

def test_pp_public_40_60():
    assert _pendlerpauschale(45, "public") == 1356.0

def test_pp_public_over_60():
    assert _pendlerpauschale(70, "public") == 2016.0

def test_pp_car_below_threshold():
    assert _pendlerpauschale(1, "car") == 0.0

def test_pp_car_2_20():
    assert _pendlerpauschale(10, "car") == 372.0

def test_pp_car_20_40():
    assert _pendlerpauschale(30, "car") == 1476.0

def test_pp_car_40_60():
    assert _pendlerpauschale(50, "car") == 2568.0

def test_pp_car_over_60():
    assert _pendlerpauschale(65, "car") == 3672.0

def test_pp_zero_km():
    assert _pendlerpauschale(0, "public") == 0.0


# ── write_anv_checklist ───────────────────────────────────────────────────────

def test_no_anv_config_produces_no_file(tmp_path):
    p = tmp_path / "out.txt"
    write_anv_checklist({}, 2025, "Jessie", p)
    assert not p.exists()


def test_basic_output_written(tmp_path):
    config = {"anv": {"home_office_days": 60}}
    p = tmp_path / "out.txt"
    write_anv_checklist(config, 2025, "Jessie", p)
    assert p.exists()
    text = p.read_text(encoding="utf-8")
    assert "Jessie" in text
    assert "2025" in text
    assert "ARBEITNEHMERVERANLAGUNG" in text


def test_home_office_pauschale_calculation(tmp_path):
    config = {"anv": {"home_office_days": 60}}
    p = tmp_path / "out.txt"
    write_anv_checklist(config, 2025, "Jessie", p)
    text = p.read_text(encoding="utf-8")
    # 60 days × €3 = €180
    assert "180" in text


def test_home_office_capped_at_100_days(tmp_path):
    config = {"anv": {"home_office_days": 150}}
    p = tmp_path / "out.txt"
    write_anv_checklist(config, 2025, "Jessie", p)
    text = p.read_text(encoding="utf-8")
    # 100 days × €3 = €300 (capped)
    assert "300" in text
    assert "capped at 100 days" in text


def test_pendlerpauschale_appears(tmp_path):
    config = {"anv": {"commute_km": 25, "commute_type": "public"}}
    p = tmp_path / "out.txt"
    write_anv_checklist(config, 2025, "Jessie", p)
    text = p.read_text(encoding="utf-8")
    assert "696" in text          # Kleines 20–40 km
    assert "Pendlerrechner" in text


def test_pendlereuro_calculated(tmp_path):
    config = {"anv": {"commute_km": 25, "commute_type": "public"}}
    p = tmp_path / "out.txt"
    write_anv_checklist(config, 2025, "Jessie", p)
    text = p.read_text(encoding="utf-8")
    # 25 km × €2 = €50 Pendlereuro
    assert "50" in text


def test_kirchenbeitrag_capped_at_400(tmp_path):
    config = {"anv": {"kirchenbeitrag_eur": 500}}
    p = tmp_path / "out.txt"
    write_anv_checklist(config, 2025, "Jessie", p)
    text = p.read_text(encoding="utf-8")
    assert "400" in text
    assert "capped at €400" in text


def test_familienbonus_plus_shown(tmp_path):
    config = {"anv": {"family_bonus_children": 2}}
    p = tmp_path / "out.txt"
    write_anv_checklist(config, 2025, "Matthias", p)
    text = p.read_text(encoding="utf-8")
    assert "Familienbonus Plus" in text
    assert "4,000" in text   # 2 × €2,000


def test_wk_comparison_itemized_wins(tmp_path):
    # 80 days home office = €240 > €132 Pauschale
    config = {"anv": {"home_office_days": 80, "tax_advisor_eur": 200}}
    p = tmp_path / "out.txt"
    write_anv_checklist(config, 2025, "Jessie", p)
    text = p.read_text(encoding="utf-8")
    assert "WORTH FILING" in text


def test_finanzonline_url_present(tmp_path):
    config = {"anv": {"home_office_days": 1}}
    p = tmp_path / "out.txt"
    write_anv_checklist(config, 2025, "Jessie", p)
    text = p.read_text(encoding="utf-8")
    assert "finanzonline" in text.lower()


def test_e1kv_reference_in_filing_steps(tmp_path):
    config = {"anv": {"home_office_days": 1}}
    p = tmp_path / "out.txt"
    write_anv_checklist(config, 2025, "Jessie", p)
    text = p.read_text(encoding="utf-8")
    assert "E1kv" in text
    assert "tax_summary.txt" in text
