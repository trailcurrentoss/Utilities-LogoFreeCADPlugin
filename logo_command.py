"""FreeCAD command and task-panel UI for the TrailCurrent Logo Deboss tool."""

import os
import FreeCAD
import FreeCADGui
import Part

from PySide import QtWidgets, QtCore

_plugin_dir = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Task Panel (sidebar UI)
# ---------------------------------------------------------------------------

class DebossLogoTaskPanel:
    """Task panel shown in the FreeCAD sidebar when the command is active."""

    def __init__(self, body_obj, face_name):
        self.body_obj = body_obj
        self.face_name = face_name
        self.form = self._build_ui()

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

        try:
            new_shape = apply_logo(
                body_shape,
                face,
                diameter=diameter,
                total_depth=total_depth,
                mountain_ratio=mountain_ratio,
                trail_ratio=trail_ratio,
                bolt_ratio=bolt_ratio,
            )
        except Exception as e:
            FreeCAD.Console.PrintError(
                f"Logo deboss failed: {e}\n"
            )
            QtWidgets.QMessageBox.critical(
                None,
                "Logo Deboss Error",
                f"Boolean operation failed:\n\n{e}\n\n"
                "Make sure you selected a flat face with enough "
                "room for the logo.",
            )
            return False

        # Create the result as a new Part::Feature
        result_obj = doc.addObject("Part::Feature", "LogoDeboss")
        result_obj.Shape = new_shape

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
            f"Logo debossed onto {self.body_obj.Label}.{self.face_name} "
            f"(diameter={diameter}mm, depth={total_depth}mm)\n"
        )
        return True

    def reject(self):
        """Called when the user presses Cancel."""
        FreeCADGui.Control.closeDialog()
        return True

    def getStandardButtons(self):
        return int(
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
                "flat face with configurable multi-level depth."
            ),
        }

    def IsActive(self):
        """Command is active when exactly one planar face is selected."""
        sel = FreeCADGui.Selection.getSelectionEx()
        if len(sel) != 1:
            return False
        if not sel[0].SubElementNames:
            return False
        sub = sel[0].SubElementNames[0]
        if not sub.startswith("Face"):
            return False
        return True

    def Activated(self):
        """Called when the user clicks the command."""
        sel = FreeCADGui.Selection.getSelectionEx()
        if not sel:
            return

        obj = sel[0].Object
        face_name = sel[0].SubElementNames[0]
        face = getattr(obj.Shape, face_name)

        # Validate: face must be planar
        surface = face.Surface
        is_planar = hasattr(surface, "Axis") or isinstance(
            surface, Part.Plane
        )
        if not is_planar:
            from PySide import QtWidgets as Qw

            Qw.QMessageBox.warning(
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
