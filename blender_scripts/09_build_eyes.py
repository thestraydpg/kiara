import bpy
import bmesh
import mathutils
import math
import os
import numpy as np

SRC = "/home/user/kiara/assets/work/kiara_hair.blend"
OUT_BLEND = "/home/user/kiara/assets/work/kiara_eyes.blend"

bpy.ops.wm.open_mainfile(filepath=SRC)
body = [o for o in bpy.data.objects if o.name == "Kiara_Body"][0]
rig = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]

mw = body.matrix_world
min_co = mathutils.Vector((1e9,)*3)
max_co = mathutils.Vector((-1e9,)*3)
for v in body.data.vertices:
    co = mw @ v.co
    for i in range(3):
        min_co[i] = min(min_co[i], co[i])
        max_co[i] = max(max_co[i], co[i])
H = max_co.z - min_co.z
ground = min_co.z

EYE_RADIUS = 0.0105 * H   # ~20mm visible radius (full eyeball is ~24mm but eyelids hide most of it)

# Empirically calibrated eye socket position (the original skeleton's
# landmark fractions put eyes near the hairline - "crown" was measured
# from the hair-inflated bounding box, not the actual skull, throwing off
# every upper-face fraction). These were found by rendering a marker grid
# against the real baked face texture and matching by eye.
EYE_X_FRAC = 0.021      # slightly wider apart than first guess, so they don't touch
EYE_Z_FRAC = 0.925
EYE_Y_FRAC = -0.068     # pulled back further into the socket than first guess

# Actually move the eye/lid bones to the calibrated position - the
# original build_skeleton.py placed them using the flawed LM['eyes'] etc.
# fractions, which were derived from a bounding box inflated by hair.
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='EDIT')
eb = rig.data.edit_bones
for side, sign in (('L', 1), ('R', -1)):
    ex = sign * EYE_X_FRAC * H
    ez = ground + EYE_Z_FRAC * H
    ey = EYE_Y_FRAC * H
    eye_b = eb[f"eye.{side}"]
    eye_b.head = (ex, ey, ez)
    eye_b.tail = (ex, ey - 0.03*H, ez)
    for lid_name, lid_z_off in ((f"lid_upper.{side}", 0.012*H), (f"lid_lower.{side}", -0.012*H)):
        lb = eb[lid_name]
        lb.head = (ex, ey - 0.005*H, ez + lid_z_off)
        lb.tail = (ex, ey - 0.015*H, ez + lid_z_off*0.6)
bpy.ops.object.mode_set(mode='OBJECT')
print(f"Repositioned eye/lid bones to calibrated coordinates (x={EYE_X_FRAC}H z={EYE_Z_FRAC}H)")

# -- build a simple procedural iris/sclera texture (no external photo needed) --
TEX_SIZE = 256
iris_arr = np.zeros((TEX_SIZE, TEX_SIZE, 4), dtype=np.float32)
cx, cy = TEX_SIZE / 2, TEX_SIZE / 2
iris_color = np.array([0.25, 0.14, 0.07])   # warm brown, matches her look
pupil_r = TEX_SIZE * 0.14
iris_r = TEX_SIZE * 0.34
for y in range(TEX_SIZE):
    for x in range(TEX_SIZE):
        d = math.hypot(x - cx, y - cy)
        if d < pupil_r:
            col = np.array([0.01, 0.01, 0.01])
        elif d < iris_r:
            t = (d - pupil_r) / (iris_r - pupil_r)
            streak = 0.85 + 0.15 * math.sin(math.atan2(y - cy, x - cx) * 18.0)
            col = iris_color * (0.55 + 0.45 * t) * streak
            ring = 1.0 - 0.3 * max(0.0, 1.0 - abs(t - 0.85) * 10)
            col = col * ring
        else:
            # sclera: off-white, slightly shaded toward the edge
            shade = 1.0 - 0.25 * min(1.0, (d - iris_r) / (TEX_SIZE*0.5 - iris_r))
            col = np.array([0.92, 0.89, 0.86]) * shade
        iris_arr[y, x, 0:3] = col
        iris_arr[y, x, 3] = 1.0

