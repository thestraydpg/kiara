import bpy
import mathutils
import math
import os

SRC = "/home/user/kiara/assets/work/kiara_retopo.blend"
OUT_BLEND = "/home/user/kiara/assets/work/kiara_rigged.blend"

bpy.ops.wm.open_mainfile(filepath=SRC)
body = [o for o in bpy.data.objects if o.type == 'MESH'][0]

# measured bounds
min_co = mathutils.Vector((1e9,)*3)
max_co = mathutils.Vector((-1e9,)*3)
for v in body.data.vertices:
    co = body.matrix_world @ v.co
    min_co.x = min(min_co.x, co.x); max_co.x = max(max_co.x, co.x)
    min_co.y = min(min_co.y, co.y); max_co.y = max(max_co.y, co.y)
    min_co.z = min(min_co.z, co.z); max_co.z = max(max_co.z, co.z)

H = max_co.z - min_co.z
GROUND = min_co.z
CENTER_Y = (min_co.y + max_co.y) / 2.0  # mid-depth
print(f"Height={H:.4f} ground={GROUND:.4f} centerY={CENTER_Y:.4f}")

def z(frac):
    return GROUND + frac * H

# -- anthropometric landmarks (fractions of total height, ground-up) --
LM = {
    'ankle':       0.045,
    'knee':        0.285,
    'hip':         0.490,   # crotch / pubic symphysis
    'waist':       0.600,
    'ribcage_lo':  0.680,
    'chest':       0.760,
    'shoulder':    0.818,
    'neck_base':   0.860,
    'chin':        0.910,
    'mouth':       0.930,
    'nose':        0.945,
    'eyes':        0.957,
    'brow':        0.967,
    'crown':       1.000,
}

SHOULDER_HALF_W = 0.120 * H
HIP_HALF_W = 0.095 * H
CHEST_DEPTH_FRONT = -0.095 * H   # negative Y = front (toward viewer)
CHEST_DEPTH_BACK = 0.06 * H

arm = bpy.data.armatures.new("KiaraSkeleton")
rig = bpy.data.objects.new("Kiara_Armature", arm)
bpy.context.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
rig.select_set(True)

bpy.ops.object.mode_set(mode='EDIT')
eb = arm.edit_bones

def add_bone(name, head, tail, parent=None, deform=True, connect=False, roll=0.0):
    b = eb.new(name)
    b.head = head
    b.tail = tail
    b.use_deform = deform
    b.roll = roll
    if parent:
        b.parent = eb[parent] if isinstance(parent, str) else parent
        b.use_connect = connect
    return b

def lerp(a, b, t):
    return a + (b - a) * t

# ---------------------------------------------------------------
# ROOT / PELVIS
# ---------------------------------------------------------------
root = add_bone("root", (0, 0, GROUND), (0, 0, z(0.05)), deform=False)
pelvis = add_bone("pelvis", (0, 0, z(LM['hip'])), (0, -0.05*H, z(LM['hip'])+0.03*H), parent="root")

# ---------------------------------------------------------------
# SPINE: 5 lumbar + 12 thoracic + 7 cervical vertebrae
# ---------------------------------------------------------------
spine_bones = []
prev_name = "pelvis"

def build_vertebra_chain(prefix, count, z0, z1, parent_name):
    names = []
    for i in range(count):
        t0 = i / count
        t1 = (i + 1) / count
        zz0 = lerp(z0, z1, t0)
        zz1 = lerp(z0, z1, t1)
        name = f"{prefix}{count - i if 'lumbar' in prefix or 'cervical' in prefix else i+1}"
        b = add_bone(name, (0, 0, zz0), (0, 0, zz1), parent=parent_name, connect=(i > 0))
        names.append(name)
        parent_name = name
    return names, parent_name

lumbar_names, last = build_vertebra_chain("spine_L", 5, z(LM['hip']), z(LM['ribcage_lo']), "pelvis")
thoracic_names, last = build_vertebra_chain("spine_T", 12, z(LM['ribcage_lo']), z(LM['neck_base']), last)
cervical_names, last = build_vertebra_chain("neck_C", 7, z(LM['neck_base']), z(LM['chin']), last)
neck_top = last

head = add_bone("head", (0, 0, z(LM['chin'])), (0, 0, z(LM['crown'])), parent=neck_top, connect=True)

# ---------------------------------------------------------------
# RIBCAGE: sternum + 12 pairs of ribs (mechanism bones, non-deform)
# ---------------------------------------------------------------
sternum_base_t = thoracic_names[-1]  # topmost thoracic (T1) - near shoulder
sternum = add_bone("sternum", (0, CHEST_DEPTH_FRONT*0.3, z(LM['ribcage_lo'])),
                    (0, CHEST_DEPTH_FRONT, z(LM['shoulder'])), parent=thoracic_names[-1], deform=False)

