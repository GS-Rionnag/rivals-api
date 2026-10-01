"""Attribute-accessible response models for the undocumented RivalsData API."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, Any

from .hero_ids import hero_name

if TYPE_CHECKING:
    from .resources import (
        PlayerCrosshairs,
        PlayerHeroes,
        PlayerLiveGame,
        PlayerMatches,
        PlayerNameHistory,
        PlayerProficiency,
        PlayerPunishments,
        PlayerStats,
        PlayerTeammates,
    )


def _wrap(value: Any) -> Any:
    if isinstance(value, dict):
        return DataModel(value)
    if isinstance(value, list):
        return [_wrap(item) for item in value]
    return value


class DataModel(Mapping[str, Any]):
    """A tolerant mapping that exposes JSON keys as Python attributes.

    The API is undocumented, so the complete original payload remains
    available through :attr:`raw` and unknown upstream keys are preserved.
    """

    __slots__ = ("_data", "_raw")

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        self._data = dict(data or {})
        self._data.update(values)
        self._raw = dict(self._data)

    @property
    def raw(self) -> dict[str, Any]:
        """Return a shallow copy of the original JSON object."""
        return dict(self._raw)

    @property
    def hero_name(self) -> str | None:
        """Resolve this row's ``hero_id`` when it is a known hero."""
        return hero_name(self._data.get("hero_id"))

    @property
    def top_hero_name(self) -> str | None:
        """Resolve this row's ``top_hero_id`` when it is a known hero."""
        return hero_name(self._data.get("top_hero_id"))

    @property
    def win_rate(self) -> int | None:
        """Return an integer percentage when this object exposes win/loss data."""
        for key in ("win_rate", "winrate", "winRate"):
            if key in self._data:
                try:
                    value = float(self._data[key])
                    return round(value * 100) if 0 <= value <= 1 else int(value)
                except (TypeError, ValueError):
                    return None
        wins = self._data.get("wins", self._data.get("win_count"))
        losses = self._data.get("losses")
        if losses is None and "battle_count" in self._data:
            try:
                losses = int(self._data["battle_count"]) - int(wins)
            except (TypeError, ValueError):
                losses = None
        try:
            wins_count, losses_count = int(wins), int(losses)
            total = wins_count + losses_count
            return round(wins_count * 100 / total) if total else None
        except (TypeError, ValueError):
            return None

    def __getitem__(self, key: str) -> Any:
        if key == "hero_name" and key not in self._data:
            value = self.hero_name
            if value is not None:
                return value
        if key == "top_hero_name" and key not in self._data:
            value = self.top_hero_name
            if value is not None:
                return value
        return _wrap(self._data[key])

    def __iter__(self) -> Iterator[str]:
        keys = list(self._data)
        for key, value in (("hero_name", self.hero_name), ("top_hero_name", self.top_hero_name)):
            if key not in self._data and value is not None:
                keys.append(key)
        return iter(keys)

    def __len__(self) -> int:
        return sum(1 for _ in self)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping, including resolved hero names."""
        def convert(value: Any) -> Any:
            if isinstance(value, DataModel):
                return value.to_dict()
            if isinstance(value, list):
                return [convert(item) for item in value]
            if isinstance(value, Mapping):
                return {key: convert(item) for key, item in value.items()}
            return value

        return {key: convert(self[key]) for key in self}

    def __getattr__(self, name: str) -> Any:
        if name == "winrate":
            return self.win_rate
        if name == "hero_name":
            return self.hero_name
        if name == "top_hero_name":
            return self.top_hero_name
        try:
            return _wrap(self._data[name])
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __repr__(self) -> str:
        keys = ", ".join(self._data)
        return f"{type(self).__name__}({keys})"


class StatRecord(DataModel):
    """A stats row with a normalized integer ``win_rate`` convenience."""


class Character(StatRecord):
    """A Marvel Rivals character and its aggregate or per-player statistics."""

    hero_id: int | str
    hero_name: str | None
    name: str | None
    games: int | None
    wins: int | None
    losses: int | None
    kills: int | float | None
    deaths: int | float | None
    assists: int | float | None
    pick_rate: float | None
    ban_rate: float | None
    tier: str | None
    picks: int | None
    picks_no_mirror: int | None
    bans: int | None
    total_games: int | None
    winrate_no_mirror: float | None
    score: float | None
    assists_per_10: float | None
    blocked_per_10: float | None
    deaths_per_10: float | None
    dmg_per_10: float | None
    finals_per_10: float | None
    healing_per_10: float | None
    kills_per_10: float | None
    play_time: float | None
    bond_id: int | None
    solos: int | None
    accuracy: float | None
    crit_accuracy: float | int | None


class MatchPlayer(StatRecord):
    """A player entry participating in a match."""

    uid: int | str | None
    player_uid: str | None
    name: str | None
    side: int | str | None
    team_id: int | str | None
    hero_id: int | str | None
    hero: Character | None
    kills: int | None
    deaths: int | None
    assists: int | None
    is_mvp: bool | None
    is_svp: bool | None
    is_win: bool | None
    camp: int | None
    final_hits: int | None
    damage: int | None
    blocked: int | None
    healing: int | None
    accuracy: float | None
    top_hero_id: int | None
    rank_level: int | None
    rank_score: float | None
    score_change: int | None
    os: int | None
    ai: bool | None
    escaped: bool | None
    placement: int | None
    heroes: list[Character] | None

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        for key in ("hero", "character"):
            value = self._data.get(key)
            if isinstance(value, Mapping):
                self._data[key] = Character(value)
        heroes = self._data.get("heroes", self._data.get("top_heroes"))
        if isinstance(heroes, list):
            target = "heroes" if "heroes" in self._data else "top_heroes"
            self._data[target] = [Character(row) if isinstance(row, Mapping) else row for row in heroes]


class MatchTeam(DataModel):
    """One team's score and player entries in a match."""

    team_id: int | str | None
    side: int | str | None
    score: int | None
    camp: int | None
    is_win: bool | None
    round_score: int | None
    players: list[MatchPlayer] | dict[str, MatchPlayer]

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        players = self._data.get("players")
        if isinstance(players, list):
            self._data["players"] = [
                MatchPlayer(row) if isinstance(row, Mapping) else row for row in players
            ]
        elif isinstance(players, Mapping):
            self._data["players"] = {
                slot: MatchPlayer(row) if isinstance(row, Mapping) else row
                for slot, row in players.items()
            }


