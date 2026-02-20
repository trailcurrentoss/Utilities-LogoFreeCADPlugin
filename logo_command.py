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
        """Recompute the shape from BaseFeature (PartDesign mode)."""
        if not hasattr(obj, "Logo_Diameter"):
            return
        if not hasattr(obj, "BaseFeature") or obj.BaseFeature is None:
            return  # Part::FeaturePython at document root — shape set in accept()
        try:
            from logo_deboss import apply_logo
            base_shape = obj.BaseFeature.Shape
            face = getattr(base_shape, obj.Logo_FaceName)
            obj.Shape = apply_logo(
                base_shape, face,
                diameter=obj.Logo_Diameter,
                total_depth=obj.Logo_TotalDepth,
                mountain_ratio=obj.Logo_MountainPct / 100.0,
                trail_ratio=obj.Logo_TrailPct / 100.0,
                bolt_ratio=obj.Logo_BoltPct / 100.0,
                x_offset=getattr(obj, "Logo_XOffset", 0.0),
                y_offset=getattr(obj, "Logo_YOffset", 0.0),
                rotation=getattr(obj, "Logo_Rotation", 0.0),
            )
        except Exception as e:
            FreeCAD.Console.PrintError(
                "Logo Deboss recompute failed: {}\n".format(e))

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

        original = _get_logo_base_object(obj)
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
            "rotation": getattr(obj, "Logo_Rotation", 0.0),
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
# Helpers
# ---------------------------------------------------------------------------

def _find_body(obj):
    """Return the PartDesign::Body that *obj* belongs to, or None.

    Works whether *obj* is the Body itself or a feature inside it.
    """
    if hasattr(obj, "TypeId") and obj.TypeId == "PartDesign::Body":
        return obj
    if hasattr(obj, "getParentGeoFeatureGroup"):
        parent = obj.getParentGeoFeatureGroup()
        if (parent is not None
                and hasattr(parent, "TypeId")
                and parent.TypeId == "PartDesign::Body"):
            return parent
    return None


def _add_logo_properties(obj):
    """Add custom storage properties to a LogoDeboss feature object."""
    obj.addProperty(
        "App::PropertyFloat", "Logo_Diameter", "Logo Deboss",
        "Logo diameter (mm)")
    obj.addProperty(
        "App::PropertyFloat", "Logo_TotalDepth", "Logo Deboss",
        "Total deboss depth (mm)")
    obj.addProperty(
        "App::PropertyFloat", "Logo_MountainPct", "Logo Deboss",
        "Mountain depth (%)")
    obj.addProperty(
        "App::PropertyFloat", "Logo_TrailPct", "Logo Deboss",
        "Trail depth (%)")
    obj.addProperty(
        "App::PropertyFloat", "Logo_BoltPct", "Logo Deboss",
        "Bolt depth (%)")
    obj.addProperty(
        "App::PropertyFloat", "Logo_XOffset", "Logo Deboss",
        "Horizontal offset from face centre (mm)")
    obj.addProperty(
        "App::PropertyFloat", "Logo_YOffset", "Logo Deboss",
        "Vertical offset from face centre (mm)")
    obj.addProperty(
        "App::PropertyFloat", "Logo_Rotation", "Logo Deboss",
        "Rotation angle on the face (degrees)")
    obj.addProperty(
        "App::PropertyString", "Logo_FaceName", "Logo Deboss",
        "Face used on the original body")
    obj.addProperty(
        "App::PropertyString", "Logo_OriginalBody", "Logo Deboss",
        "Original body object name")


def _get_logo_base_object(obj):
    """Return the base object that a LogoDeboss result was derived from.

    For PartDesign features this is the BaseFeature; for document-level
    Part objects it is looked up by the stored Logo_OriginalBody name.
    Returns None if the base cannot be found.
    """
    if hasattr(obj, "BaseFeature") and obj.BaseFeature is not None:
        return obj.BaseFeature
    orig_name = getattr(obj, "Logo_OriginalBody", None)
    if orig_name:
        return FreeCAD.ActiveDocument.getObject(orig_name)
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

        # Rotation
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
        if "rotation" in p:
            self.rotation_spin.setValue(p["rotation"])

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
        rotation = self.rotation_spin.value()

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
                rotation=rotation,
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

        # Detect whether we are working inside a PartDesign::Body
        body = _find_body(self.body_obj)
        is_pd_edit = (self.edit_obj is not None
                      and hasattr(self.edit_obj, "BaseFeature")
                      and self.edit_obj.BaseFeature is not None)

        if is_pd_edit:
            # Re-editing a PartDesign feature — update in place
            result_obj = self.edit_obj
            result_obj.Shape = new_shape
        elif body is not None:
            # New operation inside a PartDesign::Body
            prev_tip = body.Tip
            result_obj = doc.addObject(
                "PartDesign::FeaturePython", "LogoDeboss")
            _LogoDebossProxy(result_obj)
            _LogoDebossViewProvider(result_obj.ViewObject)
            _add_logo_properties(result_obj)
            result_obj.Shape = new_shape
            # Add to Body (sets BaseFeature & Tip automatically)
            body.addObject(result_obj)
            # Ensure BaseFeature links to the previous tip
            if prev_tip is not None:
                result_obj.BaseFeature = prev_tip
        else:
            # Non-PartDesign: standalone Part::FeaturePython at doc root
            if self.edit_obj is not None:
                doc.removeObject(self.edit_obj.Name)
            result_obj = doc.addObject("Part::FeaturePython", "LogoDeboss")
            _LogoDebossProxy(result_obj)
            _LogoDebossViewProvider(result_obj.ViewObject)
            result_obj.Shape = new_shape
            _add_logo_properties(result_obj)
            # Hide the original so the debossed version is visible
            self.body_obj.ViewObject.Visibility = False

        # Store / update parameter values
        result_obj.Logo_Diameter = diameter
        result_obj.Logo_TotalDepth = total_depth
        result_obj.Logo_MountainPct = self.mountain_spin.value()
        result_obj.Logo_TrailPct = self.trail_spin.value()
        result_obj.Logo_BoltPct = self.bolt_spin.value()
        result_obj.Logo_XOffset = x_offset
        result_obj.Logo_YOffset = y_offset
        result_obj.Logo_Rotation = rotation
        if not is_pd_edit:
            result_obj.Logo_FaceName = self.face_name
            result_obj.Logo_OriginalBody = (
                body.Name if body is not None else self.body_obj.Name)

        # Copy visual properties (non-PartDesign only — Body handles its own)
        if body is None and not is_pd_edit:
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
            original = _get_logo_base_object(obj)
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
                "rotation": getattr(obj, "Logo_Rotation", 0.0),
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
