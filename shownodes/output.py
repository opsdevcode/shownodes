"""
Output objects that format values before output.
"""

from collections.abc import Sequence
from enum import Enum
from functools import total_ordering
from typing import Any, Callable


def is_non_string_sequence(obj):
    return isinstance(obj, Sequence) and not isinstance(obj, str)


FormatSpec = str | Callable | None
ErrorMode = Enum("ErrorMode", ["silent", "loud"])
function = type(lambda x: x)


class literal(str):
    pass


@total_ordering
class Output:
    def __init__(
        self,
        value: Any,
        format: FormatSpec = None,
        errors: ErrorMode = ErrorMode.silent,
    ) -> None:
        self._value = value
        self._format = format
        self._errors = errors

    def __str__(self):
        """
        The main show. Stringify the receiver according to the format specification
        given. If no format specification, call `str`. If a Python format specification
        starting with a single `{`, format value according to that spec. If another
        string, consider it a static string representation. If a callable, process the
        value though it.
        """
        try:
            match self._format:
                case None:
                    return str(self._value)
                case literal():
                    return self._format
                case str():
                    return f"{self._value:{self._format}}"
                case function():
                    return str(self._format(self._value))
                case _:
                    return str(self._value)
        except Exception as e:
            match self._errors:
                case ErrorMode.silent:
                    return ""
                case _:
                    raise (e)

    def __repr__(self):
        classname = self.__class__.__name__
        format = f", {self._format!r}" if self._format is not None else ""
        return f"{classname}({self._value!r}{format})"

    def __format__(self, format_spec):
        return f"{self._value:{format_spec}}"

    def __eq__(self, other: object) -> bool:
        other_value = other._value if isinstance(other, Output) else other
        return self._value == other_value

    def __gt__(self, other: object) -> bool:
        other_value = other._value if isinstance(other, Output) else other
        return self._value > other_value

    @staticmethod
    def unwrap(obj) -> Any | list[Any]:
        """
        Given an object or collection of objects, remove any `Output` decorations.
        """
        if isinstance(obj, Output):
            return obj._value
        elif is_non_string_sequence(obj):
            return [Output.unwrap(item) for item in obj]
        else:
            return obj

    @staticmethod
    def render(obj) -> str | list[str]:
        """
        Given an object or collection of objects, stringify the objects suitable for
        output, including invoking any `Output` formatting.
        """
        if isinstance(obj, Output):
            return str(obj)
        elif is_non_string_sequence(obj):
            return [Output.render(item) for item in obj]
        else:
            return str(obj)
