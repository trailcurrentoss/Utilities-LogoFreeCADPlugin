"""Load and position the TrailCurrent Termination Housing (DTM4P) geometry.

The housing shape is stored as a BREP file bundled with the plugin.
Its native orientation has:
  - Y axis as the height (bottom at Y=-0.9, top at Y=40.0)
  - X axis as the width (-11.5 to 11.5)
  - Z axis as the depth (-9.5 to 12.0)

When placing onto a selected face, the housing is re-oriented so that:
  - The face outward normal becomes the housing height axis (+Y)
  - The housing bottom sits flush on the face surface
"""

import os
import math

import FreeCAD
from FreeCAD import Vector, Matrix
import Part

_plugin_dir = os.path.dirname(os.path.abspath(__file__))

# The housing bottom face is at Y = -0.9 in the stored BREP.
# We shift by +0.9 so the bottom aligns with Y=0 before transforming.
_BOTTOM_Y_OFFSET = 0.9

# Center of the housing cross-section (XZ plane)
_CENTER_X = 0.0
_CENTER_Z = 1.25  # midpoint of Z range (-9.5 to 12.0)


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

    The housing geometry is positioned so that its bottom face sits flush
    on the selected face surface, extending outward along the face normal.

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

    # Build transform: local X -> u_axis, local Z -> v_axis,
    # local Y -> +normal (housing extends outward from face)
    mat = Matrix()
    # Column 1: housing X -> face U
    mat.A11 = u_axis.x
    mat.A21 = u_axis.y
    mat.A31 = u_axis.z
    # Column 2: housing Y -> face normal (outward)
    mat.A12 = normal.x
    mat.A22 = normal.y
    mat.A32 = normal.z
    # Column 3: housing Z -> face V
    mat.A13 = v_axis.x
    mat.A23 = v_axis.y
    mat.A33 = v_axis.z
    # Column 4: translation
    mat.A14 = placement.x
    mat.A24 = placement.y
    mat.A34 = placement.z

    # Load and prepare the housing shape
    housing = _load_housing_shape()

    # Shift so the bottom face sits at Y=0 and center XZ at origin
    pre_shift = Matrix()
    pre_shift.A14 = -_CENTER_X
    pre_shift.A24 = _BOTTOM_Y_OFFSET  # shift Y so bottom is at Y=0
    pre_shift.A34 = -_CENTER_Z
    housing = housing.transformShape(pre_shift)

    # Apply the face-frame transform
    housing = housing.transformShape(mat)

    # Fuse with the body
    result = body_shape.fuse(housing)
    result = result.removeSplitter()

    return result
