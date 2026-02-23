"""TrailCurrent Logo+Text Deboss Operations

Handles face alignment, layer isolation, per-layer extrusion at varying
depths, text extrusion, and the final Part boolean cuts.

Reuses the face-frame and transform helpers from logo_deboss.
"""

import Part
import FreeCAD
from FreeCAD import Vector
import math

from logo_deboss import _compute_face_frame, _build_transform
from logotext_geometry import create_logotext_faces


def apply_logotext(
    body_shape,
    face,
    diameter=18.0,
    total_depth=0.8,
    mountain_ratio=0.55,
    trail_ratio=0.30,
    bolt_ratio=0.15,
    text_ratio=1.0,
    x_offset=0.0,
    y_offset=0.0,
    rotation=0.0,
):
    """Deboss the TrailCurrent logo + text onto a face of a body.

    The circular logo is debossed with the same multi-depth layering as
    apply_logo().  The text "TrailCurrent" is debossed to the right of
    the circle at *total_depth * text_ratio*.

    Args:
        body_shape: Part.Shape to cut into.
        face:       Part.Face on which to place the logo (must be planar).
        diameter:   Logo outer circle diameter in mm.
        total_depth: Maximum deboss depth in mm.
        mountain_ratio: Mountain depth as fraction of total_depth (0-1).
        trail_ratio:    Trail depth as fraction of total_depth (0-1).
        bolt_ratio:     Bolt depth as fraction of total_depth (0-1).
        text_ratio:     Text depth as fraction of total_depth (0-1).
        x_offset:   Horizontal offset from face centre in mm.
        y_offset:   Vertical offset from face centre in mm.
        rotation:   Rotation angle on the face in degrees.

    Returns:
        A new Part.Shape with the logo+text debossed.
    """
    # ------------------------------------------------------------------
    # 1. Compute face coordinate frame and transformation matrix
    # ------------------------------------------------------------------
    center, u_axis, v_axis, normal = _compute_face_frame(face)
    if rotation:
        rad = math.radians(rotation)
        cos_r, sin_r = math.cos(rad), math.sin(rad)
        u_rot = u_axis * cos_r + v_axis * sin_r
        v_rot = -u_axis * sin_r + v_axis * cos_r
        u_axis, v_axis = u_rot, v_rot
    placement = Vector(center)
    placement = placement + u_axis * x_offset + v_axis * y_offset
    mat = _build_transform(placement, u_axis, v_axis, normal)

    # ------------------------------------------------------------------
    # 2. Create 2D logo + text faces and isolate non-overlapping layers
    # ------------------------------------------------------------------
    faces = create_logotext_faces(diameter)

    # Logo layers (same isolation as logo_deboss.py)
    bolt_layer = faces["bolt"]
    trail_layer = faces["trail"].cut(faces["bolt"])
    mountain_layer = faces["mountain"].cut(faces["trail"]).cut(faces["bolt"])
    circle_layer = (
        faces["circle"]
        .cut(faces["mountain"])
        .cut(faces["trail"])
        .cut(faces["bolt"])
    )

    # Text layer (no overlap with circle — positioned to the right)
    text_layer = faces["text"]

    # ------------------------------------------------------------------
    # 3. Extrude each layer and transform to face frame
    # ------------------------------------------------------------------
    depths = {
        "circle": total_depth,
        "mountain": total_depth * mountain_ratio,
        "trail": total_depth * trail_ratio,
        "bolt": total_depth * bolt_ratio,
        "text": total_depth * text_ratio,
    }

    layers = [
        ("circle", circle_layer),
        ("mountain", mountain_layer),
        ("trail", trail_layer),
        ("bolt", bolt_layer),
        ("text", text_layer),
    ]

    cutting_solids = []
    for name, layer_face in layers:
        depth = depths[name]
        if depth < 1e-4:
            continue
        solid = layer_face.extrude(Vector(0, 0, depth))
        solid = solid.transformShape(mat)
        cutting_solids.append(solid)

    # ------------------------------------------------------------------
    # 4. Sequential boolean cuts
    # ------------------------------------------------------------------
    result = body_shape.copy()
    for solid in cutting_solids:
        result = result.cut(solid)

    return result
