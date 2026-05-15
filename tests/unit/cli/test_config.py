"""Unit tests for CLI config helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from deep_agent.cli import config as config_mod


@pytest.fixture
def isolated_config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Use a temp home so ``~/.config/ask`` stays under ``tmp_path``."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


def test_get_config_dir_creates_directory(isolated_config_home: Path) -> None:
    d = config_mod.get_config_dir()
    assert d.is_dir()
    assert d == isolated_config_home / ".config" / "ask"


def test_load_config_empty_when_missing(isolated_config_home: Path) -> None:
    assert config_mod.load_config() == {}


def test_save_and_roundtrip(isolated_config_home: Path) -> None:
    config_mod.save_config({"url": "http://example.test", "auth": {}})
    loaded = config_mod.load_config()
    assert loaded == {"url": "http://example.test", "auth": {}}
    path = config_mod.get_config_dir() / "config.json"
    assert path.is_file()
    assert json.loads(path.read_text())["url"] == "http://example.test"


def test_resolve_url_precedence(isolated_config_home: Path) -> None:
    assert config_mod.resolve_url("http://flag.test") == "http://flag.test"
    with patch.dict(os.environ, {"AGENT_URL": "http://env.test"}):
        assert config_mod.resolve_url(None) == "http://env.test"
    with patch.dict(os.environ, {}, clear=True):
        config_mod.save_config({"url": "http://cfg.test"})
        assert config_mod.resolve_url(None) == "http://cfg.test"


def test_resolve_url_missing_raises(isolated_config_home: Path) -> None:
    with patch.dict(os.environ, {}, clear=True):
        config_mod.save_config({})
        with pytest.raises(ValueError, match="No agent URL"):
            config_mod.resolve_url(None)


def test_get_token_from_auth_section(isolated_config_home: Path) -> None:
    config_mod.save_config({"auth": {"access_token": "tok"}})
    assert config_mod.get_token() == "tok"
    config_mod.save_config({"auth": {"api_key": "k"}})
    assert config_mod.get_token() == "k"


def test_alias_add_and_resolve(isolated_config_home: Path) -> None:
    config_mod.save_config({"aliases": {"prod": "http://prod.test"}})
    assert config_mod.get_aliases() == {"prod": "http://prod.test"}
    assert config_mod.resolve_alias("prod") == "http://prod.test"
    assert config_mod.resolve_alias("missing") is None


def test_resolve_url_resolves_alias(isolated_config_home: Path) -> None:
    config_mod.save_config({"aliases": {"local": "http://local.test:5002"}})
    home = str(isolated_config_home)
    with patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}, clear=True):
        assert config_mod.resolve_url("local") == "http://local.test:5002"


def test_resolve_url_prefers_literal_over_alias(isolated_config_home: Path) -> None:
    config_mod.save_config({"aliases": {"local": "http://aliased.test"}})
    with patch.dict(os.environ, {}, clear=True):
        assert config_mod.resolve_url("http://explicit.test") == "http://explicit.test"


def test_get_aliases_empty_when_missing(isolated_config_home: Path) -> None:
    config_mod.save_config({})
    assert config_mod.get_aliases() == {}