class TeamScore(DataModel):
    player: int | None
    opponent: int | None


class DraftEntry(DataModel):
    battle_side: int
    effect_battle_side: int
    hero_id: int
    is_pick: bool
    round_idx: int


class Match(DataModel):
    """A match detail record, with typed teams and player entries."""

    match_uid: str | int | None
    replay_id: str | int | None
    winner_camp: int | str | None
    duration_seconds: int | None
    map_id: int | str | None
    game_mode_id: int | str | None
    game_play_mode_id: int | str | None
    platform: int | str | None
    timestamp: int | str | None
    draft: list[DraftEntry] | dict[str, DraftEntry] | None
    teams: list[MatchTeam] | dict[str, MatchTeam] | None
    is_win: bool | None
    season: int | None
    score_change: int | None
    rank_level: int | None
    rank_score: float | None
    team_score: TeamScore | None


    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        if isinstance(self._data.get("team_score"), Mapping):
            self._data["team_score"] = TeamScore(self._data["team_score"])
        for key in ("teams", "draft"):
            value = self._data.get(key)
            if isinstance(value, list):
                cls = MatchTeam if key == "teams" else DraftEntry
                self._data[key] = [cls(row) if isinstance(row, Mapping) else row for row in value]
            elif isinstance(value, Mapping):
                cls = MatchTeam if key == "teams" else DraftEntry
                self._data[key] = {
                    name: cls(row) if isinstance(row, Mapping) else row
                    for name, row in value.items()
                }


class MatchHistory(DataModel):
    """A paginated match-history response containing typed match rows."""

    matches: list[Match]
    next_cursor: str | None
    source: str | None

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        rows = self._data.get("matches")
        if isinstance(rows, list):
            self._data["matches"] = [Match(row) if isinstance(row, Mapping) else row for row in rows]


# Endpoint-specific public API records. Unknown keys stay accessible through
# DataModel, while these annotations describe every field observed so far.
class PlayerSummary(StatRecord):
    uid: int | str | None
    name: str | None
    icon: str | int | None
    wins: int | None
    losses: int | None
    status: str | PlayerStatus | None
    rank_score: int | float | None
    rank_level: int | str | None
    heroes: list[int | Character] | None
    os: int | None
    position: int | None
    season: int | None

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        if isinstance(self._data.get("status"), Mapping):
            self._data["status"] = PlayerStatus(self._data["status"])
        if isinstance(self._data.get("heroes"), list):
            self._data["heroes"] = [Character(row) if isinstance(row, Mapping) else row for row in self._data["heroes"]]


