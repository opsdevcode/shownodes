import pytest

from shownodes.output import ErrorMode, Output, literal


def test_basic():
    v = Output(3)
    assert Output.unwrap(v) == 3
    assert str(v) == "3"


def test_format():
    v = Output(3)
    assert f"{v:04d}" == "0003"

    vo = Output(0.12, "0.1%")
    assert str(vo) == "12.0%"


def test_functional_format():
    """
    Show that given a function as a formatter, the function is
    invoked appropriately.
    """
    fn = lambda x: str(2 * x)
    vfn = Output(4, fn)
    assert str(vfn) == "8"


def test_ordering():
    """
    Ensure ordering of Object instances is same as ordering of their
    enclosed values. Secondarily confirms that @total_ordering decorator
    did its job correctly.
    """
    assert Output(3) == Output(3)
    assert Output(3) > Output(2)
    assert Output(3) < Output(12)
    assert Output(3, "xyz") == Output(3)


def test_collection_sorting():
    """
    Test sorting, including alongside non-Output objects.
    """
    l = [
        19,
        Output(4, literal("****")),
        Output(0, literal("\N{EM DASH}")),
        Output(1, literal("*")),
        Output(2, literal("**")),
    ]
    sl = sorted(l)
    assert Output.unwrap(sl) == [0, 1, 2, 4, 19]


def test_rendering():
    """Test rendering, alongside rendering non-Output objects"""
    l = [
        Output(4, literal("****")),
        Output(0, literal("\N{EM DASH}")),
        Output(1, literal("*")),
        Output(2, literal("**")),
        19,
    ]
    sl = sorted(l)
    assert Output.render(sl) == ["—", "*", "**", "****", "19"]


def test_errors_silent():
    assert str(Output("this", "%0.2f")) == ""


def test_errors_loud():
    with pytest.raises(Exception):
        assert str(Output("this", "%0.2f", errors=ErrorMode.loud))
