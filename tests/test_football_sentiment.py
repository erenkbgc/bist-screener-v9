"""Futbol duygusu: olay gunu ve mac sonucu kodlamasi."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import research_football_sentiment as fs  # noqa: E402


def test_event_day_is_next_session_strictly_after_match():
    days = pd.DatetimeIndex(["2024-03-08", "2024-03-11", "2024-03-12"])  # Cuma, Pzt, Sali
    assert days[fs.event_day(days, pd.Timestamp("2024-03-09"))] == pd.Timestamp("2024-03-11")  # Cmt mac
    assert days[fs.event_day(days, pd.Timestamp("2024-03-11"))] == pd.Timestamp("2024-03-12")  # Pzt aksam


def test_national_matches_competitive_only_and_result_from_turkey_side(tmp_path, monkeypatch):
    csv = tmp_path / "intl_results.csv"
    pd.DataFrame([
        {"date": "2016-06-12", "home_team": "Turkey", "away_team": "Croatia", "home_score": 0, "away_score": 1,
         "tournament": "UEFA Euro", "city": "", "country": "", "neutral": True},
        {"date": "2016-06-21", "home_team": "Czech Republic", "away_team": "Turkey", "home_score": 0, "away_score": 2,
         "tournament": "UEFA Euro", "city": "", "country": "", "neutral": True},
        {"date": "2016-05-29", "home_team": "Turkey", "away_team": "Montenegro", "home_score": 1, "away_score": 0,
         "tournament": "Friendly", "city": "", "country": "", "neutral": False},
    ]).to_csv(csv, index=False)
    monkeypatch.setattr(fs, "FOOTBALL", tmp_path)
    m = fs.national_matches()
    assert list(m["result"]) == ["L", "W"]


def test_club_matches_none_without_files(tmp_path, monkeypatch):
    monkeypatch.setattr(fs, "FOOTBALL", tmp_path)
    assert fs.club_matches() is None
