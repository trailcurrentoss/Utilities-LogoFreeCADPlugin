"""FreeCAD command and task-panel UI for the TrailCurrent Logo+Text Deboss tool."""

import os
import FreeCAD
import FreeCADGui
import Part

from PySide import QtWidgets, QtCore

_plugin_dir = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# FeaturePython proxy & ViewProvider (enables double-click re-edit)
# ---------------------------------------------------------------------------

class _LogoTextDebossProxy:
    """Data proxy for a LogoTextDeboss PartDesign::FeatureSubtractivePython."""

    def __init__(self, obj):
        obj.Proxy = self

    def execute(self, obj):
        """Recompute the debossed shape.

        For PartDesign integration the Shape must be the cumulative solid
        (base + our cuts) and AddSubShape the isolated cutting tool.
        Shapes are stored in the feature's local coordinate system.
        """
        if not hasattr(obj, "LogoText_Diameter"):
            return

        if hasattr(obj, "BaseFeature") and obj.BaseFeature is not None:
            base_shape = obj.BaseFeature.Shape
        elif hasattr(obj, "LogoText_OriginalBody") and obj.LogoText_OriginalBody:
            original = FreeCAD.ActiveDocument.getObject(obj.LogoText_OriginalBody)
            if original is None or original.Shape.isNull():
                return
            base_shape = original.Shape
        else:
            return

        try:
            from logotext_deboss import apply_logotext
            face_name = getattr(obj, "LogoText_FaceName", "")
            if not face_name:
                return
            face_idx = int(face_name.replace("Face", "")) if face_name.startswith("Face") else -1
            if face_idx < 1 or face_idx > len(base_shape.Faces):
                FreeCAD.Console.PrintWarning(
                    "Logo+Text Deboss: {} not found on base shape "
                    "(has {} faces), keeping existing shape.\n"
                    .format(face_name, len(base_shape.Faces)))
                return
            face = base_shape.Faces[face_idx - 1]
            new_shape = apply_logotext(
                base_shape, face,
                diameter=obj.LogoText_Diameter,
                total_depth=obj.LogoText_TotalDepth,
                mountain_ratio=obj.LogoText_MountainPct / 100.0,
                trail_ratio=obj.LogoText_TrailPct / 100.0,
                bolt_ratio=obj.LogoText_BoltPct / 100.0,
                text_ratio=obj.LogoText_TextPct / 100.0,
                x_offset=getattr(obj, "LogoText_XOffset", 0.0),
                y_offset=getattr(obj, "LogoText_YOffset", 0.0),
                rotation=getattr(obj, "LogoText_Rotation", 0.0),
            )
            if new_shape and not new_shape.isNull():
                # Transform to feature-local coordinates
                new_shape.transformShape(
                    obj.Placement.inverse().toMatrix(), True)
                obj.Shape = new_shape
                if hasattr(obj, "AddSubShape"):
                    tool = base_shape.cut(new_shape)
                    tool.transformShape(
                        obj.Placement.inverse().toMatrix(), True)
                    obj.AddSubShape = tool
        except Exception as e:
            FreeCAD.Console.PrintError(
                "Logo+Text Deboss recompute failed: {}\n".format(e))

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None


