from binary import BinaryUnits, convert_units


def GiB(mb: int, input_unit: BinaryUnits = BinaryUnits.MB) -> str:
    """
    Given size as int MB (by default, but can be other units,
    such as BinaryUnits.B, BinaryUnits.KB, BinaryUnits.GB, etc.),
    output in nice GiB format.
    """
    magnitude, units = convert_units(mb, input_unit, BinaryUnits.GB)
    return f"{magnitude:0,.0f} {units}"


def intGiB(mb: int, input_unit: BinaryUnits = BinaryUnits.MB) -> int:
    """
    Given size as int MB (by default, but can be other units,
    such as BinaryUnits.B, BinaryUnits.KB, BinaryUnits.GB, etc.),
    output in nice integer GiB format.
    """
    magnitude, units = convert_units(mb, input_unit, BinaryUnits.GB)
    return int(round(magnitude, 0))
