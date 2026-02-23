"""Blender Python script: Product photography studio scene.

Launched by the FreeCAD "Send to Blender" command.
Usage: blender --python blender_studio_template.py -- --stl <path> [options]

All scene manipulation uses data-level API (bpy.data) rather than
bpy.ops operators, which require a 3D viewport context that may not
exist when running via --python.
"""

import bpy
import bmesh
import sys
import argparse
import math
import os
import struct
from mathutils import Vector, Matrix


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args():
    """Parse arguments passed after Blender's -- separator."""
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    parser = argparse.ArgumentParser(description="Studio scene setup")
    parser.add_argument("--stl", required=True, help="Path to STL file")
    parser.add_argument("--material", default="white_plastic",
                        help="Material preset name")
    parser.add_argument("--freecad-color", default="0.8,0.8,0.8",
                        help="R,G,B color from FreeCAD (0-1 range)")
    parser.add_argument("--resolution", nargs=2, type=int,
                        default=[1920, 1080], help="Render resolution W H")
    parser.add_argument("--samples", type=int, default=256,
                        help="Cycles render samples")
    parser.add_argument("--focal-length", type=float, default=85.0,
                        help="Camera focal length in mm")
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Scene setup (all data-level, no bpy.ops)
# ---------------------------------------------------------------------------

def clear_scene():
    """Remove all default objects using data-level API."""
    # Remove all objects from every collection
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    # Clean up orphan data blocks
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    for cam in list(bpy.data.cameras):
        if cam.users == 0:
            bpy.data.cameras.remove(cam)
    for light in list(bpy.data.lights):
        if light.users == 0:
            bpy.data.lights.remove(light)
    for mat in list(bpy.data.materials):
        if mat.users == 0:
            bpy.data.materials.remove(mat)


def setup_render_engine(samples, res_x, res_y):
    """Configure Cycles render engine with GPU fallback to CPU."""
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = res_x
    scene.render.resolution_y = res_y
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False

    # Try GPU rendering, fall back to CPU
    try:
        cycles_prefs = bpy.context.preferences.addons['cycles'].preferences
        cycles_prefs.get_devices()
        for device_type in ['OPTIX', 'CUDA', 'HIP', 'METAL']:
            try:
                cycles_prefs.compute_device_type = device_type
                cycles_prefs.get_devices()
                for dev in cycles_prefs.devices:
                    dev.use = True
                scene.cycles.device = 'GPU'
                break
            except Exception:
                continue
        else:
            scene.cycles.device = 'CPU'
    except Exception:
        scene.cycles.device = 'CPU'

    # White world background at low strength for subtle ambient fill
    world = bpy.data.worlds.new("StudioWorld")
    scene.world = world
    world.use_nodes = True
    bg_node = world.node_tree.nodes["Background"]
    bg_node.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    bg_node.inputs["Strength"].default_value = 0.3


# ---------------------------------------------------------------------------
# Model import and positioning (data-level where possible)
# ---------------------------------------------------------------------------

def _is_binary_stl(filepath):
    """Determine whether an STL file is binary or ASCII format.

    Uses file-size validation rather than checking for a 'solid' prefix,
    because some binary STL files have headers that start with 'solid'.
    """
    file_size = os.path.getsize(filepath)
    if file_size < 84:
        return False
    with open(filepath, 'rb') as f:
        f.read(80)  # skip header
        num_triangles = struct.unpack('<I', f.read(4))[0]
    expected_size = 84 + (num_triangles * 50)
    return file_size == expected_size


def _read_stl_binary(filepath):
    """Read a binary STL file. Return list of ((v1), (v2), (v3)) tuples."""
    with open(filepath, 'rb') as f:
        f.read(80)  # skip header
        num_triangles = struct.unpack('<I', f.read(4))[0]
        triangles = []
        for _ in range(num_triangles):
            data = f.read(50)
            if len(data) < 50:
                break
            # Skip normal (12 bytes), read 3 vertices (9 floats), skip attr (2 bytes)
            vals = struct.unpack('<12x9f2x', data)
            v1 = (vals[0], vals[1], vals[2])
            v2 = (vals[3], vals[4], vals[5])
            v3 = (vals[6], vals[7], vals[8])
            triangles.append((v1, v2, v3))
    return triangles


