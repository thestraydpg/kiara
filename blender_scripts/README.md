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
| `10_export_gltf.py` | `kiara_eyes.blend` (update `SRC` - currently still points at `kiara_hair.blend` from before the eye work landed) | `godot/assets/kiara.glb` | Exports to glTF for Godot |

## Known issues to fix in a future pass

- **Thigh texture artifact**: a small jagged black bake-miss region on
  the left thigh in the albedo texture (seam/UV defect, not a ray-distance
  issue - see commit history for what was already ruled out).
- **Eyelid blink geometry**: the blink mechanism is correctly wired
  (bones parented right, rotation direction correct) but the cut-sphere
  eyelid cap shape distorts at full-closure rotation angles - needs an
  actual pivot/shape redesign, better done interactively in Blender's
  GUI than through more headless iteration.
- **Jaw/lips**: still flat texture, no real separation yet (in progress).
