# TrailCurrent Logo & QR Code Plugin for FreeCAD

A FreeCAD workbench for branding 3D-printed parts with the TrailCurrent logo and scannable QR codes. Deboss the logo as a multi-level relief, or emboss/deboss QR codes linking to tutorials, instructional videos, or other online materials.

![TrailCurrent Logo](resources/icons/TrailCurrentLogo.svg) ![QR Code](resources/icons/QRCode.svg)

## Features

### Logo Deboss

Select any flat face, click the toolbar button, and the plugin cuts the TrailCurrent logo into the surface with four layers at different depths:

| Layer | What it is | Depth behavior |
|-------|-----------|----------------|
| Circle background | The round border of the logo | Deepest cut (the "floor") |
| Mountain silhouette | The mountain peaks | Mid-depth cut |
| Trail path | The winding trail line | Shallow cut |
| Lightning bolt | The electricity accent | Shallowest cut (barely below the surface) |

This creates a staircase-like relief where the bolt appears most raised, followed by the trail, then the mountain, with the circle background at the bottom.

### QR Code Emboss / Deboss

Generate a QR code from any URL or text and apply it directly to a flat face. The QR code can be:

- **Embossed** (raised) or **debossed** (recessed)
- Sized to fit your part (5-200 mm)
- Positioned anywhere on the face with X/Y offsets
- Configured with error correction level (L/M/Q/H) and quiet-zone border

The live preview shows module count, QR version, and module size so you can verify scannability before committing.

### Re-editing

Both logo and QR code objects store their parameters. To change settings after creation:

- **Double-click** the object in the model tree to reopen the edit panel
- Or select the object and click the toolbar button

All parameters are pre-filled from the previous values.

## Quick Start

1. [Install the plugin](docs/installation.md)
2. Restart FreeCAD
3. Open your project and select a flat face on a solid body
4. Switch to the **TrailCurrent Logo** workbench (dropdown in the toolbar)
5. Click **Deboss TrailCurrent Logo** or **QR Code Emboss** in the toolbar
6. Adjust the parameters in the side panel
7. Click **OK**

## Documentation

- [Installation Guide](docs/installation.md) -- How to install via Addon Manager or manually
- [Usage Guide](docs/usage.md) -- Step-by-step walkthrough with tips for both tools
- [Settings Reference](docs/settings.md) -- Detailed explanation of every parameter

## Requirements

- FreeCAD 0.21 or newer (tested with FreeCAD 1.0)
- The `qrcode` Python package is **bundled** with the plugin -- no separate installation needed

## File Structure

```
├── package.xml           # Addon Manager metadata
├── InitGui.py            # Workbench registration
├── Init.py               # Non-GUI initialization
├── logo_command.py       # Logo toolbar command, task panel, and ViewProvider
├── logo_geometry.py      # SVG logo → FreeCAD 2D geometry conversion
├── logo_deboss.py        # Logo boolean cut operations and face alignment
├── qr_command.py         # QR code toolbar command, task panel, and ViewProvider
├── qr_emboss.py          # QR code generation, geometry, and boolean operations
├── qrcode/               # Bundled qrcode Python package (no pip install needed)
├── install.sh            # Manual install helper (Linux)
├── LICENSE               # MIT License
├── resources/
│   └── icons/
│       ├── TrailCurrentLogo.svg
│       └── QRCode.svg
└── docs/
    ├── installation.md
    ├── usage.md
    └── settings.md
```

## License

MIT License. See [LICENSE](LICENSE) for details.

## Links

- [GitHub Repository](https://github.com/trailcurrentoss/Utilities-LogoFreeCADPlugin)
- [Issue Tracker](https://github.com/trailcurrentoss/Utilities-LogoFreeCADPlugin/issues)
- [TrailCurrent Project](https://github.com/trailcurrentoss)
