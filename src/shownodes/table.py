"""
Nicely print a table on the console using the rich library
"""

import re
from functools import lru_cache
from pprint import pprint
from typing import Any, Sequence

from rich import box
from rich.color import ANSI_COLOR_NAMES
from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.text import Text

from .output import Output

# type definitions for list-of-lists table format
RowType = list[Any]
TableType = list[RowType]


from collections import defaultdict

ALIGN_MAP = defaultdict(
    lambda: "left",
    {
        "<": "left",
        "^": "center",
        ">": "right",
    },
)


class Column:
    """
    Store data/metadata for a column. Name and alignment are the primary attributes,
    but other attributes (width, format, padding, text style, etc.) are possible.
    """

    def __init__(self, name: str, align: str = "left") -> None:
        if name.endswith(("<", "^", ">")):
            self.align = ALIGN_MAP[name[-1]]
            self.name = name[:-1]
        else:
            self.align = align
            self.name = name

    def __str__(self) -> str:
        return f"{self.name}"

    def __repr__(self) -> str:
        return f"Column({self.name}, {self.align})"


# Possible Column attributes:
# - align (left, right, center, fill)
# - width
# - format strings
# - format functions
# - padding
# - color
# - styles (bold, underline, etc.)


class Header(list):
    """
    A list of Column objects.
    """

    def __init__(self, spec: str | list[str] | None) -> None:
        items = self._parse_spec(spec)
        super().__init__(items)

    def _parse_spec(self, spec: str | list[str] | None) -> list[Column]:
        if spec is None:
            return []
        if isinstance(spec, list):
            return [Column(item) for item in spec]
        return [Column(item) for item in spec.split()]

    def follow(self, which: str, other: str | Column | list) -> "Header":
        """
        A fancy inset_after. Follow a given named column with a new column
        or a few.
        """
        if isinstance(other, Column):
            other = [other]
        elif isinstance(other, str):
            other = self._parse_spec(other)
        elif isinstance(other, list):
            # list could be mixed, so we need to follow each item
            for item in other:
                item = Column(item) if not isinstance(item, Column) else item
                self.follow(which, item)
                which = item.name if hasattr(item, "name") else item
            return self
        # find the target and insert other after it
        for i, col in enumerate(self):
            if col.name == which:
                posn = i + 1
                self[posn:posn] = other
                return self
        raise ValueError(f"Column {which} not found")

    def __repr__(self) -> str:
        return f"Header({', '.join(repr(item) for item in self)})"


class RowHighlighter:
    """
    Class to highlight rows in a table
    """

    colors = {
        "yellow": (255, 255, 128),
        "pink": (255, 175, 210),
        "green": (128, 255, 128),
        "blue": (192, 192, 255),
        "orange": (255, 200, 128),
        "purple": (200, 128, 200),
    }

    def __init__(self) -> None:
        self.colors = RowHighlighter.colors.copy()

    @lru_cache(maxsize=20)
    def style_for_color(self, color: str) -> Style:
        try:
            rgb = self.colors[color]
            return Style(bgcolor=f"rgb{rgb}")
        except KeyError:
            print(f"WARNING: Invalid color {color}")
            return self.style_for_color("yellow")

    def choose_highlight_style(self, cells: list[str], highlight_spec: Sequence[str]) -> Style | None:
        """
        Given a list of strings (cells in a row), determine a if the highlight_spec
        requires it be highlighted. Return the appropriate `rich.style.Style` if
        highlighting is required, else `None`.
        """
        for i, needle in enumerate(highlight_spec):
            color_name = "yellow"
            if ":" in needle:
                color_name, needle = needle.split(":")
            for needle_part in needle.split(","):
                if any(needle_part in cell for cell in cells):
                    return self.style_for_color(color_name)
        return None


row_highlighter = RowHighlighter()