class LeaderboardPlayer(PlayerSummary):
    """A ranked player from the global leaderboard."""


class LeaderboardResponse(DataModel):
    count: int | None
    players: list[LeaderboardPlayer]
    updated_at: str | int | None

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        if isinstance(self._data.get("players"), list):
            self._data["players"] = [LeaderboardPlayer(row) if isinstance(row, Mapping) else row for row in self._data["players"]]


class TierListResponse(DataModel):
    last_update: int | None
    heroes: list[Character]

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        if isinstance(self._data.get("heroes"), list):
            self._data["heroes"] = [Character(row) if isinstance(row, Mapping) else row for row in self._data["heroes"]]


class CombatAverages(DataModel):
    assists: float | None
    damage: float | None
    damage_blocked: float | None
    deaths: float | None
    finals: float | None
    healing: float | None
    kills: float | None
    solo_kills: float | None


class HeroModeStats(StatRecord):
    accuracy: float | None
    bonds: list[DataModel]
    games: int | None
    kda: float | None
    losses: int | None
    mvps: int | None
    per_10: CombatAverages | None
    per_game: CombatAverages | None
    svps: int | None
    wins: int | None
    winrate: float | int | None

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        for key in ("per_10", "per_game"):
            if isinstance(self._data.get(key), Mapping):
                self._data[key] = CombatAverages(self._data[key])


class HeroStatsRecord(Character):
    """Detailed hero stats including the source's leaderboard position.

    ``rank`` is the number shown as #N in the profile's left-hand hero card.
    It is shared source metadata, not a rank calculated for the selected mode.
    None means the source did not supply a position.
    """

    mode: str | None
    competitive: HeroModeStats | None
    quickplay: HeroModeStats | None
    rank: int | str | None

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        self._data.setdefault("rank", None)
        for key in ("competitive", "quickplay"):
            if isinstance(self._data.get(key), Mapping):
                self._data[key] = HeroModeStats(self._data[key])


class ClassModeStats(HeroModeStats):
    """Calculated mode totals whose win rate is always a percentage."""

    @property
    def win_rate(self) -> int | None:
        # Upstream win-rate fields can be fractions or percentages. Derived
        # rates use counts so that a calculated 1% is not interpreted as 100%.
        wins, losses = self._data["wins"], self._data["losses"]
        total = wins + losses
        return round(wins * 100 / total) if total else None


class ClassStatsRecord(DataModel):
    """Calculated hero participation totals for one player class."""

    player_class: str
    role: str
    hero_ids: list[int | str]
    competitive: ClassModeStats
    quickplay: ClassModeStats

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        for key in ("competitive", "quickplay"):
            if isinstance(self._data.get(key), Mapping):
                self._data[key] = ClassModeStats(self._data[key])


class ClassStatsResponse(DataModel):
    """Derived class totals, excluded rows, and calculation metadata."""

    classes: list[ClassStatsRecord]
    excluded: list[DataModel]
    metadata: DataModel

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        self._data["classes"] = [
            ClassStatsRecord(row) for row in self._data.get("classes", [])
        ]


class HeroDetail(DataModel):
    hero: Character | None
    stats: Character | None
    last_update: int | None
    season: int | None

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        for key in ("hero", "stats"):
            if isinstance(self._data.get(key), Mapping):
                self._data[key] = Character(self._data[key])


class HeroMetaPoint(DataModel):
    ban_rate: float | None
    games: int | None
    pick_rate: float | None
    ts: int | None
    winrate_no_mirror: float | None


class HeroMeta(DataModel):
    hero_id: int | str | None
    last_update: int | None
    points: list[HeroMetaPoint]
    range: str | None
    window_days: int | None

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        if isinstance(self._data.get("points"), list):
            self._data["points"] = [HeroMetaPoint(row) if isinstance(row, Mapping) else row for row in self._data["points"]]


class TeamUpRecord(StatRecord):
    heroes: list[Character] | None
    hero_ids: list[int | str] | None
    games: int | None
    wins: int | None
    losses: int | None
    bond_id: int | None
    nm_winrate: float | None
    pickrate: float | None