def _read_stl_ascii(filepath):
    """Read an ASCII STL file. Return list of ((v1), (v2), (v3)) tuples."""
    triangles = []
    current_verts = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('vertex'):
                parts = line.split()
                current_verts.append((
                    float(parts[1]), float(parts[2]), float(parts[3])
                ))
                if len(current_verts) == 3:
                    triangles.append(tuple(current_verts))
                    current_verts = []
    return triangles


def _import_stl_data_level(stl_path):
    """Import an STL file using pure data-level API (no bpy.ops).

    Reads both binary and ASCII STL formats.  Deduplicates vertices
    for clean mesh topology.  Returns the created bpy.types.Object,
    or None on failure.
    """
    if not os.path.isfile(stl_path):
        print("ERROR: STL file not found: {}".format(stl_path))
        return None

    try:
        if _is_binary_stl(stl_path):
            triangles = _read_stl_binary(stl_path)
        else:
            triangles = _read_stl_ascii(stl_path)
    except Exception as e:
        print("ERROR: Failed to parse STL file: {}".format(e))
        return None

    if not triangles:
        print("ERROR: STL file contains no triangles.")
        return None

    # Build mesh via bmesh with vertex deduplication
    bm = bmesh.new()
    vert_cache = {}
    precision = 6

    for v1_co, v2_co, v3_co in triangles:
        face_verts = []
        for co in (v1_co, v2_co, v3_co):
            key = (round(co[0], precision),
                   round(co[1], precision),
                   round(co[2], precision))
            if key not in vert_cache:
                vert_cache[key] = bm.verts.new(co)
            face_verts.append(vert_cache[key])

        # Skip degenerate faces where vertices coincide after dedup
        if (face_verts[0] == face_verts[1]
                or face_verts[1] == face_verts[2]
                or face_verts[0] == face_verts[2]):
            continue

        try:
            bm.faces.new(face_verts)
        except ValueError:
            pass  # duplicate face — skip

    mesh_name = os.path.splitext(os.path.basename(stl_path))[0]
    mesh_data = bpy.data.meshes.new(mesh_name)
    bm.to_mesh(mesh_data)
    bm.free()
    mesh_data.update()

    obj = bpy.data.objects.new(mesh_name, mesh_data)
    bpy.context.collection.objects.link(obj)
    return obj


def import_stl(stl_path):
    """Import the STL file and return the imported object.

    Uses a pure data-level STL parser (no bpy.ops) so the import works
    reliably when Blender is launched via --python without a 3D viewport.
    """
    return _import_stl_data_level(stl_path)


def _get_mesh_bounds(obj):
    """Compute world-space bounding box from mesh vertices directly.

    Does not rely on obj.bound_box (which can be stale) or any ops calls.
    """
    mesh = obj.data
    mat = obj.matrix_world

    if not mesh.vertices:
        return Vector((0, 0, 0)), Vector((0, 0, 0)), 0.001

    world_verts = [mat @ v.co for v in mesh.vertices]
    min_v = Vector((
        min(v.x for v in world_verts),
        min(v.y for v in world_verts),
        min(v.z for v in world_verts),
    ))
    max_v = Vector((
        max(v.x for v in world_verts),
        max(v.y for v in world_verts),
        max(v.z for v in world_verts),
    ))

    center = (min_v + max_v) / 2.0
    size = max(max_v.x - min_v.x, max_v.y - min_v.y, max_v.z - min_v.z)
    return min_v, max_v, center, max(size, 0.001)


def apply_scale_to_mesh(obj):
    """Bake the object's scale into its mesh vertices (replaces ops.transform_apply)."""
    mesh = obj.data
    scale = obj.scale.copy()

    if scale.x == 1.0 and scale.y == 1.0 and scale.z == 1.0:
        return

    scale_mat = Matrix.Diagonal(scale).to_4x4()
    mesh.transform(scale_mat)
    mesh.update()
    obj.scale = (1.0, 1.0, 1.0)


def center_model_on_floor(obj):
    """Move model so its bottom sits on Z=0 and it is centered on XY origin.

    Returns (center, size) of the repositioned model.
    Uses direct mesh/matrix manipulation instead of bpy.ops.
    """
    min_v, max_v, center, size = _get_mesh_bounds(obj)

    # Shift so bottom is at Z=0 and XY is centered at origin
    obj.location.x -= center.x
    obj.location.y -= center.y
    obj.location.z -= min_v.z

    # Recompute bounds after move
    bpy.context.view_layer.update()
    min_v, max_v, center, size = _get_mesh_bounds(obj)
    return center, size


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------

