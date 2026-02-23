"""QR-code emboss / deboss operations for FreeCAD.

Generates a QR code from a URL (or arbitrary text), converts the module
matrix into FreeCAD geometry, and applies it to a planar face via boolean
fuse (emboss) or cut (deboss).

Requires the ``qrcode`` Python package:
    pip install qrcode
"""

import math

import FreeCAD
from FreeCAD import Vector, Matrix
import Part

try:
    import qrcode
    import qrcode.constants
    _HAS_QRCODE = True
except ImportError:
    _HAS_QRCODE = False

# Map user-friendly error-correction labels to qrcode constants.
if _HAS_QRCODE:
    _EC_MAP = {
        "L": qrcode.constants.ERROR_CORRECT_L,
        "M": qrcode.constants.ERROR_CORRECT_M,
        "Q": qrcode.constants.ERROR_CORRECT_Q,
        "H": qrcode.constants.ERROR_CORRECT_H,
    }
else:
    _EC_MAP = {}


# ---------------------------------------------------------------------------
# QR matrix generation
# ---------------------------------------------------------------------------

def check_qrcode_available():
    """Raise *ImportError* with installation instructions when missing."""
    if not _HAS_QRCODE:
        raise ImportError(
            "The 'qrcode' Python package is required for QR code generation.\n\n"
            "Install it in FreeCAD's Python environment:\n"
            "  pip install qrcode\n\n"
            "Or from FreeCAD's Python console:\n"
            "  import subprocess, sys\n"
            "  subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'qrcode'])"
        )