class TeamUpsResponse(DataModel):
    last_update: int | None
    heroes: dict[str, dict[str, TeamUpRecord]]

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        heroes = self._data.get("heroes")
        if isinstance(heroes, Mapping):
            self._data["heroes"] = {
                hero: {
                    slot: TeamUpRecord(row) if isinstance(row, Mapping) else row
                    for slot, row in slots.items()
                } if isinstance(slots, Mapping) else slots
                for hero, slots in heroes.items()
            }


class HeroLeaderboardPlayer(PlayerSummary):
    assists: int | None
    avg_placement: float | None
    deaths: float | None
    games: int | None
    kills: float | None
    score: float | None


class HeroLeaderboardResponse(DataModel):
    last_update: int | None
    players: list[HeroLeaderboardPlayer]

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        if isinstance(self._data.get("players"), list):
            self._data["players"] = [HeroLeaderboardPlayer(row) if isinstance(row, Mapping) else row for row in self._data["players"]]


class PunishmentRecord(DataModel):
    uid: int | str | None
    name: str | None
    kind: str | None
    reason: str | int | None
    issued_at: str | int | None
    expires_at: str | int | None
    rank: int | str | None
    icon: int | str | None
    peak_rank_level: int | None
    peak_rank_score: float | None


class XPRecord(DataModel):
    uid: int | str | None
    name: str | None
    icon: str | int | None
    rank: int | None
    xp: int | None


class InsightPage(DataModel):
    last_update: str | int | None
    next: str | None
    results: list[DataModel]


class PunishmentsPage(InsightPage):
    results: list[PunishmentRecord]

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        self._data["results"] = [PunishmentRecord(row) if isinstance(row, Mapping) else row for row in self._data.get("results", [])]


class XPPage(InsightPage):
    results: list[XPRecord]

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        self._data["results"] = [XPRecord(row) if isinstance(row, Mapping) else row for row in self._data.get("results", [])]


class Top500Season(DataModel):
    season: int | None
    placement: int | None
    score: float | None


class Top500Player(PlayerSummary):
    avg_placement: float | None
    avg_score: float | None
    finishes: int | None
    seasons: list[Top500Season] | None

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        if isinstance(self._data.get("seasons"), list):
            self._data["seasons"] = [Top500Season(row) if isinstance(row, Mapping) else row for row in self._data["seasons"]]


class Top500Response(DataModel):
    count: int | None
    last_update: str | int | None
    os: int | str | None
    players: list[Top500Player]

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        self._data["players"] = [Top500Player(row) if isinstance(row, Mapping) else row for row in self._data.get("players", [])]


class HeroInsightRecord(Character):
    pct: float | None
    ci95: float | None
    vs_avg: float | None
    games: int | None
    players: int | None
    leaves: int | None
    weighted_banned: float | None
    weighted_players: float | None
    qualifying_players: int | None
    leaves_per_player: float | None


class HeroInsights(DataModel):
    heroes: list[HeroInsightRecord]
    last_update: str | int | None
    mode: str | None
    overall_pct: float | None

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        self._data["heroes"] = [HeroInsightRecord(row) if isinstance(row, Mapping) else row for row in self._data.get("heroes", [])]


class CommBanHero(HeroInsightRecord):
    qualifying_players: int | None
    weighted_banned: float | None
    weighted_players: float | None


class LeaverHero(HeroInsightRecord):
    games: int | None
    leaves: int | None
    leaves_per_player: float | None
    players: int | None


class CommBanInsights(HeroInsights):
    heroes: list[CommBanHero]

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        DataModel.__init__(self, data, **values)
        self._data["heroes"] = [CommBanHero(row) if isinstance(row, Mapping) else row for row in self._data.get("heroes", [])]


class LeaverInsights(HeroInsights):
    heroes: list[LeaverHero]

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        DataModel.__init__(self, data, **values)
        self._data["heroes"] = [LeaverHero(row) if isinstance(row, Mapping) else row for row in self._data.get("heroes", [])]


class Teammate(StatRecord):
    teammate_uid: int | str | None
    name: str | None
    icon: str | None
    games: int | None
    wins: int | None
    losses: int | None


class CrosshairRecord(DataModel):
    crosshair: str | dict[str, Any] | None
    uses: int | None


class HeroProficiency(DataModel):
    proficiency_level: int
    proficiency_point: int


class Proficiency(DataModel):
    hero_proficiency_infos: dict[str, HeroProficiency]

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        infos = self._data.get("hero_proficiency_infos")
        if isinstance(infos, Mapping):
            self._data["hero_proficiency_infos"] = {
                hero: HeroProficiency(row) if isinstance(row, Mapping) else row
                for hero, row in infos.items()
            }


