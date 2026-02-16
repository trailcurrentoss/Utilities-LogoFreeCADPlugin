# TrailCurrent Logo Deboss Plugin for FreeCAD

A FreeCAD workbench that debosses the TrailCurrent brand logo onto any flat face. The logo is cut as a multi-level relief with four distinct layers at different depths, producing a visually striking result ideal for 3D-printed enclosures and cases.

![TrailCurrent Logo](resources/icons/TrailCurrentLogo.svg)

## What It Does

Select any flat face on a solid body, click the toolbar button, adjust the size and depth to fit your part, and press OK. The plugin cuts the logo into the surface with four layers at different depths:

| Layer | What it is | Depth behavior |
|-------|-----------|----------------|
| Circle background | The round border of the logo | Deepest cut (the "floor") |
| Mountain silhouette | The mountain peaks | Mid-depth cut |
| Trail path | The winding trail line | Shallow cut |
| Lightning bolt | The electricity accent | Shallowest cut (barely below the surface) |

This creates a staircase-like relief where the bolt appears most raised, followed by the trail, then the mountain, with the circle background sitting at the bottom.

## Quick Start

1. [Install the plugin](docs/installation.md)
2. Restart FreeCAD
3. Open your project and select a flat face on a solid body
4. Switch to the **TrailCurrent Logo** workbench (dropdown in the toolbar)
5. Click **Deboss TrailCurrent Logo** in the toolbar
6. Adjust the diameter and depth in the side panel
7. Click **OK**

## Documentation

- [Installation Guide](docs/installation.md) — How to install via Addon Manager or manually
- [Usage Guide](docs/usage.md) — Step-by-step walkthrough with tips
- [Settings Reference](docs/settings.md) — Detailed explanation of every parameter

## Requirements

- FreeCAD 0.20 or newer
- No external Python dependencies (uses only built-in FreeCAD/Part APIs)

## File Structure

```
├── package.xml           # Addon Manager metadata
├── InitGui.py            # Workbench registration
├── Init.py               # Non-GUI initialization
├── logo_command.py       # Toolbar command and settings panel UI
├── logo_geometry.py      # SVG logo → FreeCAD 2D geometry conversion
├── logo_deboss.py        # Boolean cut operations and face alignment
├── install.sh            # Manual install helper (Linux)
├── LICENSE               # MIT License
└── resources/
    └── icons/
        └── TrailCurrentLogo.svg
```

## License

MIT License. See [LICENSE](LICENSE) for details.

## Links

- [GitHub Repository](https://github.com/trailcurrentoss/Utilities-LogoFreeCADPlugin)
- [Issue Tracker](https://github.com/trailcurrentoss/Utilities-LogoFreeCADPlugin/issues)
- [TrailCurrent Project](https://github.com/trailcurrentoss)
