"""TrailCurrent Logo Deboss Operations

Handles face alignment, layer isolation via 2D boolean subtraction,
per-layer extrusion at varying depths, and the final Part boolean cuts.
"""

import Part
import FreeCAD
from FreeCAD import Vector, Matrix
import math

from logo_geometry import create_logo_faces


def _compute_face_frame(face):
    """Compute a local coordinate frame for a planar face.

    Returns:
        (center, u_axis, v_axis, normal) where normal points outward,
        and u/v span the face plane.

    Raises:
        ValueError: if the face is not planar.
    """
    surface = face.Surface

    if hasattr(surface, "Axis"):
        normal = surface.Axis
    else:
        # Fallback: sample the normal at the parametric center
        u_min, u_max, v_min, v_max = face.ParameterRange
        normal = face.normalAt(
            (u_min + u_max) / 2.0, (v_min + v_max) / 2.0
        )

    center = face.CenterOfMass

    # Build orthonormal U, V axes in the face plane.
    # Pick whichever world axis is least parallel to normal as the seed.
    ax = abs(normal.x)
    ay = abs(normal.y)
    az = abs(normal.z)

    if ax <= ay and ax <= az:
        seed = Vector(1, 0, 0)
    elif ay <= ax and ay <= az:
        seed = Vector(0, 1, 0)
    else:
        seed = Vector(0, 0, 1)

    u_axis = normal.cross(seed)
    u_axis.normalize()
    v_axis = normal.cross(u_axis)
    v_axis.normalize()

    return center, u_axis, v_axis, normal


def _build_transform(center, u_axis, v_axis, normal):
    """Build a 4x4 matrix that maps local XY-plane geometry onto a face.

    Local X → u_axis, local Y → v_axis, local Z → -normal (into body).
    Origin is placed at *center*.
    """
    mat = Matrix()
    # Column 1: local X → u_axis
    mat.A11 = u_axis.x
    mat.A21 = u_axis.y
    mat.A31 = u_axis.z
    # Column 2: local Y → v_axis
    mat.A12 = v_axis.x
    mat.A22 = v_axis.y
    mat.A32 = v_axis.z
    # Column 3: local Z → -normal (into the body)
    mat.A13 = -normal.x
    mat.A23 = -normal.y
    mat.A33 = -normal.z
    # Column 4: translation to face center
    mat.A14 = center.x
    mat.A24 = center.y
    mat.A34 = center.z
    return mat


def apply_logo(
    body_shape,
    face,
    diameter=18.0,
    total_depth=0.8,
    mountain_ratio=0.55,
    trail_ratio=0.30,
    bolt_ratio=0.15,
    x_offset=0.0,
    y_offset=0.0,
):
    """Deboss the TrailCurrent logo onto a face of a body.

    Each logo element is cut at a different depth to create a layered
    relief effect:
      - Circle background: *total_depth* (deepest)
      - Mountain:          *total_depth * mountain_ratio*
      - Trail path:        *total_depth * trail_ratio*
      - Lightning bolt:    *total_depth * bolt_ratio* (shallowest)

    Args:
        body_shape: Part.Shape to cut into.
        face:       Part.Face on which to place the logo (must be planar).
        diameter:   Logo outer circle diameter in mm.
        total_depth: Maximum deboss depth in mm.
        mountain_ratio: Mountain depth as fraction of total_depth (0-1).
        trail_ratio:    Trail depth as fraction of total_depth (0-1).
        bolt_ratio:     Bolt depth as fraction of total_depth (0-1).
        x_offset:   Horizontal offset from face centre in mm.
        y_offset:   Vertical offset from face centre in mm.

    Returns:
        A new Part.Shape with the logo debossed.
    """
    # ------------------------------------------------------------------
    # 1. Compute face coordinate frame and transformation matrix
    # ------------------------------------------------------------------
    center, u_axis, v_axis, normal = _compute_face_frame(face)
    # Apply user-specified offset in the face plane
    placement = Vector(center)
    placement = placement + u_axis * x_offset + v_axis * y_offset
    mat = _build_transform(placement, u_axis, v_axis, normal)

    # ------------------------------------------------------------------
    # 2. Create raw 2D logo faces and isolate non-overlapping layers
    # ------------------------------------------------------------------
    faces = create_logo_faces(diameter)

    # 2D booleans: each layer excludes higher-priority features so
    # there is no geometric overlap between cutting solids.
    bolt_layer = faces["bolt"]
    trail_layer = faces["trail"].cut(faces["bolt"])
    mountain_layer = faces["mountain"].cut(faces["trail"]).cut(faces["bolt"])
    circle_layer = (
        faces["circle"]
        .cut(faces["mountain"])
        .cut(faces["trail"])
        .cut(faces["bolt"])
    )

    # ------------------------------------------------------------------
    # 3. Extrude each layer to its own depth and transform to face frame
    # ------------------------------------------------------------------
    depths = {
        "circle": total_depth,
        "mountain": total_depth * mountain_ratio,
        "trail": total_depth * trail_ratio,
        "bolt": total_depth * bolt_ratio,
    }

    layers = [
        ("circle", circle_layer),
        ("mountain", mountain_layer),
        ("trail", trail_layer),
        ("bolt", bolt_layer),
    ]

    cutting_solids = []
    for name, layer_face in layers:
        depth = depths[name]
        if depth < 1e-4:
            continue

        # Extrude along local +Z (which maps to -normal, i.e. into body)
        solid = layer_face.extrude(Vector(0, 0, depth))
        solid = solid.transformGeometry(mat)
        cutting_solids.append(solid)

    # ------------------------------------------------------------------
    # 4. Sequential boolean cuts
    # ------------------------------------------------------------------
    result = body_shape.copy()
    for solid in cutting_solids:
        result = result.cut(solid)

    return result
