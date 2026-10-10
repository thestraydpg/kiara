"""
Generates a simplified humanoid MJCF model for RL locomotion training,
using the SAME proportions (H, anthropometric landmark fractions) as the
Blender rig in godot_pipeline scripts, so the trained policy's joint
angles retarget cleanly onto the full 177-bone display skeleton later.

This is deliberately a REDUCED-DOF model (one consolidated spine joint
instead of 24 individual vertebrae, no fingers/toes) - full biomechanical
detail is unnecessary and actively harmful for RL tractability. Physical
locomotion training learns a ~20-30 DOF control problem; the extra detail
(fingers, individual vertebrae, facial bones) stays purely cosmetic on the
display rig and gets driven by retargeting + the authored gesture layer,
not by the physics policy itself.
"""

H = 1.884          # character height, meters - matches the Blender rig
MASS_KG = 62.0      # total body mass estimate

# Winter's biomechanical body segment mass fractions (standard reference
# tables used in biomechanics/robotics for exactly this purpose).
MASS_FRAC = {
    "head_neck": 0.081, "trunk": 0.497,
    "upper_arm": 0.028, "forearm": 0.016, "hand": 0.006,
    "thigh": 0.100, "shank": 0.0465, "foot": 0.0145,
}

# Landmark heights as fraction of H (ground-up) - same system used in
# build_skeleton.py for the display rig.
LM = {
    'ankle': 0.045, 'knee': 0.285, 'hip': 0.490, 'waist': 0.600,
    'chest': 0.760, 'shoulder': 0.818, 'neck_base': 0.860, 'crown': 1.000,
}

def z(frac):
    return frac * H

SHOULDER_HALF_W = 0.120 * H
HIP_HALF_W = 0.095 * H
UPPERARM_LEN = 0.186 * H
FOREARM_LEN = 0.146 * H
HAND_LEN = 0.075 * H
THIGH_LEN = z(LM['hip']) - z(LM['knee'])
SHANK_LEN = z(LM['knee']) - z(LM['ankle'])
FOOT_LEN = 0.16 * H

m = lambda frac: MASS_KG * frac

# Visual-only skin: her actual mesh (Kiara_Body from the Blender pipeline),
# rigid-cut per body part by dominant skin weight and re-exported into each
# MuJoCo body's own local rest frame - see
# scratchpad/export_mujoco_skin.py (the one-off Blender export) and the
# cross-validated Z_OFFSET it used. contype/conaffinity=0 so these never
# touch physics/collision (the capsules above keep doing that job
# unchanged), and mass="0" so they add zero mass/inertia - without that,
# a body with two geoms has their masses SUMMED, which would silently
# change the dynamics an already-trained policy was trained against.
# group=1 (mesh) vs group=2 (capsule) so view.py can toggle which one
# renders without touching physics either way.
SKIN_BODIES = ["pelvis", "spine", "head",
               "upperarm_L", "forearm_L", "hand_L", "upperarm_R", "forearm_R", "hand_R",
               "thigh_L", "shank_L", "foot_L", "thigh_R", "shank_R", "foot_R"]

def skin_geom(body_name: str) -> str:
    return (f'<geom type="mesh" mesh="mesh_{body_name}" material="mat_skin" '
            f'mass="0" contype="0" conaffinity="0" group="1"/>')

mesh_assets = "\n    ".join(f'<mesh name="mesh_{b}" file="meshes/kiara_{b}.obj"/>' for b in SKIN_BODIES)

