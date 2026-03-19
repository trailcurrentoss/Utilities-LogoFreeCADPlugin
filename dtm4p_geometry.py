"""Load and position the TrailCurrent Termination Housing (DTM4P) geometry.

The housing shape is stored as a BREP file bundled with the plugin.
Its native orientation has:
  - Y axis along the housing length (rear attachment at Y=40, front at Y=-0.9)
  - X axis as the width (-11.5 to 11.5)
  - Z axis as the depth (-9.5 to 12.0)

When placing onto a selected face, the housing is re-oriented so that:
  - The rear attachment face (Y=40) sits flush on the selected face
  - The connector opening (front) points outward along the face normal
"""

import os
import math

import FreeCAD
from FreeCAD import Vector, Matrix
import Part

_plugin_dir = os.path.dirname(os.path.abspath(__file__))

# The rear attachment face is at Y=40 in the stored BREP.
_REAR_Y = 40.0

# Center of the rear attachment face cross-section (XZ plane).
# Rear face (Face1): center=(0, 40, 3.0), spans X(-11.5 to 11.5), Z(-9.5 to 12.0)
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

    # Build transform matrix (must be a proper rotation, det=+1).
    # After the pre-transform the housing has:
    #   +Y pointing outward (front/opening direction)
    #   X and Z centred at origin
    # Map: housing +Y -> face normal, X -> U, Z -> V.
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

    # Pre-transform: rotate 180° around X axis so the rear attachment
    # face (Y=40) ends up at Y=0 and the front opening points in +Y.
    # Rotation around X by 180°: (x, y, z) -> (x, -y, -z)
    # Combined with translation to centre the shape:
    #   x' = x - center_X
    #   y' = -(y - REAR_Y) = REAR_Y - y    (rear face -> Y=0, front -> +Y)
    #   z' = -(z - center_Z) = center_Z - z
    pre = Matrix()
    pre.A11 = 1.0                # x unchanged
    pre.A22 = -1.0               # y negated (180° rotation around X)
    pre.A33 = -1.0               # z negated (180° rotation around X)
    pre.A14 = -_CENTER_X         # centre X
    pre.A24 = _REAR_Y            # translate then negate Y
    pre.A34 = _CENTER_Z          # translate then negate Z
    housing.transformShape(pre)

    # Sink the rear face 0.1mm into the body so the fuse has clean
    # overlap rather than two coplanar faces meeting at a seam.
    sink = Matrix()
    sink.A24 = -0.1
    housing.transformShape(sink)

    # Apply the face-frame transform
    housing.transformShape(mat)

    # Fuse with the body
    result = body_shape.fuse(housing)
    result = result.removeSplitter()

    return result
