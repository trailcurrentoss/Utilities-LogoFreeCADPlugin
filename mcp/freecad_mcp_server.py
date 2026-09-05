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
RPC_PORT = int(os.environ.get("FREECAD_RPC_PORT", "12785"))
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


def _format(result: dict) -> str:
    """Render an RPC result dict as text."""
    parts = []
    if result.get("stdout"):
        parts.append(result["stdout"].rstrip())
    if result.get("result"):
        parts.append(result["result"])
    if result.get("stderr"):
        parts.append("[stderr]\n" + result["stderr"].rstrip())
    if result.get("error"):
        parts.append("[error]\n" + result["error"].rstrip())
    if result.get("dialogs"):
        # A prompt was answered automatically. The operation may have taken a
        # default branch it would not have taken interactively, so say so
        # loudly rather than letting it look like a clean success.
        parts.append("[dialogs auto-dismissed -- the answer below was assumed]\n  "
                     + "\n  ".join(result["dialogs"]))
    return "\n".join(parts) if parts else "(no output)"


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

    return _format(result)


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
def set_expression(
    object_name: str,
    property_name: str,
    expression: str,
    document: str = "",
) -> str:
    """Bind an object property to a FreeCAD expression so it recomputes itself.

    PREFER THIS OVER WRITING A LITERAL VALUE. A property set to a number is dead
    geometry -- only whoever ran the script can change it. A property bound to an
    expression is driven by the model, and the user can edit it in the GUI.

    Typical use is driving dimensions from a spreadsheet alias:
        set_expression("pad_Rib01", "Length", "Design.thickness")
        set_expression("Pocket", "Length", "Design.wall * 2")

    Args:
        object_name: Object whose property to bind (e.g. "pad_Rib01").
        property_name: Property to drive (e.g. "Length", "Radius", "Angle").
        expression: FreeCAD expression, e.g. "Design.thickness" or "Box.Height / 2".
        document: Document name. Empty string for the active document.
    """
    return _call(textwrap.dedent("""\
        doc = App.getDocument({doc!r}) if {doc!r} else App.ActiveDocument
        obj = doc.getObject({name!r})
        if obj is None:
            print("ERROR: no object named", {name!r})
        else:
            obj.setExpression({prop!r}, {expr!r})
            doc.recompute()
            print("bound", {name!r} + "." + {prop!r}, "->", {expr!r})
            print("value now:", getattr(obj, {prop!r}, "?"))
    """).format(name=object_name, prop=property_name, expr=expression, doc=document))


@mcp.tool()
def clear_expression(object_name: str, property_name: str, document: str = "") -> str:
    """Remove an expression binding, leaving the property at its current value.

    Args:
        object_name: Object to unbind.
        property_name: Property to release.
        document: Document name. Empty string for the active document.
    """
    return _call(textwrap.dedent("""\
        doc = App.getDocument({doc!r}) if {doc!r} else App.ActiveDocument
        obj = doc.getObject({name!r})
        obj.setExpression({prop!r}, None)
        doc.recompute()
        print("cleared expression on", {name!r} + "." + {prop!r})
    """).format(name=object_name, prop=property_name, doc=document))


@mcp.tool()
def spreadsheet_set(
    sheet_name: str,
    cell: str,
    value: str,
    alias: str = "",
    document: str = "",
) -> str:
    """Write a cell in a Spreadsheet, optionally giving it an alias.

    A Spreadsheet of aliased inputs is FreeCAD's native place for design
    parameters. Put the inputs there and bind geometry to them with
    set_expression, instead of baking numbers into the objects.

    Values carry units: "19.05 mm", "3 in". Formulas start with "=" and may
    reference other aliases: "=rail_wing + extra_roll".

    Args:
        sheet_name: Spreadsheet object name. Created if it does not exist.
        cell: Cell address, e.g. "B4".
        value: Cell content -- a quantity, a number, text, or an "=" formula.
        alias: Optional alias for the cell, making it referenceable by name.
        document: Document name. Empty string for the active document.
    """
    return _call(textwrap.dedent("""\
        doc = App.getDocument({doc!r}) if {doc!r} else App.ActiveDocument
        sh = doc.getObject({sheet!r})
        if sh is None:
            sh = doc.addObject("Spreadsheet::Sheet", {sheet!r})
            print("created spreadsheet", {sheet!r})
        sh.set({cell!r}, {value!r})
        if {alias!r}:
            sh.setAlias({cell!r}, {alias!r})
        doc.recompute()
        print({cell!r}, "=", {value!r}, ("alias " + {alias!r}) if {alias!r} else "")
        if {alias!r}:
            print("resolves to:", sh.get({alias!r}))
    """).format(sheet=sheet_name, cell=cell, value=value, alias=alias, doc=document))


