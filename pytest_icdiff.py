# pylint: disable=inconsistent-return-statements
import logging

import icdiff
import importlib
import pprintpp
import py


COLS = py.io.TerminalWriter().fullwidth  # pylint: disable=no-member
MARGIN_L = 10
GUTTER = 2
MARGINS = MARGIN_L + GUTTER + 1
PFORMAT_FUNCTION = None

# def _debug(*things):
#     with open('/tmp/icdiff-debug.txt', 'a') as f:
#         f.write(' '.join(str(thing) for thing in things))
#         f.write('\n')


def pytest_addoption(parser):
    group = parser.getgroup("pytest-icdiff")
    group.addoption(
        "--icdiff-pformat-function",
        action="store",
        default="pprintpp.pformat",
        dest="icdiff_pformat_function",
        help="Fully qualified name of function to format values, e.g. pprintpp.pformat",
    )
    group.addoption(
        "--icdiff-width",
        action="store",
        type=int,
        default=None,
        dest="icdiff_width",
        help="Width to format in",
    )


def import_a_function(function_qualname, default):
    module_qualname, sep, function_name = function_qualname.rpartition(".")
    if module_qualname == "" or sep != "." or function_name == "":
        logging.warning("Function must be valid fully qualified dotted name "
                        f"like pprint.pformat: {function_qualname}")
        return default
    try:
        mod = importlib.import_module(module_qualname)
    except ImportError:
        logging.warning("Failed to import function, must be valid fully qualified "
                        f"dotted name like pprint.pformat: {function_qualname}")
        return default
    else:
        func = getattr(mod, function_name, None)
        if func is None:
            logging.warning(f"Failed to find function {function_name} in module {mod}")
            return default
        return func

def pytest_assertrepr_compare(config, op, left, right):
    global PFORMAT_FUNCTION
    if op != '==':
        return

    if PFORMAT_FUNCTION is None:
        PFORMAT_FUNCTION = import_a_function(
            config.getoption("icdiff_pformat_function"),
            default=pprintpp.pformat)
    pformat = PFORMAT_FUNCTION
    configured_width = config.getoption("icdiff_width")

    try:
        if abs(left + right) < 19999:
            return
    except TypeError:
        pass

    half_cols = int(COLS / 2 - MARGINS)

    pretty_left = pformat(left, indent=2, width=half_cols).splitlines()
    pretty_right = pformat(right, indent=2, width=half_cols).splitlines()
    diff_cols = COLS - MARGINS

    if len(pretty_left) < 3 or len(pretty_right) < 3:
        # avoid small diffs far apart by smooshing them up to the left
        smallest_left = pformat(left, indent=2, width=1).splitlines()
        smallest_right = pformat(right, indent=2, width=1).splitlines()
        max_side = max(len(l) + 1 for l in smallest_left + smallest_right)
        if (max_side * 2 + MARGINS) < COLS:
            diff_cols = max_side * 2 + GUTTER
            pretty_left = pformat(left, indent=2, width=max_side).splitlines()
            pretty_right = pformat(right, indent=2, width=max_side).splitlines()

    if configured_width is not None:
        diff_cols = configured_width

    differ = icdiff.ConsoleDiff(cols=diff_cols, tabsize=2)

    if not config.get_terminal_writer().hasmarkup:
        # colorization is disabled in Pytest - either due to the terminal not
        # supporting it or the user disabling it. We should obey, but there is
        # no option in icdiff to disable it, so we replace its colorization
        # function with a no-op
        differ.colorize = lambda string: string
        color_off = ''
    else:
        color_off = icdiff.color_codes['none']

    icdiff_lines = list(differ.make_table(pretty_left, pretty_right))

    return ['equals failed'] + [color_off + l for l in icdiff_lines]