class ProficiencyResponse(DataModel):
    accounts: dict[str, Proficiency]

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        self._data = {key: Proficiency(value) if isinstance(value, Mapping) else value for key, value in self._data.items()}

    @property
    def accounts(self) -> dict[str, Proficiency]:
        return dict(self._data)


class PlayerSearchResult(DataModel):
    uid: int
    aid: str | None
    name: str | None
    icon: str | None


class PlayerStatus(DataModel):
    battle_id: str | int | None
    status: str | None
    is_online: bool | None


class RankRecord(StatRecord):
    rank_game_id: int | str | None
    rank_score: int | float | None
    rank_level: int | str | None
    battle_count: int | None
    win_count: int | None
    losses: int | None
    diff_score: float | int | None
    level: int | None
    max_level: int | None
    max_rank_score: float | int | None
    protect_score: int | None
    update_time: int | None
    fixed_battle_count: int | None
    fixed_finished: int | None
    season_max_level: int | None


class PunishmentEntry(DataModel):
    expire: str | None
    name: str | None
    reason: str | None
    time: str | None
    uid: str | None


class PlayerPunishments(DataModel):
    chat: PunishmentEntry | None
    login: PunishmentEntry | None
    rank: PunishmentEntry | None

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        for key in ("chat", "login", "rank"):
            if isinstance(self._data.get(key), Mapping):
                self._data[key] = PunishmentEntry(self._data[key])


class NameHistoryRecord(DataModel):
    first_seen: str | int | None
    name: str | None


class MapModeStats(StatRecord):
    games: int
    losses: int
    winrate: float | int
    wins: int


class MapRecord(StatRecord):
    map: str
    competitive: MapModeStats | None
    quickplay: MapModeStats | None

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        for key in ("competitive", "quickplay"):
            if isinstance(self._data.get(key), Mapping):
                self._data[key] = MapModeStats(self._data[key])


class BanRecord(StatRecord):
    hero_id: int
    losses: int
    matches: int
    winrate: float | int
    wins: int


class LiveGamePlayer(MatchPlayer):
    games: int | None
    icon: int | str | None
    losses: int | None
    proficiency: DataModel | None
    rank: int | str | None
    top_heroes: list[Character] | None
    wins: int | None


class LiveGame(DataModel):
    players: dict[str, LiveGamePlayer] | list[LiveGamePlayer]
    team_avg_rank: dict[str, int | float]

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        players = self._data.get("players")
        if isinstance(players, Mapping):
            self._data["players"] = {key: LiveGamePlayer(row) if isinstance(row, Mapping) else row for key, row in players.items()}
        elif isinstance(players, list):
            self._data["players"] = [LiveGamePlayer(row) if isinstance(row, Mapping) else row for row in players]


class FactionRank(StatRecord):
    battle_count: int | None
    level: int | None
    rank_score: float | None
    season: int | None
    unranked: bool | None
    win_count: int | None


class FactionConfig(DataModel):
    cur_head_icon_id: int | str | None
    rank_game: FactionRank | None

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        if isinstance(self._data.get("rank_game"), Mapping):
            self._data["rank_game"] = FactionRank(self._data["rank_game"])


class FactionGame(DataModel):
    last_online_time: int | None


class FactionMember(DataModel):
    aid: str | None
    config_server: FactionConfig | None
    games: dict[str, FactionGame] | None
    name: str | None
    status: PlayerStatus | None

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        if isinstance(self._data.get("status"), Mapping):
            self._data["status"] = PlayerStatus(self._data["status"])
        if isinstance(self._data.get("config_server"), Mapping):
            self._data["config_server"] = FactionConfig(self._data["config_server"])
        games = self._data.get("games")
        if isinstance(games, Mapping):
            self._data["games"] = {key: FactionGame(row) if isinstance(row, Mapping) else row for key, row in games.items()}


class FavoritePlayer(FactionMember):
    """A profile summary returned by the favorites lookup."""


class FactionResult(DataModel):
    finished_at: int | None
    id: str | None
    mrc_season: int | None
    name: str | None
    placement: int | None


class FactionSummary(DataModel):
    id: str | int | None
    name: str | None
    type: str | int | None