iris_img = bpy.data.images.new("Kiara_Iris", TEX_SIZE, TEX_SIZE, alpha=False)
iris_img.pixels.foreach_set(iris_arr.ravel())
iris_img.filepath_raw = "/home/user/kiara/assets/work/kiara_iris.png"
iris_img.file_format = 'PNG'
iris_img.save()
print("Generated iris/sclera texture")

eye_mat = bpy.data.materials.new("Kiara_EyeMat")
eye_mat.use_nodes = True
nt = eye_mat.node_tree
bsdf = nt.nodes.get("Principled BSDF")
tex_node = nt.nodes.new("ShaderNodeTexImage")
tex_node.image = iris_img
nt.links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.15

# -- eyelid material: skin-tone-ish, matches surrounding face reasonably --
lid_mat = bpy.data.materials.new("Kiara_LidMat")
lid_mat.use_nodes = True
lid_bsdf = lid_mat.node_tree.nodes.get("Principled BSDF")
lid_bsdf.inputs["Base Color"].default_value = (0.70, 0.47, 0.34, 1.0)
lid_bsdf.inputs["Roughness"].default_value = 0.5


def get_bone_head_world(bone_name):
    b = rig.data.bones[bone_name]
    return rig.matrix_world @ b.head_local


def make_eyeball(side, sign):
    bone_pos = get_bone_head_world(f"eye.{side}")
    bpy.ops.mesh.primitive_uv_sphere_add(radius=EYE_RADIUS, location=bone_pos, segments=20, ring_count=14)
    obj = bpy.context.active_object
    obj.name = f"Eyeball.{side}"
    # orient so the iris (UV seam) faces forward (-Y, toward camera/front)
    obj.rotation_euler = (math.radians(90), 0, 0)
    obj.data.materials.append(eye_mat)

    # UV project so the iris lands on the front-facing pole
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.sphere_project()
    bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    rig.data.bones.active = rig.data.bones[f"eye.{side}"]
    bpy.ops.object.parent_set(type='BONE', keep_transform=True)
    return obj


def make_eyelid(side, sign, upper: bool):
    bone_name = f"lid_upper.{side}" if upper else f"lid_lower.{side}"
    bone_pos = get_bone_head_world(bone_name)
    eye_pos = get_bone_head_world(f"eye.{side}")

    # a thin curved cap: take a UV sphere slightly larger than the eyeball,
    # keep only the top (or bottom) third as the lid shell
    r = EYE_RADIUS * 1.12
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=eye_pos, segments=16, ring_count=12)
    obj = bpy.context.active_object
    obj.name = f"Eyelid_{'Upper' if upper else 'Lower'}.{side}"
    obj.data.materials.append(lid_mat)

    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    # local Z here corresponds to world Z before any rotation (sphere not
    # yet rotated) - keep only the cap on the correct side
    # cover more of the sphere than a naive half-split would - real open
    # eyes only expose a lens-shaped band around the equator, most of the
    # eyeball hides behind the lids even "open"
    to_delete = []
    for v in bm.verts:
        if upper and v.co.z < r * 0.30:
            to_delete.append(v)
        elif not upper and v.co.z > -r * 0.30:
            to_delete.append(v)
    bmesh.ops.delete(bm, geom=to_delete, context='VERTS')
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')

    # move the lid's origin to the bone position (its rotation pivot)
    obj.location = bone_pos
    delta = eye_pos - bone_pos
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    for v in bm.verts:
        v.co += delta  # shift geometry so it still sits over the eyeball
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    rig.data.bones.active = rig.data.bones[bone_name]
    bpy.ops.object.parent_set(type='BONE', keep_transform=True)
    return obj


eyeballs = []
eyelids = []
for side, sign in (('L', 1), ('R', -1)):
    eyeballs.append(make_eyeball(side, sign))
    eyelids.append(make_eyelid(side, sign, upper=True))
    eyelids.append(make_eyelid(side, sign, upper=False))

print(f"Created {len(eyeballs)} eyeballs, {len(eyelids)} eyelid pieces")

os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"Saved: {OUT_BLEND}")
