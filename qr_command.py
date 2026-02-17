"""FreeCAD command and task-panel UI for the QR Code Emboss tool."""

import os

import FreeCAD
import FreeCADGui
import Part

from PySide import QtWidgets, QtCore

_plugin_dir = os.path.dirname(os.path.abspath(__file__))

_EC_KEYS = ["L", "M", "Q", "H"]


# ---------------------------------------------------------------------------
# FeaturePython proxy & ViewProvider (enables double-click re-edit)
# ---------------------------------------------------------------------------

class _QRCodeProxy:
    """Data proxy for a QRCode Part::FeaturePython object."""

    def __init__(self, obj):
        obj.Proxy = self

    def execute(self, obj):
        pass  # Shape is set manually in accept()

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None


class _QRCodeViewProvider:
    """ViewProvider that enables double-click re-editing of QR code objects."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def _open_edit_panel(self, obj):
        """Open the task panel pre-filled with the object's stored parameters."""
        if not hasattr(obj, "QR_URL"):
            return False

        original = FreeCAD.ActiveDocument.getObject(obj.QR_OriginalBody)
        if original is None:
            QtWidgets.QMessageBox.warning(
                None, "QR Code",
                "Cannot re-edit: the original body object was deleted.",
            )
            return True

        prefill = {
            "url": obj.QR_URL,
            "size": obj.QR_Size,
            "height": obj.QR_Height,
            "emboss": obj.QR_Emboss,
            "ec": obj.QR_ErrorCorrection,
            "border": obj.QR_Border,
            "x_offset": obj.QR_XOffset if hasattr(obj, "QR_XOffset") else 0.0,
            "y_offset": obj.QR_YOffset if hasattr(obj, "QR_YOffset") else 0.0,
        }
        panel = QRCodeTaskPanel(
            original, obj.QR_FaceName,
            edit_obj=obj, prefill=prefill,
        )
        FreeCADGui.Control.showDialog(panel)
        return True

    def doubleClicked(self, vobj):
        try:
            return self._open_edit_panel(vobj.Object)
        except Exception as e:
            FreeCAD.Console.PrintError(
                "QR Code doubleClicked error: {}\n".format(e))
            return False

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return False
        try:
            return self._open_edit_panel(vobj.Object)
        except Exception as e:
            FreeCAD.Console.PrintError(
                "QR Code setEdit error: {}\n".format(e))
            return False

    def unsetEdit(self, vobj, mode=0):
        FreeCADGui.Control.closeDialog()
        return True

    def getIcon(self):
        return os.path.join(
            _plugin_dir, "resources", "icons", "QRCode.svg"
        )

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None


# ---------------------------------------------------------------------------
# Task Panel (sidebar UI)
# ---------------------------------------------------------------------------

