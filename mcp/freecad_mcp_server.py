#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP server for FreeCAD integration.

Connects to the XML-RPC server running inside FreeCAD and exposes
FreeCAD operations as MCP tools for use by Claude Code and other
MCP-compatible AI assistants.

Usage
-----
  # With uv (recommended — zero-install):
  uv run --with mcp python3 freecad_mcp_server.py

  # Or if mcp is already installed:
  python3 freecad_mcp_server.py

  # Add to Claude Code:
  claude mcp add freecad -- uv run --with mcp python3 /path/to/freecad_mcp_server.py
"""

# -- Path fix: prevent our parent addon's mcp/ directory (this very
# directory) from shadowing the 'mcp' pip package. Python prepends the
# script's directory to sys.path, and the parent also ends up there when
# the CWD is the addon root.
import os as _os
import sys as _sys

_this_dir = _os.path.dirname(_os.path.abspath(__file__))
_addon_dir = _os.path.dirname(_this_dir)
for _p in ("", _this_dir, _addon_dir):
    while _p in _sys.path:
        _sys.path.remove(_p)
del _this_dir, _addon_dir, _p
# -- End path fix

import json
import os
import textwrap
import xmlrpc.client

from mcp.server.fastmcp import FastMCP

# ── Configuration ──────────────────────────────────────────────────

RPC_HOST = os.environ.get("FREECAD_RPC_HOST", "127.0.0.1")
RPC_PORT = int(os.environ.get("FREECAD_RPC_PORT", "9876"))
RPC_URL = "http://{}:{}/RPC2".format(RPC_HOST, RPC_PORT)

mcp = FastMCP(
    name="FreeCAD",
    instructions=textwrap.dedent("""\
        MCP server for interacting with a running FreeCAD instance.
        FreeCAD must be open with the MCP RPC server started
        (TrailCurrent Logo workbench → MCP Server button).

        The most powerful tool is execute_code, which runs arbitrary
        Python inside FreeCAD's interpreter. The convenience tools
        cover common operations without needing to write Python.

        In FreeCAD's Python environment, these modules are pre-imported:
          FreeCAD / App, FreeCADGui / Gui, Part, Mesh, Draft,
          Sketcher, PartDesign, Import, BOPTools

        Key patterns:
          doc = App.ActiveDocument
          obj = doc.getObject("Box")
          obj.Height = 20
          doc.recompute()
    """),
)


def _rpc():
    """Get an XML-RPC proxy to FreeCAD."""
    return xmlrpc.client.ServerProxy(RPC_URL, allow_none=True)


def _call(code: str) -> str:
    """Execute code in FreeCAD and return formatted output."""
    try:
        proxy = _rpc()
        result = proxy.execute(code)
    except ConnectionRefusedError:
        return (
            "ERROR: Cannot connect to FreeCAD RPC server at {}. "
            "Make sure FreeCAD is running and the MCP RPC server is started "
            "(TrailCurrent Logo workbench > MCP Server toolbar button)."
        ).format(RPC_URL)
    except Exception as e:
        return "ERROR: RPC call failed: {}".format(e)

    parts = []
    if result.get("stdout"):
        parts.append(result["stdout"].rstrip())
    if result.get("result"):
        parts.append(result["result"])
    if result.get("stderr"):
        parts.append("[stderr]\n" + result["stderr"].rstrip())
    if result.get("error"):
        parts.append("[error]\n" + result["error"].rstrip())

    return "\n".join(parts) if parts else "(no output)"


# ── Tools ──────────────────────────────────────────────────────────


@mcp.tool()
def execute_code(code: str) -> str:
    """Execute arbitrary Python code inside FreeCAD's interpreter.

    The code runs on FreeCAD's main thread with full access to all
    FreeCAD modules (App, Gui, Part, Mesh, Draft, etc.).

    Use print() to produce output. If the code is a single expression,
    its repr() is returned automatically.

    Examples:
      # List all objects in the active document
      for obj in App.ActiveDocument.Objects:
          print(obj.Name, obj.TypeId)

      # Create a box
      doc = App.ActiveDocument or App.newDocument("Unnamed")
      box = doc.addObject("Part::Box", "MyBox")
      box.Length = 50
      box.Width = 30
      box.Height = 10
      doc.recompute()

      # Boolean cut
      cut = doc.addObject("Part::Cut", "MyCut")
      cut.Base = doc.getObject("Box")
      cut.Tool = doc.getObject("Cylinder")
      doc.recompute()
    """
    return _call(code)


@mcp.tool()
def list_documents() -> str:
    """List all open FreeCAD documents with their names and file paths."""
    return _call(textwrap.dedent("""\
        import json
        docs = []
        for name, doc in App.listDocuments().items():
            docs.append({
                "name": doc.Name,
                "label": doc.Label,
                "filename": doc.FileName or "(unsaved)",
                "object_count": len(doc.Objects),
            })
        print(json.dumps(docs, indent=2))
    """))


@mcp.tool()
def get_document_info(document: str = "") -> str:
    """Get detailed info about a document including all its objects.

    Args:
        document: Document name. Empty string for the active document.
    """
    return _call(textwrap.dedent("""\
        import json
        doc_name = {doc!r}
        doc = App.getDocument(doc_name) if doc_name else App.ActiveDocument
        if doc is None:
            print("ERROR: No active document")
        else:
            objects = []
            for obj in doc.Objects:
                info = {{
                    "name": obj.Name,
                    "label": obj.Label,
                    "type": obj.TypeId,
                    "visibility": obj.ViewObject.Visibility if hasattr(obj, "ViewObject") and obj.ViewObject else None,
                }}
                if hasattr(obj, "Shape") and obj.Shape and not obj.Shape.isNull():
                    s = obj.Shape
                    shape_info = {{
                        "type": s.ShapeType,
                        "volume": round(s.Volume, 4),
                        "area": round(s.Area, 4),
                    }}
                    try:
                        bb = s.BoundBox
                        shape_info["bounds"] = {{
                            "min": [round(bb.XMin, 4), round(bb.YMin, 4), round(bb.ZMin, 4)],
                            "max": [round(bb.XMax, 4), round(bb.YMax, 4), round(bb.ZMax, 4)],
                        }}
                    except Exception:
                        pass
                    info["shape"] = shape_info
                objects.append(info)
            result = {{
                "name": doc.Name,
                "label": doc.Label,
                "filename": doc.FileName or "(unsaved)",
                "objects": objects,
            }}
            print(json.dumps(result, indent=2, default=str))
    """).format(doc=document))


@mcp.tool()
def get_object_properties(object_name: str, document: str = "") -> str:
    """Get all properties of a FreeCAD object.

    Args:
        object_name: The internal Name of the object.
        document: Document name. Empty string for active document.
    """
    return _call(textwrap.dedent("""\
        import json
        doc_name = {doc!r}
        doc = App.getDocument(doc_name) if doc_name else App.ActiveDocument
        if doc is None:
            print("ERROR: No active document")
        else:
            obj = doc.getObject({name!r})
            if obj is None:
                print("ERROR: Object {name!r} not found")
            else:
                props = {{}}
                for p in obj.PropertiesList:
                    try:
                        val = getattr(obj, p)
                        # Make values JSON-serializable
                        if hasattr(val, "x") and hasattr(val, "y") and hasattr(val, "z"):
                            val = {{"x": val.x, "y": val.y, "z": val.z}}
                        elif hasattr(val, "Base") and hasattr(val, "Rotation"):
                            val = {{
                                "Base": {{"x": val.Base.x, "y": val.Base.y, "z": val.Base.z}},
                                "Rotation": list(val.Rotation.Q),
                            }}
                        elif isinstance(val, (list, tuple)):
                            val = [str(v) for v in val]
                        elif not isinstance(val, (int, float, bool, str, type(None))):
                            val = str(val)
                        props[p] = val
                    except Exception as e:
                        props[p] = "<error: {{}}>".format(e)
                info = {{
                    "name": obj.Name,
                    "label": obj.Label,
                    "type": obj.TypeId,
                    "properties": props,
                }}
                print(json.dumps(info, indent=2, default=str))
    """).format(name=object_name, doc=document))


@mcp.tool()
def set_object_property(
    object_name: str,
    property_name: str,
    value: str,
    document: str = "",
) -> str:
    """Set a property on a FreeCAD object.

    The value is evaluated as a Python expression in FreeCAD's context,
    so you can use FreeCAD types like App.Vector(1, 2, 3).

    Args:
        object_name: The internal Name of the object.
        property_name: The property to set (e.g. "Height", "Label").
        value: Python expression for the value (e.g. "42.0", "'MyLabel'",
               "App.Vector(0, 0, 1)").
        document: Document name. Empty string for active document.
    """
    return _call(textwrap.dedent("""\
        doc = App.getDocument({doc!r}) if {doc!r} else App.ActiveDocument
        obj = doc.getObject({name!r})
        if obj is None:
            print("ERROR: Object {name!r} not found")
        else:
            setattr(obj, {prop!r}, {value})
            doc.recompute()
            new_val = getattr(obj, {prop!r})
            print("Set {name}.{prop} = " + repr(new_val))
    """).format(
        name=object_name,
        prop=property_name,
        value=value,
        doc=document,
    ))


@mcp.tool()
def create_document(name: str = "Unnamed") -> str:
    """Create a new empty FreeCAD document.

    Args:
        name: Name for the new document.
    """
    return _call("doc = App.newDocument({!r})\nprint('Created document:', doc.Name)".format(name))


@mcp.tool()
def open_document(file_path: str) -> str:
    """Open a FreeCAD document file (.FCStd).

    Args:
        file_path: Absolute path to the .FCStd file.
    """
    return _call(textwrap.dedent("""\
        doc = App.openDocument({path!r})
        print("Opened:", doc.Name, "({{}})".format(doc.FileName))
        print("Objects:", len(doc.Objects))
    """).format(path=file_path))


@mcp.tool()
def save_document(file_path: str = "", document: str = "") -> str:
    """Save a FreeCAD document.

    Args:
        file_path: Path to save to. Empty to save in-place.
        document: Document name. Empty string for active document.
    """
    return _call(textwrap.dedent("""\
        doc = App.getDocument({doc!r}) if {doc!r} else App.ActiveDocument
        if doc is None:
            print("ERROR: No active document")
        else:
            path = {path!r}
            if path:
                doc.saveAs(path)
                print("Saved as:", path)
            else:
                doc.save()
                print("Saved:", doc.FileName)
    """).format(path=file_path, doc=document))


@mcp.tool()
def close_document(document: str = "") -> str:
    """Close a FreeCAD document.

    Args:
        document: Document name. Empty string for active document.
    """
    return _call(textwrap.dedent("""\
        doc = App.getDocument({doc!r}) if {doc!r} else App.ActiveDocument
        if doc is None:
            print("ERROR: No active document")
        else:
            name = doc.Name
            App.closeDocument(name)
            print("Closed document:", name)
    """).format(doc=document))


@mcp.tool()
def add_object(
    type_id: str,
    name: str,
    document: str = "",
) -> str:
    """Add a new object to a FreeCAD document.

    Common type_ids:
      Part::Box, Part::Cylinder, Part::Sphere, Part::Cone, Part::Torus,
      Part::Cut, Part::Fuse, Part::Common, Part::Extrusion,
      Part::Feature, Part::FeaturePython,
      Mesh::Feature, Sketcher::SketchObject,
      PartDesign::Body, PartDesign::Pad, PartDesign::Pocket

    Args:
        type_id: FreeCAD object type (e.g. "Part::Box").
        name: Name for the new object.
        document: Document name. Empty string for active document.
    """
    return _call(textwrap.dedent("""\
        doc = App.getDocument({doc!r}) if {doc!r} else App.ActiveDocument
        if doc is None:
            doc = App.newDocument("Unnamed")
        obj = doc.addObject({type_id!r}, {name!r})
        doc.recompute()
        print("Created", obj.Name, "(" + obj.TypeId + ")")
    """).format(type_id=type_id, name=name, doc=document))


@mcp.tool()
def remove_object(object_name: str, document: str = "") -> str:
    """Remove an object from a FreeCAD document.

    Args:
        object_name: The internal Name of the object to remove.
        document: Document name. Empty string for active document.
    """
    return _call(textwrap.dedent("""\
        doc = App.getDocument({doc!r}) if {doc!r} else App.ActiveDocument
        if doc is None:
            print("ERROR: No active document")
        else:
            doc.removeObject({name!r})
            doc.recompute()
            print("Removed:", {name!r})
    """).format(name=object_name, doc=document))


@mcp.tool()
def get_selection() -> str:
    """Get the currently selected objects in FreeCAD."""
    return _call(textwrap.dedent("""\
        import json
        sel = Gui.Selection.getSelectionEx()
        if not sel:
            print("(nothing selected)")
        else:
            items = []
            for s in sel:
                info = {
                    "object": s.ObjectName,
                    "document": s.DocumentName,
                    "type": s.Object.TypeId if s.Object else None,
                    "sub_elements": list(s.SubElementNames) if s.SubElementNames else [],
                }
                items.append(info)
            print(json.dumps(items, indent=2))
    """))


@mcp.tool()
def recompute(document: str = "") -> str:
    """Recompute (rebuild) all objects in a FreeCAD document.

    Args:
        document: Document name. Empty string for active document.
    """
    return _call(textwrap.dedent("""\
        doc = App.getDocument({doc!r}) if {doc!r} else App.ActiveDocument
        if doc is None:
            print("ERROR: No active document")
        else:
            touched = doc.recompute()
            print("Recomputed", len(touched) if touched else 0, "objects in", doc.Name)
    """).format(doc=document))


@mcp.tool()
def export_object(
    object_names: str,
    file_path: str,
    document: str = "",
) -> str:
    """Export one or more objects to a file (STEP, STL, BREP, OBJ, etc.).

    The format is determined by the file extension.

    Args:
        object_names: Comma-separated list of object names to export.
        file_path: Output file path with extension (e.g. "/tmp/part.step").
        document: Document name. Empty string for active document.
    """
    return _call(textwrap.dedent("""\
        import Part as _Part
        doc = App.getDocument({doc!r}) if {doc!r} else App.ActiveDocument
        if doc is None:
            print("ERROR: No active document")
        else:
            names = [n.strip() for n in {names!r}.split(",")]
            objs = [doc.getObject(n) for n in names]
            missing = [n for n, o in zip(names, objs) if o is None]
            if missing:
                print("ERROR: Objects not found:", missing)
            else:
                shapes = [o.Shape for o in objs if hasattr(o, "Shape")]
                if not shapes:
                    print("ERROR: No exportable shapes found")
                else:
                    _Part.export(shapes, {path!r})
                    print("Exported", len(shapes), "shape(s) to", {path!r})
    """).format(names=object_names, path=file_path, doc=document))


@mcp.tool()
def capture_screenshot(
    file_path: str,
    width: int = 1920,
    height: int = 1080,
) -> str:
    """Capture a screenshot of the current FreeCAD 3D view.

    Args:
        file_path: Where to save the image (e.g. "/tmp/freecad_view.png").
        width: Image width in pixels.
        height: Image height in pixels.
    """
    return _call(textwrap.dedent("""\
        view = Gui.ActiveDocument.ActiveView
        view.saveImage({path!r}, {w}, {h}, "Current")
        print("Screenshot saved to", {path!r})
    """).format(path=file_path, w=width, h=height))


@mcp.tool()
def fit_view() -> str:
    """Fit the 3D view to show all objects."""
    return _call("Gui.SendMsgToActiveView('ViewFit')\nprint('View fitted')")


@mcp.tool()
def import_file(file_path: str, document: str = "") -> str:
    """Import a file (STEP, IGES, STL, SVG, DXF, etc.) into a document.

    Args:
        file_path: Path to the file to import.
        document: Document name. Empty string for active document.
    """
    return _call(textwrap.dedent("""\
        import Import
        doc = App.getDocument({doc!r}) if {doc!r} else App.ActiveDocument
        if doc is None:
            doc = App.newDocument("Imported")
        Import.insert({path!r}, doc.Name)
        doc.recompute()
        print("Imported", {path!r}, "into", doc.Name)
        print("Objects now:", len(doc.Objects))
    """).format(path=file_path, doc=document))


# ── Entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
