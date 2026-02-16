"""Locator module — exists solely so InitGui.py can find the plugin directory.

FreeCAD does not set __file__ when it executes InitGui.py, so we import
this module (which *does* have __file__) and derive paths from it.
"""
import os

PLUGIN_DIR = os.path.dirname(__file__)
ICON_DIR = os.path.join(PLUGIN_DIR, "resources", "icons")
