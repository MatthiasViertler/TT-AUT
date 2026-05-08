"""Tests for main.py directory-scanning helpers."""

import sys
from pathlib import Path

import pytest

# Import helpers from main (they have no side effects)
sys.path.insert(0, str(Path(__file__).parent.parent))
from main import _resolve_inputs, _detect_person_from_paths


# ── _resolve_inputs ────────────────────────────────────────────────────────────

def test_file_passthrough(tmp_path):
    f = tmp_path / "export.csv"
    f.touch()
    assert _resolve_inputs([f]) == [f]


def test_directory_expanded(tmp_path):
    (tmp_path / "2024").mkdir()
    f = tmp_path / "2024" / "ib_2024.csv"
    f.touch()
    assert _resolve_inputs([tmp_path]) == [f]


def test_directory_recursive_multi_year(tmp_path):
    for year in (2023, 2024, 2025):
        d = tmp_path / f"IB/{year}"
        d.mkdir(parents=True)
        (d / f"export_{year}.csv").touch()
    result = _resolve_inputs([tmp_path])
    assert len(result) == 3
    assert all(p.suffix == ".csv" for p in result)
    assert result == sorted(result)   # sorted order guaranteed


def test_directory_skips_dotfiles(tmp_path):
    (tmp_path / ".hidden.csv").touch()
    (tmp_path / "~tmp.xlsx").touch()
    (tmp_path / "_draft.csv").touch()
    (tmp_path / "real.csv").touch()
    result = _resolve_inputs([tmp_path])
    assert result == [tmp_path / "real.csv"]


def test_directory_skips_unknown_extensions(tmp_path):
    (tmp_path / "notes.pdf").touch()
    (tmp_path / "export.csv").touch()
    result = _resolve_inputs([tmp_path])
    assert result == [tmp_path / "export.csv"]


def test_directory_empty_returns_nothing(tmp_path, capsys):
    result = _resolve_inputs([tmp_path])
    assert result == []
    captured = capsys.readouterr()
    assert "No broker files found" in captured.err


def test_mix_file_and_directory(tmp_path):
    d = tmp_path / "subdir"
    d.mkdir()
    f_dir = d / "ib_2024.csv"
    f_dir.touch()
    f_direct = tmp_path / "ib_2025.csv"
    f_direct.touch()
    result = _resolve_inputs([f_direct, d])
    assert f_direct in result
    assert f_dir in result
    assert len(result) == 2


def test_xlsx_detected(tmp_path):
    f = tmp_path / "saxo.xlsx"
    f.touch()
    assert _resolve_inputs([tmp_path]) == [f]


# ── _detect_person_from_paths ─────────────────────────────────────────────────

def test_detect_single_person(tmp_path):
    p = tmp_path / "matthias" / "data" / "IB" / "2025" / "export.csv"
    p.parent.mkdir(parents=True)
    p.touch()
    assert _detect_person_from_paths([p], tmp_path) == "matthias"


def test_detect_multiple_persons_returns_none(tmp_path):
    for person in ("matthias", "jessie"):
        p = tmp_path / person / "data" / "export.csv"
        p.parent.mkdir(parents=True)
        p.touch()
    paths = [
        tmp_path / "matthias" / "data" / "export.csv",
        tmp_path / "jessie"   / "data" / "export.csv",
    ]
    assert _detect_person_from_paths(paths, tmp_path) is None


def test_detect_path_outside_users_returns_none(tmp_path):
    p = tmp_path / "other" / "file.csv"
    p.parent.mkdir(parents=True)
    p.touch()
    users_dir = tmp_path / "users"
    users_dir.mkdir()
    assert _detect_person_from_paths([p], users_dir) is None
