# Settings Reference

Both tools open a settings panel in the left sidebar. This page documents every parameter.

---

## Logo Deboss Settings

### Logo Diameter

| | |
|---|---|
| **What it controls** | The overall size of the logo on the surface |
| **Unit** | Millimeters (mm) |
| **Default** | 18.0 mm |
| **Range** | 5.0 -- 100.0 mm |
| **Step size** | 1.0 mm |

This is the diameter of the outer circle. Everything inside -- the mountain, trail, and bolt -- scales proportionally. A diameter of 18 mm fits well on small enclosure lids. Larger cases can use 25-40 mm.

Make sure the selected face is larger than the diameter you choose, leaving some margin around the edges.

### Total Depth

| | |
|---|---|
| **What it controls** | How deep the deepest part of the logo is cut below the surface |
| **Unit** | Millimeters (mm) |
| **Default** | 0.80 mm |
| **Range** | 0.10 -- 5.00 mm |
| **Step size** | 0.05 mm |

This is the maximum cut depth, which applies to the circle background. All other layers are cut to a fraction of this depth.

**This value must be less than the wall thickness behind the face you're cutting into.**

#### Depth guidelines by wall thickness

| Wall thickness | Recommended Total Depth | Notes |
|---------------|------------------------|-------|
| 0.8 mm | 0.30 -- 0.50 mm | Thin lids, keep conservative |
| 1.2 mm (typical 3D print) | 0.60 -- 0.80 mm | Default setting works well |
| 2.0 mm | 0.80 -- 1.20 mm | Room for deeper, more dramatic relief |
| 3.0+ mm | 1.00 -- 2.00 mm | Full depth range available |

### X Offset / Y Offset

| | |
|---|---|
| **What it controls** | Position of the logo relative to the face center |
| **Unit** | Millimeters (mm) |
| **Default** | 0.0 mm |
| **Range** | -500.0 -- 500.0 mm |
| **Step size** | 1.0 mm |

Moves the logo horizontally (X) or vertically (Y) from the center of the selected face. Useful when placing the logo off-center or when combining with a QR code on the same face.

### Depth Ratios

The three depth ratio sliders control how deep each logo element is cut, expressed as a **percentage of the Total Depth**.

#### How the layers work

```
 Surface  ─────────────────────────────────────
              ░░░░░  Bolt (15%)
           ░░░░░░░░░░░  Trail (30%)
        ░░░░░░░░░░░░░░░░░  Mountain (55%)
     ░░░░░░░░░░░░░░░░░░░░░░░  Circle (100%)
 Floor    ─────────────────────────────────────
```

#### Mountain Depth

| | |
|---|---|
| **Default** | 55% |
| **Range** | 10 -- 90% |
| **Step size** | 5% |

The mountain silhouette cut depth as a percentage of Total Depth. Higher values = mountain sits closer to the floor. Lower values = mountain appears more raised.

#### Trail Depth

| | |
|---|---|
| **Default** | 30% |
| **Range** | 5 -- 80% |
| **Step size** | 5% |

The winding trail path cut depth. Should generally be less than Mountain Depth to maintain the correct visual layering.

#### Bolt Depth

| | |
|---|---|
| **Default** | 15% |
| **Range** | 5 -- 70% |
| **Step size** | 5% |

The lightning bolt cut depth. This should be the shallowest (lowest percentage) to keep the bolt as the most prominent raised feature.

### Default Settings -- Worked Example

With all defaults (Total Depth = 0.80 mm):

| Layer | Depth % | Cut depth | Distance below surface | Distance above floor |
|-------|---------|-----------|----------------------|---------------------|
| Surface | -- | 0.00 mm | 0.00 mm | 0.80 mm |
| Bolt | 15% | 0.12 mm | 0.12 mm | 0.68 mm |
| Trail | 30% | 0.24 mm | 0.24 mm | 0.56 mm |
| Mountain | 55% | 0.44 mm | 0.44 mm | 0.36 mm |
| Circle floor | 100% | 0.80 mm | 0.80 mm | 0.00 mm |

### Logo Presets

