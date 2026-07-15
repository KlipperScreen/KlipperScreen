import re

# Matches any element using the `fill:var(--filament-color)` placeholder, regardless
# of which theme's spool.svg it comes from or how that theme shapes the filament
# coil (a plain rect, a curved wedge, one shape, two shapes, etc).
FILAMENT_COLOR_RE = re.compile(r"<path[^>]*?fill:var\(--filament-color\)[^>]*?/>")
SVG_TAG_RE = re.compile(r"(<svg\b[^>]*>)")
VIEWBOX_RE = re.compile(r'viewBox="\s*[\d.\-]+\s+[\d.\-]+\s+([\d.]+)\s+([\d.]+)\s*"')

DEFAULT_COLOR = "000000"


def normalize_hex(value):
    """Strip whitespace/leading '#' from a single color value."""
    return value.strip().lstrip("#")


def filament_colors_from_dict(filament):
    """
    Resolve the ordered list of filament colors from a Spoolman filament
    dict (as returned over the Moonraker API): prefer multi_color_hexes
    (comma separated) when present, falling back to the single color_hex,
    and finally to a default so callers always get at least one color.
    """
    if not filament:
        return [DEFAULT_COLOR]

    multi = filament.get("multi_color_hexes")
    if isinstance(multi, str) and multi.strip():
        colors = [normalize_hex(c) for c in multi.split(",") if c.strip()]
        if colors:
            return colors

    color = filament.get("color_hex")
    if isinstance(color, str) and color.strip():
        return [normalize_hex(color)]

    return [DEFAULT_COLOR]


def _gradient_stops(colors):
    n = len(colors)
    if n <= 1:
        color = colors[0] if colors else DEFAULT_COLOR
        return f'<stop offset="0" stop-color="#{color}"/><stop offset="1" stop-color="#{color}"/>'
    return "".join(
        f'<stop offset="{i / (n - 1):.4f}" stop-color="#{c}"/>' for i, c in enumerate(colors)
    )


def apply_filament_gradient(svg_text, colors):
    """
    Recolor a spool icon's filament-colored elements with a single smooth
    top-to-bottom gradient through `colors`, in order (first color nearest
    the spool's near/inner face, shifting through to the last color at the
    outer edge).

    This works generically across every theme's spool.svg without knowing
    its geometry: whichever elements use `fill:var(--filament-color)` are
    cloned into an SVG <mask> (preserving their exact original shape), and
    a single gradient-filled rect is painted through that mask in place of
    the first such element. Any additional filament-color elements are
    dropped, since the mask already covers their combined silhouette.

    A single color behaves exactly like the previous plain fill (no mask
    or gradient overhead), so this is a drop-in replacement.
    """
    if not colors:
        return svg_text.replace("var(--filament-color)", f"#{DEFAULT_COLOR}")
    if len(colors) == 1:
        return svg_text.replace("var(--filament-color)", f"#{colors[0]}")

    matches = list(FILAMENT_COLOR_RE.finditer(svg_text))
    if not matches:
        return svg_text

    width, height = 235, 500
    viewbox_match = VIEWBOX_RE.search(svg_text)
    if viewbox_match:
        width, height = float(viewbox_match.group(1)), float(viewbox_match.group(2))

    mask_shapes = "".join(
        re.sub(r"fill:var\(--filament-color\)", "fill:#ffffff", match.group(0)) for match in matches
    )

    grad_id, mask_id = "filamentGradient", "filamentMask"
    defs = (
        "<defs>"
        f'<linearGradient id="{grad_id}" gradientUnits="userSpaceOnUse" '
        f'x1="0" y1="0" x2="0" y2="{height}">{_gradient_stops(colors)}</linearGradient>'
        f'<mask id="{mask_id}" maskUnits="userSpaceOnUse" x="0" y="0" '
        f'width="{width}" height="{height}">'
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="black"/>'
        f"{mask_shapes}"
        "</mask>"
        "</defs>"
    )
    gradient_rect = (
        f'<rect x="0" y="0" width="{width}" height="{height}" '
        f'fill="url(#{grad_id})" mask="url(#{mask_id})"/>'
    )

    first = matches[0]
    out = svg_text[: first.start()] + gradient_rect + svg_text[first.end() :]
    out = FILAMENT_COLOR_RE.sub("", out)
    out = SVG_TAG_RE.sub(lambda m: m.group(1) + defs, out, count=1)
    return out
