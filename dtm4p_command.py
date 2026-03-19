"""FreeCAD command and task-panel UI for the DTM4P Termination Housing tool."""

import os
import FreeCAD
import FreeCADGui
import Part

from PySide import QtWidgets, QtCore

_plugin_dir = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# FeaturePython proxy & ViewProvider (enables double-click re-edit)
# ---------------------------------------------------------------------------

class _DTM4PProxy:
    """Data proxy for a DTM4P PartDesign::FeatureAdditivePython."""

    def __init__(self, obj):
        obj.Proxy = self

    def execute(self, obj):
        """Recompute the fused shape."""
        FreeCAD.Console.PrintMessage(
            "DTM4P.execute() called for {}\n".format(obj.Name))
        if not hasattr(obj, "DTM4P_FaceName"):
            FreeCAD.Console.PrintWarning(
                "DTM4P.execute(): no DTM4P_FaceName property yet\n")
            return

        if hasattr(obj, "BaseFeature") and obj.BaseFeature is not None:
            base_shape = obj.BaseFeature.Shape
        elif hasattr(obj, "DTM4P_OriginalBody") and obj.DTM4P_OriginalBody:
            original = FreeCAD.ActiveDocument.getObject(
                obj.DTM4P_OriginalBody)
            if original is None or original.Shape.isNull():
                return
            base_shape = original.Shape
        else:
            return

        try:
            from dtm4p_geometry import place_housing
            face_name = obj.DTM4P_FaceName
            if not face_name:
                return
            face_idx = int(face_name.replace("Face", ""))
            if face_idx < 1 or face_idx > len(base_shape.Faces):
                FreeCAD.Console.PrintWarning(
                    "DTM4P: {} not found on base shape "
                    "(has {} faces), keeping existing shape.\n"
                    .format(face_name, len(base_shape.Faces)))
                return
            face = base_shape.Faces[face_idx - 1]

            # Resolve edge if stored
            edge = None
            edge_name = getattr(obj, "DTM4P_EdgeName", "")
            if edge_name:
                edge_idx = int(edge_name.replace("Edge", ""))
                if 1 <= edge_idx <= len(base_shape.Edges):
                    edge = base_shape.Edges[edge_idx - 1]

            new_shape = place_housing(
                base_shape, face,
                x_offset=getattr(obj, "DTM4P_XOffset", 0.0),
                y_offset=getattr(obj, "DTM4P_YOffset", 0.0),
                rotation=getattr(obj, "DTM4P_Rotation", 0.0),
                edge=edge,
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
                "DTM4P recompute failed: {}\n".format(e))

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None


