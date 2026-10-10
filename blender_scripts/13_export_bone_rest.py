import bpy
import json

SRC = "/home/user/kiara/assets/work/kiara_jaw.blend"
OUT_JSON = "/home/user/kiara/mujoco/blender_bone_rest.json"

## Dumps each retarget-relevant bone's rest-pose rotation basis (in
## armature space, which is world space here since the armature object's
## own transform is identity - confirmed before writing this), for
## mujoco/retarget_server.py to use when converting a MuJoCo body's
## world-space rotation into the equivalent LOCAL pose rotation for that
## Blender bone (Godot's set_bone_pose_rotation() expects a delta from
## rest, expressed in the bone's own rest-local frame, not world space -
## see retarget_server.py's module docstring for the actual conjugation
## math this feeds into).
BONES = [
    "pelvis",
    "spine_L1", "spine_L2", "spine_L3", "spine_L4", "spine_L5",
    "spine_T1", "spine_T2", "spine_T3", "spine_T4", "spine_T5", "spine_T6",
    "spine_T7", "spine_T8", "spine_T9", "spine_T10", "spine_T11", "spine_T12",
    "neck_C1", "neck_C2", "neck_C3", "neck_C4", "neck_C5", "neck_C6", "neck_C7", "head",
    "upperarm.L", "forearm.L", "hand.L", "upperarm.R", "forearm.R", "hand.R",
    "thigh.L", "shin.L", "foot.L", "thigh.R", "shin.R", "foot.R",
]

bpy.ops.wm.open_mainfile(filepath=SRC)
rig = bpy.data.objects["Kiara_Armature"]

out = {}
for name in BONES:
    b = rig.data.bones[name]
    m = b.matrix_local
    out[name] = {
        "basis": [list(m.col[0][:3]), list(m.col[1][:3]), list(m.col[2][:3])],
        "parent": b.parent.name if b.parent else None,
    }

json.dump(out, open(OUT_JSON, "w"), indent=1)
print(f"Wrote {OUT_JSON} ({len(out)} bones)")