for i, tname in enumerate(thoracic_names):
    t_frac = i / (len(thoracic_names) - 1)
    zz = lerp(z(LM['ribcage_lo']), z(LM['shoulder']), t_frac)
    rib_reach_x = lerp(0.12*H, 0.09*H, t_frac)
    rib_reach_y = lerp(CHEST_DEPTH_FRONT*0.8, CHEST_DEPTH_FRONT*0.3, t_frac)
    for side, sign in (('L', 1), ('R', -1)):
        add_bone(f"rib_{i+1:02d}.{side}", (0, 0.03*H, zz), (sign*rib_reach_x, rib_reach_y, zz),
                  parent=tname, deform=False)

# ---------------------------------------------------------------
# SHOULDER GIRDLE + ARMS + HANDS (per side)
# ---------------------------------------------------------------
def build_arm(side, sign):
    # T-pose: arms extend horizontally outward along X, not down along Z.
    shoulder_z = z(LM['shoulder'])
    neck_base_z = z(LM['neck_base'])

    UPPERARM_LEN = 0.186*H
    FOREARM_LEN = 0.146*H
    HAND_LEN = 0.075*H

    shoulder_x = SHOULDER_HALF_W
    elbow_x = shoulder_x + UPPERARM_LEN
    wrist_x = elbow_x + FOREARM_LEN
    hand_tip_x = wrist_x + HAND_LEN

    clavicle = add_bone(f"clavicle.{side}", (sign*0.03*H, 0, neck_base_z),
                         (sign*shoulder_x, 0, shoulder_z), parent=thoracic_names[-1])
    scapula = add_bone(f"scapula.{side}", (sign*0.06*H, 0.04*H, shoulder_z+0.02*H),
                        (sign*shoulder_x*0.9, 0.05*H, shoulder_z), parent=clavicle, deform=False)

    upperarm = add_bone(f"upperarm.{side}", (sign*shoulder_x, 0, shoulder_z),
                         (sign*elbow_x, 0, shoulder_z), parent=clavicle, connect=True)
    forearm = add_bone(f"forearm.{side}", (sign*elbow_x, 0, shoulder_z),
                        (sign*wrist_x, 0, shoulder_z), parent=upperarm, connect=True)
    forearm_twist = add_bone(f"forearm_twist.{side}", (sign*lerp(elbow_x, wrist_x, 0.5), 0, shoulder_z),
                              (sign*wrist_x, 0, shoulder_z), parent=forearm, deform=True)
    hand = add_bone(f"hand.{side}", (sign*wrist_x, 0, shoulder_z),
                     (sign*hand_tip_x, -0.015*H, shoulder_z), parent=forearm, connect=True)

    # fingers: thumb (2 phalanges), index/middle/ring/pinky (3 phalanges) + metacarpals
    # spread laterally in Y (front/back of flat hand), extend further out in X
    finger_spec = {
        'thumb':  (2, -0.025*H, 0.025*H),
        'index':  (3, 0.0,     0.018*H),
        'middle': (3, 0.0,     0.0),
        'ring':   (3, 0.0,    -0.018*H),
        'pinky':  (3, -0.01*H,-0.032*H),
    }
    for fname, (segs, fx, fy) in finger_spec.items():
        base_x = hand_tip_x + fx
        base_y = -0.015*H + fy
        meta = add_bone(f"{fname}_meta.{side}", (sign*base_x, base_y, shoulder_z),
                         (sign*(base_x+0.02*H), base_y, shoulder_z), parent=hand, deform=False)
        prev = meta
        seg_len = 0.022*H if fname != 'thumb' else 0.028*H
        cursor = mathutils.Vector((sign*(base_x+0.02*H), base_y, shoulder_z))
        direction = mathutils.Vector((sign*1.0, 0, 0)).normalized()
        for s in range(segs):
            nxt = cursor + direction * seg_len
            b = add_bone(f"{fname}_{s+1:02d}.{side}", tuple(cursor), tuple(nxt), parent=prev, connect=True, deform=False)
            prev = b
            cursor = nxt

    return upperarm

build_arm('L', 1)
build_arm('R', -1)

