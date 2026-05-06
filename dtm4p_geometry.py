"""Load and position the TrailCurrent Termination Housing (DTM4P) geometry.

The housing shape is stored as a BREP file bundled with the plugin
in canonical orientation:
  - Centred at the origin in the XY plane
  - Physical bottom at Z=0
  - Housing extends along +Z (height ~21.5 mm)
  - X is the width axis (~23 mm), Y is the depth axis (~40.9 mm)
  - Front opening is at Y_min (~-20.45), rear at Y_max (~+20.45)

When placing onto a selected face the housing is oriented so that:
  - Local Z maps to the face outward normal (housing stands up from face)
  - X/Y offsets align with the model's world X/Y/Z axes (projected onto
    the face plane) so they behave predictably
  - If an edge is provided, the housing front (opening) aligns to that
    edge and the housing is positioned so the front starts at the edge
"""

import os
import math

import FreeCAD
from FreeCAD import Vector, Matrix
import Part

_plugin_dir = os.path.dirname(os.path.abspath(__file__))

# Front face Y coordinate in canonical BREP (the opening side)
_FRONT_Y = -20.45


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

    U and V axes are aligned with the model's world axes (projected onto
    the face plane) so that X/Y offsets correspond to the global coordinate
    system rather than arbitrary directions.

    Returns (center, u_axis, v_axis, normal).
    """
    u_min, u_max, v_min, v_max = face.ParameterRange
    normal = face.normalAt(
        (u_min + u_max) / 2.0, (v_min + v_max) / 2.0
    )
    if face.Orientation == "Reversed":
        normal = normal * -1.0
    center = face.CenterOfMass

    # Project world X onto the face plane to get U.  If world X is
    # (nearly) parallel to the normal, fall back to world Y.
    world_x = Vector(1, 0, 0)
    world_y = Vector(0, 1, 0)

    proj_x = world_x - normal * normal.dot(world_x)
    if proj_x.Length > 1e-6:
        u_axis = proj_x
        u_axis.normalize()
    else:
        proj_y = world_y - normal * normal.dot(world_y)
        u_axis = proj_y
        u_axis.normalize()

    v_axis = normal.cross(u_axis)
    v_axis.normalize()

    return center, u_axis, v_axis, normal


def _compute_edge_frame(face, edge):
    """Compute a frame where the housing front aligns to *edge*.

    The edge tangent direction becomes the housing width axis (local X).
    The perpendicular direction on the face (pointing away from the edge
    into the face) becomes the housing depth axis (local Y).

    Returns (anchor, u_axis, v_axis, normal) where *anchor* is the
    midpoint of the edge.
    """
    u_min, u_max, v_min, v_max = face.ParameterRange
    normal = face.normalAt(
        (u_min + u_max) / 2.0, (v_min + v_max) / 2.0
    )
    if face.Orientation == "Reversed":
        normal = normal * -1.0

    # Edge tangent at midpoint
    e_first, e_last = edge.ParameterRange
    tangent = edge.tangentAt((e_first + e_last) / 2.0)
    tangent.normalize()

    # u_axis = along the edge (housing width)
    u_axis = tangent

    # v_axis = perpendicular to edge on the face, pointing inward
    # (away from the edge, into the face interior)
    v_axis = normal.cross(u_axis)
    v_axis.normalize()

    # Check v_axis points toward the face centre; flip if needed
    anchor = edge.CenterOfMass
    to_center = face.CenterOfMass - anchor
    if to_center.dot(v_axis) < 0:
        v_axis = v_axis * -1.0
        u_axis = u_axis * -1.0  # keep right-handed

    return anchor, u_axis, v_axis, normal


def place_housing(
    body_shape,
    face,
    x_offset=0.0,
    y_offset=0.0,
    rotation=0.0,
    edge=None,
):
    """Place the termination housing onto a face and fuse it with the body.

    Args:
        body_shape: Part.Shape to fuse with.
        face:       Planar Part.Face to place the housing on.
        x_offset:   Offset along the face U axis (mm).
        y_offset:   Offset along the face V axis (mm).
        rotation:   Rotation angle on the face (degrees).
        edge:       Optional Part.Edge. When provided the housing front
                    (opening) is aligned to this edge and positioned so
                    the front face starts at the edge line.

    Returns:
        A new Part.Shape with the housing fused.
    """
    if edge is not None:
        center, u_axis, v_axis, normal = _compute_edge_frame(face, edge)
        # Shift the anchor so the housing front face (at local Y = _FRONT_Y)
        # lines up with the edge.  The anchor is already on the edge;
        # we need to offset along v_axis so that the front face (Y_min)
        # of the housing sits exactly at the edge line.
        # In the transform, local Y maps to v_axis.  The front is at
        # local Y = _FRONT_Y (negative).  To place it at the edge we
        # shift by -_FRONT_Y along v_axis.
        center = center + v_axis * (-_FRONT_Y)
    else:
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
    mat = Matrix()
    mat.A11 = u_axis.x;  mat.A12 = v_axis.x;  mat.A13 = normal.x;  mat.A14 = placement.x
    mat.A21 = u_axis.y;  mat.A22 = v_axis.y;  mat.A23 = normal.y;  mat.A24 = placement.y
    mat.A31 = u_axis.z;  mat.A32 = v_axis.z;  mat.A33 = normal.z;  mat.A34 = placement.z

    housing = _load_housing_shape()
    housing.transformShape(mat)

    result = body_shape.fuse(housing)
    result = result.removeSplitter()

    return result
