import bpy
import os

SRC = "/home/user/kiara/assets/release-hummbuggery/Meshy_AI_Black_Bikini_Studio_P_1001102304_texture.blend"
OUT_BLEND = "/home/user/kiara/assets/work/kiara_retopo.blend"
TARGET_FACES = 24000

bpy.ops.wm.open_mainfile(filepath=SRC)
obj = [o for o in bpy.data.objects if o.type == 'MESH'][0]
bpy.context.view_layer.objects.active = obj
obj.select_set(True)

dims = obj.dimensions[:]
print(f"Source mesh: {obj.name} verts={len(obj.data.vertices)} polys={len(obj.data.polygons)} dims={dims}")

# Pick voxel size relative to the mesh's smallest meaningful dimension so we
# don't over/under-resolve. Target: voxel remesh to a few hundred-k faces,
# then decimate down to TARGET_FACES for a clean final collapse.
max_dim = max(dims)
voxel_size = max_dim / 400.0  # heuristic: ~400 voxels across the long axis
print(f"Using voxel_size={voxel_size:.5f}")

remesh_mod = obj.modifiers.new(name="VoxelRemesh", type='REMESH')
remesh_mod.mode = 'VOXEL'
remesh_mod.voxel_size = voxel_size
remesh_mod.adaptivity = 0.0
remesh_mod.use_smooth_shade = True

bpy.ops.object.modifier_apply(modifier=remesh_mod.name)
print(f"After voxel remesh: verts={len(obj.data.vertices)} polys={len(obj.data.polygons)}")

face_count = len(obj.data.polygons)
if face_count > TARGET_FACES:
    ratio = TARGET_FACES / face_count
    dec_mod = obj.modifiers.new(name="Decimate", type='DECIMATE')
    dec_mod.decimate_type = 'COLLAPSE'
    dec_mod.ratio = ratio
    bpy.ops.object.modifier_apply(modifier=dec_mod.name)
    print(f"After decimate (ratio={ratio:.4f}): verts={len(obj.data.vertices)} polys={len(obj.data.polygons)}")
else:
    print("Voxel remesh already under target, skipping decimate")

# cleanup
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=0.0001)
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode='OBJECT')

print(f"Final: verts={len(obj.data.vertices)} polys={len(obj.data.polygons)}")

os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"Saved: {OUT_BLEND}")