@mcp.tool()
def spreadsheet_get(sheet_name: str, cell_or_alias: str = "", document: str = "") -> str:
    """Read a spreadsheet cell or alias, or list every alias if none is given.

    Args:
        sheet_name: Spreadsheet object name.
        cell_or_alias: Cell address or alias. Empty lists all aliases.
        document: Document name. Empty string for the active document.
    """
    return _call(textwrap.dedent("""\
        doc = App.getDocument({doc!r}) if {doc!r} else App.ActiveDocument
        sh = doc.getObject({sheet!r})
        if sh is None:
            print("ERROR: no spreadsheet named", {sheet!r})
        elif {key!r}:
            print({key!r}, "=", sh.get({key!r}))
        else:
            props = [p for p in sh.PropertiesList if sh.getTypeIdOfProperty(p) != "App::PropertyString"]
            found = 0
            for p in sh.PropertiesList:
                try:
                    v = sh.get(p)
                except Exception:
                    continue
                print("  {{:<14s}} {{}}".format(p, v))
                found += 1
            if not found:
                print("(no aliases defined)")
    """).format(sheet=sheet_name, key=cell_or_alias, doc=document))


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
def set_visibility(
    object_names: str,
    visible: bool = True,
    document: str = "",
) -> str:
    """Show or hide objects, handling the cases that silently render nothing.

    Visibility in FreeCAD is not one flag. Three traps make a model vanish while
    every object still reports Visibility=True, and all three are handled here:

      * PartDesign: the Body's Tip feature is what draws, not the Body.
      * App::Link: renders nothing when its source Body's Tip is hidden.
      * Assembly / App::Part containers: hiding one hides every child.

    Args:
        object_names: Comma-separated names, or "*" for everything.
        visible: True to show, False to hide.
        document: Document name. Empty string for the active document.
    """
    return _call(textwrap.dedent("""\
        doc = App.getDocument({doc!r}) if {doc!r} else App.ActiveDocument
        names = {names!r}
        objs = doc.Objects if names.strip() == "*" else [
            doc.getObject(n.strip()) for n in names.split(",") if n.strip()]
        vis = {vis!r}
        done = 0
        for o in objs:
            if o is None:
                continue
            try:
                o.ViewObject.Visibility = vis
                done += 1
            except Exception:
                continue
            # a Body draws through its Tip feature
            if o.TypeId == "PartDesign::Body" and getattr(o, "Tip", None) is not None:
                try:
                    o.Tip.ViewObject.Visibility = True
                except Exception:
                    pass
            # a Link draws through its source Body's Tip
            if o.TypeId == "App::Link":
                src = getattr(o, "LinkedObject", None)
                if src is not None and getattr(src, "Tip", None) is not None:
                    try:
                        src.Tip.ViewObject.Visibility = True
                    except Exception:
                        pass
        doc.recompute()
        print("set Visibility=" + str(vis), "on", done, "object(s)")
        shown = [o.Name for o in doc.Objects
                 if getattr(getattr(o, "ViewObject", None), "Visibility", False)]
        print("visible now:", len(shown))
    """).format(names=object_names, vis=visible, doc=document))


@mcp.tool()
def measure(
    object_a: str,
    object_b: str = "",
    document: str = "",
) -> str:
    """Measure an object, or the distance and overlap between two.

    Use this to VERIFY a model rather than trusting that it built correctly.
    With one object you get its bounding box; with two you additionally get the
    minimum distance between them and their intersection volume.

    An intersection volume above zero on parts that should merely touch means
    they interfere. A distance above zero on parts that should mate means a gap.

    Args:
        object_a: First object name.
        object_b: Optional second object name.
        document: Document name. Empty string for the active document.
    """
    return _call(textwrap.dedent("""\
        IN = 25.4
        doc = App.getDocument({doc!r}) if {doc!r} else App.ActiveDocument
        def shape_of(o):
            if o.TypeId == "App::Link":
                b = o.LinkedObject.Shape
                s = b.copy()
                s.Placement = o.LinkPlacement.multiply(b.Placement)
                return s
            return o.Shape
        a = doc.getObject({a!r})
        if a is None:
            print("ERROR: no object named", {a!r})
        else:
            sa = shape_of(a); bb = sa.BoundBox
            print("{{}}: {{:.4f}} x {{:.4f}} x {{:.4f}} mm  ({{:.4f}} x {{:.4f}} x {{:.4f}} in)".format(
                a.Name, bb.XLength, bb.YLength, bb.ZLength,
                bb.XLength/IN, bb.YLength/IN, bb.ZLength/IN))
            print("  origin ({{:.4f}}, {{:.4f}}, {{:.4f}}) mm   volume {{:.3f}} in3".format(
                bb.XMin, bb.YMin, bb.ZMin, sa.Volume/IN**3))
            if {b!r}:
                bo = doc.getObject({b!r})
                if bo is None:
                    print("ERROR: no object named", {b!r})
                else:
                    sb = shape_of(bo)
                    dist = sa.distToShape(sb)[0]
                    common = sa.common(sb).Volume
                    print("  distance to {{}}: {{:.6f}} mm ({{:.6f}} in)".format(
                        bo.Name, dist, dist/IN))
                    print("  intersection   : {{:.6f}} mm3 ({{:.6f}} in3){{}}".format(
                        common, common/IN**3, "  <-- INTERFERENCE" if common > 1e-3 else ""))
    """).format(a=object_a, b=object_b, doc=document))


