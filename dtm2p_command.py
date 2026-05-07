"""FreeCAD command and task-panel UI for the DTM2P Termination Housing tool."""

import os
import FreeCAD
import FreeCADGui
import Part

from FreeCAD import Vector
from PySide import QtWidgets, QtCore

_plugin_dir = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# FeaturePython proxy & ViewProvider (enables double-click re-edit)
# ---------------------------------------------------------------------------

class _DTM2PProxy:
    """Data proxy for a DTM2P PartDesign::FeatureAdditivePython."""

    def __init__(self, obj):
        obj.Proxy = self

    def execute(self, obj):
        """Recompute the fused shape."""
        FreeCAD.Console.PrintMessage(
            "DTM2P.execute() called for {}\n".format(obj.Name))
        if not hasattr(obj, "DTM2P_FaceName"):
            FreeCAD.Console.PrintWarning(
                "DTM2P.execute(): no DTM2P_FaceName property yet\n")
            return

        # Ensure the frame storage properties exist (added in v2.4 — older
        # documents won't have them yet).
        _ensure_frame_properties(obj)

        if hasattr(obj, "BaseFeature") and obj.BaseFeature is not None:
            base_shape = obj.BaseFeature.Shape
        elif hasattr(obj, "DTM2P_OriginalBody") and obj.DTM2P_OriginalBody:
            original = FreeCAD.ActiveDocument.getObject(
                obj.DTM2P_OriginalBody)
            if original is None or original.Shape.isNull():
                return
            base_shape = original.Shape
        else:
            return

        try:
            from dtm2p_geometry import (
                place_housing_from_frame,
                compute_face_frame, compute_edge_frame,
            )

            anchor, u_axis, v_axis, normal = _resolve_frame(obj, base_shape)
            if anchor is None:
                return

            new_shape = place_housing_from_frame(
                base_shape, anchor, u_axis, v_axis, normal,
                x_offset=getattr(obj, "DTM2P_XOffset", 0.0),
                y_offset=getattr(obj, "DTM2P_YOffset", 0.0),
                rotation=getattr(obj, "DTM2P_Rotation", 0.0),
            )
            if new_shape and not new_shape.isNull():
                new_shape.transformShape(
                    obj.Placement.inverse().toMatrix(), True)
                obj.Shape = new_shape
                if hasattr(obj, "AddSubShape"):
                    tool = new_shape.cut(base_shape)
                    tool.transformShape(
                        obj.Placement.inverse().toMatrix(), True)
                    obj.AddSubShape = tool
        except Exception as e:
            FreeCAD.Console.PrintError(
                "DTM2P recompute failed: {}\n".format(e))

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None