class QRCodeTaskPanel:
    """Task panel shown in the FreeCAD sidebar when the QR command is active."""

    def __init__(self, body_obj, face_name, edit_obj=None, prefill=None):
        self.body_obj = body_obj
        self.face_name = face_name
        self.edit_obj = edit_obj          # existing QR result being re-edited
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
        header = QtWidgets.QLabel("<b>QR Code Emboss</b>")
        header.setAlignment(QtCore.Qt.AlignCenter)
        layout.addRow(header)

        # URL input
        self.url_edit = QtWidgets.QLineEdit()
        self.url_edit.setPlaceholderText("https://example.com/tutorial")
        self.url_edit.setToolTip(
            "URL or text to encode in the QR code.\n"
            "Shorter URLs produce fewer modules and scan more reliably."
        )
        layout.addRow("URL / Data:", self.url_edit)

        # Separator
        sep1 = QtWidgets.QFrame()
        sep1.setFrameShape(QtWidgets.QFrame.HLine)
        layout.addRow(sep1)

        # Dimensions label
        dim_label = QtWidgets.QLabel("<i>Dimensions</i>")
        dim_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addRow(dim_label)

        # QR code size
        self.size_spin = QtWidgets.QDoubleSpinBox()
        self.size_spin.setRange(5.0, 200.0)
        self.size_spin.setValue(20.0)
        self.size_spin.setSingleStep(1.0)
        self.size_spin.setDecimals(1)
        self.size_spin.setSuffix(" mm")
        self.size_spin.setToolTip(
            "Side length of the QR code square.\n"
            "Larger values improve scannability but need more surface area."
        )
        layout.addRow("QR Size:", self.size_spin)

        # Height / Depth
        self.height_spin = QtWidgets.QDoubleSpinBox()
        self.height_spin.setRange(0.10, 5.00)
        self.height_spin.setValue(0.50)
        self.height_spin.setSingleStep(0.05)
        self.height_spin.setDecimals(2)
        self.height_spin.setSuffix(" mm")
        self.height_spin.setToolTip(
            "How far the QR modules protrude (emboss) or\n"
            "are recessed (deboss) from the surface.\n"
            "0.3 – 0.8 mm works well for most 3D prints."
        )
        layout.addRow("Height / Depth:", self.height_spin)

        # Mode
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["Emboss (raised)", "Deboss (recessed)"])
        self.mode_combo.setToolTip(
            "Emboss: QR modules protrude from the surface.\n"
            "Deboss: QR modules are cut into the surface."
        )
        layout.addRow("Mode:", self.mode_combo)

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
        sep2 = QtWidgets.QFrame()
        sep2.setFrameShape(QtWidgets.QFrame.HLine)
        layout.addRow(sep2)

        # Scanning parameters label
        scan_label = QtWidgets.QLabel("<i>Scanning parameters</i>")
        scan_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addRow(scan_label)

        # Error correction
        self.ec_combo = QtWidgets.QComboBox()
        self.ec_combo.addItems([
            "L  –  7 % recovery",
            "M  – 15 % recovery",
            "Q  – 25 % recovery",
            "H  – 30 % recovery",
        ])
        self.ec_combo.setCurrentIndex(1)  # default M
        self.ec_combo.setToolTip(
            "Higher error correction makes the code more\n"
            "robust to damage or printing artefacts, but\n"
            "increases the number of modules."
        )
        layout.addRow("Error Correction:", self.ec_combo)

        # Border (quiet zone)
        self.border_spin = QtWidgets.QSpinBox()
        self.border_spin.setRange(0, 8)
        self.border_spin.setValue(2)
        self.border_spin.setSuffix(" modules")
        self.border_spin.setToolTip(
            "Quiet-zone border around the QR code.\n"
            "The standard requires 4, but 2 is usually\n"
            "sufficient for most scanners."
        )
        layout.addRow("Border:", self.border_spin)

        # Info label
        self.info_label = QtWidgets.QLabel("")
        self.info_label.setAlignment(QtCore.Qt.AlignCenter)
        self.info_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addRow(self.info_label)

        # Update info when parameters change
        self.url_edit.textChanged.connect(self._update_info)
        self.size_spin.valueChanged.connect(self._update_info)
        self.ec_combo.currentIndexChanged.connect(self._update_info)
        self.border_spin.valueChanged.connect(self._update_info)

        self._update_info()

        return widget

    def _apply_prefill(self, p):
        """Set widget values from a saved-parameter dict."""
        if "url" in p:
            self.url_edit.setText(p["url"])
        if "size" in p:
            self.size_spin.setValue(p["size"])
        if "height" in p:
            self.height_spin.setValue(p["height"])
        if "emboss" in p:
            self.mode_combo.setCurrentIndex(0 if p["emboss"] else 1)
        if "ec" in p:
            idx = _EC_KEYS.index(p["ec"]) if p["ec"] in _EC_KEYS else 1
            self.ec_combo.setCurrentIndex(idx)
        if "border" in p:
            self.border_spin.setValue(p["border"])
        if "x_offset" in p:
            self.x_offset_spin.setValue(p["x_offset"])
        if "y_offset" in p:
            self.y_offset_spin.setValue(p["y_offset"])
        self._update_info()

    def _update_info(self):
        """Show estimated module size based on current parameters."""
        url = self.url_edit.text().strip()
        if not url:
            self.info_label.setText("Enter a URL to see module size estimate")
            return

        try:
            from qr_emboss import generate_qr_matrix
            ec_key = _EC_KEYS[self.ec_combo.currentIndex()]
            border = self.border_spin.value()
            matrix = generate_qr_matrix(url, ec_key, border)
            n = len(matrix)
            size = self.size_spin.value()
            mod_mm = size / float(n)
            version = (n - 2 * border - 17) // 4 + 1
            colour = "#060" if mod_mm >= 0.3 else "#c00"
            self.info_label.setText(
                '<span style="color:{c}">Version {v}, {n}x{n} modules, '
                '{m:.2f} mm/module</span>'
                .format(c=colour, v=version, n=n, m=mod_mm)
            )
        except ImportError:
            self.info_label.setText(
                '<span style="color:#c00">'
                'qrcode package not installed</span>'
            )
        except Exception:
            self.info_label.setText("")

    # -- Task panel interface ----------------------------------------------

    def accept(self):
        """Called when the user presses OK."""
        url = self.url_edit.text().strip()
        if not url:
            QtWidgets.QMessageBox.warning(
                None, "QR Code",
                "Please enter a URL or text to encode.",
            )
            return False

        size = self.size_spin.value()
        height = self.height_spin.value()
        emboss = self.mode_combo.currentIndex() == 0
        ec_key = _EC_KEYS[self.ec_combo.currentIndex()]
        border = self.border_spin.value()
        x_offset = self.x_offset_spin.value()
        y_offset = self.y_offset_spin.value()

        try:
            from qr_emboss import apply_qr

            face = getattr(self.body_obj.Shape, self.face_name)
            body_shape = self.body_obj.Shape

            new_shape, module_size = apply_qr(
                body_shape,
                face,
                url,
                size=size,
                height=height,
                emboss=emboss,
                error_correction=ec_key,
                border=border,
                x_offset=x_offset,
                y_offset=y_offset,
            )
        except ImportError as exc:
            QtWidgets.QMessageBox.critical(
                None, "Missing Dependency", str(exc),
            )
            return False
        except Exception as exc:
            FreeCAD.Console.PrintError(
                "QR code operation failed: {}\n".format(exc)
            )
            QtWidgets.QMessageBox.critical(
                None,
                "QR Code Error",
                "Boolean operation failed:\n\n{}\n\n"
                "Make sure the selected face has enough room for "
                "the QR code.".format(exc),
            )
            return False

        doc = FreeCAD.ActiveDocument

        # If re-editing, remove the old result first
        if self.edit_obj is not None:
            doc.removeObject(self.edit_obj.Name)

        # Create the result as a FeaturePython (enables double-click re-edit)
        label = "QRCodeEmboss" if emboss else "QRCodeDeboss"
        result_obj = doc.addObject("Part::FeaturePython", label)
        _QRCodeProxy(result_obj)
        _QRCodeViewProvider(result_obj.ViewObject)
        result_obj.Shape = new_shape

        # Store parameters so the QR code can be re-edited later
        result_obj.addProperty(
            "App::PropertyString", "QR_URL", "QR Code", "Encoded URL")
        result_obj.addProperty(
            "App::PropertyFloat", "QR_Size", "QR Code", "QR code size (mm)")
        result_obj.addProperty(
            "App::PropertyFloat", "QR_Height", "QR Code", "Height / depth (mm)")
        result_obj.addProperty(
            "App::PropertyBool", "QR_Emboss", "QR Code", "True=emboss, False=deboss")
        result_obj.addProperty(
            "App::PropertyString", "QR_ErrorCorrection", "QR Code",
            "Error correction level (L/M/Q/H)")
        result_obj.addProperty(
            "App::PropertyInteger", "QR_Border", "QR Code",
            "Quiet-zone border (modules)")
        result_obj.addProperty(
            "App::PropertyFloat", "QR_XOffset", "QR Code",
            "Horizontal offset from face centre (mm)")
        result_obj.addProperty(
            "App::PropertyFloat", "QR_YOffset", "QR Code",
            "Vertical offset from face centre (mm)")
        result_obj.addProperty(
            "App::PropertyString", "QR_FaceName", "QR Code",
            "Face used on the original body")
        result_obj.addProperty(
            "App::PropertyString", "QR_OriginalBody", "QR Code",
            "Original body object name")

        result_obj.QR_URL = url
        result_obj.QR_Size = size
        result_obj.QR_Height = height
        result_obj.QR_Emboss = emboss
        result_obj.QR_ErrorCorrection = ec_key
        result_obj.QR_Border = border
        result_obj.QR_XOffset = x_offset
        result_obj.QR_YOffset = y_offset
        result_obj.QR_FaceName = self.face_name
        result_obj.QR_OriginalBody = self.body_obj.Name

        # Copy visual properties from the source
        if hasattr(self.body_obj, "ViewObject"):
            src_vo = self.body_obj.ViewObject
            dst_vo = result_obj.ViewObject
            if hasattr(src_vo, "ShapeColor"):
                dst_vo.ShapeColor = src_vo.ShapeColor
            if hasattr(src_vo, "Transparency"):
                dst_vo.Transparency = src_vo.Transparency

        # Hide the original body so the modified version is visible
        self.body_obj.ViewObject.Visibility = False

        doc.recompute()
        FreeCADGui.Control.closeDialog()

        mode_word = "embossed" if emboss else "debossed"
        FreeCAD.Console.PrintMessage(
            "QR code {} onto {}.{} "
            "(size={}mm, height={}mm, module={:.3f}mm)\n"
            .format(
                mode_word, self.body_obj.Label, self.face_name,
                size, height, module_size,
            )
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

class QRCodeCommand:
    """FreeCAD command that embosses/debosses a QR code onto a face."""

    def GetResources(self):
        return {
            "Pixmap": os.path.join(
                _plugin_dir, "resources", "icons", "QRCode.svg"
            ),
            "MenuText": "QR Code Emboss",
            "ToolTip": (
                "Emboss or deboss a QR code onto the selected flat face.\n"
                "Select an existing QR result to re-edit its parameters.\n"
                "Encode a URL linking to tutorials, instructional videos,\n"
                "or other online materials for your product."
            ),
        }

    def IsActive(self):
        """Active when a planar face or an existing QR result is selected."""
        sel = FreeCADGui.Selection.getSelectionEx()
        if len(sel) != 1:
            return False
        obj = sel[0].Object
        # Re-edit mode: existing QR result selected
        if hasattr(obj, "QR_URL"):
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

        # --- Re-edit an existing QR code result ---
        if hasattr(obj, "QR_URL"):
            original = FreeCAD.ActiveDocument.getObject(obj.QR_OriginalBody)
            if original is None:
                QtWidgets.QMessageBox.warning(
                    None, "QR Code",
                    "Cannot re-edit: the original body object was deleted.",
                )
                return

            prefill = {
                "url": obj.QR_URL,
                "size": obj.QR_Size,
                "height": obj.QR_Height,
                "emboss": obj.QR_Emboss,
                "ec": obj.QR_ErrorCorrection,
                "border": obj.QR_Border,
                "x_offset": obj.QR_XOffset if hasattr(obj, "QR_XOffset") else 0.0,
                "y_offset": obj.QR_YOffset if hasattr(obj, "QR_YOffset") else 0.0,
            }
            panel = QRCodeTaskPanel(
                original, obj.QR_FaceName,
                edit_obj=obj, prefill=prefill,
            )
            FreeCADGui.Control.showDialog(panel)
            return

        # --- New QR code on a selected face ---
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
                "QR codes require a flat surface for reliable scanning.",
            )
            return

        panel = QRCodeTaskPanel(obj, face_name)
        FreeCADGui.Control.showDialog(panel)


# Register the command with FreeCAD
FreeCADGui.addCommand("TrailCurrent_QRCodeEmboss", QRCodeCommand())