def print_table(
    rows, header: Header | list[str], footer: list[str] | None = None, width=None, highlight: Sequence[str] = ()
) -> None:
    """
    Use rich to print a table
    """

    if width is not None and width > 0:
        console = Console(width=width)
    else:
        console = Console()

    table = Table(
        show_header=True,
        show_footer=False,
        header_style=None,
        box=box.SIMPLE,
        collapse_padding=True,
        show_edge=True,
        pad_edge=False,
        padding=0,
    )

    # adjust style
    gutter = " " * 2
    table.box.mid_vertical = gutter
    table.box.head_vertical = gutter
    table.box.foot_vertical = gutter
    table.box.head_row_cross = gutter
    table.box.foot_row_cross = gutter
    table.box.row_cross = gutter
    table.box.foot_row_horizontal = table.box.head_row_horizontal
    table.box.row_horizontal = table.box.head_row_horizontal

    for i, col_header in enumerate(header):
        justify = col_header.align if hasattr(col_header, "align") else "left"
        table.add_column(col_header.name if hasattr(col_header, "name") else col_header, justify=justify)

    for row in rows:
        if row is None:
            table.add_section()
        else:
            rendered_row = Output.render(row)
            style = row_highlighter.choose_highlight_style(rendered_row, highlight)
            table.add_row(*rendered_row, style=style)

    if footer:
        table.add_section()
        rendered_row = Output.render(footer)
        table.add_row(*rendered_row, style=None)

    console.print(table, justify="left")


def export_table(rows, header, footer, cluster_name):
    """
    Export table as CSV
    """
    import csv
    import time
    from pathlib import Path

    if isinstance(header, Header):
        header = [h.name for h in header]

    now = int(time.time())
    outpath = Path(f"/localhost/Downloads/shownodes-{cluster_name}-{now}.csv")
    with outpath.open("w") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)
        writer.writerow(footer)
    outpath_pretty = str(outpath).replace("/localhost", "~")
    print(f"Table exported to {outpath_pretty}")


"""
Infrastructure for sorting tables conveniently
"""


# Some fields have natural aliases to which they can be conveniently referred.
field_aliases = {
    "memory mem ram": "mem",
    "cpu cpus": "cpu",
    "$ $/hr price cost": "$/hr",
    "type flavor": "type",
    "zone az": "az",
    "captype cap": "captype",
    "disc discount $%": "$%",
}

# Map aliases to their canonical names
field_alias = {k: v for korig, v in field_aliases.items() for k in korig.split()}


class ColumnInfo:
    def __init__(self, spec, header):
        self.spec = spec
        self.reverse = spec.startswith("-")
        field_raw = spec.lstrip("-").lower()
        self.name = field_alias.get(field_raw, field_raw)
        self.index = header.index(self.name.upper())

    def __repr__(self):
        classname = self.__class__.__name__
        core = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())
        return f"{classname}({core})"


def column_values(name: str, rows: TableType, header: RowType) -> list[Any]:
    """
    Return the values of a given named column.
    """
    field_info = ColumnInfo(name, header)
    return [row[field_info.index] for row in rows]


def sort_rows(rows: TableType, sort_by: str, header: RowType) -> TableType:
    """
    Sort rows by (possibly multiple) fields named in sort_by (a CSV of fields).
    In each field, a `-` prefix reverses sort order. E.g. "cpu,-mem" sorts by
    cpu ascending, then mem descending. header is the table header, used to find
    indices in each row of the given sort fields. Fields may have aliases, e.g.
    "az" is equivalent to "zone", "price" to "$/hr".

    Sorting is one of those things that seems simple but is actually pretty
    complicated if done for human convenience.
    """
    header_names = [h.name if hasattr(h, "name") else h for h in header]
    sort_fields = sort_by.split(",")
    for sort_field in reversed(sort_fields):
        field_info = ColumnInfo(sort_field, header_names)
        # reverse = sort_field.startswith("-")
        # sort_field = sort_field.lstrip("-").lower()
        # field_name = field_alias.get(sort_field, sort_field)
        # field_index = header.index(field_name.upper())
        key_func = lambda row: row[field_info.index]
        rows = sorted(rows, key=key_func, reverse=field_info.reverse)
    return rows
