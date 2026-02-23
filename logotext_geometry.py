"""TrailCurrent Logo + Text Geometry Generator

Creates the TrailCurrent circular logo (circle, mountain, trail, bolt)
plus the word "TrailCurrent" as FreeCAD Part.Face objects for debossing.

All letter geometry is defined as hardcoded polygon outlines — no font
files or Part.makeWireString() calls.  Letters are designed as bold
geometric sans-serif block forms suitable for shallow debossing.

Layout ratios are derived from the trailcurrent.com website header SVG
(viewBox 0 0 240 48):
  - Icon ~38 px wide  |  text starts at x ≈ 52  |  font-size=24
  - text cap height ≈ 55 % of logo diameter
  - gap             ≈ 23 % of logo diameter
"""

import Part
from FreeCAD import Vector

from logo_geometry import create_logo_faces, _make_face_from_polygon


# ---------------------------------------------------------------------------
# Block-letter definitions (design units: cap_height = 10, x_height = 7)
# ---------------------------------------------------------------------------
# Each entry: (advance_width, [outer_polygons], [hole_polygons])
# Polygons are lists of (x, y) tuples, origin at bottom-left of glyph.

_S = 1.8        # stroke width
_CAP = 10.0     # capital height
_XH = 7.0       # x-height
_SPACING = 1.0  # inter-character gap

_GLYPHS = {
    # -- Capitals ----------------------------------------------------------
    'T': (7.0,
          [[(0, 10), (7, 10), (7, 8.2), (4.4, 8.2),
            (4.4, 0), (2.6, 0), (2.6, 8.2), (0, 8.2)]],
          []),

    'C': (5.4,
          [[(0, 0), (5.4, 0), (5.4, 1.8), (1.8, 1.8),
            (1.8, 8.2), (5.4, 8.2), (5.4, 10), (0, 10)]],
          []),

    # -- Lowercase ---------------------------------------------------------
    'r': (3.8,
          [[(0, 0), (1.8, 0), (1.8, 5.2), (3.8, 5.2),
            (3.8, 7), (0, 7)]],
          []),

    'a': (5.4,
          [[(0, 0), (5.4, 0), (5.4, 7), (0, 7)]],
          [[(1.8, 1.8), (3.6, 1.8), (3.6, 5.2), (1.8, 5.2)]]),

    'i': (1.8,
          [[(0, 0), (1.8, 0), (1.8, 7), (0, 7)],
           [(0, 8.2), (1.8, 8.2), (1.8, 10), (0, 10)]],
          []),

    'l': (1.8,
          [[(0, 0), (1.8, 0), (1.8, 10), (0, 10)]],
          []),

    'u': (5.4,
          [[(0, 0), (5.4, 0), (5.4, 7), (3.6, 7),
            (3.6, 1.8), (1.8, 1.8), (1.8, 7), (0, 7)]],
          []),

    'e': (5.4,
          [[(0, 0), (5.4, 0), (5.4, 2.6), (1.8, 2.6),
            (1.8, 4.4), (5.4, 4.4), (5.4, 7), (0, 7)]],
          []),

    'n': (5.4,
          [[(0, 0), (1.8, 0), (1.8, 5.2), (3.6, 5.2),
            (3.6, 0), (5.4, 0), (5.4, 7), (0, 7)]],
          []),

    't': (4.2,
          [[(0, 0), (1.8, 0), (1.8, 5.2), (4.2, 5.2),
            (4.2, 7), (1.8, 7), (1.8, 10), (0, 10)]],
          []),
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_glyph_face(char, x_offset, scale):
    """Return a Part.Shape for *char* translated by *x_offset* and scaled."""
    if char not in _GLYPHS:
        raise ValueError("No glyph defined for {!r}".format(char))

    _, outers, holes = _GLYPHS[char]

    faces = []
    for poly in outers:
        pts = [(x * scale + x_offset, y * scale) for x, y in poly]
        faces.append(_make_face_from_polygon(pts))

    if not faces:
        raise ValueError("Glyph {!r} has no outer polygons".format(char))

    # Fuse all outer polygons (e.g. stem + dot for 'i')
    result = faces[0]
    for f in faces[1:]:
        result = result.fuse(f)

    # Cut holes (e.g. counter of 'a')
    for hole_poly in holes:
        pts = [(x * scale + x_offset, y * scale) for x, y in hole_poly]
        hole_face = _make_face_from_polygon(pts)
        result = result.cut(hole_face)

    return result


def _create_text_shape(text, cap_height):
    """Build a Part.Shape for *text* at the given cap height.

    The resulting shape sits on the baseline (y = 0) with its left edge
    at x = 0.  Only characters present in _GLYPHS are supported.
    """
    scale = cap_height / _CAP
    cursor_x = 0.0
    char_shapes = []

    for ch in text:
        if ch not in _GLYPHS:
            raise ValueError("Unsupported character {!r}".format(ch))
        adv_width = _GLYPHS[ch][0]
        shape = _build_glyph_face(ch, cursor_x, scale)
        char_shapes.append(shape)
        cursor_x += (adv_width + _SPACING) * scale

    if not char_shapes:
        raise ValueError("No characters produced geometry.")

    result = char_shapes[0]
    for s in char_shapes[1:]:
        result = result.fuse(s)

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_logotext_faces(diameter=18.0):
    """Create logo faces plus "TrailCurrent" text face.

    The circular logo is identical to the standard logo.  The text is
    positioned to the right of the circle, sized and spaced to match the
    trailcurrent.com header layout.

    Args:
        diameter: outer circle diameter in mm (drives all sizing)

    Returns:
        dict with keys 'circle', 'mountain', 'trail', 'bolt', 'text',
        each mapping to a Part.Face (or compound) in the XY plane
        centered on the origin (logo centre).
    """
    faces = create_logo_faces(diameter)

    # Text sizing from website ratios
    text_cap_height = diameter * 0.55
    gap = diameter * 0.23
    text_x_start = diameter / 2.0 + gap

    text_shape = _create_text_shape("TrailCurrent", text_cap_height)

    # Vertically centre the text with the logo (y = 0 is logo centre).
    # The text baseline is at y = 0 in its local frame; cap-height
    # letters extend to y = text_cap_height.  Centre vertically:
    bb = text_shape.BoundBox
    dy = -(bb.YMin + bb.YMax) / 2.0
    text_shape.translate(Vector(text_x_start, dy, 0))

    faces["text"] = text_shape
    return faces
