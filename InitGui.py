# -*- coding: utf-8 -*-
import os
import sys
import inspect
import FreeCAD
import FreeCADGui

try:
    # Derive our plugin directory from the code object's filename.
    # FreeCAD does not set __file__ when it exec()s InitGui.py, but the
    # code object always knows its source path.
    _plugin_dir = os.path.dirname(os.path.abspath(
        inspect.currentframe().f_code.co_filename
    ))
    # FreeCAD exec()s this file with separate globals/locals dicts.
    # Class bodies can only see globals, so we must store it there.
    globals()['_plugin_dir'] = _plugin_dir

    if _plugin_dir not in sys.path:
        sys.path.insert(0, _plugin_dir)

    FreeCAD.Console.PrintMessage(
        "TrailCurrent Logo plugin: loading from {}\n".format(_plugin_dir)
    )

    class TrailCurrentLogoWorkbench(FreeCADGui.Workbench):
        MenuText = "TrailCurrent Logo"
        ToolTip = "Deboss the TrailCurrent brand logo and emboss QR codes onto flat surfaces"
        Icon = os.path.join(_plugin_dir, "resources", "icons", "TrailCurrentLogo.svg")

        def GetClassName(self):
            return "Gui::PythonWorkbench"

        def Initialize(self):
            FreeCAD.Console.PrintMessage("TrailCurrent Logo: Initialize()\n")
            import logo_command
            import qr_command
            cmd_list = ["TrailCurrent_DebossLogo", "TrailCurrent_QRCodeEmboss"]
            self.appendToolbar("TrailCurrent Logo", cmd_list)
            self.appendMenu("TrailCurrent", cmd_list)

        def Activated(self):
            FreeCAD.Console.PrintMessage("TrailCurrent Logo: Activated\n")

        def Deactivated(self):
            pass

    FreeCADGui.addWorkbench(TrailCurrentLogoWorkbench)
    FreeCAD.Console.PrintMessage("TrailCurrent Logo plugin: workbench registered OK\n")
except Exception as e:
    FreeCAD.Console.PrintError("TrailCurrent Logo plugin FAILED: {}\n".format(e))