# ---------------------------------------------------------------
# LEGS + FEET + TOES (per side)
# ---------------------------------------------------------------
def build_leg(side, sign):
    hip_x = sign*HIP_HALF_W
    hip_z = z(LM['hip'])
    knee_z = z(LM['knee'])
    ankle_z = z(LM['ankle'])
    ball_z = GROUND + 0.01*H

    thigh = add_bone(f"thigh.{side}", (hip_x, 0, hip_z), (hip_x, 0.01*H, knee_z), parent="pelvis")
    thigh_twist = add_bone(f"thigh_twist.{side}", (hip_x, 0.005*H, lerp(hip_z, knee_z, 0.5)),
                            (hip_x, 0.01*H, knee_z), parent=thigh, deform=True)
    shin = add_bone(f"shin.{side}", (hip_x, 0.01*H, knee_z), (hip_x, 0, ankle_z), parent=thigh, connect=True)
    shin_twist = add_bone(f"shin_twist.{side}", (hip_x, 0.005*H, lerp(knee_z, ankle_z, 0.5)),
                           (hip_x, 0, ankle_z), parent=shin, deform=True)
    foot = add_bone(f"foot.{side}", (hip_x, 0, ankle_z), (hip_x, -0.11*H, ball_z), parent=shin, connect=True)
    toes_base = add_bone(f"toes.{side}", (hip_x, -0.11*H, ball_z), (hip_x, -0.16*H, ball_z), parent=foot, connect=True)

    toe_spec = {
        'big':   (2, sign*0.035*H),
        'idx2':  (3, sign*0.02*H),
        'mid':   (3, sign*0.005*H),
        'idx4':  (3, -sign*0.01*H),
        'small': (3, -sign*0.025*H),
    }
    for tname, (segs, tx) in toe_spec.items():
        base = mathutils.Vector((hip_x + tx, -0.16*H, ball_z))
        seg_len = 0.018*H
        cursor = base.copy()
        prev = toes_base
        for s in range(segs):
            nxt = cursor + mathutils.Vector((0, -seg_len, 0))
            b = add_bone(f"toe_{tname}_{s+1:02d}.{side}", tuple(cursor), tuple(nxt), parent=prev, connect=(s>0), deform=False)
            prev = b
            cursor = nxt

build_leg('L', 1)
build_leg('R', -1)

# ---------------------------------------------------------------
# FACE (mounted on 'head' bone)
# ---------------------------------------------------------------
skull_z = z(LM['crown'])
chin_z = z(LM['chin'])
# Fine facial bones: non-deform for now. The current mesh has no separated
# facial geometry (eyes/lids/lips/brows are all one low-poly blob from the
# uniform decimation), so there's nothing distinct for the heat solver to
# bind these to yet. They stay in the rig as pose/drive targets for a future
# high-density face pass and for MuJoCo-side expression driving.
jaw = add_bone("jaw", (0, -0.07*H, lerp(chin_z, skull_z, 0.35)), (0, -0.11*H, chin_z), parent="head", deform=False)

eye_z = z(LM['eyes'])
brow_z = z(LM['brow'])
mouth_z = z(LM['mouth'])
nose_y = -0.10*H

for side, sign in (('L', 1), ('R', -1)):
    ex = sign*0.035*H
    add_bone(f"eye.{side}", (ex, -0.08*H, eye_z), (ex, -0.11*H, eye_z), parent="head", deform=False)
    add_bone(f"lid_upper.{side}", (ex, -0.095*H, eye_z+0.008*H), (ex, -0.105*H, eye_z+0.004*H), parent="head", deform=False)
    add_bone(f"lid_lower.{side}", (ex, -0.095*H, eye_z-0.008*H), (ex, -0.105*H, eye_z-0.004*H), parent="head", deform=False)
    add_bone(f"brow_inner.{side}", (sign*0.015*H, -0.09*H, brow_z), (sign*0.025*H, -0.1*H, brow_z), parent="head", deform=False)
    add_bone(f"brow_outer.{side}", (sign*0.04*H, -0.085*H, brow_z-0.005*H), (sign*0.05*H, -0.095*H, brow_z-0.005*H), parent="head", deform=False)
    add_bone(f"cheek.{side}", (sign*0.04*H, -0.08*H, lerp(eye_z, mouth_z, 0.5)), (sign*0.05*H, -0.09*H, lerp(eye_z, mouth_z, 0.5)), parent="head", deform=False)
    add_bone(f"lip_corner.{side}", (sign*0.025*H, nose_y, mouth_z), (sign*0.03*H, nose_y-0.01*H, mouth_z), parent=jaw, deform=False)

add_bone("lip_upper", (0, nose_y, mouth_z+0.008*H), (0, nose_y-0.01*H, mouth_z+0.008*H), parent="head", deform=False)
add_bone("lip_lower", (0, nose_y, mouth_z-0.008*H), (0, nose_y-0.01*H, mouth_z-0.008*H), parent=jaw, deform=False)
add_bone("nose", (0, -0.1*H, z(LM['nose'])), (0, -0.13*H, z(LM['nose'])-0.01*H), parent="head", deform=False)

bpy.ops.object.mode_set(mode='OBJECT')

total_bones = len(arm.bones)
deform_bones = len([b for b in arm.bones if b.use_deform])
print(f"Total bones: {total_bones}")
print(f"Deform bones: {deform_bones}")
print(f"Non-deform (mechanism) bones: {total_bones - deform_bones}")

os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"Saved: {OUT_BLEND}")
