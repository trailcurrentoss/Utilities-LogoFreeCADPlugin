"""TrailCurrent Logo Geometry Generator

Converts the TrailCurrent brand icon SVG elements into FreeCAD Part.Face
objects suitable for boolean deboss operations.

Logo elements (from trailcurrent-icon.svg, viewBox 0 0 48 48):
  - Circle:   cx=24 cy=24 r=22
  - Mountain: M6,36 L16,14 L22,22 L32,8 L42,36 Z
  - Trail:    M10,32 Q16,26 22,30 Q28,34 34,28 Q38,24 42,26  (stroke-width=3)
  - Bolt:     M34,14 L38,22 L32,22 L36,32                     (stroke-width=2.5)

All geometry is built using only FreeCAD Part APIs (no external dependencies).
"""

import Part
from FreeCAD import Vector
import math

# ---------------------------------------------------------------------------
# SVG constants
# ---------------------------------------------------------------------------
SVG_CX, SVG_CY = 24.0, 24.0
SVG_CIRCLE_DIAMETER = 44.0  # radius 22 * 2

SVG_MOUNTAIN = [(6, 36), (16, 14), (22, 22), (32, 8), (42, 36)]

SVG_TRAIL_CURVES = [
    # (start, control, end) for each quadratic bezier segment
    ((10, 32), (16, 26), (22, 30)),
    ((22, 30), (28, 34), (34, 28)),
    ((34, 28), (38, 24), (42, 26)),
]
SVG_TRAIL_STROKE_WIDTH = 3.0

SVG_BOLT = [(34, 14), (38, 22), (32, 22), (36, 32)]
SVG_BOLT_STROKE_WIDTH = 2.5


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _svg_to_local(sx, sy, scale):
    """Convert SVG coordinates to local XY centered at origin, Y flipped."""
    return ((sx - SVG_CX) * scale, -(sy - SVG_CY) * scale)


def _sample_quadratic_bezier(p0, p1, p2, n=16):
    """Return n+1 points sampling a quadratic Bezier curve."""
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1.0 - t
        x = u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]
        y = u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
        pts.append((x, y))
    return pts


def _buffer_path(points_2d, half_width, cap_segments=8):
    """Convert an open polyline into a closed buffered polygon.

    Creates left/right offset polylines and joins them with semicircular
    endcaps to form a closed outline (like a stroke-to-fill conversion).

    Args:
        points_2d: list of (x, y) tuples defining the path centerline
        half_width: half of the desired stroke width
        cap_segments: number of line segments per semicircular endcap

    Returns:
        list of (x, y) tuples forming a closed polygon (first != last)
    """
    n = len(points_2d)
    if n < 2:
        return []

    left = []
    right = []

    for i in range(n):
        # Compute tangent at this point
        if i == 0:
            dx = points_2d[1][0] - points_2d[0][0]
            dy = points_2d[1][1] - points_2d[0][1]
        elif i == n - 1:
            dx = points_2d[-1][0] - points_2d[-2][0]
            dy = points_2d[-1][1] - points_2d[-2][1]
        else:
            dx = points_2d[i + 1][0] - points_2d[i - 1][0]
            dy = points_2d[i + 1][1] - points_2d[i - 1][1]

        length = math.hypot(dx, dy)
        if length < 1e-12:
            continue
        dx /= length
        dy /= length

        # Perpendicular (rotated 90 degrees counter-clockwise)
        nx = -dy * half_width
        ny = dx * half_width

        left.append((points_2d[i][0] + nx, points_2d[i][1] + ny))
        right.append((points_2d[i][0] - nx, points_2d[i][1] - ny))

    # End cap at the last point (semicircle from right[-1] to left[-1])
    end_dx = points_2d[-1][0] - points_2d[-2][0]
    end_dy = points_2d[-1][1] - points_2d[-2][1]
    end_len = math.hypot(end_dx, end_dy)
    end_dx /= end_len
    end_dy /= end_len

    end_cap = []
    for i in range(1, cap_segments):
        angle = -math.pi / 2 + math.pi * i / cap_segments
        cx = points_2d[-1][0] + half_width * (
            end_dx * math.cos(angle) + end_dy * math.sin(angle)
        )
        cy = points_2d[-1][1] + half_width * (
            end_dy * math.cos(angle) - end_dx * math.sin(angle)
        )
        end_cap.append((cx, cy))

    # Start cap at the first point (semicircle from left[0] to right[0])
    st_dx = points_2d[1][0] - points_2d[0][0]
    st_dy = points_2d[1][1] - points_2d[0][1]
    st_len = math.hypot(st_dx, st_dy)
    st_dx /= st_len
    st_dy /= st_len

    start_cap = []
    for i in range(1, cap_segments):
        angle = math.pi / 2 + math.pi * i / cap_segments
        cx = points_2d[0][0] + half_width * (
            st_dx * math.cos(angle) + st_dy * math.sin(angle)
        )
        cy = points_2d[0][1] + half_width * (
            st_dy * math.cos(angle) - st_dx * math.sin(angle)
        )
        start_cap.append((cx, cy))

    # Assemble: left forward → end cap → right reversed → start cap
    polygon = left + end_cap + list(reversed(right)) + start_cap
    return polygon


