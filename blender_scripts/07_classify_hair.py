import bpy
import mathutils
import numpy as np

SRC = "/home/user/kiara/assets/work/kiara_physics.blend"
bpy.ops.wm.open_mainfile(filepath=SRC)
body = [o for o in bpy.data.objects if o.name == "Kiara_Body"][0]
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

img = bpy.data.images.get("Kiara_Albedo")
W, Hp = img.size
arr = np.empty(W*Hp*4, dtype=np.float32)
img.pixels.foreach_get(arr)
arr = arr.reshape(Hp, W, 4)

uv_layer = mesh.uv_layers.active.data

# per-vertex average UV (first loop found) and sampled color
vert_uv = {}
for poly in mesh.polygons:
    for li in poly.loop_indices:
        vi = mesh.loops[li].vertex_index
        if vi not in vert_uv:
            vert_uv[vi] = uv_layer[li].uv

head_z_lo = z(0.80)  # include some neck/shoulder-adjacent hair fringe

hair_verts = []
skin_verts = []
for v in mesh.vertices:
    co = mw @ v.co
    if co.z < head_z_lo:
        continue
    uv = vert_uv.get(v.index)
    if uv is None:
        continue
    px = min(W-1, max(0, int(uv.x * W)))
    py = min(Hp-1, max(0, int(uv.y * Hp)))
    r, g, b = arr[py, px, 0], arr[py, px, 1], arr[py, px, 2]
    luminance = 0.299*r + 0.587*g + 0.114*b
    if luminance < 0.12:   # dark = hair (black coily hair)
        hair_verts.append(v.index)
    else:
        skin_verts.append(v.index)

print(f"Head-region vertices: hair={len(hair_verts)} skin/face={len(skin_verts)}")

# save classification for the next script
import json
with open("/tmp/claude-0/-home-user-kiara/e6032987-7913-58d2-813f-0fdc268b7bce/scratchpad/hair_verts.json", "w") as f:
    json.dump({"hair": hair_verts, "H": H, "ground": ground}, f)
print("Saved hair vertex classification")
