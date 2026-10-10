import bpy
import os

LOWPOLY_SRC = "/home/user/kiara/assets/work/kiara_uv.blend"
HIGHPOLY_SRC = "/home/user/kiara/assets/release-hummbuggery/Meshy_AI_Black_Bikini_Studio_P_1001102304_texture.blend"
OUT_BLEND = "/home/user/kiara/assets/work/kiara_textured.blend"

bpy.ops.wm.open_mainfile(filepath=LOWPOLY_SRC)
lowpoly = [o for o in bpy.data.objects if o.type == 'MESH'][0]
lowpoly.name = "Kiara_Body"

# append the high-poly textured source mesh into this file
with bpy.data.libraries.load(HIGHPOLY_SRC, link=False) as (data_from, data_to):
    data_to.objects = [n for n in data_from.objects if n == 'Mesh_0'] or data_from.objects[:1]

highpoly = None
for obj in data_to.objects:
    if obj is not None:
        bpy.context.collection.objects.link(obj)
        highpoly = obj
        break

# newly linked objects have a stale (zero) matrix_world until the depsgraph
# is updated - this silently broke the bake (every ray missed) last run.
bpy.context.view_layer.update()
print(f"Highpoly matrix_world after update: {list(highpoly.matrix_world)}")

print(f"Highpoly appended: {highpoly.name} verts={len(highpoly.data.vertices)}")
print(f"Lowpoly target: {lowpoly.name} verts={len(lowpoly.data.vertices)}")

# (previously freed unused secondary maps here to save memory, but that step
# corrupted the bake's color sampling for reasons not fully root-caused -
# dropping bake resolution to 4K/2K already resolved the OOM on its own, so
# this step is skipped entirely now.)

# new material + image for lowpoly (scaled down from 8K/4K to fit memory)
albedo_img = bpy.data.images.new("Kiara_Albedo", 4096, 4096, alpha=False)
normal_img = bpy.data.images.new("Kiara_Normal", 2048, 2048, alpha=False)
normal_img.colorspace_settings.name = 'Non-Color'

mat = bpy.data.materials.new("Kiara_BakedMat")
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes.get("Principled BSDF")

albedo_node = nt.nodes.new("ShaderNodeTexImage")
albedo_node.image = albedo_img
albedo_node.location = (-400, 300)
nt.links.new(albedo_node.outputs["Color"], bsdf.inputs["Base Color"])

normal_tex_node = nt.nodes.new("ShaderNodeTexImage")
normal_tex_node.image = normal_img
normal_tex_node.location = (-400, 0)
normal_map_node = nt.nodes.new("ShaderNodeNormalMap")
normal_map_node.location = (-150, 0)
nt.links.new(normal_tex_node.outputs["Color"], normal_map_node.inputs["Color"])
nt.links.new(normal_map_node.outputs["Normal"], bsdf.inputs["Normal"])

lowpoly.data.materials.clear()
lowpoly.data.materials.append(mat)

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 8
scene.cycles.use_denoising = False
scene.view_layers[0].cycles.use_denoising = False

bpy.ops.object.select_all(action='DESELECT')
highpoly.select_set(True)
lowpoly.select_set(True)
bpy.context.view_layer.objects.active = lowpoly

bake_settings = scene.render.bake
bake_settings.use_selected_to_active = True
bake_settings.cage_extrusion = 0.15
bake_settings.max_ray_distance = 0.5
bake_settings.margin = 16
bake_settings.use_clear = True

# --- DIFFUSE / ALBEDO BAKE ---
albedo_node.select = True
nt.nodes.active = albedo_node
print("Baking albedo...")
bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'})
print("Albedo bake done")

albedo_img.filepath_raw = "/home/user/kiara/assets/work/kiara_albedo.png"
albedo_img.file_format = 'PNG'
albedo_img.save()
print("Saved albedo PNG")

# --- NORMAL BAKE ---
normal_tex_node.select = True
nt.nodes.active = normal_tex_node
print("Baking normal...")
bpy.ops.object.bake(type='NORMAL')
print("Normal bake done")

normal_img.filepath_raw = "/home/user/kiara/assets/work/kiara_normal.png"
normal_img.file_format = 'PNG'
normal_img.save()
print("Saved normal PNG")

bpy.data.objects.remove(highpoly, do_unlink=True)

os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"Saved: {OUT_BLEND}")
