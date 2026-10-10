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

# A real adult eyeball is ~24mm diameter (12mm radius), not ~40mm - the
# previous 0.0105*H (~20mm radius) built an eyeball roughly double true
# size. Combined with not being recessed far enough into the socket,
# the sphere's front surface measured ~9-10mm in front of the nearest
# eyelid/socket skin (probed directly: eyeball front at y=-0.1479 vs.
# nearest socket skin at y=-0.1385) - that's the literal geometry of
# the "bulging Pixar eyes" look. Shrinking the sphere to real scale.
EYE_RADIUS = 0.0064 * H   # ~12mm radius, real adult eyeball scale

# Empirically calibrated eye socket position (the original skeleton's
# landmark fractions put eyes near the hairline - "crown" was measured
# from the hair-inflated bounding box, not the actual skull, throwing off
# every upper-face fraction). These were found by rendering a marker grid
# against the real baked face texture and matching by eye. X/Z (spacing,
# height) were fine - only depth (Y) and the oversized radius above were
# causing the bulge.
EYE_X_FRAC = 0.021      # slightly wider apart than first guess, so they don't touch
EYE_Z_FRAC = 0.925
EYE_Y_FRAC = -0.060     # recessed further into the socket now that the eyeball is real-world scale

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
    for lid_name, lid_z_off in ((f"lid_upper.{side}", 0.0073*H), (f"lid_lower.{side}", -0.0073*H)):
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
bsdf.inputs["Roughness"].default_value = 0.35

# -- eyelid material --
# A flat, textureless material next to the photo-baked, pore-detailed
# face skin is what actually reads as "a fake eye glued onto a body it
# wasn't originally on" - no amount of color accuracy alone fixes that,
# the lid needs comparable micro-detail. Two things, both grounded in
# the real asset rather than guessed:
#  1. Base color sampled directly from the baked albedo texture at the
#     confirmed socket-adjacent skin pixels (median of the non-hair,
#     non-eye/brow-outlier samples - see scratchpad probe scripts from
#     this session), not an invented value. (0.70,0.47,0.34) before was
#     noticeably more orange/saturated than the real (0.67,0.53,0.42).
#  2. Procedural noise driving both a bump (pore-scale micro-displacement)
#     and a subtle base-color variation, so the surface isn't perfectly
#     flat-shaded next to a surface that has real detail everywhere.
#     This can't literally reuse the face's own pore texture - the face
#     UV island is low-resolution and smart-UV-packed so tightly with
#     hair-clump islands that the only "clean" patch near the socket is
#     a few dozen pixels, including the eye/brow themselves at this
#     scale - tiling that would look far worse than procedural noise.
lid_mat = bpy.data.materials.new("Kiara_LidMat")
lid_mat.use_nodes = True
nt_lid = lid_mat.node_tree
lid_bsdf = nt_lid.nodes.get("Principled BSDF")
lid_bsdf.inputs["Base Color"].default_value = (0.6706, 0.5255, 0.4235, 1.0)
lid_bsdf.inputs["Roughness"].default_value = 0.55

lid_noise = nt_lid.nodes.new("ShaderNodeTexNoise")
lid_noise.inputs["Scale"].default_value = 420.0
lid_noise.inputs["Detail"].default_value = 4.0
lid_noise.inputs["Roughness"].default_value = 0.6

lid_colorramp = nt_lid.nodes.new("ShaderNodeValToRGB")
lid_colorramp.color_ramp.elements[0].position = 0.45
lid_colorramp.color_ramp.elements[0].color = (0.92, 0.92, 0.92, 1.0)
lid_colorramp.color_ramp.elements[1].position = 0.55
lid_colorramp.color_ramp.elements[1].color = (1.05, 1.05, 1.05, 1.0)
nt_lid.links.new(lid_noise.outputs["Fac"], lid_colorramp.inputs["Fac"])

lid_mix = nt_lid.nodes.new("ShaderNodeMix")
lid_mix.data_type = 'RGBA'
lid_mix.blend_type = 'MULTIPLY'
lid_mix.inputs["Factor"].default_value = 0.5
lid_mix.inputs["A"].default_value = (0.6706, 0.5255, 0.4235, 1.0)
nt_lid.links.new(lid_colorramp.outputs["Color"], lid_mix.inputs["B"])
nt_lid.links.new(lid_mix.outputs["Result"], lid_bsdf.inputs["Base Color"])