class _DTM4PViewProvider:
    """ViewProvider that enables double-click re-editing of DTM4P objects."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def _open_edit_panel(self, obj):
        if not hasattr(obj, "DTM4P_FaceName"):
            return False

        original = _get_dtm4p_base_object(obj)
        if original is None:
            QtWidgets.QMessageBox.warning(
                None, "DTM4P",
                "Cannot re-edit: the original body object was deleted.",
            )
            return True

        prefill = {
            "x_offset": getattr(obj, "DTM4P_XOffset", 0.0),
            "y_offset": getattr(obj, "DTM4P_YOffset", 0.0),
            "rotation": getattr(obj, "DTM4P_Rotation", 0.0),
        }
        edge_name = getattr(obj, "DTM4P_EdgeName", "")
        panel = DTM4PTaskPanel(
            original, obj.DTM4P_FaceName,
            edge_name=edge_name,
            edit_obj=obj, prefill=prefill,
        )
        FreeCADGui.Control.showDialog(panel)
        return True

    def doubleClicked(self, vobj):
        try:
            return self._open_edit_panel(vobj.Object)
        except Exception as e:
            FreeCAD.Console.PrintError(
                "DTM4P doubleClicked error: {}\n".format(e))
            return False

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return False
        try:
            return self._open_edit_panel(vobj.Object)
        except Exception as e:
            FreeCAD.Console.PrintError(
                "DTM4P setEdit error: {}\n".format(e))
            return False

    def unsetEdit(self, vobj, mode=0):
        FreeCADGui.Control.closeDialog()
        return True

    def getIcon(self):
        return os.path.join(
            _plugin_dir, "resources", "icons", "DTM4P.svg"
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


def _add_dtm4p_properties(obj):
    """Add custom storage properties to a DTM4P feature object."""
    obj.addProperty(
        "App::PropertyFloat", "DTM4P_XOffset", "DTM4P",
        "Offset along the face U axis (mm)")
    obj.addProperty(
        "App::PropertyFloat", "DTM4P_YOffset", "DTM4P",
        "Offset along the face V axis (mm)")
    obj.addProperty(
        "App::PropertyFloat", "DTM4P_Rotation", "DTM4P",
        "Rotation angle on the face (degrees)")
    obj.addProperty(
        "App::PropertyString", "DTM4P_FaceName", "DTM4P",
        "Face used on the original body")
    obj.addProperty(
        "App::PropertyString", "DTM4P_EdgeName", "DTM4P",
        "Edge used for front alignment (optional)")
    obj.addProperty(
        "App::PropertyString", "DTM4P_OriginalBody", "DTM4P",
        "Original body object name")


def _get_dtm4p_base_object(obj):
    """Return the base object that a DTM4P result was derived from."""
    if hasattr(obj, "BaseFeature") and obj.BaseFeature is not None:
        return obj.BaseFeature
    orig_name = getattr(obj, "DTM4P_OriginalBody", None)
    if orig_name:
        return FreeCAD.ActiveDocument.getObject(orig_name)
    return None


# ---------------------------------------------------------------------------
# Task Panel (sidebar UI)
# ---------------------------------------------------------------------------

class DTM4PTaskPanel:
    """Task panel shown in the FreeCAD sidebar when the DTM4P command is active."""

    def __init__(self, body_obj, face_name, edge_name="",
                 edit_obj=None, prefill=None):
        self.body_obj = body_obj
        self.face_name = face_name
        self.edge_name = edge_name
        self.edit_obj = edit_obj
        self.form = self._build_ui()
        if prefill:
            self._apply_prefill(prefill)

    def _build_ui(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        layout.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.AllNonFixedFieldsGrow
        )

        header = QtWidgets.QLabel("<b>DTM4P Termination Housing</b>")
        header.setAlignment(QtCore.Qt.AlignCenter)
        layout.addRow(header)

        info = QtWidgets.QLabel(
            "<i>Places a Deutsch DTM04-4P termination housing\n"
            "onto the selected face, extending outward.</i>"
        )
        info.setWordWrap(True)
        layout.addRow(info)

        # Edge alignment info
        if self.edge_name:
            edge_label = QtWidgets.QLabel(
                "<b>Front aligned to:</b> {}".format(self.edge_name)
            )
            layout.addRow(edge_label)
        else:
            edge_label = QtWidgets.QLabel(
                "<i>Tip: Select a Face + Edge to align the\n"
                "housing front to the edge.</i>"
            )
            edge_label.setWordWrap(True)
            layout.addRow(edge_label)

        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        layout.addRow(sep)

        self.x_offset_spin = QtWidgets.QDoubleSpinBox()
        self.x_offset_spin.setRange(-500.0, 500.0)
        self.x_offset_spin.setValue(0.0)
        self.x_offset_spin.setSingleStep(1.0)
        self.x_offset_spin.setDecimals(1)
        self.x_offset_spin.setSuffix(" mm")
        if self.edge_name:
            self.x_offset_spin.setToolTip(
                "Offset along the edge direction.")
            layout.addRow("Along Edge:", self.x_offset_spin)
        else:
            self.x_offset_spin.setToolTip(
                "Offset along the model X axis (projected onto the face).")
            layout.addRow("X Offset:", self.x_offset_spin)

        self.y_offset_spin = QtWidgets.QDoubleSpinBox()
        self.y_offset_spin.setRange(-500.0, 500.0)
        self.y_offset_spin.setValue(0.0)
        self.y_offset_spin.setSingleStep(1.0)
        self.y_offset_spin.setDecimals(1)
        self.y_offset_spin.setSuffix(" mm")
        if self.edge_name:
            self.y_offset_spin.setToolTip(
                "Offset perpendicular to the edge (positive = away from edge).")
            layout.addRow("From Edge:", self.y_offset_spin)
        else:
            self.y_offset_spin.setToolTip(
                "Offset along the model Y axis (projected onto the face).")
            layout.addRow("Y Offset:", self.y_offset_spin)

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

    def _apply_prefill(self, p):
        if "x_offset" in p:
            self.x_offset_spin.setValue(p["x_offset"])
        if "y_offset" in p:
            self.y_offset_spin.setValue(p["y_offset"])
        if "rotation" in p:
            self.rotation_spin.setValue(p["rotation"])

    def accept(self):
        from dtm4p_geometry import place_housing

        doc = FreeCAD.ActiveDocument
        body_shape = self.body_obj.Shape
        face = getattr(body_shape, self.face_name)

        x_offset = self.x_offset_spin.value()
        y_offset = self.y_offset_spin.value()
        rotation = self.rotation_spin.value()

        # Resolve edge
        edge = None
        if self.edge_name:
            edge = getattr(body_shape, self.edge_name, None)

        try:
            new_shape = place_housing(
                body_shape, face,
                x_offset=x_offset,
                y_offset=y_offset,
                rotation=rotation,
                edge=edge,
            )
        except Exception as e:
            FreeCAD.Console.PrintError(
                "DTM4P placement failed: {}\n".format(e)
            )
            QtWidgets.QMessageBox.critical(
                None,
                "DTM4P Error",
                "Fuse operation failed:\n\n{}\n\n"
                "Make sure you selected a flat face with enough "
                "room for the housing.".format(e),
            )
            return False

        body = _find_body(self.body_obj)
        is_pd_edit = (self.edit_obj is not None
                      and hasattr(self.edit_obj, "BaseFeature"))

        if is_pd_edit:
            result_obj = self.edit_obj
            result_obj.DTM4P_XOffset = x_offset
            result_obj.DTM4P_YOffset = y_offset
            result_obj.DTM4P_Rotation = rotation
            result_obj.DTM4P_EdgeName = self.edge_name
        elif body is not None:
            result_obj = doc.addObject(
                "PartDesign::FeatureAdditivePython", "DTM4P")
            _DTM4PProxy(result_obj)
            _DTM4PViewProvider(result_obj.ViewObject)
            _add_dtm4p_properties(result_obj)
            result_obj.DTM4P_XOffset = x_offset
            result_obj.DTM4P_YOffset = y_offset
            result_obj.DTM4P_Rotation = rotation
            result_obj.DTM4P_FaceName = self.face_name
            result_obj.DTM4P_EdgeName = self.edge_name
            result_obj.DTM4P_OriginalBody = body.Name
            body.addObject(result_obj)
        else:
            if self.edit_obj is not None:
                doc.removeObject(self.edit_obj.Name)
            result_obj = doc.addObject("Part::FeaturePython", "DTM4P")
            _DTM4PProxy(result_obj)
            _DTM4PViewProvider(result_obj.ViewObject)
            _add_dtm4p_properties(result_obj)
            result_obj.DTM4P_XOffset = x_offset
            result_obj.DTM4P_YOffset = y_offset
            result_obj.DTM4P_Rotation = rotation
            result_obj.DTM4P_FaceName = self.face_name
            result_obj.DTM4P_EdgeName = self.edge_name
            result_obj.DTM4P_OriginalBody = self.body_obj.Name
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
            "DTM4P housing placed onto {}.{}{}\n"
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

class DTM4PCommand:
    """FreeCAD command that places a DTM4P termination housing onto a face."""

    def GetResources(self):
        return {
            "Pixmap": os.path.join(
                _plugin_dir, "resources", "icons", "DTM4P.svg"
            ),
            "MenuText": "Place DTM4P Housing",
            "ToolTip": (
                "DTM4P\n"
                "Place a Deutsch DTM04-4P termination housing onto the\n"
                "selected flat face, extending outward from the surface.\n"
                "Select a Face + Edge to align the housing front to the edge.\n"
                "Select an existing DTM4P result to re-edit."
            ),
        }

    def IsActive(self):
        sel = FreeCADGui.Selection.getSelectionEx()
        if len(sel) != 1:
            return False
        obj = sel[0].Object
        if hasattr(obj, "DTM4P_FaceName"):
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

        # --- Re-edit an existing DTM4P result ---
        if hasattr(obj, "DTM4P_FaceName"):
            original = _get_dtm4p_base_object(obj)
            if original is None:
                QtWidgets.QMessageBox.warning(
                    None, "DTM4P",
                    "Cannot re-edit: the original body object was deleted.",
                )
                return
            prefill = {
                "x_offset": getattr(obj, "DTM4P_XOffset", 0.0),
                "y_offset": getattr(obj, "DTM4P_YOffset", 0.0),
                "rotation": getattr(obj, "DTM4P_Rotation", 0.0),
            }
            edge_name = getattr(obj, "DTM4P_EdgeName", "")
            panel = DTM4PTaskPanel(
                original, obj.DTM4P_FaceName,
                edge_name=edge_name,
                edit_obj=obj, prefill=prefill,
            )
            FreeCADGui.Control.showDialog(panel)
            return

        # --- New placement: extract face and optional edge ---
        sub_names = sel[0].SubElementNames
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
                "The DTM4P housing can only be placed on flat surfaces.",
            )
            return

        panel = DTM4PTaskPanel(obj, face_name, edge_name=edge_name)
        FreeCADGui.Control.showDialog(panel)


FreeCADGui.addCommand("TrailCurrent_DTM4P", DTM4PCommand())
