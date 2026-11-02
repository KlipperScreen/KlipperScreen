"""Shared pytest setup for the KlipperScreen test suite.

Three responsibilities:

1. Make ``tests`` and ``tests/fakes`` importable, and the repository root
   importable so ``import panels.*`` / ``import ks_includes.*`` work.
2. Install the *real* KlipperScreen translations into the Python builtins so
   that ``_`` / ``ngettext`` behave exactly as they do in production.  This is
   important: localized strings change text width and therefore layout, so a
   stub ``_ = lambda s: s`` would give a false sense of fidelity.
3. Register the ``--fit-panel`` CLI option used to narrow the render-fit matrix
   (see ``tests/render/test_fit_matrix.py``).  It lives here -- not in the render
   conftest -- because only a conftest loaded before option parsing (the shared
   early-load conftest) may register CLI options; a per-directory conftest loads
   too late for ``pytest -m render --fit-panel ...`` to see it from the repo root.
"""

import os
import sys

# Repository root (so `import panels`, `import ks_includes`).
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
for path in (REPO_ROOT, TESTS_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

_LOCALES = os.path.join(REPO_ROOT, "ks_includes", "locales")
_translation = None
try:
    import gettext

    _translation = gettext.translation(
        "KlipperScreen", localedir=_LOCALES, languages=["en"], fallback=True
    )
    _translation.install(names=["gettext", "ngettext"])
except Exception:  # pragma: no cover - fallback so tests still run without .mo
    import builtins

    builtins._ = lambda s: s  # noqa: E731
    builtins.ngettext = lambda s, p, n: s if n == 1 else p


def pytest_addoption(parser):
    """Narrow the render-fit matrix to specific panels, e.g.::

        pytest -m render --fit-panel job_status,temperature

    instead of the whole panel x resolution x font sweep.  Leave it unset for
    the full matrix.  Registered here (the early-load shared conftest) rather
    than in the render conftest so it is visible to ``pytest -m render`` from
    the repo root.
    """
    parser.addoption(
        "--fit-panel",
        action="store",
        default="",
        help="comma-separated panel names to include in the fit matrix "
        "(default: all TESTED_PANELS)",
    )