def _make_face_from_polygon(pts_2d):
    """Create a Part.Face from a list of 2D (x, y) points."""
    vecs = [Vector(x, y, 0) for x, y in pts_2d]
    vecs.append(vecs[0])  # close the polygon
    wire = Part.makePolygon(vecs)
    return Part.Face(wire)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_logo_faces(diameter=18.0):
    """Create all four logo element faces at the given diameter.

    All faces lie in the XY plane, centered at the origin.  The circle
    face has the specified *diameter*; the other elements are scaled
    proportionally from the SVG source.

    Args:
        diameter: outer circle diameter in mm

    Returns:
        dict with keys 'circle', 'mountain', 'trail', 'bolt',
        each mapping to a Part.Face clipped to the circle boundary.
    """
    scale = diameter / SVG_CIRCLE_DIAMETER

    # --- Circle --------------------------------------------------------
    circle_edge = Part.makeCircle(
        diameter / 2.0, Vector(0, 0, 0), Vector(0, 0, 1)
    )
    circle_face = Part.Face(Part.Wire(circle_edge))

    # --- Mountain ------------------------------------------------------
    mt_pts = [_svg_to_local(x, y, scale) for x, y in SVG_MOUNTAIN]
    mountain_face = _make_face_from_polygon(mt_pts)
    mountain_face = mountain_face.common(circle_face)

    # --- Trail (stroke → solid) ----------------------------------------
    trail_svg_pts = []
    for i, (p0, p1, p2) in enumerate(SVG_TRAIL_CURVES):
        segment = _sample_quadratic_bezier(p0, p1, p2, n=20)
        if i > 0:
            segment = segment[1:]  # avoid duplicate join point
        trail_svg_pts.extend(segment)

    trail_local = [_svg_to_local(x, y, scale) for x, y in trail_svg_pts]
    trail_hw = SVG_TRAIL_STROKE_WIDTH * scale / 2.0
    trail_poly = _buffer_path(trail_local, trail_hw)
    trail_face = _make_face_from_polygon(trail_poly)
    trail_face = trail_face.common(circle_face)

    # --- Bolt (stroke → solid) -----------------------------------------
    bolt_local = [_svg_to_local(x, y, scale) for x, y in SVG_BOLT]
    bolt_hw = SVG_BOLT_STROKE_WIDTH * scale / 2.0
    bolt_poly = _buffer_path(bolt_local, bolt_hw)
    bolt_face = _make_face_from_polygon(bolt_poly)
    bolt_face = bolt_face.common(circle_face)

    return {
        "circle": circle_face,
        "mountain": mountain_face,
        "trail": trail_face,
        "bolt": bolt_face,
    }
