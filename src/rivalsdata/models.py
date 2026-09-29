"""Attribute-accessible response models for the undocumented RivalsData API."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from .hero_ids import hero_name


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

    __slots__ = ("_data",)

    def __init__(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        self._data = dict(data or {})
        self._data.update(values)

    @property
    def raw(self) -> dict[str, Any]:
        """Return a shallow copy of the original JSON object."""
        return dict(self._data)

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
        for key in ("hero_name", "top_hero_name"):
            if key not in self._data and self[key] is not None:
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


class Player(DataModel):
    """Public player profile with lazy access to profile subresources."""

    __slots__ = ("_client",)

    def __init__(self, data: Mapping[str, Any], client: Any) -> None:
        super().__init__(data)
        object.__setattr__(self, "_client", client)

    @property
    def stats(self) -> Any:
        from .resources import PlayerStats

        return PlayerStats(self._client, int(self._data["uid"]))

    @property
    def heroes(self) -> Any:
        from .resources import PlayerHeroes

        return PlayerHeroes(self._client, int(self._data["uid"]))

    @property
    def matches(self) -> Any:
        from .resources import PlayerMatches

        return PlayerMatches(self._client, int(self._data["uid"]))

    @property
    def live_game(self) -> Any:
        """The player's current live-game resource, if they are in a match."""
        from .resources import PlayerLiveGame

        return PlayerLiveGame(self._client, self._data)

    @property
    def teammates(self) -> Any:
        from .resources import PlayerTeammates

        return PlayerTeammates(self._client, int(self._data["uid"]))

    @property
    def crosshairs(self) -> Any:
        from .resources import PlayerCrosshairs

        return PlayerCrosshairs(self._client, int(self._data["uid"]))

    @property
    def proficiency(self) -> Any:
        from .resources import PlayerProficiency

        return PlayerProficiency(self._client, int(self._data["uid"]))

    @property
    def punishments(self) -> Any:
        from .resources import PlayerPunishments

        return PlayerPunishments(self._client, int(self._data["uid"]))

    @property
    def name_history(self) -> Any:
        from .resources import PlayerNameHistory

        return PlayerNameHistory(self._client, int(self._data["uid"]))

    @property
    def win_rate(self) -> int | None:
        """Overall competitive win rate when the profile includes wins/losses."""
        direct = StatRecord(self._data).win_rate
        if direct is not None:
            return direct
        for key in ("rank_game_season", "leaderboard"):
            nested = self._data.get(key)
            if isinstance(nested, dict):
                competitive = [
                    value for account_id, value in nested.items()
                    if str(account_id).startswith("1001") and isinstance(value, dict)
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
