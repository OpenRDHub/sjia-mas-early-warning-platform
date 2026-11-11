import json
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LabPoint:
    date: str
    code: str
    value: float
    ref_low: "float | None"
    ref_high: "float | None"


@dataclass(frozen=True)
class Checkin:
    date: str
    temp: "float | None"
    symptoms: dict


class TimeSeriesProvider(ABC):
    """Read-only by design: no write methods exist on this interface."""

    @abstractmethod
    def get_lab_series(self, pid, code, until=None) -> list[LabPoint]: ...

    @abstractmethod
    def get_checkins(self, pid, until=None) -> list[Checkin]: ...

    @abstractmethod
    def codes(self, pid) -> list[str]: ...


class SqliteTimeSeries(TimeSeriesProvider):
    def __init__(self, store):
        self._store = store

    def get_lab_series(self, pid, code, until=None):
        sql = ("SELECT date, code, value, ref_low, ref_high "
               "FROM lab WHERE pid=? AND code=?")
        params: list = [pid, code]
        if until:
            sql += " AND date<=?"
            params.append(until)
        sql += " ORDER BY date"
        return [LabPoint(*r) for r in self._store.rows(sql, tuple(params))]

    def get_checkins(self, pid, until=None):
        sql = "SELECT date, temp, symptoms FROM checkin WHERE pid=?"
        params: list = [pid]
        if until:
            sql += " AND date<=?"
            params.append(until)
        sql += " ORDER BY date"
        return [Checkin(d, t, json.loads(s))
                for d, t, s in self._store.rows(sql, tuple(params))]

    def codes(self, pid):
        return [r[0] for r in self._store.rows(
            "SELECT DISTINCT code FROM lab WHERE pid=? ORDER BY code", (pid,))]
