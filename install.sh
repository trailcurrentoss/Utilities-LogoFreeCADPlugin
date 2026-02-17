#!/bin/bash
# Install the TrailCurrent Logo & QR Code plugin into FreeCAD.
#
# Usage (local development):
#   ./install.sh
#
# For snap installs: copies files (snap sandbox can't follow symlinks to
# external storage).  For native installs: creates a symlink.
#
# Re-run this script after making changes to sync updates (snap only;
# native symlinks pick up changes automatically).
#
# Addon Manager users: You don't need this script.  Install directly
# from FreeCAD → Tools → Addon Manager → search "TrailCurrent Logo".

set -e

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_NAME="$(basename "$PLUGIN_DIR")"

# Detect FreeCAD Mod directory
if [ -d "$HOME/snap/freecad/common/Mod" ]; then
    MOD_DIR="$HOME/snap/freecad/common/Mod"
    IS_SNAP=1
elif [ -d "$HOME/.local/share/FreeCAD/Mod" ]; then
    MOD_DIR="$HOME/.local/share/FreeCAD/Mod"
    IS_SNAP=0
elif [ -d "$HOME/.FreeCAD/Mod" ]; then
    MOD_DIR="$HOME/.FreeCAD/Mod"
    IS_SNAP=0
else
    echo "ERROR: Could not find FreeCAD Mod directory."
    echo "Searched:"
    echo "  $HOME/snap/freecad/common/Mod"
    echo "  $HOME/.local/share/FreeCAD/Mod"
    echo "  $HOME/.FreeCAD/Mod"
    exit 1
fi

DEST="$MOD_DIR/$PLUGIN_NAME"

if [ "$IS_SNAP" = "1" ]; then
    # Snap: copy files (sandbox blocks symlinks to external storage)
    echo "Snap FreeCAD detected — copying files."

    # Remove old install (symlink or directory)
    if [ -L "$DEST" ]; then
        rm "$DEST"
    elif [ -d "$DEST" ]; then
        rm -rf "$DEST"
    fi

    cp -r "$PLUGIN_DIR" "$DEST"
    # Remove development artifacts from the copy
    rm -rf "$DEST/.git"
    rm -rf "$DEST/.claude"
    rm -rf "$DEST/__pycache__"
    find "$DEST" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find "$DEST" -name "*.pyc" -delete 2>/dev/null || true
    echo "Copied: $PLUGIN_DIR -> $DEST"
else
    # Native install: symlink
    if [ -L "$DEST" ]; then
        rm "$DEST"
    elif [ -d "$DEST" ]; then
        rm -rf "$DEST"
    fi

    ln -sf "$PLUGIN_DIR" "$DEST"
    echo "Linked: $DEST -> $PLUGIN_DIR"
fi

echo ""
echo "Restart FreeCAD to load the workbench."
echo "Look for 'TrailCurrent Logo' in the workbench dropdown."
echo ""
echo "Available tools:"
echo "  - Deboss TrailCurrent Logo  (multi-level relief logo)"
echo "  - QR Code Emboss            (scannable QR codes)"
