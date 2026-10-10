import bpy
import json
import os

SRC = "/home/user/kiara/assets/work/kiara_jaw.blend"
OUT_DIR = "/home/user/kiara/mujoco/meshes"

## Cuts Kiara_Body into 15 rigid per-body-part pieces and exports each as
## an OBJ already positioned in that MuJoCo body's own local rest frame,
## so build_humanoid_mjcf.py's <mesh file="meshes/kiara_<body>.obj"/>
## references can be dropped straight into the training skeleton as a
## visual-only overlay (contype/conaffinity=0, mass="0") on top of the
## existing collision capsules - what MuJoCo's viewer shows stops being
## a stick figure without touching the physics a policy was trained
## against at all.
##
## Rigid, not smoothly skinned: each vertex goes entirely to whichever
## one of the 15 MuJoCo bodies its summed Blender bone weights favor
## most (reusing the vertex groups 03_skin_mesh.py already painted), and
## only faces whose vertices all agree end up in that piece - vertices
## that would've blended across two bones at a joint get dropped rather
## than stitched, leaving a small gap at elbows/knees/etc. Full smooth
## skinning is possible via MuJoCo's own <skin> element, but that needs
## its own binary .skn format exactly right with no way to preview the
## result from here - this rigid-piece approach uses plain, well-
## documented OBJ mesh geoms instead, at the cost of those gaps.
##
## MUJOCO_RESTS below are build_humanoid_mjcf.py's body positions at
## qpos0 (every joint at its default angle, so every body is unrotated -
## translation only, confirmed before writing this) - re-derive these
## with mujoco.mj_forward() if H, the LM landmark fractions, or any bone
## LENGTH constant in that file ever changes; they will not self-update.
MUJOCO_RESTS = {
    "pelvis": (0.0, 0.0, 0.9232), "spine": (0.0, 0.0, 0.9432), "head": (0.0, 0.0, 1.2861),
    "upperarm_L": (0.2261, 0.0, 0.9432), "forearm_L": (0.5765, 0.0, 0.9432), "hand_L": (0.8516, 0.0, 0.9432),
    "upperarm_R": (-0.2261, 0.0, 0.9432), "forearm_R": (-0.5765, 0.0, 0.9432), "hand_R": (-0.8516, 0.0, 0.9432),
    "thigh_L": (0.179, 0.0, 0.9232), "shank_L": (0.179, 0.0, 0.537), "foot_L": (0.179, 0.0, 0.0848),
    "thigh_R": (-0.179, 0.0, 0.9232), "shank_R": (-0.179, 0.0, 0.537), "foot_R": (-0.179, 0.0, 0.0848),
}

# Cross-validated against two independent landmark pairs (pelvis and
# hand.L, agreeing to ~4 decimal places - see session notes/git log).
# Both pipelines share the exact same LM fractions and H=1.884
# (ground-up, Z-up, no rotation/scale difference at rest), but
# kiara_jaw.blend's object origin has been re-centered at some point
# since the rig was first authored at true ground-zero, so a pure
# Z-offset is needed to bring it back into MuJoCo's convention. X/Y
# already line up exactly with no offset.
Z_OFFSET = 0.950144

BONE_TO_BODY = {}
def assign(body, names):
    for n in names:
        BONE_TO_BODY[n] = body

assign("pelvis", ["pelvis", "glute_jiggle.L", "glute_jiggle.R"])
assign("spine", [f"spine_L{i}" for i in range(1, 6)] + [f"spine_T{i}" for i in range(1, 13)] +
       ["belly_jiggle", "sternum", "breast_root.L", "breast_jiggle.L", "breast_root.R", "breast_jiggle.R",
        "clavicle.L", "clavicle.R", "scapula.L", "scapula.R"] +
       [f"rib_{i:02d}.{s}" for i in range(1, 13) for s in "LR"])
assign("head", [f"neck_C{i}" for i in range(1, 8)] +
       ["head", "jaw", "lip_corner.L", "lip_corner.R", "lip_lower", "lip_upper", "nose",
        "eye.L", "eye.R", "lid_upper.L", "lid_upper.R", "lid_lower.L", "lid_lower.R",
        "brow_inner.L", "brow_inner.R", "brow_outer.L", "brow_outer.R", "cheek.L", "cheek.R"] +
       [f"hair_clump_{i:02d}" for i in range(10)])

FINGER_PREFIXES = ["thumb_meta", "thumb_01", "thumb_02", "index_meta", "index_01", "index_02", "index_03",
                   "middle_meta", "middle_01", "middle_02", "middle_03", "ring_meta", "ring_01", "ring_02",
                   "ring_03", "pinky_meta", "pinky_01", "pinky_02", "pinky_03"]
