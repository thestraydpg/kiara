import bpy
import os

SRC = "/home/user/kiara/assets/work/kiara_jaw.blend"
OUT_DIR = "/home/user/kiara/godot/assets"
OUT_GLB = os.path.join(OUT_DIR, "kiara.glb")

bpy.ops.wm.open_mainfile(filepath=SRC)
body = [o for o in bpy.data.objects if o.name == "Kiara_Body"][0]
rig = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
rig.name = "Kiara_Armature"

bones = rig.data.bones
total = len(bones)
deform = len([b for b in bones if b.use_deform])
print(f"Armature: {total} bones, {deform} deform")
print(f"Mesh: {len(body.data.vertices)} verts, {len(body.vertex_groups)} vgroups")

mat = body.data.materials[0]
print(f"Material: {mat.name}")
for node in mat.node_tree.nodes:
    if node.type == 'TEX_IMAGE' and node.image:
        print(f"  tex node: {node.name} image={node.image.name} has_data={node.image.has_data} filepath={node.image.filepath!r}")

os.makedirs(OUT_DIR, exist_ok=True)

bpy.ops.object.select_all(action='DESELECT')
body.select_set(True)
rig.select_set(True)
bpy.context.view_layer.objects.active = rig

bpy.ops.export_scene.gltf(
    filepath=OUT_GLB,
    export_format='GLB',
    use_selection=True,
    export_image_format='AUTO',
    export_materials='EXPORT',
    export_skins=True,
    export_morph=False,
    export_apply=False,
    export_yup=True,
    export_animations=False,
    export_optimize_animation_size=False,
    export_rest_position_armature=True,
)

print(f"Exported: {OUT_GLB}")
print(f"Size: {os.path.getsize(OUT_GLB) / 1e6:.1f} MB")