@mcp.tool()
def check_interference(object_names: str = "*", document: str = "") -> str:
    """Pairwise interference check across many objects.

    Reports every pair whose solids actually overlap. Bounding boxes are used to
    skip non-touching pairs, so this stays usable on assemblies with dozens of
    parts. Run it before believing an assembly is correct -- coincident
    placement numbers do not prove the solids mate.

    Args:
        object_names: Comma-separated names, or "*" for all links and solids.
        document: Document name. Empty string for the active document.
    """
    return _call(textwrap.dedent("""\
        IN = 25.4
        doc = App.getDocument({doc!r}) if {doc!r} else App.ActiveDocument
        names = {names!r}
        if names.strip() == "*":
            objs = [o for o in doc.Objects
                    if o.TypeId == "App::Link" or
                    (hasattr(o, "Shape") and o.Shape and o.Shape.Solids)]
        else:
            objs = [doc.getObject(n.strip()) for n in names.split(",") if n.strip()]
        def shape_of(o):
            if o.TypeId == "App::Link":
                b = o.LinkedObject.Shape
                s = b.copy()
                s.Placement = o.LinkPlacement.multiply(b.Placement)
                return s
            return o.Shape
        shp = [(o.Name, shape_of(o)) for o in objs if o is not None]
        hits = 0
        pairs = 0
        for i in range(len(shp)):
            for j in range(i + 1, len(shp)):
                n1, s1 = shp[i]; n2, s2 = shp[j]
                b1, b2 = s1.BoundBox, s2.BoundBox
                if not (b1.XMin < b2.XMax - 1e-7 and b2.XMin < b1.XMax - 1e-7 and
                        b1.YMin < b2.YMax - 1e-7 and b2.YMin < b1.YMax - 1e-7 and
                        b1.ZMin < b2.ZMax - 1e-7 and b2.ZMin < b1.ZMax - 1e-7):
                    continue
                pairs += 1
                v = s1.common(s2).Volume
                if v > 1e-3:
                    hits += 1
                    print("  INTERFERENCE {{}} x {{}}: {{:.6f}} in3".format(n1, n2, v/IN**3))
        print("checked {{}} object(s), {{}} overlapping bbox pair(s), {{}} real interference(s)".format(
            len(shp), pairs, hits))
    """).format(names=object_names, doc=document))


@mcp.tool()
def get_errors(document: str = "") -> str:
    """List objects that failed to recompute or are still touched.

    A FreeCAD document happily holds broken features. Nothing raises, the tree
    just shows a marker most scripted callers never look at, so a build can
    report success while several features are in error. Check this after any
    multi-step build.

    Args:
        document: Document name. Empty string for the active document.
    """
    return _call(textwrap.dedent("""\
        doc = App.getDocument({doc!r}) if {doc!r} else App.ActiveDocument
        bad, touched, nullshape = [], [], []
        for o in doc.Objects:
            if o.isError():
                bad.append(o.Name)
            if o.State and "Touched" in o.State:
                touched.append(o.Name)
            if hasattr(o, "Shape") and o.Shape is not None and o.Shape.isNull() \\
               and o.TypeId not in ("App::Part", "App::Link"):
                nullshape.append(o.Name)
        print("objects        :", len(doc.Objects))
        print("in error       :", len(bad), bad[:12])
        print("still touched  :", len(touched), touched[:12])
        print("null shape     :", len(nullshape), nullshape[:12])
        if not bad and not touched:
            print("document is clean")
    """).format(doc=document))