class Faction(DataModel):
    id: int | str | None
    name: str | None
    description: str | None
    members: list[FactionMember]
    captain: str | int | None
    region: str | None
    results: list[FactionResult]
    tag: str | None
    type: int | str | None

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        if isinstance(self._data.get("members"), list):
            self._data["members"] = [FactionMember(row) if isinstance(row, Mapping) else row for row in self._data["members"]]
        if isinstance(self._data.get("results"), list):
            self._data["results"] = [FactionResult(row) if isinstance(row, Mapping) else row for row in self._data["results"]]


class ProfileCard(DataModel):
    uid: int | str | None
    updated_at: int | None
    leaderboard_social: DataModel | None
    socials: dict[str, DataModel | str] | None


class FavoritesResponse(DataModel):
    players: list[FavoritePlayer]

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        super().__init__(data, **values)
        if isinstance(self._data.get("players"), list):
            self._data["players"] = [FavoritePlayer(row) if isinstance(row, Mapping) else row for row in self._data["players"]]


class Player(DataModel):
    """Public player profile with lazy access to profile subresources."""

    uid: int | str
    name: str | None
    level: int | None
    xp: int | None
    icon: str | None
    faction: FactionSummary | None
    claimed: bool | None
    last_seen: int | str | None
    login_os: int | str | None
    status: PlayerStatus | None
    rank_game_season: dict[str, RankRecord] | None
    leaderboard: dict[str, RankRecord] | None
    match_history_is_visible: int | bool | None

    __slots__ = ("_client",)

    def __init__(self, data: Mapping[str, Any], client: Any) -> None:
        super().__init__(data)
        object.__setattr__(self, "_client", client)
        faction = self._data.get("faction")
        if isinstance(faction, Mapping):
            self._data["faction"] = FactionSummary(faction)
        status = self._data.get("status")
        if isinstance(status, Mapping):
            self._data["status"] = PlayerStatus(status)
        for key in ("rank_game_season", "leaderboard"):
            nested = self._data.get(key)
            if isinstance(nested, Mapping):
                self._data[key] = {
                    account: RankRecord(row) if isinstance(row, Mapping) else row
                    for account, row in nested.items()
                }

    @property
    def stats(self) -> PlayerStats:
        from .resources import PlayerStats

        return PlayerStats(self._client, int(self._data["uid"]))

    @property
    def heroes(self) -> PlayerHeroes:
        from .resources import PlayerHeroes

        return PlayerHeroes(self._client, int(self._data["uid"]))

    @property
    def matches(self) -> PlayerMatches:
        from .resources import PlayerMatches

        return PlayerMatches(self._client, int(self._data["uid"]))

    @property
    def live_game(self) -> PlayerLiveGame:
        """The player's current live-game resource, if they are in a match."""
        from .resources import PlayerLiveGame

        return PlayerLiveGame(self._client, self._data)

    @property
    def teammates(self) -> PlayerTeammates:
        from .resources import PlayerTeammates

        return PlayerTeammates(self._client, int(self._data["uid"]))

    @property
    def crosshairs(self) -> PlayerCrosshairs:
        from .resources import PlayerCrosshairs

        return PlayerCrosshairs(self._client, int(self._data["uid"]))

    @property
    def proficiency(self) -> PlayerProficiency:
        from .resources import PlayerProficiency

        return PlayerProficiency(self._client, int(self._data["uid"]))

    @property
    def punishments(self) -> PlayerPunishments:
        from .resources import PlayerPunishments

        return PlayerPunishments(self._client, int(self._data["uid"]))

    @property
    def name_history(self) -> PlayerNameHistory:
        from .resources import PlayerNameHistory

        return PlayerNameHistory(self._client, int(self._data["uid"]))

    @property
    def win_rate(self) -> int | None:
        """Current-season competitive win rate when profile counts are available.

        Uses a direct source rate or the latest available competitive season
        with usable counts. This property does not aggregate across seasons.
        """
        direct = StatRecord(self._data).win_rate
        if direct is not None:
            return direct
        for key in ("rank_game_season", "leaderboard"):
            nested = self._data.get(key)
            if isinstance(nested, Mapping):
                competitive = [
                    value for account_id, value in nested.items()
                    if str(account_id).startswith("1001") and isinstance(value, Mapping)
                ]
                competitive.sort(
                    key=lambda row: int(row.get("rank_game_id", 0)), reverse=True
                )
                for row in competitive:
                    rate = StatRecord(row).win_rate
                    if rate is not None:
                        return rate
                rate = StatRecord(nested).win_rate
                if rate is not None:
                    return rate
        return None