TOE_PREFIXES = ["toes", "toe_big_01", "toe_big_02", "toe_idx2_01", "toe_idx2_02", "toe_idx2_03",
                "toe_mid_01", "toe_mid_02", "toe_mid_03", "toe_idx4_01", "toe_idx4_02", "toe_idx4_03",
                "toe_small_01", "toe_small_02", "toe_small_03"]

for side in ("L", "R"):
    assign(f"upperarm_{side}", [f"upperarm.{side}"])
    assign(f"forearm_{side}", [f"forearm.{side}", f"forearm_twist.{side}"])
    assign(f"hand_{side}", [f"hand.{side}"] + [f"{p}.{side}" for p in FINGER_PREFIXES])
    assign(f"thigh_{side}", [f"thigh.{side}", f"thigh_twist.{side}"])
    assign(f"shank_{side}", [f"shin.{side}", f"shin_twist.{side}"])
    assign(f"foot_{side}", [f"foot.{side}"] + [f"{p}.{side}" for p in TOE_PREFIXES])

MUJOCO_BODIES = list(MUJOCO_RESTS.keys())

bpy.ops.wm.open_mainfile(filepath=SRC)
body = bpy.data.objects["Kiara_Body"]
mesh = body.data
mw = body.matrix_world

vg_index_to_name = {vg.index: vg.name for vg in body.vertex_groups}

vert_bucket = [None] * len(mesh.vertices)
unmapped_weight_total = 0.0
for v in mesh.vertices:
    totals = {}
    for g in v.groups:
        bone_name = vg_index_to_name.get(g.group)
        bucket = BONE_TO_BODY.get(bone_name)
        if bucket is None:
            unmapped_weight_total += g.weight
            continue
        totals[bucket] = totals.get(bucket, 0.0) + g.weight
    if totals:
        vert_bucket[v.index] = max(totals.items(), key=lambda kv: kv[1])[0]

print(f"Unmapped weight total (bones with no bucket, e.g. 'root'): {unmapped_weight_total:.4f}")

mesh.calc_normals_split()
uv_layer = mesh.uv_layers.active.data if mesh.uv_layers.active else None

os.makedirs(OUT_DIR, exist_ok=True)

for bucket in MUJOCO_BODIES:
    bx, by, bz = MUJOCO_RESTS[bucket]

    keep_faces = [poly for poly in mesh.polygons if all(vert_bucket[vi] == bucket for vi in poly.vertices)]
    if not keep_faces:
        print(f"{bucket}: NO FACES (empty bucket) - skipping")
        continue

    used_verts = sorted({vi for poly in keep_faces for vi in poly.vertices})
    remap = {old: new + 1 for new, old in enumerate(used_verts)}  # OBJ is 1-indexed

    out_path = os.path.join(OUT_DIR, f"kiara_{bucket}.obj")
    with open(out_path, "w") as f:
        f.write(f"# Kiara visual skin piece for MuJoCo body '{bucket}' - generated by\n")
        f.write(f"# blender_scripts/12_export_mujoco_skin.py, do not hand-edit.\n")
        for vi in used_verts:
            wco = mw @ mesh.vertices[vi].co
            lx, ly, lz = wco.x - bx, wco.y - by, (wco.z + Z_OFFSET) - bz
            f.write(f"v {lx:.6f} {ly:.6f} {lz:.6f}\n")
        if uv_layer:
            for vi in used_verts:
                for poly in keep_faces:
                    if vi in poly.vertices:
                        li = list(poly.vertices).index(vi)
                        uv = uv_layer[poly.loop_indices[li]].uv
                        f.write(f"vt {uv.x:.6f} {uv.y:.6f}\n")
                        break
        for vi in used_verts:
            n = mesh.vertices[vi].normal
            f.write(f"vn {n.x:.6f} {n.y:.6f} {n.z:.6f}\n")
        f.write(f"o kiara_{bucket}\n")
        for poly in keep_faces:
            idxs = [remap[vi] for vi in poly.vertices]
            if uv_layer:
                f.write("f " + " ".join(f"{i}/{i}/{i}" for i in idxs) + "\n")
            else:
                f.write("f " + " ".join(f"{i}//{i}" for i in idxs) + "\n")

    print(f"{bucket}: {len(used_verts)} verts, {len(keep_faces)} faces -> {out_path}")

print("DONE - now (re)run mujoco/build_humanoid_mjcf.py to pick these up")
