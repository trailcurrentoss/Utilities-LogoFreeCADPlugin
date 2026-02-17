"""FreeCAD command and task-panel UI for the TrailCurrent Logo Deboss tool."""

import os
import FreeCAD
import FreeCADGui
import Part

from PySide import QtWidgets, QtCore

_plugin_dir = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# FeaturePython proxy & ViewProvider (enables double-click re-edit)
# ---------------------------------------------------------------------------

class _LogoDebossProxy:
    """Data proxy for a LogoDeboss Part::FeaturePython object."""

    def __init__(self, obj):
        obj.Proxy = self

    def execute(self, obj):
        pass  # Shape is set manually in accept()

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None


class _LogoDebossViewProvider:
    """ViewProvider that enables double-click re-editing of LogoDeboss objects."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def _open_edit_panel(self, obj):
        """Open the task panel pre-filled with the object's stored parameters."""
        if not hasattr(obj, "Logo_Diameter"):
            return False

        original = FreeCAD.ActiveDocument.getObject(obj.Logo_OriginalBody)
        if original is None:
            QtWidgets.QMessageBox.warning(
                None, "Logo Deboss",
                "Cannot re-edit: the original body object was deleted.",
            )
            return True

        prefill = {
            "diameter": obj.Logo_Diameter,
            "total_depth": obj.Logo_TotalDepth,
            "mountain_pct": obj.Logo_MountainPct,
            "trail_pct": obj.Logo_TrailPct,
            "bolt_pct": obj.Logo_BoltPct,
            "x_offset": obj.Logo_XOffset if hasattr(obj, "Logo_XOffset") else 0.0,
            "y_offset": obj.Logo_YOffset if hasattr(obj, "Logo_YOffset") else 0.0,
        }
        panel = DebossLogoTaskPanel(
            original, obj.Logo_FaceName,
            edit_obj=obj, prefill=prefill,
        )
        FreeCADGui.Control.showDialog(panel)
        return True

    def doubleClicked(self, vobj):
        try:
            return self._open_edit_panel(vobj.Object)
        except Exception as e:
            FreeCAD.Console.PrintError(
                "Logo Deboss doubleClicked error: {}\n".format(e))
            return False

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return False
        try:
            return self._open_edit_panel(vobj.Object)
        except Exception as e:
            FreeCAD.Console.PrintError(
                "Logo Deboss setEdit error: {}\n".format(e))
            return False

    def unsetEdit(self, vobj, mode=0):
        FreeCADGui.Control.closeDialog()
        return True

    def getIcon(self):
        return os.path.join(
            _plugin_dir, "resources", "icons", "TrailCurrentLogo.svg"
        )

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None


# ---------------------------------------------------------------------------
# Task Panel (sidebar UI)
# ---------------------------------------------------------------------------

