import bpy
import mathutils
import os

SRC = "/home/user/kiara/assets/work/kiara_rigged.blend"
OUT_BLEND = "/home/user/kiara/assets/work/kiara_skinned.blend"

bpy.ops.wm.open_mainfile(filepath=SRC)
body = [o for o in bpy.data.objects if o.type == 'MESH'][0]
rig = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]

TWIST_SUFFIX_MAP = {
    "forearm_twist.L": "forearm.L", "forearm_twist.R": "forearm.R",
    "thigh_twist.L": "thigh.L",     "thigh_twist.R": "thigh.R",
    "shin_twist.L": "shin.L",       "shin_twist.R": "shin.R",
}

all_deform = [b for b in rig.data.bones if b.use_deform]
twist_bones = {b.name: b for b in all_deform if b.name in TWIST_SUFFIX_MAP}
primary_bones = [b for b in all_deform if b.name not in TWIST_SUFFIX_MAP]

print(f"Primary deform bones: {len(primary_bones)}")
print(f"Twist bones (split from parent): {len(twist_bones)}")

# precompute bone segments in world space
def bone_segment(b):
    h = rig.matrix_world @ b.head_local
    t = rig.matrix_world @ b.tail_local
    return h, t

primary_segs = {b.name: bone_segment(b) for b in primary_bones}

def point_segment_dist_t(p, a, b):
    ab = b - a
    ab_len2 = ab.length_squared
    if ab_len2 < 1e-12:
        return (p - a).length, 0.0
    t = (p - a).dot(ab) / ab_len2
    t_clamped = max(0.0, min(1.0, t))
    closest = a + ab * t_clamped
    return (p - closest).length, t_clamped

# ensure vertex groups exist for ALL deform bones (primary + twist)
for b in all_deform:
    if b.name not in body.vertex_groups:
        body.vertex_groups.new(name=b.name)
vg_lookup = {vg.name: vg for vg in body.vertex_groups}

K = 4           # influences per vertex among primary bones
FALLOFF_POWER = 2.5

mw = body.matrix_world
vert_count = len(body.data.vertices)
print(f"Skinning {vert_count} vertices against {len(primary_bones)} primary bones...")

for vi, v in enumerate(body.data.vertices):
    wco = mw @ v.co
    dists = []
    for name, (a, b) in primary_segs.items():
        d, t = point_segment_dist_t(wco, a, b)
        dists.append((d, name, t))
    dists.sort(key=lambda x: x[0])
    nearest = dists[:K]

    # inverse-distance^power weighting, normalized
    eps = 1e-5
    raw = [1.0 / ((d + eps) ** FALLOFF_POWER) for d, _, _ in nearest]
    total = sum(raw)
    weights = {name: (r / total) for (d, name, t), r in zip(nearest, raw)}
    t_for = {name: t for d, name, t in nearest}

    # split distal portion of twist-parent weight into the twist bone
    final = dict(weights)
    for twist_name, parent_name in TWIST_SUFFIX_MAP.items():
        if parent_name in final:
            t_param = t_for.get(parent_name, 0.5)
            if t_param > 0.4:
                # fraction of parent's weight moves to twist bone, ramping
                # from 0 at t=0.4 to 0.6 at t=1.0 (distal end twists most)
                frac = min(0.6, (t_param - 0.4) / 0.6 * 0.6)
                move = final[parent_name] * frac
                final[parent_name] -= move
                final[twist_name] = final.get(twist_name, 0.0) + move

    for name, w in final.items():
        if w > 1e-4:
            vg_lookup[name].add([vi], w, 'REPLACE')

    if vi % 5000 == 0:
        print(f"  ...{vi}/{vert_count}")

print("Skinning pass complete.")

# add armature modifier
if not any(m.type == 'ARMATURE' for m in body.modifiers):
    mod = body.modifiers.new(name="Armature", type='ARMATURE')
    mod.object = rig
body.parent = rig

# verify
totals = {name: 0.0 for name in vg_lookup}
for v in body.data.vertices:
    for g in v.groups:
        totals[body.vertex_groups[g.group].name] = totals.get(body.vertex_groups[g.group].name, 0.0) + g.weight

weak = [n for n, t in totals.items() if t < 0.01]
print(f"\nBones with near-zero total weight: {len(weak)} / {len(totals)}")
for n in sorted(weak):
    print(f"  WEAK: {n}")

unweighted = sum(1 for v in body.data.vertices if len(v.groups) == 0)
print(f"Vertices with zero influence: {unweighted} / {vert_count}")

os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"Saved: {OUT_BLEND}")
