# Usage Guide

## Overview

The plugin cuts the TrailCurrent logo into a flat surface of your choosing. You select a face, set the size and depth, and the plugin does the rest using boolean cut operations.

The result is a new solid object called **LogoDeboss** with the logo carved into it. The original body is hidden but not deleted, so you can always go back.

## Step-by-Step Walkthrough

### 1. Open your project

Open the FreeCAD file containing the part you want to brand. This works with any solid body that has at least one flat face — case lids, enclosure panels, flat plates, etc.

### 2. Switch to the TrailCurrent Logo workbench

Use the workbench dropdown in the main toolbar (it usually says "Start" or "Part Design") and select **TrailCurrent Logo**.

The toolbar now shows the **Deboss TrailCurrent Logo** button with the TrailCurrent icon.

### 3. Select a flat face

In the 3D view, click on the flat face where you want the logo placed. The face must be:

- **Planar** — flat surfaces only, not curved or cylindrical
- **Large enough** — the face should be wider than your chosen logo diameter

You should see the face highlight when you click it. The status bar at the bottom will show something like `Face6` to confirm the selection.

### 4. Click the toolbar button

Click **Deboss TrailCurrent Logo** in the toolbar (or find it under **TrailCurrent > Deboss TrailCurrent Logo** in the menu bar).

A settings panel opens in the left sidebar.

### 5. Adjust the settings

The panel has five settings. See the [Settings Reference](settings.md) for detailed explanations of each one. In most cases, you only need to adjust the first two:

- **Logo Diameter** — how large the logo is on the face
- **Total Depth** — how deep the cut goes (keep this less than your wall thickness)

The three depth ratio sliders control how the four logo layers stack relative to each other. The defaults produce a good result for most cases.

### 6. Click OK

Press **OK** to run the deboss operation. This performs several boolean cuts and may take a few seconds depending on your part's complexity.

When it finishes:
- A new object called **LogoDeboss** appears in the model tree
- The original body is hidden (not deleted)
- The 3D view shows your part with the logo cut into it

### 7. Inspect the result

Rotate the view to check that the logo looks correct. You should see four distinct depth levels in the carved area:

- The circle background sits at the deepest level
- The mountain peaks sit above that
- The winding trail sits higher still
- The lightning bolt is the most raised, sitting just barely below the original surface

## Tips

### Choosing the right diameter

- For small enclosures (credit card to smartphone size), try **12-18 mm**
- For medium cases (Raspberry Pi to router size), try **18-25 mm**
- For large panels or covers, **25-40 mm** works well
- The logo scales proportionally — all elements maintain their relative positions at any size

### Choosing the right depth

- **Measure your wall thickness first.** The total depth must be less than the thickness of the wall behind the face you're cutting into. If you cut too deep, you'll punch through.
- For 3D printing with standard 1.2 mm walls, a total depth of **0.6-0.8 mm** works well
- For thicker walls (2+ mm), you can go deeper for a more dramatic effect — try **1.0-1.5 mm**
- For thin lids (under 1 mm), keep the total depth at **0.3-0.5 mm**

### Working with the result

- The **LogoDeboss** object is a standalone Part::Feature. You can continue modeling on it, export it to STL, or use it as input for further operations.
- The original body is only hidden, not deleted. Toggle its visibility in the model tree to bring it back.
- If you want to undo the operation, delete the LogoDeboss object and un-hide the original body.
- To try different settings, delete the LogoDeboss object, un-hide the original, select the face again, and re-run the command.

### Exporting for 3D printing

1. Select the **LogoDeboss** object in the model tree
2. Go to **File > Export** (or **Part > Export CAD**)
3. Choose **STL Mesh (.stl)** as the format
4. Save the file

The multi-level relief should be clearly visible in your slicer's preview.

## Limitations

- **Flat faces only.** The logo cannot be applied to curved, cylindrical, or spherical surfaces. The command will show a warning if you select a non-planar face.
- **One logo at a time.** To apply multiple logos (e.g., on different faces), run the command again on the LogoDeboss result from the first operation.
- **Boolean complexity.** Very complex bodies with many features may cause the boolean cut to be slow or fail. If the operation fails, try simplifying the body first or using a slightly smaller diameter.