@mcp.tool()
def export_dxf(
    object_names: str,
    file_path: str,
    units: str = "in",
    deviation: float = 0.01,
    document: str = "",
) -> str:
    """Export flat geometry to a 2D DXF, 1:1, with no external library.

    Writes edges straight out of the shapes as DXF LINE entities. Curves are
    discretised to `deviation`. This is 1:1 geometry suitable for CAM, not a
    projected drawing view.

    Why not the obvious routes: FreeCAD's importDXF exporter needs a helper
    library it prompts to download, and that prompt deadlocks scripted sessions;
    TechDraw's writeDXFView was verified to emit an empty file here even for
    solids. Writing the entities directly avoids both.

    The entity count is verified before reporting success -- a DXF containing
    only headers is a failure, not an export.

    Args:
        object_names: Comma-separated object names (sketches, solids, or links).
        file_path: Destination .dxf path.
        units: "in" or "mm". FreeCAD works in mm; "in" divides by 25.4 and sets
            the DXF unit headers to inches.
        deviation: Chord tolerance for discretising curves, in output units.
        document: Document name. Empty string for the active document.
    """
    return _call(textwrap.dedent("""\
        doc = App.getDocument({doc!r}) if {doc!r} else App.ActiveDocument
        scale = 25.4 if {units!r} == "in" else 1.0
        insunits = 1 if {units!r} == "in" else 4
        objs = [doc.getObject(n.strip()) for n in {names!r}.split(",") if n.strip()]
        objs = [o for o in objs if o is not None]

        def shape_of(o):
            if o.TypeId == "App::Link":
                b = o.LinkedObject.Shape
                s = b.copy()
                s.Placement = o.LinkPlacement.multiply(b.Placement)
                return s
            return getattr(o, "Shape", None)

        segs = []
        for o in objs:
            sh = shape_of(o)
            if sh is None or sh.isNull():
                continue
            for e in sh.Edges:
                try:
                    pts = e.discretize(Deviation={dev!r} * scale)
                except Exception:
                    pts = [e.Vertexes[0].Point, e.Vertexes[-1].Point] \\
                          if len(e.Vertexes) >= 2 else []
                for i in range(len(pts) - 1):
                    a, b = pts[i], pts[i + 1]
                    if (a - b).Length > 1e-9:
                        segs.append((a.x / scale, a.y / scale,
                                     b.x / scale, b.y / scale))

        if not segs:
            print("FAILED: no edges found on", [o.Name for o in objs])
        else:
            out = ["999", "created by FreeCAD MCP",
                   "0", "SECTION", "2", "HEADER",
                   "9", "$INSUNITS", "70", str(insunits),
                   "9", "$MEASUREMENT", "70", "0" if {units!r} == "in" else "1",
                   "0", "ENDSEC",
                   "0", "SECTION", "2", "ENTITIES"]
            for x1, y1, x2, y2 in segs:
                out += ["0", "LINE", "8", "CUT",
                        "10", "%.6f" % x1, "20", "%.6f" % y1, "30", "0.0",
                        "11", "%.6f" % x2, "21", "%.6f" % y2, "31", "0.0"]
            out += ["0", "ENDSEC", "0", "EOF"]
            with open({path!r}, "w") as fh:
                fh.write("\\n".join(out) + "\\n")
            xs = [v for s in segs for v in (s[0], s[2])]
            ys = [v for s in segs for v in (s[1], s[3])]
            import os
            print("exported", {path!r}, os.path.getsize({path!r}), "bytes")
            print("  {{}} LINE entities from {{}} object(s)".format(len(segs), len(objs)))
            print("  extents {{:.4f}} x {{:.4f}} {{}}".format(
                max(xs) - min(xs), max(ys) - min(ys), {units!r}))
    """).format(names=object_names, path=file_path, units=units,
                dev=deviation, doc=document))


@mcp.tool()
def capture_screenshot(
    file_path: str,
    width: int = 1920,
    height: int = 1080,
    method: str = "auto",
) -> str:
    """Capture a screenshot of the current FreeCAD 3D view.

    The image is checked for content before returning. A blank screenshot
    otherwise reads as success, and the caller carries on believing it saw
    the model. When the image is empty this retries with an on-screen grab
    and, if that is empty too, says the scene has nothing visible in it.

    Args:
        file_path: Where to save the image (e.g. "/tmp/freecad_view.png").
        width: Image width in pixels (offscreen only; a widget grab uses the
            viewport's own size).
        height: Image height in pixels.
        method: "auto", "offscreen", or "widget".
    """
    try:
        result = _rpc().screenshot(file_path, width, height, "Current", method)
    except Exception as e:  # server too old to expose screenshot()
        return _call(textwrap.dedent("""\
            view = Gui.ActiveDocument.ActiveView
            view.saveImage({path!r}, {w}, {h}, "Current")
            print("Screenshot saved to", {path!r})
            print("NOTE: reload the FreeCAD MCP workbench to enable "
                  "blank-render detection ({err})")
        """).format(path=file_path, w=width, h=height, err=e))
    return _format(result)


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
