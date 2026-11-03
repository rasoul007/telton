"""Launcher tests — these run without network and without a Windows console."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

LAUNCHER = Path(__file__).resolve().parent.parent / "scripts" / "launcher.py"


def load_launcher():
    spec = importlib.util.spec_from_file_location("telton_launcher", LAUNCHER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def launcher():
    return load_launcher()


def test_has_handles_missing_dotted_module(launcher):
    """This used to raise ModuleNotFoundError and crash the Windows launcher."""
    assert launcher._has("definitely_not_installed_pkg.child") is False
    assert launcher._has("this_module_does_not_exist_at_all") is False


def test_has_finds_real_modules(launcher):
    assert launcher._has("json") is True
    assert launcher._has("importlib.util") is True


def test_missing_packages_returns_list_without_raising(launcher):
    missing = launcher.missing_packages()
    assert isinstance(missing, list)


def test_launcher_source_is_ascii_only(launcher):
    """Windows consoles mangle Persian text, so the UI must stay ASCII."""
    raw = LAUNCHER.read_bytes()
    offenders = [b for b in raw if b > 127]
    assert offenders == [], "launcher.py contains non-ASCII bytes"


def test_menu_choices_are_listed(launcher, capsys, monkeypatch):
    monkeypatch.setattr(launcher, "clear", lambda: None)
    monkeypatch.setattr("builtins.input", lambda *_: "0")
    monkeypatch.setattr(launcher, "ensure_ready", lambda: True)
    assert launcher.main() == 0
    out = capsys.readouterr().out
    assert "Make video for YouTube" in out
    assert "Make video for Instagram" in out
    assert "Upload to YouTube" in out