def _set_bsdf_input(bsdf, name, value, fallback_name=None):
    """Set a Principled BSDF input, handling renamed inputs across versions."""
    if name in bsdf.inputs:
        bsdf.inputs[name].default_value = value
    elif fallback_name and fallback_name in bsdf.inputs:
        bsdf.inputs[fallback_name].default_value = value


def apply_material(obj, material_type, freecad_color_str):
    """Apply a material preset to the model. Sets smooth shading via mesh API."""
    if material_type == "raw":
        return

    mat = bpy.data.materials.new("ModelMaterial")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]

    if material_type == "match_freecad":
        r, g, b = [float(c) for c in freecad_color_str.split(",")]
        bsdf.inputs["Base Color"].default_value = (r, g, b, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.4
    elif material_type == "white_plastic":
        bsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.95, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.3
        _set_bsdf_input(bsdf, "Specular IOR Level", 0.5, "Specular")
    elif material_type == "dark_grey_plastic":
        bsdf.inputs["Base Color"].default_value = (0.15, 0.15, 0.15, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.35
        _set_bsdf_input(bsdf, "Specular IOR Level", 0.5, "Specular")
    elif material_type == "brushed_aluminum":
        bsdf.inputs["Base Color"].default_value = (0.85, 0.85, 0.87, 1.0)
        bsdf.inputs["Metallic"].default_value = 1.0
        bsdf.inputs["Roughness"].default_value = 0.25

    obj.data.materials.clear()
    obj.data.materials.append(mat)

    # Smooth shading via mesh data (no ops call needed)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    obj.data.update()


# ---------------------------------------------------------------------------
# Studio environment
# ---------------------------------------------------------------------------

def create_cyclorama(model_size):
    """Create a curved white backdrop (cyclorama) behind and under the model.

    A cyclorama is a seamless floor-to-wall surface used in photography
    studios. The floor is flat, then curves upward into a vertical wall.
    """
    scale = max(model_size, 0.01) * 3.0

    mesh = bpy.data.meshes.new("Cyclorama")
    bm = bmesh.new()

    segments = 16
    width = scale * 2.0
    depth = scale * 1.5
    height = scale * 1.5
    curve_radius = scale * 0.5
    cols = 12

    rows = []

    # Floor section (flat, extends forward from the model)
    floor_steps = 8
    for i in range(floor_steps):
        y = -depth + (depth - curve_radius) * (i / max(floor_steps - 1, 1))
        row = []
        for j in range(cols):
            x = -width + 2.0 * width * (j / max(cols - 1, 1))
            row.append(bm.verts.new((x, y, 0.0)))
        rows.append(row)

    # Curved section (quarter circle from floor to wall)
    for i in range(1, segments + 1):
        angle = (math.pi / 2) * (i / segments)
        y = (depth - curve_radius) + curve_radius * math.sin(angle)
        z = curve_radius * (1.0 - math.cos(angle))
        row = []
        for j in range(cols):
            x = -width + 2.0 * width * (j / max(cols - 1, 1))
            row.append(bm.verts.new((x, y, z)))
        rows.append(row)

    # Vertical wall section (extends upward)
    wall_steps = 4
    for i in range(1, wall_steps + 1):
        z = curve_radius + height * (i / wall_steps)
        row = []
        for j in range(cols):
            x = -width + 2.0 * width * (j / max(cols - 1, 1))
            row.append(bm.verts.new((x, depth, z)))
        rows.append(row)

    # Create faces between adjacent rows
    for i in range(len(rows) - 1):
        for j in range(len(rows[i]) - 1):
            bm.faces.new([
                rows[i][j], rows[i][j + 1],
                rows[i + 1][j + 1], rows[i + 1][j]
            ])

    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("Cyclorama", mesh)
    bpy.context.collection.objects.link(obj)

    # White matte material
    mat = bpy.data.materials.new("CycloramaMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    bsdf.inputs["Roughness"].default_value = 1.0
    _set_bsdf_input(bsdf, "Specular IOR Level", 0.0, "Specular")
    obj.data.materials.append(mat)

    # Smooth shading via mesh data
    for poly in obj.data.polygons:
        poly.use_smooth = True
    obj.data.update()

    return obj


def create_three_point_lighting(model_center, model_size):
    """Create key, fill, and rim lights for product photography."""
    s = max(model_size, 0.01)

    def _make_area_light(name, energy, size, color, location):
        data = bpy.data.lights.new(name, 'AREA')
        data.energy = energy
        data.size = size
        data.color = color
        obj = bpy.data.objects.new(name, data)
        bpy.context.collection.objects.link(obj)
        obj.location = location
        # Point at model center
        direction = model_center - obj.location
        obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
        return obj

    key = _make_area_light(
        "KeyLight",
        energy=500 * (s ** 2),
        size=s * 1.5,
        color=(1.0, 0.98, 0.95),
        location=(
            model_center.x + s * 2.0,
            model_center.y - s * 1.5,
            model_center.z + s * 2.5,
        ),
    )
    fill = _make_area_light(
        "FillLight",
        energy=200 * (s ** 2),
        size=s * 2.5,
        color=(0.95, 0.97, 1.0),
        location=(
            model_center.x - s * 2.5,
            model_center.y - s * 1.0,
            model_center.z + s * 1.5,
        ),
    )
    rim = _make_area_light(
        "RimLight",
        energy=350 * (s ** 2),
        size=s * 1.0,
        color=(1.0, 1.0, 1.0),
        location=(
            model_center.x - s * 0.5,
            model_center.y + s * 2.5,
            model_center.z + s * 3.0,
        ),
    )
    return key, fill, rim


def setup_camera(model_center, model_size, focal_length):
    """Create and position a camera for product photography."""
    cam_data = bpy.data.cameras.new("StudioCamera")
    cam_data.lens = focal_length
    cam_data.clip_start = 0.001
    cam_data.clip_end = max(model_size * 100, 10.0)

    cam_obj = bpy.data.objects.new("StudioCamera", cam_data)
    bpy.context.collection.objects.link(cam_obj)

    # Distance scales with focal length (longer lens = farther back)
    distance = max(model_size, 0.01) * (focal_length / 35.0) * 2.5
    cam_obj.location = (
        model_center.x + distance * 0.4,
        model_center.y - distance,
        model_center.z + model_size * 0.6,
    )

    # Track-To constraint to keep camera aimed at model center
    target = bpy.data.objects.new("CameraTarget", None)
    target.location = model_center
    bpy.context.collection.objects.link(target)
    target.empty_display_size = 0.01

    constraint = cam_obj.constraints.new('TRACK_TO')
    constraint.target = target
    constraint.track_axis = 'TRACK_NEGATIVE_Z'
    constraint.up_axis = 'UP_Y'

    bpy.context.scene.camera = cam_obj
    return cam_obj


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    print("=== FreeCAD -> Blender Studio Setup ===")
    print("STL: {}".format(args.stl))

    clear_scene()
    print("Scene cleared.")

    setup_render_engine(args.samples, args.resolution[0], args.resolution[1])
    print("Render engine configured (Cycles, {} samples).".format(args.samples))

    # Import STL
    model = import_stl(args.stl)
    if model is None:
        print("ERROR: No object imported from STL. Aborting.")
        return
    print("Imported: {} ({} polygons)".format(
        model.name, len(model.data.polygons)))

    # FreeCAD exports in mm; Blender defaults to meters.
    # Scale mesh vertices directly from mm to m.
    model.scale = (0.001, 0.001, 0.001)
    bpy.context.view_layer.update()
    apply_scale_to_mesh(model)
    print("Scale applied (mm -> m).")

    # Center on floor
    model_center, model_size = center_model_on_floor(model)
    print("Model centered. Size: {:.4f} m, Center: ({:.4f}, {:.4f}, {:.4f})".format(
        model_size, model_center.x, model_center.y, model_center.z))

    # Apply material
    apply_material(model, args.material, args.freecad_color)
    print("Material applied: {}".format(args.material))

    # Build studio environment
    create_cyclorama(model_size)
    print("Cyclorama created.")

    create_three_point_lighting(model_center, model_size)
    print("3-point lighting created.")

    setup_camera(model_center, model_size, args.focal_length)
    print("Camera set up (focal length: {} mm).".format(args.focal_length))

    # Select model as active object
    for obj in bpy.data.objects:
        obj.select_set(False)
    model.select_set(True)
    bpy.context.view_layer.objects.active = model

    print("=== Studio scene ready. Press F12 to render. ===")


if __name__ == "__main__":
    main()
