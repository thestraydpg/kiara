# Blender pipeline scripts

Run in order with `blender -b --python <script>.py` against the previous
stage's output (each script's `SRC`/`OUT_BLEND` constants show the
input/output chain). These reconstruct everything in `assets/work/`,
which is gitignored (large binary Blender files, regenerated from these
scripts rather than versioned directly).

| Script | Input | Output | What it does |
|---|---|---|---|
| `01_retopo.py` | release asset `Meshy_AI_Black_Bikini_Studio_P_..._texture.blend` | `kiara_retopo.blend` | Voxel remesh + decimate the ~2M-poly scan down to a 24k-poly game-ready mesh |
| `02_build_skeleton.py` | `kiara_retopo.blend` | `kiara_rigged.blend` | Generates the 160-bone biomechanical skeleton (full spine vertebrae, ribcage, hands, feet, face) |
| `03_skin_mesh.py` | `kiara_rigged.blend` | `kiara_skinned.blend` | Custom distance-based weight painting (Blender's built-in heat solver fails on this bone count/overlap) |
| `04_unwrap_clean.py` | `kiara_skinned.blend` | `kiara_uv.blend` | Dedicated high-density face UV island, separate from the fragmented auto-UV body |
| `05_bake_textures.py` | `kiara_uv.blend` + original high-poly source | `kiara_textured.blend` + `kiara_albedo.png`/`kiara_normal.png` | Bakes the real photo-sourced color data onto the clean UV layout |
| `06_add_jiggle_bones.py` | `kiara_textured.blend` | `kiara_physics.blend` | Breast/belly/glute secondary-motion bones, weighted from real mesh apex coordinates |
| `07_classify_hair.py` | `kiara_physics.blend` | `hair_verts.json` | Classifies head-region vertices as hair vs. skin via baked texture color |
| `08_build_hair_clumps.py` | `kiara_physics.blend` + `hair_verts.json` | `kiara_hair.blend` | 10 angular hair-clump bones for coily-hair jiggle physics |
| `09_build_eyes.py` | `kiara_hair.blend` | `kiara_eyes.blend` | Real eyeball + eyelid geometry (previously just flat texture), rigged for gaze/blink |
| `10_export_gltf.py` | `kiara_jaw.blend` | `godot/assets/kiara.glb` | Exports to glTF for Godot |
| `11_separate_jaw_lips.py` | `kiara_eyes.blend` | `kiara_jaw.blend` | Separates jaw and lips into real mesh (previously flat texture) |
| `12_export_mujoco_skin.py` | `kiara_jaw.blend` | `mujoco/meshes/kiara_<body>.obj` (15 files) | Cuts Kiara_Body into 15 rigid pieces (by dominant skin weight) matching MuJoCo's 15-body training skeleton, so `mujoco/build_humanoid_mjcf.py` can show her real shape instead of plain capsules - visual only, zero mass/collision impact on the trained physics |

## Known issues to fix in a future pass

- **Eyelid blink geometry**: the blink mechanism is correctly wired
  (bones parented right, rotation direction correct) but the cut-sphere
  eyelid cap shape distorts at full-closure rotation angles - needs an
  actual pivot/shape redesign, better done interactively in Blender's
  GUI than through more headless iteration.
- **Eye shape**: currently a plain spherical-zone cut (lens/stadium
  shape, not a pointed almond). Reference photos show clear almond
  corners; three procedural attempts at that (elliptical taper,
  flat-core+linear-ramp taper, horizontal stretch) all looked worse
  than the plain cut - see the comment in 09_build_eyes.py. Getting a
  true almond needs lid geometry sculpted against the eyeball's
  curvature, not a parametric cut.
- **MuJoCo visual skin has gaps at joints**: 12_export_mujoco_skin.py
  rigidly cuts the mesh per body part (each vertex goes entirely to one
  of the 15 training-skeleton bodies) rather than smoothly blending
  across the joint the way the real 177-bone Godot rig does - a vertex
  that would've blended between, say, thigh and shank gets dropped
  rather than stitched, leaving a thin gap at knees/elbows/shoulders/
  etc. Real smooth deformation needs MuJoCo's own `<skin>` element
  (per-vertex multi-bone blend weights, same idea as Godot's skinning)
  instead of plain rigid OBJ mesh geoms - not done here because that
  format's exact binary layout couldn't be verified from a sandbox with
  no display to render the result and check it landed correctly.

## Fixed (previously listed here)

- ~~Thigh texture artifact~~: the "bake-miss" black region on the
  left thigh/hip wasn't actually a bake failure - it was pubic-area
  hair texture from the source scan bleeding onto that UV island.
  Inpainted out directly in kiara_albedo.png (not re-baked - see git
  history, no pipeline script currently reproduces this step, it was
  a one-off image fix via opencv).
- ~~Jaw/lips flat texture~~: real mesh separation landed in
  11_separate_jaw_lips.py.