class _DTM2PViewProvider:
    """ViewProvider that enables double-click re-editing of DTM2P objects."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def _open_edit_panel(self, obj):
        if not hasattr(obj, "DTM2P_FaceName"):
            return False

        original = _get_dtm2p_base_object(obj)
        if original is None:
            QtWidgets.QMessageBox.warning(
                None, "DTM2P",
                "Cannot re-edit: the original body object was deleted.",
            )
            return True

        prefill = {
            "x_offset": getattr(obj, "DTM2P_XOffset", 0.0),
            "y_offset": getattr(obj, "DTM2P_YOffset", 0.0),
            "rotation": getattr(obj, "DTM2P_Rotation", 0.0),
        }
        edge_name = getattr(obj, "DTM2P_EdgeName", "")
        initial_frame = None
        _ensure_frame_properties(obj)
        if _frame_is_set(obj):
            initial_frame = (
                Vector(obj.DTM2P_FrameAnchor),
                Vector(obj.DTM2P_FrameU),
                Vector(obj.DTM2P_FrameV),
                Vector(obj.DTM2P_FrameNormal),
            )
        panel = DTM2PTaskPanel(
            original, obj.DTM2P_FaceName,
            edge_name=edge_name,
            edit_obj=obj, prefill=prefill,
            initial_frame=initial_frame,
        )
        FreeCADGui.Control.showDialog(panel)
        return True

    def doubleClicked(self, vobj):
        try:
            return self._open_edit_panel(vobj.Object)
        except Exception as e:
            FreeCAD.Console.PrintError(
                "DTM2P doubleClicked error: {}\n".format(e))
            return False

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return False
        try:
            return self._open_edit_panel(vobj.Object)
        except Exception as e:
            FreeCAD.Console.PrintError(
                "DTM2P setEdit error: {}\n".format(e))
            return False

    def unsetEdit(self, vobj, mode=0):
        FreeCADGui.Control.closeDialog()
        return True

    def getIcon(self):
        return os.path.join(
            _plugin_dir, "resources", "icons", "DTM2P.svg"
        )

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_body(obj):
    """Return the PartDesign::Body that *obj* belongs to, or None."""
    if hasattr(obj, "TypeId") and obj.TypeId == "PartDesign::Body":
        return obj
    if hasattr(obj, "getParentGeoFeatureGroup"):
        parent = obj.getParentGeoFeatureGroup()
        if (parent is not None
                and hasattr(parent, "TypeId")
                and parent.TypeId == "PartDesign::Body"):
            return parent
    return None


def _add_dtm2p_properties(obj):
    """Add custom storage properties to a DTM2P feature object."""
    obj.addProperty(
        "App::PropertyFloat", "DTM2P_XOffset", "DTM2P",
        "Offset along the face U axis (mm)")
    obj.addProperty(
        "App::PropertyFloat", "DTM2P_YOffset", "DTM2P",
        "Offset along the face V axis (mm)")
    obj.addProperty(
        "App::PropertyFloat", "DTM2P_Rotation", "DTM2P",
        "Rotation angle on the face (degrees)")
    obj.addProperty(
        "App::PropertyString", "DTM2P_FaceName", "DTM2P",
        "Face used on the original body (display only)")
    obj.addProperty(
        "App::PropertyString", "DTM2P_EdgeName", "DTM2P",
        "Edge used for front alignment (display only)")
    obj.addProperty(
        "App::PropertyString", "DTM2P_OriginalBody", "DTM2P",
        "Original body object name")
    _ensure_frame_properties(obj)


def _ensure_frame_properties(obj):
    """Add frame-storage properties if not already present.

    The frame (anchor + U/V/normal) is the source of truth for placement
    at execute time. Storing it directly decouples the housing position
    from face/edge index lookups, which is what made placement break when
    other DTM features were added or removed from the body chain.
    """
    if not hasattr(obj, "DTM2P_FrameAnchor"):
        obj.addProperty(
            "App::PropertyVector", "DTM2P_FrameAnchor", "DTM2P",
            "Frame anchor point in world coordinates")
    if not hasattr(obj, "DTM2P_FrameU"):
        obj.addProperty(
            "App::PropertyVector", "DTM2P_FrameU", "DTM2P",
            "Frame U axis (housing local X)")
    if not hasattr(obj, "DTM2P_FrameV"):
        obj.addProperty(
            "App::PropertyVector", "DTM2P_FrameV", "DTM2P",
            "Frame V axis (housing local Y)")
    if not hasattr(obj, "DTM2P_FrameNormal"):
        obj.addProperty(
            "App::PropertyVector", "DTM2P_FrameNormal", "DTM2P",
            "Frame normal (housing local Z, outward from face)")


def _frame_is_set(obj):
    """Return True if the stored frame on *obj* looks valid."""
    n = getattr(obj, "DTM2P_FrameNormal", None)
    return n is not None and n.Length > 1e-9


def _store_frame(obj, anchor, u_axis, v_axis, normal):
    _ensure_frame_properties(obj)
    obj.DTM2P_FrameAnchor = Vector(anchor)
    obj.DTM2P_FrameU = Vector(u_axis)
    obj.DTM2P_FrameV = Vector(v_axis)
    obj.DTM2P_FrameNormal = Vector(normal)


def _resolve_frame(obj, base_shape):
    """Return (anchor, u, v, normal) for *obj*.

    Prefers the stored frame. Falls back to looking up face/edge by name
    on *base_shape* (one-time migration) for older documents.
    """
    from dtm2p_geometry import compute_face_frame, compute_edge_frame

    if _frame_is_set(obj):
        return (
            Vector(obj.DTM2P_FrameAnchor),
            Vector(obj.DTM2P_FrameU),
            Vector(obj.DTM2P_FrameV),
            Vector(obj.DTM2P_FrameNormal),
        )

    # Migration path: derive frame from face_name on the current base.
    face_name = getattr(obj, "DTM2P_FaceName", "")
    if not face_name:
        return (None, None, None, None)
    try:
        face_idx = int(face_name.replace("Face", ""))
    except ValueError:
        return (None, None, None, None)
    if face_idx < 1 or face_idx > len(base_shape.Faces):
        FreeCAD.Console.PrintWarning(
            "DTM2P: stored {} no longer resolves on base shape "
            "({} faces). Open the edit panel and click "
            "'Re-attach to selection' to point it at the correct face.\n"
            .format(face_name, len(base_shape.Faces)))
        return (None, None, None, None)
    face = base_shape.Faces[face_idx - 1]

    edge = None
    edge_name = getattr(obj, "DTM2P_EdgeName", "")
    if edge_name:
        try:
            edge_idx = int(edge_name.replace("Edge", ""))
            if 1 <= edge_idx <= len(base_shape.Edges):
                edge = base_shape.Edges[edge_idx - 1]
        except ValueError:
            pass

    if edge is not None:
        anchor, u, v, n = compute_edge_frame(face, edge)
    else:
        anchor, u, v, n = compute_face_frame(face)

    _store_frame(obj, anchor, u, v, n)
    FreeCAD.Console.PrintMessage(
        "DTM2P: migrated {} frame to absolute coordinates.\n"
        .format(obj.Name))
    return anchor, u, v, n


def _get_dtm2p_base_object(obj):
    """Return the base object that a DTM2P result was derived from."""
    if hasattr(obj, "BaseFeature") and obj.BaseFeature is not None:
        return obj.BaseFeature
    orig_name = getattr(obj, "DTM2P_OriginalBody", None)
    if orig_name:
        return FreeCAD.ActiveDocument.getObject(orig_name)
    return None


def _read_face_edge_from_selection(skip_obj=None):
    """Read the first Face (and optional Edge) from the active selection.

    Returns (source_obj, face_name, face, edge_name, edge) or
    (None, "", None, "", None) if nothing usable is selected.
    Selections matching *skip_obj* are ignored so the panel can scan past
    a re-selected DTM feature itself.
    """
    sel = FreeCADGui.Selection.getSelectionEx()
    for s in sel:
        if skip_obj is not None and s.Object is skip_obj:
            continue
        if not s.SubElementNames:
            continue
        face_name = ""
        edge_name = ""
        for n in s.SubElementNames:
            if n.startswith("Face") and not face_name:
                face_name = n
            elif n.startswith("Edge") and not edge_name:
                edge_name = n
        if not face_name:
            continue
        try:
            face = getattr(s.Object.Shape, face_name)
        except Exception:
            continue
        edge = None
        if edge_name:
            try:
                edge = getattr(s.Object.Shape, edge_name)
            except Exception:
                edge_name = ""
        return s.Object, face_name, face, edge_name, edge
    return None, "", None, "", None


# ---------------------------------------------------------------------------
# Task Panel (sidebar UI)
# ---------------------------------------------------------------------------

class DTM2PTaskPanel:
    """Task panel shown in the FreeCAD sidebar when the DTM2P command is active."""

    def __init__(self, body_obj, face_name, edge_name="",
                 edit_obj=None, prefill=None, initial_frame=None):
        self.body_obj = body_obj
        self.face_name = face_name
        self.edge_name = edge_name
        self.edit_obj = edit_obj
        # Frame is computed lazily from face/edge in accept(), or refreshed
        # by the "Re-attach to selection" button while editing. For edit
        # mode an initial_frame from stored properties keeps the housing
        # in place even if face_name no longer resolves on base_shape.
        self._frame = initial_frame
        self.form = self._build_ui()
        if prefill:
            self._apply_prefill(prefill)
        self._refresh_attachment_label()

    def _build_ui(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        layout.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.AllNonFixedFieldsGrow
        )

        header = QtWidgets.QLabel("<b>DTM2P Termination Housing</b>")
        header.setAlignment(QtCore.Qt.AlignCenter)
        layout.addRow(header)

        info = QtWidgets.QLabel(
            "<i>Places a Deutsch DTM04-2P termination housing\n"
            "onto the selected face, extending outward.</i>"
        )
        info.setWordWrap(True)
        layout.addRow(info)

        self.attachment_label = QtWidgets.QLabel("")
        self.attachment_label.setWordWrap(True)
        layout.addRow(self.attachment_label)

        # Re-attach button is only useful when editing an existing feature.
        if self.edit_obj is not None:
            self.reattach_btn = QtWidgets.QPushButton(
                "Re-attach to selection"
            )
            self.reattach_btn.setToolTip(
                "Select a Face (and optional Edge) in the 3D view, then\n"
                "click here to re-anchor this housing without rebuilding\n"
                "the model. Useful when upstream geometry has changed."
            )
            self.reattach_btn.clicked.connect(self._on_reattach_clicked)
            layout.addRow(self.reattach_btn)

        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        layout.addRow(sep)

        self.x_offset_spin = QtWidgets.QDoubleSpinBox()
        self.x_offset_spin.setRange(-500.0, 500.0)
        self.x_offset_spin.setValue(0.0)
        self.x_offset_spin.setSingleStep(1.0)
        self.x_offset_spin.setDecimals(1)
        self.x_offset_spin.setSuffix(" mm")
        self.x_label = QtWidgets.QLabel("X Offset:")
        layout.addRow(self.x_label, self.x_offset_spin)

        self.y_offset_spin = QtWidgets.QDoubleSpinBox()
        self.y_offset_spin.setRange(-500.0, 500.0)
        self.y_offset_spin.setValue(0.0)
        self.y_offset_spin.setSingleStep(1.0)
        self.y_offset_spin.setDecimals(1)
        self.y_offset_spin.setSuffix(" mm")
        self.y_label = QtWidgets.QLabel("Y Offset:")
        layout.addRow(self.y_label, self.y_offset_spin)

        self.rotation_spin = QtWidgets.QDoubleSpinBox()
        self.rotation_spin.setRange(-180.0, 180.0)
        self.rotation_spin.setValue(0.0)
        self.rotation_spin.setSingleStep(5.0)
        self.rotation_spin.setDecimals(1)
        self.rotation_spin.setSuffix(" deg")
        self.rotation_spin.setToolTip(
            "Rotation angle on the face (degrees)."
        )
        layout.addRow("Rotation:", self.rotation_spin)

        return widget

    def _refresh_attachment_label(self):
        body_label = (self.body_obj.Label
                      if self.body_obj is not None else "?")
        if self.edge_name:
            self.attachment_label.setText(
                "<b>Attached to:</b> {}.{}<br/>"
                "<b>Front aligned to:</b> {}".format(
                    body_label, self.face_name, self.edge_name)
            )
            self.x_label.setText("Along Edge:")
            self.x_offset_spin.setToolTip(
                "Offset along the edge direction.")
            self.y_label.setText("From Edge:")
            self.y_offset_spin.setToolTip(
                "Offset perpendicular to the edge (positive = away from edge).")
        else:
            self.attachment_label.setText(
                "<b>Attached to:</b> {}.{}<br/>"
                "<i>Tip: Select a Face + Edge to align the housing front "
                "to the edge.</i>".format(body_label, self.face_name)
            )
            self.x_label.setText("X Offset:")
            self.x_offset_spin.setToolTip(
                "Offset along the model X axis (projected onto the face).")
            self.y_label.setText("Y Offset:")
            self.y_offset_spin.setToolTip(
                "Offset along the model Y axis (projected onto the face).")

    def _on_reattach_clicked(self):
        src_obj, face_name, face, edge_name, edge = \
            _read_face_edge_from_selection(skip_obj=self.edit_obj)
        if src_obj is None or face is None:
            QtWidgets.QMessageBox.information(
                None, "DTM2P",
                "Select a Face (and optionally an Edge) on a body in the\n"
                "3D view, then click 'Re-attach to selection' again."
            )
            return

        surface = face.Surface
        is_planar = hasattr(surface, "Axis") or isinstance(
            surface, Part.Plane)
        if not is_planar:
            QtWidgets.QMessageBox.warning(
                None, "Non-Planar Face",
                "Please select a flat (planar) face."
            )
            return

        from dtm2p_geometry import compute_face_frame, compute_edge_frame
        if edge is not None:
            self._frame = compute_edge_frame(face, edge)
        else:
            self._frame = compute_face_frame(face)

        self.body_obj = src_obj
        self.face_name = face_name
        self.edge_name = edge_name
        self._refresh_attachment_label()
        FreeCAD.Console.PrintMessage(
            "DTM2P: re-attached to {}.{}{}\n".format(
                src_obj.Label, face_name,
                " + " + edge_name if edge_name else ""))

    def _apply_prefill(self, p):
        if "x_offset" in p:
            self.x_offset_spin.setValue(p["x_offset"])
        if "y_offset" in p:
            self.y_offset_spin.setValue(p["y_offset"])
        if "rotation" in p:
            self.rotation_spin.setValue(p["rotation"])

    def _resolve_frame_for_accept(self):
        """Return (anchor, u, v, normal) — refresh from current selection if needed."""
        if self._frame is not None:
            return self._frame
        from dtm2p_geometry import compute_face_frame, compute_edge_frame
        body_shape = self.body_obj.Shape
        face = getattr(body_shape, self.face_name)
        edge = (getattr(body_shape, self.edge_name, None)
                if self.edge_name else None)
        if edge is not None:
            return compute_edge_frame(face, edge)
        return compute_face_frame(face)

    def accept(self):
        from dtm2p_geometry import place_housing_from_frame

        doc = FreeCAD.ActiveDocument

        x_offset = self.x_offset_spin.value()
        y_offset = self.y_offset_spin.value()
        rotation = self.rotation_spin.value()

        try:
            anchor, u_axis, v_axis, normal = self._resolve_frame_for_accept()
        except Exception as e:
            FreeCAD.Console.PrintError(
                "DTM2P frame computation failed: {}\n".format(e))
            QtWidgets.QMessageBox.critical(
                None, "DTM2P Error",
                "Could not compute a placement frame from the\n"
                "selected face/edge:\n\n{}".format(e))
            return False

        # For new placements (no existing PD edit) we need the body shape
        # for the fuse preview path; for PD edits the proxy.execute() will
        # do the fuse against BaseFeature, so we just need to validate.
        body = _find_body(self.body_obj)
        is_pd_edit = (self.edit_obj is not None
                      and hasattr(self.edit_obj, "BaseFeature"))

        # Validate the fuse for the non-PartDesign path so we can show a
        # helpful error before mutating the document.
        if not is_pd_edit:
            try:
                new_shape = place_housing_from_frame(
                    self.body_obj.Shape,
                    anchor, u_axis, v_axis, normal,
                    x_offset=x_offset,
                    y_offset=y_offset,
                    rotation=rotation,
                )
            except Exception as e:
                FreeCAD.Console.PrintError(
                    "DTM2P placement failed: {}\n".format(e))
                QtWidgets.QMessageBox.critical(
                    None, "DTM2P Error",
                    "Fuse operation failed:\n\n{}\n\n"
                    "Make sure you selected a flat face with enough "
                    "room for the housing.".format(e))
                return False

        if is_pd_edit:
            result_obj = self.edit_obj
            result_obj.DTM2P_XOffset = x_offset
            result_obj.DTM2P_YOffset = y_offset
            result_obj.DTM2P_Rotation = rotation
            result_obj.DTM2P_FaceName = self.face_name
            result_obj.DTM2P_EdgeName = self.edge_name
            _store_frame(result_obj, anchor, u_axis, v_axis, normal)
        elif body is not None:
            result_obj = doc.addObject(
                "PartDesign::FeatureAdditivePython", "DTM2P")
            _DTM2PProxy(result_obj)
            _DTM2PViewProvider(result_obj.ViewObject)
            _add_dtm2p_properties(result_obj)
            result_obj.DTM2P_XOffset = x_offset
            result_obj.DTM2P_YOffset = y_offset
            result_obj.DTM2P_Rotation = rotation
            result_obj.DTM2P_FaceName = self.face_name
            result_obj.DTM2P_EdgeName = self.edge_name
            result_obj.DTM2P_OriginalBody = body.Name
            _store_frame(result_obj, anchor, u_axis, v_axis, normal)
            body.addObject(result_obj)
        else:
            if self.edit_obj is not None:
                doc.removeObject(self.edit_obj.Name)
            result_obj = doc.addObject("Part::FeaturePython", "DTM2P")
            _DTM2PProxy(result_obj)
            _DTM2PViewProvider(result_obj.ViewObject)
            _add_dtm2p_properties(result_obj)
            result_obj.DTM2P_XOffset = x_offset
            result_obj.DTM2P_YOffset = y_offset
            result_obj.DTM2P_Rotation = rotation
            result_obj.DTM2P_FaceName = self.face_name
            result_obj.DTM2P_EdgeName = self.edge_name
            result_obj.DTM2P_OriginalBody = self.body_obj.Name
            _store_frame(result_obj, anchor, u_axis, v_axis, normal)
            result_obj.Shape = new_shape
            self.body_obj.ViewObject.Visibility = False
            if hasattr(self.body_obj, "ViewObject"):
                src_vo = self.body_obj.ViewObject
                dst_vo = result_obj.ViewObject
                if hasattr(src_vo, "ShapeColor"):
                    dst_vo.ShapeColor = src_vo.ShapeColor
                if hasattr(src_vo, "Transparency"):
                    dst_vo.Transparency = src_vo.Transparency

        doc.recompute()
        FreeCADGui.Control.closeDialog()
        FreeCAD.Console.PrintMessage(
            "DTM2P housing placed onto {}.{}{}\n"
            .format(self.body_obj.Label, self.face_name,
                    " aligned to " + self.edge_name if self.edge_name else "")
        )
        return True

    def reject(self):
        FreeCADGui.Control.closeDialog()
        return True

    def getStandardButtons(self):
        return (
            QtWidgets.QDialogButtonBox.Ok
            | QtWidgets.QDialogButtonBox.Cancel
        )


# ---------------------------------------------------------------------------
# FreeCAD Command
# ---------------------------------------------------------------------------

class DTM2PCommand:
    """FreeCAD command that places a DTM2P termination housing onto a face."""

    def GetResources(self):
        return {
            "Pixmap": os.path.join(
                _plugin_dir, "resources", "icons", "DTM2P.svg"
            ),
            "MenuText": "Place DTM2P Housing",
            "ToolTip": (
                "DTM2P\n"
                "Place a Deutsch DTM04-2P termination housing onto the\n"
                "selected flat face, extending outward from the surface.\n"
                "Select a Face + Edge to align the housing front to the edge.\n"
                "Select an existing DTM2P result to re-edit."
            ),
        }

    def IsActive(self):
        sel = FreeCADGui.Selection.getSelectionEx()
        if len(sel) != 1:
            return False
        obj = sel[0].Object
        if hasattr(obj, "DTM2P_FaceName"):
            return True
        if not sel[0].SubElementNames:
            return False
        # Active if at least one Face is selected
        return any(n.startswith("Face") for n in sel[0].SubElementNames)

    def Activated(self):
        sel = FreeCADGui.Selection.getSelectionEx()
        if not sel:
            return

        obj = sel[0].Object
        sub_names = sel[0].SubElementNames
        has_face_sub = (
            bool(sub_names) and any(n.startswith("Face") for n in sub_names)
        )

        # --- Re-edit an existing DTM2P result (only when no face is selected) ---
        if hasattr(obj, "DTM2P_FaceName") and not has_face_sub:
            original = _get_dtm2p_base_object(obj)
            if original is None:
                QtWidgets.QMessageBox.warning(
                    None, "DTM2P",
                    "Cannot re-edit: the original body object was deleted.",
                )
                return
            prefill = {
                "x_offset": getattr(obj, "DTM2P_XOffset", 0.0),
                "y_offset": getattr(obj, "DTM2P_YOffset", 0.0),
                "rotation": getattr(obj, "DTM2P_Rotation", 0.0),
            }
            edge_name = getattr(obj, "DTM2P_EdgeName", "")
            initial_frame = None
            _ensure_frame_properties(obj)
            if _frame_is_set(obj):
                initial_frame = (
                    Vector(obj.DTM2P_FrameAnchor),
                    Vector(obj.DTM2P_FrameU),
                    Vector(obj.DTM2P_FrameV),
                    Vector(obj.DTM2P_FrameNormal),
                )
            panel = DTM2PTaskPanel(
                original, obj.DTM2P_FaceName,
                edge_name=edge_name,
                edit_obj=obj, prefill=prefill,
                initial_frame=initial_frame,
            )
            FreeCADGui.Control.showDialog(panel)
            return

        # --- New placement: extract face and optional edge ---
        face_name = ""
        edge_name = ""
        for name in sub_names:
            if name.startswith("Face") and not face_name:
                face_name = name
            elif name.startswith("Edge") and not edge_name:
                edge_name = name

        if not face_name:
            return

        face = getattr(obj.Shape, face_name)

        # Validate: face must be planar
        surface = face.Surface
        is_planar = hasattr(surface, "Axis") or isinstance(
            surface, Part.Plane
        )
        if not is_planar:
            QtWidgets.QMessageBox.warning(
                None,
                "Non-Planar Face",
                "Please select a flat (planar) face.\n"
                "The DTM2P housing can only be placed on flat surfaces.",
            )
            return

        panel = DTM2PTaskPanel(obj, face_name, edge_name=edge_name)
        FreeCADGui.Control.showDialog(panel)


FreeCADGui.addCommand("TrailCurrent_DTM2P", DTM2PCommand())