class _LogoTextDebossViewProvider:
    """ViewProvider that enables double-click re-editing."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def _open_edit_panel(self, obj):
        if not hasattr(obj, "LogoText_Diameter"):
            return False
        original = _get_logotext_base_object(obj)
        if original is None:
            QtWidgets.QMessageBox.warning(
                None, "Logo+Text Deboss",
                "Cannot re-edit: the original body object was deleted.")
            return True
        prefill = {
            "diameter": obj.LogoText_Diameter,
            "total_depth": obj.LogoText_TotalDepth,
            "mountain_pct": obj.LogoText_MountainPct,
            "trail_pct": obj.LogoText_TrailPct,
            "bolt_pct": obj.LogoText_BoltPct,
            "text_pct": obj.LogoText_TextPct,
            "x_offset": getattr(obj, "LogoText_XOffset", 0.0),
            "y_offset": getattr(obj, "LogoText_YOffset", 0.0),
            "rotation": getattr(obj, "LogoText_Rotation", 0.0),
        }
        panel = DebossLogoTextTaskPanel(
            original, obj.LogoText_FaceName,
            edit_obj=obj, prefill=prefill)
        FreeCADGui.Control.showDialog(panel)
        return True

    def doubleClicked(self, vobj):
        try:
            return self._open_edit_panel(vobj.Object)
        except Exception as e:
            FreeCAD.Console.PrintError(
                "Logo+Text Deboss doubleClicked error: {}\n".format(e))
            return False

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return False
        try:
            return self._open_edit_panel(vobj.Object)
        except Exception as e:
            FreeCAD.Console.PrintError(
                "Logo+Text Deboss setEdit error: {}\n".format(e))
            return False

    def unsetEdit(self, vobj, mode=0):
        FreeCADGui.Control.closeDialog()
        return True

    def getIcon(self):
        return os.path.join(
            _plugin_dir, "resources", "icons", "TrailCurrentLogoText.svg")

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


def _add_logotext_properties(obj):
    """Add custom storage properties to a LogoTextDeboss feature object."""
    obj.addProperty(
        "App::PropertyFloat", "LogoText_Diameter", "Logo+Text Deboss",
        "Logo diameter (mm)")
    obj.addProperty(
        "App::PropertyFloat", "LogoText_TotalDepth", "Logo+Text Deboss",
        "Total deboss depth (mm)")
    obj.addProperty(
        "App::PropertyFloat", "LogoText_MountainPct", "Logo+Text Deboss",
        "Mountain depth (%)")
    obj.addProperty(
        "App::PropertyFloat", "LogoText_TrailPct", "Logo+Text Deboss",
        "Trail depth (%)")
    obj.addProperty(
        "App::PropertyFloat", "LogoText_BoltPct", "Logo+Text Deboss",
        "Bolt depth (%)")
    obj.addProperty(
        "App::PropertyFloat", "LogoText_TextPct", "Logo+Text Deboss",
        "Text depth (%)")
    obj.addProperty(
        "App::PropertyFloat", "LogoText_XOffset", "Logo+Text Deboss",
        "Horizontal offset from face centre (mm)")
    obj.addProperty(
        "App::PropertyFloat", "LogoText_YOffset", "Logo+Text Deboss",
        "Vertical offset from face centre (mm)")
    obj.addProperty(
        "App::PropertyFloat", "LogoText_Rotation", "Logo+Text Deboss",
        "Rotation angle on the face (degrees)")
    obj.addProperty(
        "App::PropertyString", "LogoText_FaceName", "Logo+Text Deboss",
        "Face used on the original body")
    obj.addProperty(
        "App::PropertyString", "LogoText_OriginalBody", "Logo+Text Deboss",
        "Original body object name")


def _get_logotext_base_object(obj):
    """Return the base object that a LogoTextDeboss result was derived from."""
    if hasattr(obj, "BaseFeature") and obj.BaseFeature is not None:
        return obj.BaseFeature
    orig_name = getattr(obj, "LogoText_OriginalBody", None)
    if orig_name:
        return FreeCAD.ActiveDocument.getObject(orig_name)
    return None


# ---------------------------------------------------------------------------
# Task Panel (sidebar UI)
# ---------------------------------------------------------------------------

class DebossLogoTextTaskPanel:
    """Task panel for the Logo+Text Deboss command."""

    def __init__(self, body_obj, face_name, edit_obj=None, prefill=None):
        self.body_obj = body_obj
        self.face_name = face_name
        self.edit_obj = edit_obj
        self.form = self._build_ui()
        if prefill:
            self._apply_prefill(prefill)

    def _build_ui(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        layout.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.AllNonFixedFieldsGrow)

        header = QtWidgets.QLabel("<b>TrailCurrent Logo+Text Deboss</b>")
        header.setAlignment(QtCore.Qt.AlignCenter)
        layout.addRow(header)

        # Logo diameter
        self.diameter_spin = QtWidgets.QDoubleSpinBox()
        self.diameter_spin.setRange(5.0, 100.0)
        self.diameter_spin.setValue(18.0)
        self.diameter_spin.setSingleStep(1.0)
        self.diameter_spin.setDecimals(1)
        self.diameter_spin.setSuffix(" mm")
        self.diameter_spin.setToolTip(
            "Logo circle diameter.  Text scales proportionally.")
        layout.addRow("Logo Diameter:", self.diameter_spin)

        # Total depth
        self.depth_spin = QtWidgets.QDoubleSpinBox()
        self.depth_spin.setRange(0.10, 5.00)
        self.depth_spin.setValue(0.80)
        self.depth_spin.setSingleStep(0.05)
        self.depth_spin.setDecimals(2)
        self.depth_spin.setSuffix(" mm")
        self.depth_spin.setToolTip(
            "Maximum deboss depth (circle background).\n"
            "Adjust based on your lid/wall thickness.")
        layout.addRow("Total Depth:", self.depth_spin)

        # Placement offsets
        self.x_offset_spin = QtWidgets.QDoubleSpinBox()
        self.x_offset_spin.setRange(-500.0, 500.0)
        self.x_offset_spin.setValue(0.0)
        self.x_offset_spin.setSingleStep(1.0)
        self.x_offset_spin.setDecimals(1)
        self.x_offset_spin.setSuffix(" mm")
        self.x_offset_spin.setToolTip(
            "Horizontal offset from the face centre.")
        layout.addRow("X Offset:", self.x_offset_spin)

        self.y_offset_spin = QtWidgets.QDoubleSpinBox()
        self.y_offset_spin.setRange(-500.0, 500.0)
        self.y_offset_spin.setValue(0.0)
        self.y_offset_spin.setSingleStep(1.0)
        self.y_offset_spin.setDecimals(1)
        self.y_offset_spin.setSuffix(" mm")
        self.y_offset_spin.setToolTip(
            "Vertical offset from the face centre.")
        layout.addRow("Y Offset:", self.y_offset_spin)

        # Rotation
        self.rotation_spin = QtWidgets.QDoubleSpinBox()
        self.rotation_spin.setRange(-180.0, 180.0)
        self.rotation_spin.setValue(0.0)
        self.rotation_spin.setSingleStep(5.0)
        self.rotation_spin.setDecimals(1)
        self.rotation_spin.setSuffix(" deg")
        self.rotation_spin.setToolTip(
            "Rotation angle on the face (degrees).")
        layout.addRow("Rotation:", self.rotation_spin)

        # Separator
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        layout.addRow(sep)

        depth_label = QtWidgets.QLabel(
            "<i>Depth ratios (% of total depth)</i>")
        depth_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addRow(depth_label)

        # Mountain depth ratio
        self.mountain_spin = QtWidgets.QDoubleSpinBox()
        self.mountain_spin.setRange(10, 90)
        self.mountain_spin.setValue(55)
        self.mountain_spin.setSingleStep(5)
        self.mountain_spin.setDecimals(0)
        self.mountain_spin.setSuffix(" %")
        self.mountain_spin.setToolTip(
            "Mountain silhouette cut depth as % of total.")
        layout.addRow("Mountain Depth:", self.mountain_spin)

        # Trail depth ratio
        self.trail_spin = QtWidgets.QDoubleSpinBox()
        self.trail_spin.setRange(5, 80)
        self.trail_spin.setValue(30)
        self.trail_spin.setSingleStep(5)
        self.trail_spin.setDecimals(0)
        self.trail_spin.setSuffix(" %")
        self.trail_spin.setToolTip(
            "Winding trail path cut depth as % of total.")
        layout.addRow("Trail Depth:", self.trail_spin)

        # Bolt depth ratio
        self.bolt_spin = QtWidgets.QDoubleSpinBox()
        self.bolt_spin.setRange(5, 70)
        self.bolt_spin.setValue(15)
        self.bolt_spin.setSingleStep(5)
        self.bolt_spin.setDecimals(0)
        self.bolt_spin.setSuffix(" %")
        self.bolt_spin.setToolTip(
            "Lightning bolt cut depth as % of total.\n"
            "Shallowest element — appears most raised.")
        layout.addRow("Bolt Depth:", self.bolt_spin)

        # Text depth ratio
        self.text_spin = QtWidgets.QDoubleSpinBox()
        self.text_spin.setRange(5, 100)
        self.text_spin.setValue(100)
        self.text_spin.setSingleStep(5)
        self.text_spin.setDecimals(0)
        self.text_spin.setSuffix(" %")
        self.text_spin.setToolTip(
            "\"TrailCurrent\" text cut depth as % of total.\n"
            "100 % = same depth as circle background.")
        layout.addRow("Text Depth:", self.text_spin)

        return widget

    def _apply_prefill(self, p):
        if "diameter" in p:
            self.diameter_spin.setValue(p["diameter"])
        if "total_depth" in p:
            self.depth_spin.setValue(p["total_depth"])
        if "mountain_pct" in p:
            self.mountain_spin.setValue(p["mountain_pct"])
        if "trail_pct" in p:
            self.trail_spin.setValue(p["trail_pct"])
        if "bolt_pct" in p:
            self.bolt_spin.setValue(p["bolt_pct"])
        if "text_pct" in p:
            self.text_spin.setValue(p["text_pct"])
        if "x_offset" in p:
            self.x_offset_spin.setValue(p["x_offset"])
        if "y_offset" in p:
            self.y_offset_spin.setValue(p["y_offset"])
        if "rotation" in p:
            self.rotation_spin.setValue(p["rotation"])

    # -- Task panel interface ----------------------------------------------

    def accept(self):
        from logotext_deboss import apply_logotext

        doc = FreeCAD.ActiveDocument
        body_shape = self.body_obj.Shape
        face = getattr(body_shape, self.face_name)

        diameter = self.diameter_spin.value()
        total_depth = self.depth_spin.value()
        mountain_ratio = self.mountain_spin.value() / 100.0
        trail_ratio = self.trail_spin.value() / 100.0
        bolt_ratio = self.bolt_spin.value() / 100.0
        text_ratio = self.text_spin.value() / 100.0
        x_offset = self.x_offset_spin.value()
        y_offset = self.y_offset_spin.value()
        rotation = self.rotation_spin.value()

        try:
            new_shape = apply_logotext(
                body_shape, face,
                diameter=diameter,
                total_depth=total_depth,
                mountain_ratio=mountain_ratio,
                trail_ratio=trail_ratio,
                bolt_ratio=bolt_ratio,
                text_ratio=text_ratio,
                x_offset=x_offset,
                y_offset=y_offset,
                rotation=rotation,
            )
        except Exception as e:
            FreeCAD.Console.PrintError(
                "Logo+Text deboss failed: {}\n".format(e))
            QtWidgets.QMessageBox.critical(
                None,
                "Logo+Text Deboss Error",
                "Operation failed:\n\n{}\n\n"
                "Make sure you selected a flat face with enough "
                "room for the logo and text.".format(e))
            return False

        body = _find_body(self.body_obj)
        is_pd_edit = (self.edit_obj is not None
                      and hasattr(self.edit_obj, "BaseFeature"))

        if is_pd_edit:
            # Re-editing — update properties, let recompute handle Shape.
            result_obj = self.edit_obj
            result_obj.LogoText_Diameter = diameter
            result_obj.LogoText_TotalDepth = total_depth
            result_obj.LogoText_MountainPct = self.mountain_spin.value()
            result_obj.LogoText_TrailPct = self.trail_spin.value()
            result_obj.LogoText_BoltPct = self.bolt_spin.value()
            result_obj.LogoText_TextPct = self.text_spin.value()
            result_obj.LogoText_XOffset = x_offset
            result_obj.LogoText_YOffset = y_offset
            result_obj.LogoText_Rotation = rotation
        elif body is not None:
            # New operation inside a PartDesign::Body.
            # Set parameter properties, then let body.addObject() set
            # BaseFeature and doc.recompute() call execute() for Shape.
            result_obj = doc.addObject(
                "PartDesign::FeatureSubtractivePython", "LogoTextDeboss")
            _LogoTextDebossProxy(result_obj)
            _LogoTextDebossViewProvider(result_obj.ViewObject)
            _add_logotext_properties(result_obj)
            result_obj.LogoText_Diameter = diameter
            result_obj.LogoText_TotalDepth = total_depth
            result_obj.LogoText_MountainPct = self.mountain_spin.value()
            result_obj.LogoText_TrailPct = self.trail_spin.value()
            result_obj.LogoText_BoltPct = self.bolt_spin.value()
            result_obj.LogoText_TextPct = self.text_spin.value()
            result_obj.LogoText_XOffset = x_offset
            result_obj.LogoText_YOffset = y_offset
            result_obj.LogoText_Rotation = rotation
            result_obj.LogoText_FaceName = self.face_name
            result_obj.LogoText_OriginalBody = body.Name
            # Do NOT set BaseFeature, Shape, or AddSubShape manually.
            body.addObject(result_obj)
        else:
            if self.edit_obj is not None:
                doc.removeObject(self.edit_obj.Name)
            result_obj = doc.addObject(
                "Part::FeaturePython", "LogoTextDeboss")
            _LogoTextDebossProxy(result_obj)
            _LogoTextDebossViewProvider(result_obj.ViewObject)
            _add_logotext_properties(result_obj)
            result_obj.LogoText_Diameter = diameter
            result_obj.LogoText_TotalDepth = total_depth
            result_obj.LogoText_MountainPct = self.mountain_spin.value()
            result_obj.LogoText_TrailPct = self.trail_spin.value()
            result_obj.LogoText_BoltPct = self.bolt_spin.value()
            result_obj.LogoText_TextPct = self.text_spin.value()
            result_obj.LogoText_XOffset = x_offset
            result_obj.LogoText_YOffset = y_offset
            result_obj.LogoText_Rotation = rotation
            result_obj.LogoText_FaceName = self.face_name
            result_obj.LogoText_OriginalBody = self.body_obj.Name
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
            "Logo+Text debossed onto {}.{} "
            "(diameter={}mm, depth={}mm)\n"
            .format(self.body_obj.Label, self.face_name,
                    diameter, total_depth))
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

class DebossLogoTextCommand:
    """FreeCAD command that debosses logo + 'TrailCurrent' text onto a face."""

    def GetResources(self):
        return {
            "Pixmap": os.path.join(
                _plugin_dir, "resources", "icons", "TrailCurrentLogoText.svg"),
            "MenuText": "Deboss Logo + Text",
            "ToolTip": (
                "Deboss the TrailCurrent logo with the name\n"
                "\"TrailCurrent\" onto the selected flat face.\n"
                "Select an existing LogoTextDeboss result to re-edit."
            ),
        }

    def IsActive(self):
        sel = FreeCADGui.Selection.getSelectionEx()
        if len(sel) != 1:
            return False
        obj = sel[0].Object
        if hasattr(obj, "LogoText_Diameter"):
            return True
        if not sel[0].SubElementNames:
            return False
        return sel[0].SubElementNames[0].startswith("Face")

    def Activated(self):
        sel = FreeCADGui.Selection.getSelectionEx()
        if not sel:
            return

        obj = sel[0].Object

        # Re-edit existing
        if hasattr(obj, "LogoText_Diameter"):
            original = _get_logotext_base_object(obj)
            if original is None:
                QtWidgets.QMessageBox.warning(
                    None, "Logo+Text Deboss",
                    "Cannot re-edit: the original body object was deleted.")
                return
            prefill = {
                "diameter": obj.LogoText_Diameter,
                "total_depth": obj.LogoText_TotalDepth,
                "mountain_pct": obj.LogoText_MountainPct,
                "trail_pct": obj.LogoText_TrailPct,
                "bolt_pct": obj.LogoText_BoltPct,
                "text_pct": obj.LogoText_TextPct,
                "x_offset": getattr(obj, "LogoText_XOffset", 0.0),
                "y_offset": getattr(obj, "LogoText_YOffset", 0.0),
                "rotation": getattr(obj, "LogoText_Rotation", 0.0),
            }
            panel = DebossLogoTextTaskPanel(
                original, obj.LogoText_FaceName,
                edit_obj=obj, prefill=prefill)
            FreeCADGui.Control.showDialog(panel)
            return

        # New operation on selected face
        if not sel[0].SubElementNames:
            return
        face_name = sel[0].SubElementNames[0]
        face = getattr(obj.Shape, face_name)

        surface = face.Surface
        is_planar = hasattr(surface, "Axis") or isinstance(
            surface, Part.Plane)
        if not is_planar:
            QtWidgets.QMessageBox.warning(
                None, "Non-Planar Face",
                "Please select a flat (planar) face.\n"
                "The logo+text can only be debossed onto flat surfaces.")
            return

        panel = DebossLogoTextTaskPanel(obj, face_name)
        FreeCADGui.Control.showDialog(panel)


# Register the command with FreeCAD
FreeCADGui.addCommand("TrailCurrent_DebossLogoText", DebossLogoTextCommand())
