# -*- coding: utf-8 -*-
"""FreeCAD GUI command to start / stop the MCP RPC server."""

import os
import FreeCAD
import FreeCADGui

from mcp import rpc_server


class MCPServerCommand:
    """Toggle the MCP RPC server on or off."""

    def GetResources(self):
        icon_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "resources", "icons",
        )
        return {
            "Pixmap": os.path.join(icon_dir, "MCPServer.svg"),
            "MenuText": "MCP Server",
            "ToolTip": (
                "Start or stop the MCP RPC server so that external AI "
                "tools (Claude Code, etc.) can interact with FreeCAD"
            ),
        }

    def IsActive(self):
        return True

    def Activated(self):
        if rpc_server.is_running():
            rpc_server.stop()
            FreeCAD.Console.PrintMessage("MCP server stopped.\n")
        else:
            rpc_server.start()


FreeCADGui.addCommand("TrailCurrent_MCPServer", MCPServerCommand())