lid_bump = nt_lid.nodes.new("ShaderNodeBump")
lid_bump.inputs["Strength"].default_value = 0.15
nt_lid.links.new(lid_noise.outputs["Fac"], lid_bump.inputs["Height"])
nt_lid.links.new(lid_bump.outputs["Normal"], lid_bsdf.inputs["Normal"])


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

    # Manual UV projection, NOT bpy.ops.uv.sphere_project(): that operator
    # reads the 3D viewport's view angle to decide projection direction,
    # which doesn't exist in headless (-b) mode. It silently produced a
    # degenerate mapping that never actually put the iris/pupil texture
    # on the front-facing pole - the eyes rendered as blank white/peach
    # discs with no visible iris no matter how the eyelid coverage was
    # tuned, because the texture's iris was mapped somewhere off-camera.
    # Local +Z is the sphere's pole, which rotation_euler=(90,0,0) above
    # sends to world -Y (toward the camera) - so a flat orthographic
    # projection of each vertex's local (x,y) onto the texture plane
    # puts the iris exactly where it needs to be, deterministically.
    mesh = obj.data
    # primitive_uv_sphere_add() already created its own default "UVMap"
    # layer (a lat/long wrap whose pole doesn't match the front-facing
    # direction we need). Adding a second layer doesn't replace it as the
    # active-for-render layer, so the image texture node kept sampling
    # the original default UVs no matter what this one contained - the
    # iris never moved. Overwrite the existing layer's data in place
    # instead of creating a new one.
    uv_layer = mesh.uv_layers.active
    for poly in mesh.polygons:
        for loop_idx in poly.loop_indices:
            vidx = mesh.loops[loop_idx].vertex_index
            co = mesh.vertices[vidx].co
            uv_layer.data[loop_idx].uv = (0.5 + co.x / (2 * EYE_RADIUS), 0.5 + co.y / (2 * EYE_RADIUS))
    bpy.ops.object.shade_smooth()

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
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=eye_pos, segments=64, ring_count=96)
    obj = bpy.context.active_object
    obj.name = f"Eyelid_{'Upper' if upper else 'Lower'}.{side}"
    obj.data.materials.append(lid_mat)

    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    # local Z here corresponds to world Z before any rotation (sphere not
    # yet rotated) - keep only the cap on the correct side.
    #
    # A real palpebral fissure is classically constructed as two
    # circular arcs of DIFFERENT curvature meeting at the inner/outer
    # canthus points - a more curved upper-lid arc, a notably flatter
    # lower-lid arc. That asymmetry is what reads as "almond" rather
    # than a round/lens shape. Three earlier attempts at this (an
    # elliptical X taper, a flat-core + linear-ramp taper, a uniform
    # horizontal stretch of the cut cap) all failed by either fighting
    # the sphere's own curvature with an independently-shaped cutoff
    # (flat-topped/boxy result) or by moving kept geometry off the
    # sphere's surface entirely (stretch pulled the lid rim away from
    # the eyeball, leaving a visible gap). This instead keeps the test
    # as a per-vertex delete decision on the SAME unmodified sphere
    # (like the original plain cut), just with a properly-derived
    # curved threshold instead of a flat one - so it can't produce a
    # gap, and it's not fighting the sphere's curvature since the
    # threshold curve is deliberately shaped to taper into the corners
    # rather than cut across them.
    #
    # Circle through (-a,0), (0,b), (a,0): center is at (0,k) with
    # k=(b^2-a^2)/(2b), radius R=(b^2+a^2)/(2b); the arc's height at
    # horizontal offset x is z(x) = k + sqrt(R^2 - x^2). R >= a always
    # (R-a = (a-b)^2/(2b) >= 0), so the sqrt is defined for all |x|<=a.
    A = r * 0.80          # half-width between the inner/outer canthus points
    B_UPPER = r * 0.42    # upper lid arc peak height - more curved
    B_LOWER = r * 0.20    # lower lid arc peak depth - flatter, per real anatomy

    def arc_height(x, b):
        k = (b * b - A * A) / (2 * b)
        R = (b * b + A * A) / (2 * b)
        x = max(-A, min(A, x))
        return k + math.sqrt(max(0.0, R * R - x * x))

    b = B_UPPER if upper else B_LOWER
    to_delete = []
    for v in bm.verts:
        boundary = arc_height(v.co.x, b)
        if upper and v.co.z < boundary:
            to_delete.append(v)
        elif not upper and v.co.z > -boundary:
            to_delete.append(v)
    bmesh.ops.delete(bm, geom=to_delete, context='VERTS')
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.shade_smooth()

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
