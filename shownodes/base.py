from argparse import Namespace
from typing import Any

# Foundation global object, shared across modules
_global = Namespace()


DAYS_PER_MONTH = 30.4375


def as_int(value):
    return int(value) if value else 0


def float_maybe(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def divide_maybe(numerator, denominator: float | int | None) -> float | int | None:
    try:
        return numerator / denominator
    except Exception:
        return None
