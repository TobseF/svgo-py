"""Port of ``lib/path.test.js``."""

from svgo.path import parse_path_data, stringify_path_data


def _pd(items):
    return [{"command": c, "args": a} for c, a in items]


def test_spaces_between_commands():
    assert parse_path_data("M0 10 L \n\r\t20 30") == _pd([("M", [0, 10]), ("L", [20, 30])])


def test_spaces_and_commas_between_arguments():
    assert parse_path_data("M0 , 10 L 20 \n\r\t30,40,50") == _pd(
        [("M", [0, 10]), ("L", [20, 30]), ("L", [40, 50])]
    )


def test_forbid_commas_before_commands():
    assert parse_path_data(", M0 10") == []


def test_forbid_commas_between_commands():
    assert parse_path_data("M0,10 , L 20,30") == _pd([("M", [0, 10])])


def test_forbid_commas_between_name_and_argument():
    assert parse_path_data("M0,10 L,20,30") == _pd([("M", [0, 10])])


def test_forbid_multiple_commas():
    assert parse_path_data("M0 , , 10") == []


def test_stop_on_unknown_char():
    assert parse_path_data("M0 10 , L 20 #40") == _pd([("M", [0, 10])])


def test_stop_not_enough_arguments():
    assert parse_path_data("M0 10 L 20 L 30 40") == _pd([("M", [0, 10])])


def test_stop_moveto_not_first():
    assert parse_path_data("L 10 20") == []
    assert parse_path_data("10 20") == []


def test_stop_invalid_scientific():
    assert parse_path_data("M 0 5e++1 L 0 0") == _pd([("M", [0, 5])])


def test_stop_invalid_numbers():
    assert parse_path_data("M ...") == []


def test_arcs():
    result = parse_path_data(
        """
          M600,350
          l 50,-25
          a25,25 -30 0,1 50,-25
          25,50 -30 0,1 50,-25
          25,75 -30 01.2,-25
          a25,100 -30 0150,-25
          l 50,-25
        """
    )
    assert result == _pd([
        ("M", [600, 350]),
        ("l", [50, -25]),
        ("a", [25, 25, -30, 0, 1, 50, -25]),
        ("a", [25, 50, -30, 0, 1, 50, -25]),
        ("a", [25, 75, -30, 0, 1, 0.2, -25]),
        ("a", [25, 100, -30, 0, 1, 50, -25]),
        ("l", [50, -25]),
    ])


def test_normalize_signed_arc_radii():
    assert parse_path_data("M0 0A-10 +20 0 0 1 30 40a+50 -60 0 1 0 70 80") == _pd([
        ("M", [0, 0]),
        ("A", [10, 20, 0, 0, 1, 30, 40]),
        ("a", [50, 60, 0, 1, 0, 70, 80]),
    ])


def test_combine_same_commands():
    assert stringify_path_data(_pd([
        ("M", [0, 0]), ("h", [10]), ("h", [20]), ("h", [30]), ("H", [40]), ("H", [50]),
    ])) == "M0 0h10 20 30H40 50"


def test_not_combine_moveto():
    assert stringify_path_data(_pd([
        ("M", [0, 0]), ("M", [10, 10]), ("m", [20, 30]), ("m", [40, 50]),
    ])) == "M0 0M10 10m20 30m40 50"


def test_combine_moveto_lineto():
    assert stringify_path_data(_pd([
        ("M", [0, 0]), ("l", [10, 10]), ("M", [0, 0]), ("l", [10, 10]),
        ("M", [0, 0]), ("L", [10, 10]),
    ])) == "m0 0 10 10M0 0l10 10M0 0 10 10"
    assert stringify_path_data(_pd([("m", [0, 0]), ("L", [10, 10])])) == "M0 0 10 10"


def test_avoid_space_before_first_negative_decimals():
    assert stringify_path_data(_pd([
        ("M", [0, -1.2]), ("L", [0.3, 4]), ("L", [5, -0.6]), ("L", [7, 0.8]),
    ])) == "M0-1.2.3 4 5-.6 7 .8"


def test_space_before_scientific():
    assert stringify_path_data(
        _pd([("M", [0.1, 1e-7]), ("L", [2, 2])]), precision=7
    ) == "M.1 1e-7 2 2"


def test_configure_precision():
    path_data = _pd([
        ("M", [0, -1.9876]), ("L", [0.3, 3.14159265]),
        ("L", [-0.3, -3.14159265]), ("L", [100, 200]),
    ])
    assert stringify_path_data(path_data, precision=3) == "M0-1.988.3 3.142-.3-3.142 100 200"
    assert stringify_path_data(path_data, precision=0) == "M0-2 0 3 0-3 100 200"


def test_disable_space_after_flags():
    path_data = _pd([
        ("M", [0, 0]), ("A", [50, 50, 10, 1, 0, 0.2, 20]),
        ("a", [50, 50, 10, 1, 0, 0.2, 20]), ("a", [50, 50, 10, 1, 0, 0.2, 20]),
    ])
    assert stringify_path_data(path_data, disableSpaceAfterFlags=False) == (
        "M0 0A50 50 10 1 0 .2 20a50 50 10 1 0 .2 20 50 50 10 1 0 .2 20"
    )
    assert stringify_path_data(path_data, disableSpaceAfterFlags=True) == (
        "M0 0A50 50 10 10.2 20a50 50 10 10.2 20 50 50 10 10.2 20"
    )