| Scenario | Total Depth | Mountain | Trail | Bolt |
|----------|------------|----------|-------|------|
| Default (general purpose) | 0.80 mm | 55% | 30% | 15% |
| Thin lid (0.8-1.0 mm wall) | 0.40 mm | 60% | 35% | 15% |
| Thick case (2+ mm wall) | 1.20 mm | 55% | 30% | 15% |
| High contrast (dramatic steps) | 1.00 mm | 75% | 45% | 15% |
| Subtle branding | 0.40 mm | 50% | 30% | 15% |

---

## QR Code Settings

### URL / Data

| | |
|---|---|
| **What it controls** | The text encoded in the QR code |
| **Default** | (empty) |

Enter a URL, product code, or any text. Shorter strings produce smaller QR codes with fewer modules, which scan more reliably at small physical sizes.

### QR Size

| | |
|---|---|
| **What it controls** | Side length of the QR code square |
| **Unit** | Millimeters (mm) |
| **Default** | 20.0 mm |
| **Range** | 5.0 -- 200.0 mm |
| **Step size** | 1.0 mm |

Larger sizes improve scannability. The info label at the bottom of the panel shows the resulting module size -- aim for 0.3 mm or larger per module.

### Height / Depth

| | |
|---|---|
| **What it controls** | How far QR modules protrude (emboss) or are recessed (deboss) |
| **Unit** | Millimeters (mm) |
| **Default** | 0.50 mm |
| **Range** | 0.10 -- 5.00 mm |
| **Step size** | 0.05 mm |

For 3D printing, 0.3-0.8 mm works well. Too shallow and the modules may not be visible after printing. Too deep and you risk punching through thin walls (deboss) or creating fragile protrusions (emboss).

### Mode

| | |
|---|---|
| **Options** | Emboss (raised) / Deboss (recessed) |
| **Default** | Emboss |

- **Emboss** -- dark QR modules protrude from the surface (boolean fuse). Best when you can paint the raised area for contrast.
- **Deboss** -- dark QR modules are cut into the surface (boolean cut). Natural shadows from 3D printing provide some contrast.

### X Offset / Y Offset

| | |
|---|---|
| **What it controls** | Position of the QR code relative to the face center |
| **Unit** | Millimeters (mm) |
| **Default** | 0.0 mm |
| **Range** | -500.0 -- 500.0 mm |
| **Step size** | 1.0 mm |

Shifts the QR code horizontally (X) or vertically (Y) from the face center.

### Error Correction

| | |
|---|---|
| **What it controls** | How much damage or distortion the QR code can tolerate |
| **Default** | M (15% recovery) |
| **Options** | L (7%), M (15%), Q (25%), H (30%) |

Higher error correction makes the code more robust but increases the number of modules. For 3D-printed parts, M is a good default. Use Q or H if the part will be exposed to wear or harsh conditions.

### Border

| | |
|---|---|
| **What it controls** | Quiet-zone width around the QR code |
| **Unit** | Modules |
| **Default** | 2 |
| **Range** | 0 -- 8 |

The QR standard requires 4 modules of quiet zone, but 2 is sufficient for most phone scanners. Increase to 3-4 if scanning is unreliable.

### Info Label

The info line at the bottom of the panel updates in real time as you change parameters. It shows:

- **QR version** -- the QR code version (1-40), determined automatically from the data length and error correction
- **Module count** -- the grid size (e.g., 29x29)
- **Module size** -- the physical size of each module in mm

The text is shown in **green** when the module size is 0.3 mm or larger (good scannability) and **red** when below 0.3 mm (may be hard to scan).

---

## 3D Printing Recommendations

### Logo

For FDM printers, the depth differences between layers need to be large enough for the printer to resolve. Most printers have a layer height of 0.10-0.20 mm.

- With **0.20 mm layer height**, the default settings produce step heights of 0.12 mm between some layers. Consider increasing Total Depth to 1.0-1.2 mm for clearer separation.
- With **0.10 mm layer height**, the default 0.80 mm Total Depth gives enough resolution for all four layers to be distinguishable.

### QR Code

- Module sizes below 0.3 mm may not print cleanly or scan reliably
- For emboss mode, consider painting the raised modules with a dark color for maximum contrast
- For deboss mode, the recessed areas should be deep enough to create visible shadows (0.3+ mm)
- Test scanning the printed QR code from your intended viewing distance before producing a batch