class DebossLogoTaskPanel:
    """Task panel shown in the FreeCAD sidebar when the command is active."""

    def __init__(self, body_obj, face_name, edit_obj=None, prefill=None):
        self.body_obj = body_obj
        self.face_name = face_name
        self.edit_obj = edit_obj          # existing result being re-edited
        self.form = self._build_ui()
        if prefill:
            self._apply_prefill(prefill)

    # -- UI construction ---------------------------------------------------

    def _build_ui(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        layout.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.AllNonFixedFieldsGrow
        )

        # Header
        header = QtWidgets.QLabel("<b>TrailCurrent Logo Deboss</b>")
        header.setAlignment(QtCore.Qt.AlignCenter)
        layout.addRow(header)

        # Logo diameter
        self.diameter_spin = QtWidgets.QDoubleSpinBox()
        self.diameter_spin.setRange(5.0, 100.0)
        self.diameter_spin.setValue(18.0)
        self.diameter_spin.setSingleStep(1.0)
        self.diameter_spin.setDecimals(1)
        self.diameter_spin.setSuffix(" mm")
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
            "Adjust based on your lid/wall thickness."
        )
        layout.addRow("Total Depth:", self.depth_spin)

        # Placement offsets
        self.x_offset_spin = QtWidgets.QDoubleSpinBox()
        self.x_offset_spin.setRange(-500.0, 500.0)
        self.x_offset_spin.setValue(0.0)
        self.x_offset_spin.setSingleStep(1.0)
        self.x_offset_spin.setDecimals(1)
        self.x_offset_spin.setSuffix(" mm")
        self.x_offset_spin.setToolTip(
            "Horizontal offset from the face centre."
        )
        layout.addRow("X Offset:", self.x_offset_spin)

        self.y_offset_spin = QtWidgets.QDoubleSpinBox()
        self.y_offset_spin.setRange(-500.0, 500.0)
        self.y_offset_spin.setValue(0.0)
        self.y_offset_spin.setSingleStep(1.0)
        self.y_offset_spin.setDecimals(1)
        self.y_offset_spin.setSuffix(" mm")
        self.y_offset_spin.setToolTip(
            "Vertical offset from the face centre."
        )
        layout.addRow("Y Offset:", self.y_offset_spin)

        # Separator
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        layout.addRow(sep)

        depth_label = QtWidgets.QLabel(
            "<i>Depth ratios (% of total depth)</i>"
        )
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
            "Mountain silhouette cut depth as % of total.\n"
            "Higher = deeper cut, lower = more raised."
        )
        layout.addRow("Mountain Depth:", self.mountain_spin)

        # Trail depth ratio
        self.trail_spin = QtWidgets.QDoubleSpinBox()
        self.trail_spin.setRange(5, 80)
        self.trail_spin.setValue(30)
        self.trail_spin.setSingleStep(5)
        self.trail_spin.setDecimals(0)
        self.trail_spin.setSuffix(" %")
        self.trail_spin.setToolTip(
            "Winding trail path cut depth as % of total."
        )
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
            "Shallowest element — appears most raised."
        )
        layout.addRow("Bolt Depth:", self.bolt_spin)

        return widget

    def _apply_prefill(self, p):
        """Set widget values from a saved-parameter dict."""
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
        if "x_offset" in p:
            self.x_offset_spin.setValue(p["x_offset"])
        if "y_offset" in p:
            self.y_offset_spin.setValue(p["y_offset"])

    # -- Task panel interface ----------------------------------------------

    def accept(self):
        """Called when the user presses OK."""
        from logo_deboss import apply_logo

        doc = FreeCAD.ActiveDocument
        body_shape = self.body_obj.Shape
        face = getattr(body_shape, self.face_name)

        diameter = self.diameter_spin.value()
        total_depth = self.depth_spin.value()
        mountain_ratio = self.mountain_spin.value() / 100.0
        trail_ratio = self.trail_spin.value() / 100.0
        bolt_ratio = self.bolt_spin.value() / 100.0
        x_offset = self.x_offset_spin.value()
        y_offset = self.y_offset_spin.value()

        try:
            new_shape = apply_logo(
                body_shape,
                face,
                diameter=diameter,
                total_depth=total_depth,
                mountain_ratio=mountain_ratio,
                trail_ratio=trail_ratio,
                bolt_ratio=bolt_ratio,
                x_offset=x_offset,
                y_offset=y_offset,
            )
        except Exception as e:
            FreeCAD.Console.PrintError(
                "Logo deboss failed: {}\n".format(e)
            )
            QtWidgets.QMessageBox.critical(
                None,
                "Logo Deboss Error",
                "Boolean operation failed:\n\n{}\n\n"
                "Make sure you selected a flat face with enough "
                "room for the logo.".format(e),
            )
            return False

        # If re-editing, remove the old result first
        if self.edit_obj is not None:
            doc.removeObject(self.edit_obj.Name)

        # Create the result as a FeaturePython (enables double-click re-edit)
        result_obj = doc.addObject("Part::FeaturePython", "LogoDeboss")
        _LogoDebossProxy(result_obj)
        _LogoDebossViewProvider(result_obj.ViewObject)
        result_obj.Shape = new_shape

        # Store parameters so the logo can be re-edited later
        result_obj.addProperty(
            "App::PropertyFloat", "Logo_Diameter", "Logo Deboss",
            "Logo diameter (mm)")
        result_obj.addProperty(
            "App::PropertyFloat", "Logo_TotalDepth", "Logo Deboss",
            "Total deboss depth (mm)")
        result_obj.addProperty(
            "App::PropertyFloat", "Logo_MountainPct", "Logo Deboss",
            "Mountain depth (%)")
        result_obj.addProperty(
            "App::PropertyFloat", "Logo_TrailPct", "Logo Deboss",
            "Trail depth (%)")
        result_obj.addProperty(
            "App::PropertyFloat", "Logo_BoltPct", "Logo Deboss",
            "Bolt depth (%)")
        result_obj.addProperty(
            "App::PropertyFloat", "Logo_XOffset", "Logo Deboss",
            "Horizontal offset from face centre (mm)")
        result_obj.addProperty(
            "App::PropertyFloat", "Logo_YOffset", "Logo Deboss",
            "Vertical offset from face centre (mm)")
        result_obj.addProperty(
            "App::PropertyString", "Logo_FaceName", "Logo Deboss",
            "Face used on the original body")
        result_obj.addProperty(
            "App::PropertyString", "Logo_OriginalBody", "Logo Deboss",
            "Original body object name")

        result_obj.Logo_Diameter = diameter
        result_obj.Logo_TotalDepth = total_depth
        result_obj.Logo_MountainPct = self.mountain_spin.value()
        result_obj.Logo_TrailPct = self.trail_spin.value()
        result_obj.Logo_BoltPct = self.bolt_spin.value()
        result_obj.Logo_XOffset = x_offset
        result_obj.Logo_YOffset = y_offset
        result_obj.Logo_FaceName = self.face_name
        result_obj.Logo_OriginalBody = self.body_obj.Name

        # Copy visual properties from the source
        if hasattr(self.body_obj, "ViewObject"):
            src_vo = self.body_obj.ViewObject
            dst_vo = result_obj.ViewObject
            if hasattr(src_vo, "ShapeColor"):
                dst_vo.ShapeColor = src_vo.ShapeColor
            if hasattr(src_vo, "Transparency"):
                dst_vo.Transparency = src_vo.Transparency

        # Hide the original body so the debossed version is visible
        self.body_obj.ViewObject.Visibility = False

        doc.recompute()
        FreeCADGui.Control.closeDialog()
        FreeCAD.Console.PrintMessage(
            "Logo debossed onto {}.{} "
            "(diameter={}mm, depth={}mm)\n"
            .format(self.body_obj.Label, self.face_name,
                    diameter, total_depth)
        )
        return True

    def reject(self):
        """Called when the user presses Cancel."""
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

