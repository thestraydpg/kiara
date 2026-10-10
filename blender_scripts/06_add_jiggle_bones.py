import bpy
import mathutils
import os

SRC = "/home/user/kiara/assets/work/kiara_textured.blend"
OUT_BLEND = "/home/user/kiara/assets/work/kiara_physics.blend"

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

LM = {
    'hip':        0.490,
    'waist':      0.600,
    'ribcage_lo': 0.680,
    'chest':      0.760,
}

bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='EDIT')
eb = rig.data.edit_bones

def add_bone(name, head, tail, parent_name, deform=True):
    b = eb.new(name)
    b.head = head
    b.tail = tail
    b.use_deform = deform
    b.parent = eb[parent_name]
    return b

new_bone_names = []

# --- breast jiggle: 2-bone chain per side, root anchored at chest/sternum.
# Coordinates below are derived from the actual mesh (apex found via
# find_breast_apex.py), not anthropometric guesswork - a first pass using
# guessed proportions placed the pivot/mass too far from the real geometry,
# which left most vertex weight bound to the (static) torso bones instead
# of the jiggle bone, killing visible motion. Pivot sits at the chest wall;
# the tail extends THROUGH and past the apex so the heaviest weight lands
# well away from the pivot (real lever arm).
breast_apex_z = 0.729
for side, sign in (('L', 1), ('R', -1)):
    apex_x, apex_y = sign * 0.045 * H, -0.097 * H
    root = add_bone(f"breast_root.{side}", (sign*0.015*H, -0.02*H, z(breast_apex_z)+0.02*H),
                     (apex_x*0.5, apex_y*0.4, z(breast_apex_z)+0.01*H), "sternum", deform=True)
    tip = add_bone(f"breast_jiggle.{side}", (apex_x*0.5, apex_y*0.4, z(breast_apex_z)+0.01*H),
                    (apex_x*1.15, apex_y*1.3, z(breast_apex_z)-0.02*H), f"breast_root.{side}", deform=True)
    new_bone_names += [f"breast_root.{side}", f"breast_jiggle.{side}"]

# --- belly jiggle: single bone over the abdomen, anchored to lowest lumbar ---
belly_apex_z = 0.600
belly = add_bone("belly_jiggle", (0, -0.015*H, z(belly_apex_z)+0.03*H),
                  (0, -0.082*H*1.3, z(belly_apex_z)-0.02*H), "spine_L5", deform=True)
new_bone_names.append("belly_jiggle")

# --- glute jiggle: one bone per side, anchored to pelvis ---
glute_apex_z = 0.523
for side, sign in (('L', 1), ('R', -1)):
    apex_x = sign * 0.048 * H
    glute = add_bone(f"glute_jiggle.{side}", (apex_x*0.4, 0.015*H, z(glute_apex_z)+0.03*H),
                      (apex_x*1.15, 0.061*H*1.3, z(glute_apex_z)-0.02*H), "pelvis", deform=True)
    new_bone_names.append(f"glute_jiggle.{side}")

bpy.ops.object.mode_set(mode='OBJECT')
print(f"Added {len(new_bone_names)} jiggle bones: {new_bone_names}")

# --- reskin: redistribute weight from the parent bone to the new jiggle bone
# for vertices near the jiggle bone's segment (same approach as twist bones
# in the original skinning pass - a parametric split along the segment).
for vg_name in new_bone_names:
    if vg_name not in body.vertex_groups:
        body.vertex_groups.new(name=vg_name)

PARENT_OF = {
    "breast_root.L": "sternum", "breast_root.R": "sternum",
    "breast_jiggle.L": "breast_root.L", "breast_jiggle.R": "breast_root.R",
    "belly_jiggle": "spine_L5",
    "glute_jiggle.L": "pelvis", "glute_jiggle.R": "pelvis",
}
# sternum/spine_L5/pelvis aren't deform-weighted directly on skin in our
# current rig (sternum is non-deform; spine_L5/pelvis ARE deform bones).
# For breast/glute we instead pull from the nearest real deform bone with
# weight there: for breast use nothing-donor (additive proximity weight),
# for belly/glute pull from spine_L5/pelvis respectively.
DONOR_OF = {
    "breast_root.L": None, "breast_root.R": None,
    "breast_jiggle.L": None, "breast_jiggle.R": None,
    "belly_jiggle": "spine_L5",
    "glute_jiggle.L": "pelvis", "glute_jiggle.R": "pelvis",
}

bone_world_seg = {}
for b in rig.data.bones:
    if b.name in new_bone_names:
        bone_world_seg[b.name] = (rig.matrix_world @ b.head_local, rig.matrix_world @ b.tail_local)

def point_seg_dist_t(p, a, b):
    ab = b - a
    ab_len2 = ab.length_squared
    if ab_len2 < 1e-12:
        return (p - a).length, 0.0
    t = max(0.0, min(1.0, (p - a).dot(ab) / ab_len2))
    return (p - (a + ab * t)).length, t

RADIUS = 0.09 * H   # influence radius for jiggle weight
MAX_JIGGLE_SHARE = 0.85  # jiggle bone dominates close to its segment
vg_lookup = {vg.name: vg for vg in body.vertex_groups}
touched = {n: 0 for n in new_bone_names}

for vi, v in enumerate(mesh.vertices):
    wco = mw @ v.co
    for bname in new_bone_names:
        a, b = bone_world_seg[bname]
        d, t = point_seg_dist_t(wco, a, b)
        if d < RADIUS:
            # bias toward the tail (t near 1, away from the pivot at the
            # head) so the heavily-weighted mass has real lever arm
            lever_bias = 0.35 + 0.65 * t
            jiggle_w = max(0.0, 1.0 - d / RADIUS) ** 2 * MAX_JIGGLE_SHARE * lever_bias
            if jiggle_w > 0.02:
                # scale down ALL of this vertex's existing weights so the
                # total (existing*scale + jiggle_w) == 1.0 - this makes the
                # jiggle bone a genuinely dominant influence near its
                # segment instead of a diluted additive sliver.
                existing_total = sum(g.weight for g in v.groups)
                if existing_total > 1e-6:
                    scale = (1.0 - jiggle_w) / existing_total
                    for g in v.groups:
                        g.weight *= scale
                vg_lookup[bname].add([vi], jiggle_w, 'REPLACE')
                touched[bname] += 1

print(f"Vertices touched per jiggle bone: {touched}")

os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"Saved: {OUT_BLEND}")
