"""Build deterministic team-season summary documents from raw NHL CSVs."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from statistics import mean

from app.utils.team_names import normalize_team_name, slugify_team_name

# ---------- Matchup key helper ----------

def _matchup_key(team_a: str, team_b: str) -> tuple[str, str]:
    """Return team pair in alphabetical order for consistent matchup grouping."""
    return (team_a, team_b) if team_a < team_b else (team_b, team_a)


# ---------- Dataclasses ----------

@dataclass(slots=True)
class GameRecord:
    season_id: str
    date: date
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    status: str


@dataclass(slots=True)
class TeamGame:
    season_id: str
    date: date
    team: str
    opponent: str
    is_home: bool
    goals_for: int
    goals_against: int
    status: str
    rest_days: int | None = None
    back_to_back: bool = False


def derive_season_id(path: Path) -> str:
    """Extract season id from filename: nhl-202324-asplayed.csv -> 2023-24."""
    stem = path.stem  # e.g. "nhl-202324-asplayed"
    token = stem.split("-")[1]  # e.g. "202324"
    return f"{token[:4]}-{token[4:]}"


def load_games(path: Path) -> list[GameRecord]:
    """Parse a single season CSV into normalized GameRecords."""
    season_id = derive_season_id(path)
    games: list[GameRecord] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        next(reader, None)  # skip header
        for row in reader:
            if len(row) < 8:
                continue
            # Skip future/unplayed games (empty score fields)
            if not row[4].strip() or not row[6].strip():
                continue
            # Columns: 0=Date, 3=Visitor, 4=VisitorScore, 5=Home, 6=HomeScore, 7=Status
            games.append(
                GameRecord(
                    season_id=season_id,
                    date=date.fromisoformat(row[0]),
                    away_team=normalize_team_name(row[3]),
                    away_goals=int(row[4]),
                    home_team=normalize_team_name(row[5]),
                    home_goals=int(row[6]),
                    status=row[7].strip() or "Unknown",
                )
            )
    return games


def team_games_for_season(
    games: list[GameRecord],
) -> dict[tuple[str, str], list[TeamGame]]:
    """Expand game records into per-team game lists and compute rest/b2b."""
    by_team: dict[tuple[str, str], list[TeamGame]] = defaultdict(list)
    for game in games:
        by_team[(game.season_id, game.home_team)].append(
            TeamGame(
                season_id=game.season_id,
                date=game.date,
                team=game.home_team,
                opponent=game.away_team,
                is_home=True,
                goals_for=game.home_goals,
                goals_against=game.away_goals,
                status=game.status,
            )
        )
        by_team[(game.season_id, game.away_team)].append(
            TeamGame(
                season_id=game.season_id,
                date=game.date,
                team=game.away_team,
                opponent=game.home_team,
                is_home=False,
                goals_for=game.away_goals,
                goals_against=game.home_goals,
                status=game.status,
            )
        )

    # Compute rest days and back-to-back per team-season
    for entries in by_team.values():
        entries.sort(key=lambda item: item.date)
        previous_date: date | None = None
        for entry in entries:
            if previous_date is None:
                entry.rest_days = None
                entry.back_to_back = False
            else:
                entry.rest_days = (entry.date - previous_date).days
                entry.back_to_back = entry.rest_days == 1
            previous_date = entry.date
    return by_team


def _win_pct(games: list[TeamGame]) -> float:
    if not games:
        return 0.0
    wins = sum(1 for g in games if g.goals_for > g.goals_against)
    return wins / len(games)


def _avg(values: list[int | float]) -> float:
    if not values:
        return 0.0
    return float(mean(values))


@dataclass(slots=True)
class MatchupGame:
    """A single game viewed from the matchup (team_a vs team_b, alphabetical)."""
    team_a: str
    team_b: str
    team_a_goals: int
    team_b_goals: int
    team_a_home: bool
    status: str
    date: date
    season_id: str


def build_matchup_index(
    games: list[GameRecord],
) -> dict[tuple[str, str, str], list[MatchupGame]]:
    """Group all GameRecords into per-matchup-per-season lists.

    Key: (season_id, team_a, team_b) with team_a < team_b alphabetically.
    """
    index: dict[tuple[str, str, str], list[MatchupGame]] = defaultdict(list)
    for g in games:
        a, b = _matchup_key(g.home_team, g.away_team)
        if a == g.home_team:
            mg = MatchupGame(
                team_a=a, team_b=b,
                team_a_goals=g.home_goals, team_b_goals=g.away_goals,
                team_a_home=True, status=g.status,
                date=g.date, season_id=g.season_id,
            )
        else:
            mg = MatchupGame(
                team_a=a, team_b=b,
                team_a_goals=g.away_goals, team_b_goals=g.home_goals,
                team_a_home=False, status=g.status,
                date=g.date, season_id=g.season_id,
            )
        index[(g.season_id, a, b)].append(mg)
    # Sort each list by date
    for matchups in index.values():
        matchups.sort(key=lambda m: m.date)
    return index


def _build_h2h_doc(
    team_a: str,
    team_b: str,
    season_id: str,
    matchups: list[MatchupGame],
    doc_type: str,
) -> dict[str, object]:
    """Build a single head-to-head summary document."""
    a_wins = sum(1 for m in matchups if m.team_a_goals > m.team_b_goals)
    b_wins = sum(1 for m in matchups if m.team_b_goals > m.team_a_goals)
    a_gf = sum(m.team_a_goals for m in matchups)
    b_gf = sum(m.team_b_goals for m in matchups)
    a_home = [m for m in matchups if m.team_a_home]
    b_home = [m for m in matchups if not m.team_a_home]
    a_home_wins = sum(1 for m in a_home if m.team_a_goals > m.team_b_goals)
    b_home_wins = sum(1 for m in b_home if m.team_b_goals > m.team_a_goals)
    ot_so = sum(1 for m in matchups if m.status not in ("Final", "Unknown", ""))

    slug_a = slugify_team_name(team_a)
    slug_b = slugify_team_name(team_b)

    label = "season" if doc_type == "h2h_season" else "recent (last 8 meetings)"
    text = (
        f"{team_a} vs {team_b} {season_id} head-to-head {label} summary. "
        f"Games: {len(matchups)}. "
        f"{team_a} wins: {a_wins}. {team_b} wins: {b_wins}. "
        f"{team_a} goals for: {a_gf}. {team_b} goals for: {b_gf}. "
        f"{team_a} home games: {len(a_home)} (wins: {a_home_wins}). "
        f"{team_b} home games: {len(b_home)} (wins: {b_home_wins}). "
        f"OT/SO games: {ot_so}. "
        f"Date range: {matchups[0].date.isoformat()} to {matchups[-1].date.isoformat()}."
    )
    return {
        "id": f"{season_id}:{slug_a}-vs-{slug_b}:{doc_type}",
        "text": text,
        "metadata": {
            "teams": [team_a, team_b],
            "season_id": season_id,
            "doc_type": doc_type,
            "date_range": f"{matchups[0].date.isoformat()} to {matchups[-1].date.isoformat()}",
            "created_at": date.today().isoformat(),
            "game_count": len(matchups),
        },
    }


def _build_doc(
    team: str,
    season_id: str,
    games: list[TeamGame],
    doc_type: str,
    window: int | None = None,
) -> dict[str, object]:
    sample = games[-window:] if window else games
    label = "season" if window is None else f"last {window}"
    home_games = [g for g in sample if g.is_home]
    away_games = [g for g in sample if not g.is_home]
    rest_values = [g.rest_days for g in sample if g.rest_days is not None]
    b2b_rate = (
        sum(1 for g in sample if g.back_to_back) / len(sample) if sample else 0.0
    )
    text = (
        f"{team} {season_id} {label} summary. "
        f"Games: {len(sample)}. Win rate: {_win_pct(sample):.3f}. "
        f"Goals for per game: {_avg([g.goals_for for g in sample]):.2f}. "
        f"Goals against per game: {_avg([g.goals_against for g in sample]):.2f}. "
        f"Home win rate: {_win_pct(home_games):.3f}. "
        f"Away win rate: {_win_pct(away_games):.3f}. "
        f"Average rest days: {_avg(rest_values):.2f}. "
        f"Back-to-back rate: {b2b_rate:.3f}. "
        f"Date range: {sample[0].date.isoformat()} to {sample[-1].date.isoformat()}."
    )
    return {
        "id": f"{season_id}:{slugify_team_name(team)}:{doc_type}",
        "text": text,
        "metadata": {
            "team": team,
            "season_id": season_id,
            "doc_type": doc_type,
            "date_range": f"{sample[0].date.isoformat()} to {sample[-1].date.isoformat()}",
            "created_at": date.today().isoformat(),
            "game_count": len(sample),
        },
    }


def validation_logs(
    by_team: dict[tuple[str, str], list[TeamGame]],
    season_totals: dict[str, int],
) -> list[str]:
    """Generate validation log lines for sanity checking."""
    logs: list[str] = []
    for season_id, total_games in sorted(season_totals.items()):
        logs.append(f"{season_id}: total_games={total_games}")
    b2b_rates: list[float] = []
    for (season_id, team), games in sorted(by_team.items()):
        if len(games) > 100:
            logs.append(
                f"warning: {season_id} {team} has suspicious game_count={len(games)}"
            )
        b2b_rate = sum(1 for g in games if g.back_to_back) / len(games)
        b2b_rates.append(b2b_rate)
    if b2b_rates:
        logs.append(
            f"back_to_back_rate_distribution="
            f"min={min(b2b_rates):.3f},avg={_avg(b2b_rates):.3f},max={max(b2b_rates):.3f}"
        )
    return logs


def build_documents(
    raw_data_dir: Path,
) -> tuple[list[dict[str, object]], list[str]]:
    """Build all summary docs from raw CSVs. Returns (docs, validation_logs)."""
    all_games: list[GameRecord] = []
    season_totals: dict[str, int] = {}
    for path in sorted(raw_data_dir.glob("nhl-*-asplayed.csv")):
        games = load_games(path)
        all_games.extend(games)
        season_totals[derive_season_id(path)] = len(games)

    by_team = team_games_for_season(all_games)
    docs: list[dict[str, object]] = []
    for (season_id, team), games in sorted(by_team.items()):
        docs.append(_build_doc(team, season_id, games, "team_season_summary"))
        docs.append(
            _build_doc(
                team,
                season_id,
                games,
                "team_form_summary_last10",
                window=min(10, len(games)),
            )
        )
        docs.append(
            _build_doc(
                team,
                season_id,
                games,
                "team_form_summary_last20",
                window=min(20, len(games)),
            )
        )

    # --- H2H matchup docs ---
    matchup_index = build_matchup_index(all_games)

    # h2h_season: one doc per matchup per season
    for (season_id, team_a, team_b), matchups in sorted(matchup_index.items()):
        docs.append(_build_h2h_doc(team_a, team_b, season_id, matchups, "h2h_season"))

    # h2h_recent: last 8 meetings across all seasons per unique pair
    cross_season: dict[tuple[str, str], list[MatchupGame]] = defaultdict(list)
    for (_sid, team_a, team_b), matchups in matchup_index.items():
        cross_season[(team_a, team_b)].extend(matchups)
    for (team_a, team_b), all_matchups in sorted(cross_season.items()):
        all_matchups.sort(key=lambda m: m.date)
        recent = all_matchups[-8:]
        docs.append(_build_h2h_doc(team_a, team_b, "all", recent, "h2h_recent"))

    return docs, validation_logs(by_team, season_totals)


def chunk_documents(
    docs: list[dict[str, object]],
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[dict[str, object]]:
    """Split documents that exceed chunk_size using RecursiveCharacterTextSplitter.

    Short documents pass through unchanged. Long documents are split into
    multiple chunks with metadata propagated and chunk index appended to the ID.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunked: list[dict[str, object]] = []
    for doc in docs:
        chunks = splitter.split_text(doc["text"])
        if len(chunks) == 1:
            chunked.append(doc)
        else:
            for i, chunk_text in enumerate(chunks):
                chunked.append({
                    "id": f"{doc['id']}_chunk_{i}",
                    "text": chunk_text,
                    "metadata": {
                        **doc["metadata"],
                        "chunk_index": i,
                        "parent_doc_id": doc["id"],
                    },
                })
    return chunked


def write_documents(output_path: Path, docs: list[dict[str, object]]) -> None:
    """Write docs to JSONL file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for doc in docs:
            handle.write(json.dumps(doc) + "\n")
