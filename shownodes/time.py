"""
Utility and formatting functions relating to time and duration.
"""

import datetime as dt

import arrow

from .base import _global

_global.NOW = arrow.get()  # reference time for program run


def human_duration(ts: str, now: arrow.Arrow | None = None):
    """
    Python translation of Kubernetes `HumanDuration` function, plus a little
    shim code. For original, see e.g.:
    https://github.com/kubernetes/kubernetes/blob/master/staging/src/k8s.io/apimachinery/pkg/util/duration/duration.go

    HumanDuration returns a succinct representation of the provided duration
    with limited precision for consumption by humans. It provides ~2-3 significant
    figures of duration.
    """
    now = now or _global.NOW
    d = now - arrow.get(ts)

    if d.total_seconds() < -1:
        return "<invalid>"
    elif d.total_seconds() < 0:
        return "0s"
    elif d.total_seconds() < 60 * 2:
        return f"{int(d.total_seconds())}s"

    minutes = int(d.total_seconds() // 60)
    if minutes < 10:
        s = int(d.total_seconds()) % 60
        if s == 0:
            return f"{minutes}m"
        return f"{minutes}m{s}s"
    elif minutes < 60 * 3:
        return f"{minutes}m"

    hours = int(d.total_seconds() // 3600)
    if hours < 8:
        m = int(d.total_seconds() // 60) % 60
        if m == 0:
            return f"{hours}h"
        return f"{hours}h{m}m"
    elif hours < 48:
        return f"{hours}h"
    elif hours < 24 * 8:
        h = hours % 24
        if h == 0:
            return f"{hours // 24}d"
        return f"{hours // 24}d{h}h"
    elif hours < 24 * 365 * 2:
        return f"{hours // 24}d"
    elif hours < 24 * 365 * 8:
        dy = int(hours // 24) % 365
        if dy == 0:
            return f"{hours // 24 // 365}y"
        return f"{hours // 24 // 365}y{dy}d"

    return f"{int(hours // 24 // 365)}y"


def timestamp_to_age(ts: str, now: arrow.Arrow | None = None) -> str:
    """
    Given a timestamp in a format the `arrow` module can parse, return a much
    shorter age string indicating the approximate number of days, hours, minutes,
    or seconds the timestamp differs from the current moment. The current moment
    may be passed as a parameter. Otherwise the global moment `NOW` is assumed.
    """
    now = now or _global.NOW
    ago = now - arrow.get(ts)
    duration = {"d": 3600 * 24, "h": 3600, "m": 60, "s": 1}
    remaining = int(round(ago.total_seconds()))
    for abbrev, seconds in duration.items():
        quantity, remaining = divmod(remaining, seconds)
        if quantity:
            if remaining > seconds / 2:
                quantity += 1
            return f"{quantity}{abbrev}"
    return "0s"


def zulutime(ts: dt.datetime) -> str:
    """
    Given a datetime object, return a string in ISO 8601 format with the compact
    'Z' (Zulu) suffix.
    """
    return ts.isoformat().replace("+00:00", "Z")


def format_age(ts: str, mode: str | None = None) -> str:
    """
    Format a timestamp as a human-readable age string.
    """
    if mode and "," in mode:
        modes = mode.split(",")
        return " ".join(format_age(ts, m) for m in modes)
    mode = mode.lower()
    match mode:
        case "age":
            return timestamp_to_age(ts)
        case "k8s":
            return human_duration(ts)
        case "iso":
            return zulutime(arrow.get(ts))
        case "unix" | "epoch":
            return str(int(arrow.get(ts).timestamp()))
        case _:
            tz_abbreviations = {
                "edt": "US/Eastern",
                "est": "US/Eastern",
                "pdt": "US/Pacific",
                "pst": "US/Pacific",
                "cdt": "US/Central",
                "cst": "US/Central",
                "mdt": "US/Mountain",
                "mst": "US/Mountain",
                "zulu": "UTC",
                "gmt": "UTC",
            }
            tzname = tz_abbreviations.get(mode, mode)
            try:
                return arrow.get(ts).to(tzname).format("YYYY-MM-DD HH:mm:ss ZZZ")
            except Exception:
                return timestamp_to_age(ts)
