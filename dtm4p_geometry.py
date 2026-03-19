"""Load and position the TrailCurrent Termination Housing (DTM4P) geometry.

The housing shape is stored as a BREP file bundled with the plugin
in canonical orientation:
  - Centred at the origin in the XY plane
  - Rear attachment face at Z=0
  - Housing extends along +Z toward the front opening (~40.9 mm)
  - X is the width axis, Y is the depth axis

When placing onto a selected face the housing is oriented so that:
  - Local Z (housing length) maps to the face outward normal
  - The rear attachment face sits flush on the selected surface
  - The front opening points away from the body
"""

import os
import math

import FreeCAD
from FreeCAD import Vector, Matrix
import Part

_plugin_dir = os.path.dirname(os.path.abspath(__file__))


def _load_housing_shape():
    """Load the termination housing BREP and return a Part.Shape."""
    brep_path = os.path.join(
        _plugin_dir, "resources", "shapes",
        "TrailCurrentTerminationHousing.brep",
    )
    shape = Part.Shape()
    shape.importBrep(brep_path)
    return shape


def _compute_face_frame(face):
    """Compute a local coordinate frame for a planar face.

    Returns (center, u_axis, v_axis, normal).
    """
    u_min, u_max, v_min, v_max = face.ParameterRange
    normal = face.normalAt(
        (u_min + u_max) / 2.0, (v_min + v_max) / 2.0
    )
    center = face.CenterOfMass

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


def place_housing(
    body_shape,
    face,
    x_offset=0.0,
    y_offset=0.0,
    rotation=0.0,
):
    """Place the termination housing onto a face and fuse it with the body.

    The housing rear attachment face is placed flush on the selected face
    surface, with the connector opening pointing outward along the face
    normal.

    Args:
        body_shape: Part.Shape to fuse with.
        face:       Planar Part.Face to place the housing on.
        x_offset:   Horizontal offset from face centre (mm).
        y_offset:   Vertical offset from face centre (mm).
        rotation:   Rotation angle on the face (degrees).

    Returns:
        A new Part.Shape with the housing fused.
    """
    center, u_axis, v_axis, normal = _compute_face_frame(face)

    if rotation:
        rad = math.radians(rotation)
        cos_r, sin_r = math.cos(rad), math.sin(rad)
        u_rot = u_axis * cos_r + v_axis * sin_r
        v_rot = -u_axis * sin_r + v_axis * cos_r
        u_axis, v_axis = u_rot, v_rot

    placement = Vector(center)
    placement = placement + u_axis * x_offset + v_axis * y_offset

    # Build transform: local X -> u_axis, local Y -> v_axis,
    # local Z -> +normal (housing extends outward from face).
    # This is a proper rotation (det = +1).
    mat = Matrix()
    # Column 1: local X -> face U
    mat.A11 = u_axis.x
    mat.A21 = u_axis.y
    mat.A31 = u_axis.z
    # Column 2: local Y -> face V
    mat.A12 = v_axis.x
    mat.A22 = v_axis.y
    mat.A32 = v_axis.z
    # Column 3: local Z -> face normal (outward)
    mat.A13 = normal.x
    mat.A23 = normal.y
    mat.A33 = normal.z
    # Column 4: translation to face centre (with offsets)
    mat.A14 = placement.x
    mat.A24 = placement.y
    mat.A34 = placement.z

    # Load the housing (already in canonical orientation: centred in XY,
    # rear at Z=0, extends along +Z)
    housing = _load_housing_shape()

    # Sink the rear face 0.1 mm into the body so the fuse has clean
    # overlap rather than two coplanar faces meeting at a seam.
    sink = Matrix()
    sink.A34 = -0.1
    housing.transformShape(sink)

    # Place on the face
    housing.transformShape(mat)

    # Fuse with the body
    result = body_shape.fuse(housing)
    result = result.removeSplitter()

    return result
