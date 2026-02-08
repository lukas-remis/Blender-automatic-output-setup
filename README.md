# Output Setup Helper (Blender 5.0)

**Output Setup Helper** is a Blender compositor add-on that automatically creates and maintains a clean, production-ready compositing output setup based on enabled Render Layer passes. It automatically configures output paths, filenames and versions.

It is designed for **lookdev, lighting, and rendering workflows** where passes change frequently and manual compositor maintenance becomes slow, fragile, and error-prone.

---

## ✨ Key Features

### 🔹 One-click Compositing Setup
- Builds a full compositor node tree from scratch
- Automatically creates:
  - Render Layers node
  - File Output nodes for **beauty** and **utility** passes
  - Per-pass **DenoiseWithMix** groups for beauty passes
- Configures:
  - Output paths
  - Multilayer EXR settings
  - Versioned render folders

---

### 🔹 Smart, Non-Destructive Updates
The **Update Compositing** button keeps the compositor graph in sync with the current Render Layer configuration.

It will:
- Add newly enabled Render Layer passes
- Remove outputs for passes that were disabled
- Remove unused denoise nodes
- Preserve all valid, existing connections

You can safely press **Update Compositing** multiple times without breaking the setup.

---

### 🔹 Automatic Denoising with control
- Beauty passes are routed through a reusable **DenoiseWithMix** node group
- Uses Cycles denoising data (Normal + Albedo)
- Global **Denoise level** allows blending between raw and denoised results

Utility passes automatically bypass denoising.

---

### 🔹 Clear Output Separation
Outputs are split into two EXR multilayers:

#### Beauty
- Lighting and shading passes
- Denoised and comp-ready

#### Utility
- Data passes (Depth, Normal, Vector, Cryptomatte, Indices, etc.)
- Stored losslessly

Each output is automatically named and placed into versioned folders.

---

## 📂 Versioned Output Structure

The add-on extracts the render version from the `.blend` filename  
(e.g. `_v003`) and generates a consistent output structure:

renders/
    └── v003/
        ├── preview/
        ├── beauty/
        └── utils/

By default it goes one level up from the .blend file and into "renders" folder. This can be modified in settings.
This keeps renders organized across iterations and prevents accidental overwrites.

---

## 🖥 User Interface

The add-on is available in:

**Compositor → Sidebar → Setup Helper**

### Controls

- **Create Compositing Setup**
  - Creates a fresh compositor setup
  - Overwrites existing compositor nodes

- **Update Compositing**
  - Synchronizes the setup with current Render Layer passes
  - Adds missing passes
  - Removes obsolete outputs
  - Updates paths and version numbers

---


## ⚠ Notes

- Requires **Blender 5+**
- Designed for **Cycles**
- Best used with consistent file naming (e.g. `_v001`, `_v002`, …)

---

## 📜 License

This project is licensed under the **GNU General Public License v3 (GPL-3.0)**.




