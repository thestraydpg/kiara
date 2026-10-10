import bpy
import mathutils
import os

SRC = "/home/user/kiara/assets/work/kiara_eyes.blend"
OUT_BLEND = "/home/user/kiara/assets/work/kiara_jaw.blend"

bpy.ops.wm.open_mainfile(filepath=SRC)
body = [o for o in bpy.data.objects if o.name == "Kiara_Body"][0]
rig = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
mesh = body.data
mw = body.matrix_world

min_co = mathutils.Vector((1e9,)*3)
max_co = mathutils.Vector((-1e9,)*3)
for v in mesh.vertices:
    co = mw @ v.co
    for i in range(3):
        min_co[i] = min(min_co[i], co[i])
        max_co[i] = max(max_co[i], co[i])
H = max_co.z - min_co.z
ground = min_co.z

def z(frac):
    return ground + frac * H

# empirically calibrated from the mouth marker grid (see mouth_calibrate.png)
SEAM_Z = 0.887       # where upper lip meets lower lip
LIP_LOWER_BAND = 0.875   # lower lip proper
CHIN_BOTTOM_Z = 0.80     # where "jaw region" ends and neck begins
JAW_PIVOT_Z = 0.895      # approx TMJ/ear height - the actual rotation hinge
UPPER_LIP_TOP = 0.90     # upper lip / nose boundary

print(f"H={H:.4f} ground={ground:.4f} seam_z={z(SEAM_Z):.4f}")

# -- reposition jaw + lip bones to calibrated coordinates (same bug as
# the original eye bones: LM fractions were derived from a hair-inflated
# bounding box) --
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='EDIT')
eb = rig.data.edit_bones

jaw_b = eb["jaw"]
jaw_b.use_deform = True   # was non-deform placeholder; now does real work
jaw_b.head = (0, -0.06*H, z(JAW_PIVOT_Z))
jaw_b.tail = (0, -0.09*H, z(CHIN_BOTTOM_Z + 0.03))

lip_upper_b = eb["lip_upper"]
lip_upper_b.use_deform = True
lip_upper_b.head = (0, -0.11*H, z(UPPER_LIP_TOP))
lip_upper_b.tail = (0, -0.115*H, z(SEAM_Z))

lip_lower_b = eb["lip_lower"]
lip_lower_b.use_deform = True
lip_lower_b.head = (0, -0.11*H, z(SEAM_Z))
lip_lower_b.tail = (0, -0.11*H, z(LIP_LOWER_BAND - 0.01))

for side in ("L", "R"):
    corner_b = eb[f"lip_corner.{side}"]
    corner_b.use_deform = True

bpy.ops.object.mode_set(mode='OBJECT')
print("Repositioned jaw/lip bones, marked deform=True")

# -- weight: SHARP cutoff at the seam, not a smooth blend, so the mouth
# visibly pulls apart when the jaw opens instead of just stretching a
# continuous skin patch. Below the seam is jaw/chin territory; at/above
# is head/upper-lip territory. --
vg_lookup = {vg.name: vg for vg in body.vertex_groups}
for name in ["jaw", "lip_upper", "lip_lower", "lip_corner.L", "lip_corner.R"]:
    if name not in body.vertex_groups:
        body.vertex_groups.new(name=name)
        vg_lookup[name] = body.vertex_groups[name]

touched = {"jaw": 0, "lip_upper": 0, "lip_lower": 0, "lip_corner.L": 0, "lip_corner.R": 0}

for v in mesh.vertices:
    co = mw @ v.co
    z_frac = (co.z - ground) / H
    x_frac = co.x / H
    y_frac = co.y / H

    is_front_face = y_frac < -0.04
    is_mouth_x = abs(x_frac) < 0.05

    target_bone = None
    if z(CHIN_BOTTOM_Z) <= co.z < z(LIP_LOWER_BAND) and is_front_face:
        target_bone = "jaw"
    elif z(LIP_LOWER_BAND) <= co.z < z(SEAM_Z) and is_front_face and is_mouth_x:
        target_bone = "lip_lower"
    elif z(SEAM_Z) <= co.z < z(UPPER_LIP_TOP) and is_front_face and is_mouth_x:
        target_bone = "lip_upper"
    elif z(LIP_LOWER_BAND) <= co.z < z(UPPER_LIP_TOP) and is_front_face and 0.05 <= abs(x_frac) < 0.08:
        side = "L" if x_frac > 0 else "R"
        target_bone = f"lip_corner.{side}"

    if target_bone is None:
        continue

    # full dominant weight, sharp - no blending across the seam
    existing_total = sum(g.weight for g in v.groups)
    if existing_total > 1e-6:
        scale = 0.08 / existing_total   # leave a small 8% base-skin influence for smoothness at the mesh boundary
        for g in v.groups:
            g.weight *= scale
    vg_lookup[target_bone].add([v.index], 0.92, 'REPLACE')
    touched[target_bone] += 1

print(f"Vertices weighted: {touched}")

os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"Saved: {OUT_BLEND}")
