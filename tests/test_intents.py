"""Unit tests for bar_launch.intents.

These run without Tk and without a populated BAR data dir — they exercise the
intent translation against a fixture modinfos dict that mirrors what
build_context() produces in practice.
"""
from __future__ import annotations

import pytest

from bar_launch.intents import Intent, default_boot, resolve_intent


# Mirrors the canonical entries build_context() always inserts, plus a couple
# of $VERSION-tagged + [LOCAL] entries to exercise pinned/local resolution.
FIXTURE_MODINFOS = {
    "Spring-launcher with rapid://byar-chobby:test": {"modtype": "0", "name": "rapid://byar-chobby:test"},
    "Latest BYAR Chobby Lobby: rapid://byar-chobby:test": {"name": "rapid://byar-chobby:test", "version": "", "modtype": "5"},
    "Latest BAR Game: rapid://byar:test": {"name": "rapid://byar:test", "version": "", "modtype": "1"},
    "Beyond All Reason 2025.04.1234 $VERSION": {"modtype": "1", "name": "Beyond All Reason 2025.04.1234"},
    "[LOCAL] Beyond-All-Reason": {"modtype": "1", "name": "Beyond All Reason $VERSION"},
    "[LOCAL] BYAR-Chobby": {"modtype": "5", "name": "BYAR Chobby $VERSION"},
    "[LOCAL] Spring-launcher with BYAR-Chobby": {"modtype": "0", "name": "BYAR Chobby $VERSION"},
}


def test_default_boot():
    assert default_boot("chobby") == "launcher"
    assert default_boot("bar") == "engine"
    assert default_boot("replay") == "engine"


def test_latest_chobby_via_launcher():
    label, mi = resolve_intent(Intent("chobby", "latest", "launcher"), FIXTURE_MODINFOS)
    assert label == "Spring-launcher with rapid://byar-chobby:test"
    assert mi["modtype"] == "0"


def test_latest_chobby_direct_engine():
    label, mi = resolve_intent(Intent("chobby", "latest", "engine"), FIXTURE_MODINFOS)
    assert label == "Latest BYAR Chobby Lobby: rapid://byar-chobby:test"
    assert mi["modtype"] == "5"


def test_latest_bar_engine():
    label, mi = resolve_intent(Intent("bar", "latest", "engine"), FIXTURE_MODINFOS)
    assert label == "Latest BAR Game: rapid://byar:test"
    assert mi["modtype"] == "1"


def test_local_bar_engine():
    label, mi = resolve_intent(Intent("bar", "local", "engine"), FIXTURE_MODINFOS)
    assert label == "[LOCAL] Beyond-All-Reason"
    assert mi["modtype"] == "1"


def test_local_chobby_launcher():
    label, mi = resolve_intent(Intent("chobby", "local", "launcher"), FIXTURE_MODINFOS)
    assert label == "[LOCAL] Spring-launcher with BYAR-Chobby"
    assert mi["modtype"] == "0"


def test_local_chobby_engine():
    label, mi = resolve_intent(Intent("chobby", "local", "engine"), FIXTURE_MODINFOS)
    assert label == "[LOCAL] BYAR-Chobby"
    assert mi["modtype"] == "5"


def test_pinned_bar_by_substring():
    label, mi = resolve_intent(Intent("bar", "pinned", "engine", version="2025.04"), FIXTURE_MODINFOS)
    assert "2025.04.1234" in label
    assert mi["modtype"] == "1"


def test_pinned_requires_version():
    with pytest.raises(ValueError, match="requires version"):
        resolve_intent(Intent("bar", "pinned", "engine"), FIXTURE_MODINFOS)


def test_replay_intent_rejected():
    with pytest.raises(ValueError, match="try_start_replay"):
        resolve_intent(Intent("replay", "latest", "engine"), FIXTURE_MODINFOS)


def test_unknown_play_rejected():
    with pytest.raises(ValueError, match="unknown play"):
        resolve_intent(Intent("blizzcon", "latest", "engine"), FIXTURE_MODINFOS)


def test_local_bar_missing_raises():
    incomplete = {k: v for k, v in FIXTURE_MODINFOS.items() if not k.startswith("[LOCAL] Beyond")}
    with pytest.raises(KeyError, match="link::create"):
        resolve_intent(Intent("bar", "local", "engine"), incomplete)


def test_pinned_no_match_raises():
    with pytest.raises(KeyError, match="no entry containing"):
        resolve_intent(Intent("bar", "pinned", "engine", version="9999.99"), FIXTURE_MODINFOS)
