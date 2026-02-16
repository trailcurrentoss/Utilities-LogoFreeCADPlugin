# Settings Reference

When you activate the Deboss command, a settings panel appears in the left sidebar with five parameters. This page explains what each one does and how they interact.

## Logo Diameter

| | |
|---|---|
| **What it controls** | The overall size of the logo on the surface |
| **Unit** | Millimeters (mm) |
| **Default** | 18.0 mm |
| **Range** | 5.0 – 100.0 mm |
| **Step size** | 1.0 mm |

This is the diameter of the outer circle. Everything inside — the mountain, trail, and bolt — scales proportionally. A diameter of 18 mm fits well on small enclosure lids. Larger cases can use 25-40 mm.

Make sure the selected face is larger than the diameter you choose, leaving some margin around the edges. If the logo extends past the face boundary, the boolean cut may produce unexpected results.

## Total Depth

| | |
|---|---|
| **What it controls** | How deep the deepest part of the logo is cut below the surface |
| **Unit** | Millimeters (mm) |
| **Default** | 0.80 mm |
| **Range** | 0.10 – 5.00 mm |
| **Step size** | 0.05 mm |

This is the maximum cut depth, which applies to the circle background — the flat floor at the bottom of the logo. All other layers (mountain, trail, bolt) are cut to a fraction of this depth, so they sit at different heights above the floor.

**This value must be less than the wall thickness behind the face you're cutting into.** If Total Depth exceeds the wall thickness, the cut will punch through to the other side.

### Depth guidelines by wall thickness

| Wall thickness | Recommended Total Depth | Notes |
|---------------|------------------------|-------|
| 0.8 mm | 0.30 – 0.50 mm | Thin lids, keep conservative |
| 1.2 mm (typical 3D print) | 0.60 – 0.80 mm | Default setting works well |
| 2.0 mm | 0.80 – 1.20 mm | Room for deeper, more dramatic relief |
| 3.0+ mm | 1.00 – 2.00 mm | Full depth range available |

## Depth Ratios

The three remaining settings control how deep each logo element is cut, expressed as a **percentage of the Total Depth**. These percentages determine the layered staircase effect that makes the logo visually distinct.

### How the layers work

Think of the logo as being carved into a series of steps, viewed from the side:

```
 Surface  ─────────────────────────────────────
              ░░░░░  Bolt (15%)
           ░░░░░░░░░░░  Trail (30%)
        ░░░░░░░░░░░░░░░░░  Mountain (55%)
     ░░░░░░░░░░░░░░░░░░░░░░░  Circle (100%)
 Floor    ─────────────────────────────────────
```

- The **circle background** is always cut to 100% of the Total Depth (the floor)
- The **mountain** is cut to its percentage of Total Depth, so it sits above the floor
- The **trail** is cut shallower still, sitting above the mountain
- The **bolt** is cut the least, sitting closest to the original surface

The space between each layer's depth creates the visible step that separates them. Larger differences between percentages mean more visible separation between layers.

### Mountain Depth

| | |
|---|---|
| **What it controls** | How deep the mountain silhouette is cut, as a percentage of Total Depth |
| **Unit** | Percent (%) |
| **Default** | 55% |
| **Range** | 10 – 90% |
| **Step size** | 5% |

At the default of 55%, the mountain is cut to 55% of the Total Depth. With a Total Depth of 0.80 mm, that's a 0.44 mm cut, leaving the mountain surface 0.36 mm above the circle floor.

- **Higher values** (70-90%): Mountain sits closer to the floor, less visible separation from the background
- **Lower values** (10-40%): Mountain sits higher up, closer to the surface, more raised appearance

### Trail Depth

| | |
|---|---|
| **What it controls** | How deep the winding trail path is cut, as a percentage of Total Depth |
| **Unit** | Percent (%) |
| **Default** | 30% |
| **Range** | 5 – 80% |
| **Step size** | 5% |

At the default of 30%, the trail is cut to 30% of the Total Depth. With a Total Depth of 0.80 mm, that's a 0.24 mm cut, leaving the trail 0.56 mm above the floor and 0.20 mm above the mountain.

The trail should generally be set lower than the mountain to maintain the correct visual layering. If you set it higher than the mountain, the trail will appear to be recessed below the mountain surface rather than running across the top of it.

### Bolt Depth

| | |
|---|---|
| **What it controls** | How deep the lightning bolt accent is cut, as a percentage of Total Depth |
| **Unit** | Percent (%) |
| **Default** | 15% |
| **Range** | 5 – 70% |
| **Step size** | 5% |

At the default of 15%, the bolt is cut to 15% of the Total Depth. With a Total Depth of 0.80 mm, that's a 0.12 mm cut — barely below the surface. This makes the bolt the most prominent raised feature in the logo.

The bolt should generally be the shallowest cut (lowest percentage) to maintain the intended layering where it appears most raised.

## Default Settings — Worked Example

With all defaults (Total Depth = 0.80 mm):

| Layer | Depth % | Cut depth | Distance below surface | Distance above floor |
|-------|---------|-----------|----------------------|---------------------|
| Surface | — | 0.00 mm | 0.00 mm | 0.80 mm |
| Bolt | 15% | 0.12 mm | 0.12 mm | 0.68 mm |
| Trail | 30% | 0.24 mm | 0.24 mm | 0.56 mm |
| Mountain | 55% | 0.44 mm | 0.44 mm | 0.36 mm |
| Circle floor | 100% | 0.80 mm | 0.80 mm | 0.00 mm |

The step height between each adjacent layer:

| Transition | Step height |
|-----------|------------|
| Surface to Bolt | 0.12 mm |
| Bolt to Trail | 0.12 mm |
| Trail to Mountain | 0.20 mm |
| Mountain to Circle | 0.36 mm |

## Recommendations for 3D Printing

For FDM/FFF 3D printers, the depth differences between layers need to be large enough for the printer to resolve. Most printers have a layer height of 0.10 – 0.20 mm.

- With a **0.20 mm layer height**, the default settings produce step heights of 0.12 mm (one layer or less) between some layers. The logo will be visible but the finer steps may merge. Consider increasing Total Depth to 1.0-1.2 mm for clearer separation.
- With a **0.10 mm layer height**, the default 0.80 mm Total Depth gives enough resolution for all four layers to be distinguishable.
- For the clearest result, ensure each step height between adjacent layers is at least **one print layer height**. Use the table above as a guide and scale the Total Depth accordingly.

### Suggested presets

| Scenario | Total Depth | Mountain | Trail | Bolt |
|----------|------------|----------|-------|------|
| Default (general purpose) | 0.80 mm | 55% | 30% | 15% |
| Thin lid (0.8-1.0 mm wall) | 0.40 mm | 60% | 35% | 15% |
| Thick case (2+ mm wall) | 1.20 mm | 55% | 30% | 15% |
| High contrast (dramatic steps) | 1.00 mm | 75% | 45% | 15% |
| Subtle branding | 0.40 mm | 50% | 30% | 15% |
