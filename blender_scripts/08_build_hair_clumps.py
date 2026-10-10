import bpy
import json
import math
import mathutils
import os

SRC = "/home/user/kiara/assets/work/kiara_physics.blend"
OUT_BLEND = "/home/user/kiara/assets/work/kiara_hair.blend"

bpy.ops.wm.open_mainfile(filepath=SRC)
body = [o for o in bpy.data.objects if o.name == "Kiara_Body"][0]
rig = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
mesh = body.data
mw = body.matrix_world

with open("/tmp/claude-0/-home-user-kiara/e6032987-7913-58d2-813f-0fdc268b7bce/scratchpad/hair_verts.json") as f:
    data = json.load(f)
hair_set = set(data["hair"])
H = data["H"]
ground = data["ground"]

def z(frac):
    return ground + frac * H

# head center (X/Y) at scalp height, from the skull/face bounding region
scalp_z = z(0.90)
center_x, center_y = 0.0, -0.02 * H  # slightly forward of spine axis, matches head bone placement

N_SECTORS = 10
sector_hair = {i: [] for i in range(N_SECTORS)}
for vi in hair_set:
    co = mw @ mesh.vertices[vi].co
    ang = math.atan2(co.x - center_x, -(co.y - center_y))  # 0 = front, CCW
    sector = int(((ang + math.pi) / (2*math.pi)) * N_SECTORS) % N_SECTORS
    sector_hair[sector].append(vi)

print("Hair verts per sector:", {k: len(v) for k, v in sector_hair.items()})

bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='EDIT')
eb = rig.data.edit_bones

new_bone_names = []
clump_bone_data = {}  # name -> (pivot_world, apex_world)

for sector, verts in sector_hair.items():
    if len(verts) < 10:
        continue
    coords = [mw @ mesh.vertices[vi].co for vi in verts]
    # pivot = centroid of the vertices CLOSEST to the scalp center (innermost
    # ring - where this hair section actually attaches to the head)
    radii = [( (c.x-center_x)**2 + (c.y-center_y)**2 )**0.5 for c in coords]
    sorted_pairs = sorted(zip(radii, coords), key=lambda p: p[0])
    inner_n = max(3, len(sorted_pairs)//6)
    pivot = sum((c for _, c in sorted_pairs[:inner_n]), mathutils.Vector((0,0,0))) / inner_n
    # apex = centroid of the OUTERMOST vertices (where the hair clump ends)
    outer_n = max(3, len(sorted_pairs)//6)
    apex = sum((c for _, c in sorted_pairs[-outer_n:]), mathutils.Vector((0,0,0))) / outer_n
    # extend the bone a bit past the measured apex so peak weight sits
    # further from the pivot (same lever-arm lesson from the jiggle bones)
    direction = (apex - pivot)
    if direction.length < 1e-5:
        continue
    tail = pivot + direction * 1.4

    name = f"hair_clump_{sector:02d}"
    b = eb.new(name)
    b.head = pivot
    b.tail = tail
    b.use_deform = True
    b.parent = eb["head"]
    new_bone_names.append(name)
    clump_bone_data[name] = (pivot.copy(), tail.copy())

bpy.ops.object.mode_set(mode='OBJECT')
print(f"Added {len(new_bone_names)} hair clump bones")

# --- skin: same dominant-weight, tail-biased technique validated on the
# jiggle bones. Only touches vertices already classified as hair, and only
# reassigns weight away from 'head' (hair verts are presently fully/mostly
# bound to the head bone with no independent motion).
for vg_name in new_bone_names:
    if vg_name not in body.vertex_groups:
        body.vertex_groups.new(name=vg_name)
vg_lookup = {vg.name: vg for vg in body.vertex_groups}

def point_seg_dist_t(p, a, b):
    ab = b - a
    ab_len2 = ab.length_squared
    if ab_len2 < 1e-12:
        return (p - a).length, 0.0
    t = max(0.0, min(1.0, (p - a).dot(ab) / ab_len2))
    return (p - (a + ab * t)).length, t

MAX_HAIR_SHARE = 0.9
touched = {n: 0 for n in new_bone_names}

for sector, verts in sector_hair.items():
    name = f"hair_clump_{sector:02d}"
    if name not in clump_bone_data:
        continue
    pivot, tail = clump_bone_data[name]
    seg_len = (tail - pivot).length
    for vi in verts:
        co = mw @ mesh.vertices[vi].co
        d, t = point_seg_dist_t(co, pivot, tail)
        radius = seg_len * 0.9
        if d < radius:
            lever_bias = 0.3 + 0.7 * t
            w = max(0.0, 1.0 - d/radius) ** 1.5 * MAX_HAIR_SHARE * lever_bias
            if w > 0.03:
                v = mesh.vertices[vi]
                existing_total = sum(g.weight for g in v.groups)
                if existing_total > 1e-6:
                    scale = (1.0 - w) / existing_total
                    for g in v.groups:
                        g.weight *= scale
                vg_lookup[name].add([vi], w, 'REPLACE')
                touched[name] += 1

print(f"Vertices touched per hair clump: {touched}")

os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"Saved: {OUT_BLEND}")