class DebossLogoCommand:
    """FreeCAD command that debosses the TrailCurrent logo onto a face."""

    def GetResources(self):
        return {
            "Pixmap": os.path.join(
                _plugin_dir, "resources", "icons", "TrailCurrentLogo.svg"
            ),
            "MenuText": "Deboss TrailCurrent Logo",
            "ToolTip": (
                "Deboss the TrailCurrent brand logo onto the selected "
                "flat face with configurable multi-level depth.\n"
                "Select an existing LogoDeboss result to re-edit."
            ),
        }

    def IsActive(self):
        """Active when a planar face or an existing logo result is selected."""
        sel = FreeCADGui.Selection.getSelectionEx()
        if len(sel) != 1:
            return False
        obj = sel[0].Object
        # Re-edit mode: existing logo result selected
        if hasattr(obj, "Logo_Diameter"):
            return True
        # New mode: a face is selected
        if not sel[0].SubElementNames:
            return False
        return sel[0].SubElementNames[0].startswith("Face")

    def Activated(self):
        """Called when the user clicks the command."""
        sel = FreeCADGui.Selection.getSelectionEx()
        if not sel:
            return

        obj = sel[0].Object

        # --- Re-edit an existing logo deboss result ---
        if hasattr(obj, "Logo_Diameter"):
            original = FreeCAD.ActiveDocument.getObject(obj.Logo_OriginalBody)
            if original is None:
                QtWidgets.QMessageBox.warning(
                    None, "Logo Deboss",
                    "Cannot re-edit: the original body object was deleted.",
                )
                return

            prefill = {
                "diameter": obj.Logo_Diameter,
                "total_depth": obj.Logo_TotalDepth,
                "mountain_pct": obj.Logo_MountainPct,
                "trail_pct": obj.Logo_TrailPct,
                "bolt_pct": obj.Logo_BoltPct,
                "x_offset": obj.Logo_XOffset if hasattr(obj, "Logo_XOffset") else 0.0,
                "y_offset": obj.Logo_YOffset if hasattr(obj, "Logo_YOffset") else 0.0,
            }
            panel = DebossLogoTaskPanel(
                original, obj.Logo_FaceName,
                edit_obj=obj, prefill=prefill,
            )
            FreeCADGui.Control.showDialog(panel)
            return

        # --- New logo on a selected face ---
        if not sel[0].SubElementNames:
            return
        face_name = sel[0].SubElementNames[0]
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
                "The logo can only be debossed onto flat surfaces.",
            )
            return

        panel = DebossLogoTaskPanel(obj, face_name)
        FreeCADGui.Control.showDialog(panel)


# Register the command with FreeCAD
FreeCADGui.addCommand("TrailCurrent_DebossLogo", DebossLogoCommand())
