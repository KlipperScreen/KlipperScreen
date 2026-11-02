"""Reusable fit/lifecycle helpers for the real-GTK (Weston) tier 2 tests.

The fit metric, defined against real GTK allocation semantics.

Clipping rule
-------------
A widget is *clipped* when GTK gives it less space than it asks for and the
excess falls outside the box it lives in -- on a touch screen that clipped
content is unreachable, which is the failure we guard against.

GTK lays out a child to at most its parent's allocated size.  So a widget that
does **not** expand clips when its *natural* preferred size exceeds its
**parent's** allocated size.  An expanding widget is stretched to fill its
parent instead, so its natural size is irrelevant there and it never clips.
Therefore, for a visible widget in a live container:

    non-scrollable widget clips  iff  natural_size > parent_allocation
                                    (for the dimension it does not expand)

Two cases are deliberately excluded, because they are not screen-overflow:

  * **Hidden widgets** (``get_visible() == False``) are not rendered, so they
    cannot clip the screen.
  * **Widgets inside a parent allocated ~1px** are already collapsed with that
    parent (an empty/hidden container); they are not filling real space.

Widgets inside a :class:`Gtk.ScrolledWindow` (and the ScrolledWindows
themselves) are exempt: overflowing a scroll region is handled by scrolling, by
design, so it is not a fit failure.

The one thing this does NOT check is the root itself against the screen: the
caller asserts the host (``main_grid``) allocates to the resolution, then checks
everything beneath it for clipping.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

SCROLL = Gtk.ScrolledWindow

# A parent allocated at or below this in either dimension is treated as
# collapsed/empty (e.g. a hidden dialog box), so its children are not checked.
_COLLAPSED = 2


def check_fit(root):
    """Return ``(fits, violations)`` for the tree below ``root``.

    ``violations`` is a list of ``(widget_name, dimension, natural, parent)``
    for visible, non-scrollable, non-expanding widgets whose natural size
    exceeds their parent's allocated size (i.e. would be clipped).
    """
    violations = []
    stack = [(root, None, False)]  # (widget, parent, in_scroll_region)
    while stack:
        widget, parent, in_scroll = stack.pop()
        child_scroll = in_scroll or isinstance(widget, SCROLL)

        # Always recurse: visibility/size can differ for deeper children.
        if isinstance(widget, Gtk.Container):
            for child in widget.get_children():
                stack.append((child, widget, child_scroll))

        # Only a visible widget in a live, non-scrollable parent can clip.
        if child_scroll or parent is None:
            continue
        if not widget.get_visible():
            continue
        if (
            parent.get_allocated_width() <= _COLLAPSED
            or parent.get_allocated_height() <= _COLLAPSED
        ):
            continue

        if not widget.get_hexpand():
            nat = widget.get_preferred_width()[1]
            par = parent.get_allocated_width()
            if nat > par:
                violations.append((widget.get_css_name(), "width", nat, par))
        if not widget.get_vexpand():
            nat = widget.get_preferred_height()[1]
            par = parent.get_allocated_height()
            if nat > par:
                violations.append((widget.get_css_name(), "height", nat, par))
    return (not violations), violations


def realize(root, width, height):
    """Put ``root`` in a real window at the target size and map it.

    Returns the window.  The caller must pump GLib before reading allocations
    and destroy the window afterwards.
    """
    window = Gtk.Window()
    window.set_default_size(width, height)
    window.resize(width, height)
    window.add(root)
    window.show_all()
    return window