xml = f'''<mujoco model="kiara_locomotion">
  <compiler angle="degree" autolimits="true"/>
  <option timestep="0.002" iterations="50" solver="Newton" gravity="0 0 -9.81"/>
  <default>
    <joint damping="2" armature="0.02" limited="true"/>
    <geom type="capsule" condim="3" friction="0.9 0.1 0.1" density="1050" contype="1" conaffinity="1"/>
    <motor ctrllimited="true" ctrlrange="-1 1"/>
  </default>

  <asset>
    <texture name="tex_skin" type="2d" file="../assets/work/kiara_albedo.png"/>
    <material name="mat_skin" texture="tex_skin"/>
    {mesh_assets}
  </asset>

  <worldbody>
    <light directional="true" pos="0 0 3" dir="0 0 -1"/>
    <geom name="floor" type="plane" size="20 20 0.1" rgba="0.6 0.6 0.6 1" friction="1.0 0.1 0.1"/>

    <body name="pelvis" pos="0 0 {z(LM['hip']):.4f}">
      <freejoint name="root"/>
      <geom name="pelvis_geom" type="capsule" fromto="{-HIP_HALF_W:.4f} 0 0 {HIP_HALF_W:.4f} 0 0" size="0.09" mass="{m(0.142):.3f}" group="2"/>
      {skin_geom("pelvis")}

      <body name="spine" pos="0 0 0.02">
        <joint name="spine_bend" type="hinge" axis="1 0 0" range="-40 60"/>
        <joint name="spine_twist" type="hinge" axis="0 0 1" range="-45 45"/>
        <joint name="spine_side" type="hinge" axis="0 1 0" range="-30 30"/>
        <geom name="spine_geom" type="capsule" fromto="0 0 0 0 0 {z(LM['shoulder'])-z(LM['hip']):.4f}" size="0.11" mass="{m(MASS_FRAC['trunk']):.3f}" group="2"/>
        {skin_geom("spine")}

        <body name="head" pos="0 0 {z(LM['crown'])-z(LM['shoulder']):.4f}">
          <joint name="neck_bend" type="hinge" axis="1 0 0" range="-45 45"/>
          <joint name="neck_twist" type="hinge" axis="0 0 1" range="-70 70"/>
          <geom name="head_geom" type="sphere" size="0.11" mass="{m(MASS_FRAC['head_neck']):.3f}" group="2"/>
          {skin_geom("head")}
        </body>

        <body name="upperarm_L" pos="{SHOULDER_HALF_W:.4f} 0 0">
          <joint name="shoulder_L_flex" type="hinge" axis="1 0 0" range="-90 180"/>
          <joint name="shoulder_L_abd" type="hinge" axis="0 1 0" range="-20 170"/>
          <joint name="shoulder_L_rot" type="hinge" axis="0 0 1" range="-90 90"/>
          <geom name="upperarm_L_geom" type="capsule" fromto="0 0 0 {UPPERARM_LEN:.4f} 0 0" size="0.045" mass="{m(MASS_FRAC['upper_arm']):.3f}" group="2"/>
          {skin_geom("upperarm_L")}
          <body name="forearm_L" pos="{UPPERARM_LEN:.4f} 0 0">
            <joint name="elbow_L" type="hinge" axis="0 0 1" range="0 150"/>
            <geom name="forearm_L_geom" type="capsule" fromto="0 0 0 {FOREARM_LEN:.4f} 0 0" size="0.035" mass="{m(MASS_FRAC['forearm']):.3f}" group="2"/>
            {skin_geom("forearm_L")}
            <body name="hand_L" pos="{FOREARM_LEN:.4f} 0 0">
              <joint name="wrist_L" type="hinge" axis="0 1 0" range="-70 70"/>
              <geom name="hand_L_geom" type="capsule" fromto="0 0 0 {HAND_LEN:.4f} 0 0" size="0.025" mass="{m(MASS_FRAC['hand']):.3f}" group="2"/>
              {skin_geom("hand_L")}
            </body>
          </body>
        </body>

        <body name="upperarm_R" pos="{-SHOULDER_HALF_W:.4f} 0 0">
          <joint name="shoulder_R_flex" type="hinge" axis="1 0 0" range="-90 180"/>
          <joint name="shoulder_R_abd" type="hinge" axis="0 1 0" range="-170 20"/>
          <joint name="shoulder_R_rot" type="hinge" axis="0 0 1" range="-90 90"/>
          <geom name="upperarm_R_geom" type="capsule" fromto="0 0 0 {-UPPERARM_LEN:.4f} 0 0" size="0.045" mass="{m(MASS_FRAC['upper_arm']):.3f}" group="2"/>
          {skin_geom("upperarm_R")}
          <body name="forearm_R" pos="{-UPPERARM_LEN:.4f} 0 0">
            <joint name="elbow_R" type="hinge" axis="0 0 1" range="-150 0"/>
            <geom name="forearm_R_geom" type="capsule" fromto="0 0 0 {-FOREARM_LEN:.4f} 0 0" size="0.035" mass="{m(MASS_FRAC['forearm']):.3f}" group="2"/>
            {skin_geom("forearm_R")}
            <body name="hand_R" pos="{-FOREARM_LEN:.4f} 0 0">
              <joint name="wrist_R" type="hinge" axis="0 1 0" range="-70 70"/>
              <geom name="hand_R_geom" type="capsule" fromto="0 0 0 {-HAND_LEN:.4f} 0 0" size="0.025" mass="{m(MASS_FRAC['hand']):.3f}" group="2"/>
              {skin_geom("hand_R")}
            </body>
          </body>
        </body>
      </body>

      <body name="thigh_L" pos="{HIP_HALF_W:.4f} 0 0">
        <joint name="hip_L_flex" type="hinge" axis="1 0 0" range="-120 45"/>
        <joint name="hip_L_abd" type="hinge" axis="0 1 0" range="-45 30"/>
        <joint name="hip_L_rot" type="hinge" axis="0 0 1" range="-45 45"/>
        <geom name="thigh_L_geom" type="capsule" fromto="0 0 0 0 0 {-THIGH_LEN:.4f}" size="0.07" mass="{m(MASS_FRAC['thigh']):.3f}" group="2"/>
        {skin_geom("thigh_L")}
        <body name="shank_L" pos="0 0 {-THIGH_LEN:.4f}">
          <joint name="knee_L" type="hinge" axis="1 0 0" range="-150 5"/>
          <geom name="shank_L_geom" type="capsule" fromto="0 0 0 0 0 {-SHANK_LEN:.4f}" size="0.05" mass="{m(MASS_FRAC['shank']):.3f}" group="2"/>
          {skin_geom("shank_L")}
          <body name="foot_L" pos="0 0 {-SHANK_LEN:.4f}">
            <joint name="ankle_L_flex" type="hinge" axis="1 0 0" range="-45 30"/>
            <joint name="ankle_L_roll" type="hinge" axis="0 1 0" range="-20 20"/>
            <geom name="foot_L_geom" type="capsule" fromto="0 -0.02 0 0 {-FOOT_LEN:.4f} 0" size="0.045" mass="{m(MASS_FRAC['foot']):.3f}" group="2"/>
            {skin_geom("foot_L")}
          </body>
        </body>
      </body>

      <body name="thigh_R" pos="{-HIP_HALF_W:.4f} 0 0">
        <joint name="hip_R_flex" type="hinge" axis="1 0 0" range="-120 45"/>
        <joint name="hip_R_abd" type="hinge" axis="0 1 0" range="-30 45"/>
        <joint name="hip_R_rot" type="hinge" axis="0 0 1" range="-45 45"/>
        <geom name="thigh_R_geom" type="capsule" fromto="0 0 0 0 0 {-THIGH_LEN:.4f}" size="0.07" mass="{m(MASS_FRAC['thigh']):.3f}" group="2"/>
        {skin_geom("thigh_R")}
        <body name="shank_R" pos="0 0 {-THIGH_LEN:.4f}">
          <joint name="knee_R" type="hinge" axis="1 0 0" range="-150 5"/>
          <geom name="shank_R_geom" type="capsule" fromto="0 0 0 0 0 {-SHANK_LEN:.4f}" size="0.05" mass="{m(MASS_FRAC['shank']):.3f}" group="2"/>
          {skin_geom("shank_R")}
          <body name="foot_R" pos="0 0 {-SHANK_LEN:.4f}">
            <joint name="ankle_R_flex" type="hinge" axis="1 0 0" range="-45 30"/>
            <joint name="ankle_R_roll" type="hinge" axis="0 1 0" range="-20 20"/>
            <geom name="foot_R_geom" type="capsule" fromto="0 -0.02 0 0 {-FOOT_LEN:.4f} 0" size="0.045" mass="{m(MASS_FRAC['foot']):.3f}" group="2"/>
            {skin_geom("foot_R")}
          </body>
        </body>
      </body>
    </body>
  </worldbody>

  <actuator>
    <motor name="m_spine_bend" joint="spine_bend" gear="120"/>
    <motor name="m_spine_twist" joint="spine_twist" gear="100"/>
    <motor name="m_spine_side" joint="spine_side" gear="100"/>
    <motor name="m_neck_bend" joint="neck_bend" gear="25"/>
    <motor name="m_neck_twist" joint="neck_twist" gear="20"/>

    <motor name="m_shoulder_L_flex" joint="shoulder_L_flex" gear="40"/>
    <motor name="m_shoulder_L_abd" joint="shoulder_L_abd" gear="40"/>
    <motor name="m_shoulder_L_rot" joint="shoulder_L_rot" gear="25"/>
    <motor name="m_elbow_L" joint="elbow_L" gear="25"/>
    <motor name="m_wrist_L" joint="wrist_L" gear="10"/>

    <motor name="m_shoulder_R_flex" joint="shoulder_R_flex" gear="40"/>
    <motor name="m_shoulder_R_abd" joint="shoulder_R_abd" gear="40"/>
    <motor name="m_shoulder_R_rot" joint="shoulder_R_rot" gear="25"/>
    <motor name="m_elbow_R" joint="elbow_R" gear="25"/>
    <motor name="m_wrist_R" joint="wrist_R" gear="10"/>

    <motor name="m_hip_L_flex" joint="hip_L_flex" gear="150"/>
    <motor name="m_hip_L_abd" joint="hip_L_abd" gear="120"/>
    <motor name="m_hip_L_rot" joint="hip_L_rot" gear="60"/>
    <motor name="m_knee_L" joint="knee_L" gear="150"/>
    <motor name="m_ankle_L_flex" joint="ankle_L_flex" gear="80"/>
    <motor name="m_ankle_L_roll" joint="ankle_L_roll" gear="40"/>

    <motor name="m_hip_R_flex" joint="hip_R_flex" gear="150"/>
    <motor name="m_hip_R_abd" joint="hip_R_abd" gear="120"/>
    <motor name="m_hip_R_rot" joint="hip_R_rot" gear="60"/>
    <motor name="m_knee_R" joint="knee_R" gear="150"/>
    <motor name="m_ankle_R_flex" joint="ankle_R_flex" gear="80"/>
    <motor name="m_ankle_R_roll" joint="ankle_R_roll" gear="40"/>
  </actuator>
</mujoco>
'''

if __name__ == "__main__":
    import os
    out_path = os.path.join(os.path.dirname(__file__), "kiara_humanoid.xml")
    with open(out_path, "w") as f:
        f.write(xml)
    n_joints = xml.count("<joint ")
    n_motors = xml.count("<motor ")
    print(f"Wrote {out_path}")
    print(f"Joints: {n_joints} (+6 free root DOF)  Motors: {n_motors}")
