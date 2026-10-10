import bpy
import bmesh
import mathutils
import os

SRC = "/home/user/kiara/assets/work/kiara_skinned.blend"
OUT_BLEND = "/home/user/kiara/assets/work/kiara_uv.blend"

bpy.ops.wm.open_mainfile(filepath=SRC)
body = [o for o in bpy.data.objects if o.type == 'MESH'][0]
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
# Neck-base cutoff, comfortably above the T-pose arm/shoulder line (~0.818H),
# plus an X-distance cap so no stray shoulder/arm geometry sneaks in.
head_z_cut = ground + 0.855 * H
head_x_cap = 0.17 * H

# classify in OBJECT mode via mesh.polygons (avoids bmesh ref invalidation)
head_idx = set()
body_idx = set()
for poly in mesh.polygons:
    zs = [(mw @ mesh.vertices[i].co).z for i in poly.vertices]
    xs = [(mw @ mesh.vertices[i].co).x for i in poly.vertices]
    if min(zs) >= head_z_cut and max(abs(x) for x in xs) <= head_x_cap:
        head_idx.add(poly.index)
    else:
        body_idx.add(poly.index)

print(f"Head faces: {len(head_idx)}  Body faces: {len(body_idx)}")

if not mesh.uv_layers:
    mesh.uv_layers.new(name="UVMap")

bpy.context.view_layer.objects.active = body
bpy.ops.object.mode_set(mode='EDIT')

bm = bmesh.from_edit_mesh(mesh)
bm.faces.ensure_lookup_table()
bpy.ops.mesh.select_all(action='DESELECT')
for i in head_idx:
    bm.faces[i].select = True
bmesh.update_edit_mesh(mesh)

bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.01, area_weight=0.0)
print("Head UV unwrap done")

bm = bmesh.from_edit_mesh(mesh)
bm.faces.ensure_lookup_table()
bpy.ops.mesh.select_all(action='DESELECT')
for i in body_idx:
    bm.faces[i].select = True
bmesh.update_edit_mesh(mesh)

bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.015, area_weight=0.0)
print("Body UV unwrap done")

bpy.ops.object.mode_set(mode='OBJECT')

uv_layer = mesh.uv_layers.active.data
head_uvs = []
body_uvs = []
for poly in mesh.polygons:
    target = head_uvs if poly.index in head_idx else body_uvs
    for li in poly.loop_indices:
        target.append((li, uv_layer[li].uv))

def bbox(uvs):
    xs = [u.x for _, u in uvs]; ys = [u.y for _, u in uvs]
    return min(xs), min(ys), max(xs), max(ys)

hb = bbox(head_uvs)
bb = bbox(body_uvs)
print(f"Head UV bbox: {hb}")
print(f"Body UV bbox: {bb}")

def remap(uvs, src_bbox, dst_x0, dst_y0, dst_x1, dst_y1):
    x0, y0, x1, y1 = src_bbox
    sx = (x1 - x0) or 1.0
    sy = (y1 - y0) or 1.0
    for li, uv in uvs:
        nx = (uv.x - x0) / sx
        ny = (uv.y - y0) / sy
        uv_layer[li].uv = (dst_x0 + nx * (dst_x1 - dst_x0), dst_y0 + ny * (dst_y1 - dst_y0))

# head gets top 45% of texture (full width -> high texel density for a small
# surface area), body gets bottom 53%.
remap(head_uvs, hb, 0.02, 0.57, 0.98, 0.98)
remap(body_uvs, bb, 0.02, 0.02, 0.98, 0.53)

print("Repacked head (top 45%) and body (bottom 53%) into separate UV regions")

os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"Saved: {OUT_BLEND}")