def generate_qr_matrix(url, error_correction="M", border=2):
    """Return a 2-D boolean matrix for *url* (True = dark module).

    The returned matrix includes the quiet-zone border.
    """
    check_qrcode_available()
    ec = _EC_MAP.get(error_correction, _EC_MAP.get("M"))
    qr = qrcode.QRCode(
        version=None,
        error_correction=ec,
        box_size=1,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    return qr.get_matrix()


# ---------------------------------------------------------------------------
# Face-frame helpers (same algorithm as logo_deboss)
# ---------------------------------------------------------------------------

def _compute_face_frame(face):
    """Return *(center, u_axis, v_axis, normal)* for a planar *face*."""
    # Always use face.normalAt() which accounts for face orientation
    # (Forward/Reversed).  surface.Axis gives the mathematical plane
    # normal which can point inward on Reversed faces.
    u_min, u_max, v_min, v_max = face.ParameterRange
    normal = face.normalAt(
        (u_min + u_max) / 2.0, (v_min + v_max) / 2.0
    ).normalize()

    center = face.CenterOfMass

    ax, ay, az = abs(normal.x), abs(normal.y), abs(normal.z)
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


def _build_transform(center, u_axis, v_axis, normal, emboss=True):
    """4x4 matrix mapping local XY-plane onto the target face.

    *emboss=True*  -> local +Z maps to +normal (outward from body).
    *emboss=False* -> local +Z maps to -normal (into body / deboss).
    """
    if emboss:
        z_dir = normal
    else:
        z_dir = Vector(-normal.x, -normal.y, -normal.z)

    mat = Matrix()
    mat.A11, mat.A21, mat.A31 = u_axis.x, u_axis.y, u_axis.z
    mat.A12, mat.A22, mat.A32 = v_axis.x, v_axis.y, v_axis.z
    mat.A13, mat.A23, mat.A33 = z_dir.x, z_dir.y, z_dir.z
    mat.A14, mat.A24, mat.A34 = center.x, center.y, center.z
    return mat


# ---------------------------------------------------------------------------
# QR geometry builder
# ---------------------------------------------------------------------------

def _create_qr_solid(matrix, qr_size, height, overlap=0.01):
    """Build an extruded solid of all dark QR modules.

    The QR code is centred at the local origin in the XY plane.
    The solid extends from Z = -*overlap* to Z = +*height* so that it
    slightly penetrates the body surface for reliable boolean operations.

    Adjacent dark modules in the same row are merged into wider rectangles
    to reduce the number of shapes and speed up boolean operations.
    """
    n = len(matrix)
    if n == 0:
        return None

    module_size = qr_size / float(n)
    half = qr_size / 2.0
    z = -overlap

    # Row-merge: consecutive dark modules -> single wider rectangle
    rects = []
    for row in range(n):
        col = 0
        while col < n:
            if matrix[row][col]:
                start = col
                while col < n and matrix[row][col]:
                    col += 1
                x1 = -half + start * module_size
                x2 = -half + col * module_size
                # Row 0 is the top of the QR code; local +Y points up
                y2 = half - row * module_size
                y1 = half - (row + 1) * module_size
                rects.append((x1, y1, x2, y2))
            else:
                col += 1

    if not rects:
        return None

    # Build a Part.Face for each merged rectangle
    faces = []
    for x1, y1, x2, y2 in rects:
        pts = [
            Vector(x1, y1, z),
            Vector(x2, y1, z),
            Vector(x2, y2, z),
            Vector(x1, y2, z),
            Vector(x1, y1, z),
        ]
        wire = Part.makePolygon(pts)
        faces.append(Part.Face(wire))

    # Compound extrusion keeps all modules as one shape
    compound = Part.makeCompound(faces)
    solid = compound.extrude(Vector(0, 0, height + overlap))
    return solid


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply_qr(
    body_shape,
    face,
    url,
    size=20.0,
    height=0.5,
    emboss=True,
    error_correction="M",
    border=2,
    x_offset=0.0,
    y_offset=0.0,
):
    """Apply a QR code to *face* of *body_shape*.

    Parameters
    ----------
    body_shape : Part.Shape
        The solid body to modify.
    face : Part.Face
        Planar face on which to place the QR code.
    url : str
        Data to encode (typically a URL).
    size : float
        Side length of the QR code square in mm.
    height : float
        Emboss protrusion or deboss depth in mm.
    emboss : bool
        True -> raised (boolean fuse), False -> recessed (boolean cut).
    error_correction : str
        One of ``"L"``, ``"M"``, ``"Q"``, ``"H"``.
    border : int
        Quiet-zone width in modules (standard is 4; 2 is usually enough).
    x_offset : float
        Horizontal offset from face centre in mm.
    y_offset : float
        Vertical offset from face centre in mm.

    Returns
    -------
    (Part.Shape, float)
        The modified shape and the computed module size in mm.
    """
    # ---- generate matrix ---------------------------------------------------
    matrix = generate_qr_matrix(url, error_correction, border)
    n = len(matrix)
    module_size_mm = size / float(n)
    qr_version = (n - 2 * border - 17) // 4 + 1

    FreeCAD.Console.PrintMessage(
        "QR code: version {v}, {n}x{n} modules, "
        "module size {ms:.3f} mm\n".format(v=qr_version, n=n, ms=module_size_mm)
    )
    if module_size_mm < 0.3:
        FreeCAD.Console.PrintWarning(
            "Module size {:.3f} mm is very small – the code may be hard "
            "to print or scan.  Increase QR size or shorten the URL.\n"
            .format(module_size_mm)
        )

    # ---- build geometry ----------------------------------------------------
    solid = _create_qr_solid(matrix, size, height)
    if solid is None:
        raise RuntimeError("QR matrix produced no dark modules.")

    center, u_axis, v_axis, normal = _compute_face_frame(face)
    # Apply user-specified offset in the face plane
    placement = Vector(center)
    placement = placement + u_axis * x_offset + v_axis * y_offset
    mat = _build_transform(placement, u_axis, v_axis, normal, emboss)
    solid = solid.transformShape(mat)

    # ---- boolean operation -------------------------------------------------
    result = body_shape.copy()
    if emboss:
        result = result.fuse(solid)
    else:
        result = result.cut(solid)

    return result, module_size_mm
