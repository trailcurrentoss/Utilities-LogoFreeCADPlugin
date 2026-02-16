# Installation Guide

## Option 1: FreeCAD Addon Manager (Recommended)

The Addon Manager is FreeCAD's built-in package manager. This is the easiest way to install.

### Adding the repository

1. Open FreeCAD
2. Go to **Tools > Addon Manager**
3. Click the **gear icon** (settings) in the top-right corner
4. Select **Custom repositories**
5. In the **Repository URL** field, enter:
   ```
   https://github.com/trailcurrentoss/Utilities-LogoFreeCADPlugin
   ```
6. Leave the branch field empty (defaults to `main`)
7. Click **Add**
8. Click **OK** to close settings

### Installing

1. Back in the Addon Manager, search for **TrailCurrent Logo**
2. Select it from the results list
3. Click **Install**
4. Restart FreeCAD when prompted

### Updating

1. Open **Tools > Addon Manager**
2. Click **Check for updates** (top of the window)
3. If an update is available for TrailCurrent Logo, select it and click **Update**
4. Restart FreeCAD

## Option 2: Manual Install (Linux)

If you cloned or downloaded the repository yourself, an install script is provided for Linux systems.

### Clone and install

```bash
git clone https://github.com/trailcurrentoss/Utilities-LogoFreeCADPlugin.git
cd Utilities-LogoFreeCADPlugin
chmod +x install.sh
./install.sh
```

The script automatically detects your FreeCAD installation:

| FreeCAD Install | Mod Directory | Install Method |
|-----------------|---------------|----------------|
| Snap package | `~/snap/freecad/common/Mod/` | Copies files (snap sandbox blocks symlinks) |
| Native / AppImage | `~/.local/share/FreeCAD/Mod/` | Creates a symlink |
| Legacy native | `~/.FreeCAD/Mod/` | Creates a symlink |

For **snap installs**, you need to re-run `./install.sh` after pulling updates, because the files are copied rather than symlinked.

For **native installs**, the symlink means changes to the cloned repo take effect immediately (just restart FreeCAD).

### Manual copy (any OS)

If the install script doesn't cover your setup, you can copy the plugin manually:

1. Find your FreeCAD Mod directory:
   - Open FreeCAD
   - Go to **Edit > Preferences > General**
   - Note the **User configuration** path
   - Your Mod directory is at that same level, e.g. `~/.local/share/FreeCAD/Mod/`
   - Or type this in the FreeCAD Python console:
     ```python
     FreeCAD.getUserAppDataDir() + "Mod"
     ```

2. Copy the entire plugin folder into that Mod directory:
   ```bash
   cp -r Utilities-LogoFreeCADPlugin /path/to/FreeCAD/Mod/
   ```

3. Restart FreeCAD

## Verifying the Installation

After restarting FreeCAD:

1. Look for **TrailCurrent Logo** in the workbench dropdown (the dropdown selector in the main toolbar, usually set to "Start" or "Part Design" by default)
2. If you see it listed, the installation was successful
3. Switch to it and you should see the **Deboss TrailCurrent Logo** button in the toolbar

### Troubleshooting

**Workbench doesn't appear in the dropdown:**
- Make sure you restarted FreeCAD after installing
- Check the FreeCAD Python console (View > Panels > Python console) for error messages mentioning "TrailCurrent"
- Verify the files are in the correct Mod directory by checking that `InitGui.py` exists at the top level of the plugin folder inside Mod

**"No module named logo_command" error in the console:**
- The plugin directory may not be on Python's search path. This is usually handled automatically, but if you see this error, check that all `.py` files are in the same directory as `InitGui.py`

## Uninstalling

**Addon Manager installs:** Open **Tools > Addon Manager**, find TrailCurrent Logo, and click **Uninstall**.

**Manual installs:** Delete the plugin folder from your FreeCAD Mod directory and restart FreeCAD.
