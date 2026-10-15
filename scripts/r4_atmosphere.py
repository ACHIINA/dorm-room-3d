"""リアル版 段階R4: 実写の写真・紙の質感・額のガラス・窓の外の実写夜景(HDRI)・空気中の霞。Blender 内で exec する。"""
import bpy, bmesh, os, math
from mathutils import Vector

D = bpy.data
SC = bpy.context.scene
ROOT = os.path.dirname(D.filepath)
rel = lambda *p: bpy.path.relpath(os.path.join(ROOT, *p))
HDRI = os.path.join(ROOT, "assets_polyhaven", "hdri", "laufenurg_church_4k.hdr")
HDRI_ROT = math.radians(150)  # 丘の上のライトアップされた教会が窓の中央に来る向き


def img(path, noncolor=False):
    i = D.images.load(rel(path) if not path.startswith("//") else path, check_existing=True)
    if noncolor:
        i.colorspace_settings.name = 'Non-Color'
    return i


def tex_node(m):
    return next(n for n in m.node_tree.nodes if n.type == "TEX_IMAGE")


# ---- 1. 写真を実写プリントに差し替え ----
for i in range(8):
    m = D.materials.get(f"pinned_photo_{i}")
    if m:
        tex_node(m).image = img(os.path.join(ROOT, "textures", "real_photos", f"pinned_{i}.jpg"))
for n, f in (("art_photo_campus1", "framed_1.jpg"), ("art_photo_campus2", "framed_2.jpg")):
    tex_node(D.materials[n]).image = img(os.path.join(ROOT, "textures", "real_photos", f))


# ---- 2. 紙の質感(繊維の凹凸と粗さのむら) ----
def paper(mname, rough=(0.55, 0.75), bump=0.15, scale=900.0):
    m = D.materials[mname]
    nt = m.node_tree
    if any(n.name.startswith("paper_") for n in nt.nodes):
        return
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.name = "paper_tc"
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.name = "paper_noise"
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 6.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.name = "paper_rough"
    mr.inputs["To Min"].default_value = rough[0]
    mr.inputs["To Max"].default_value = rough[1]
    nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], b.inputs["Roughness"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.name = "paper_bump"
    bp.inputs["Strength"].default_value = bump
    bp.inputs["Distance"].default_value = 0.0004
    nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])


for n in ("art_poster_circle", "art_poster_shapes"):
    paper(n, (0.6, 0.8), 0.25)
for n in ["art_photo_campus1", "art_photo_campus2"] + [f"pinned_photo_{i}" for i in range(8)]:
    if n in D.materials:
        paper(n, (0.22, 0.35), 0.05, 1500.0)  # 光沢紙
paper("paper_white", (0.7, 0.9), 0.3)

# ---- 3. 額のガラス ----
for o in [o for o in D.objects if o.name.startswith("WD_Glass_")]:
    D.objects.remove(o, do_unlink=True)
glass = D.materials.get("frame_glass") or D.materials.new("frame_glass")
glass.use_nodes = True
gb = next(n for n in glass.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
gb.inputs["Transmission Weight"].default_value = 1.0
gb.inputs["Roughness"].default_value = 0.03
gb.inputs["IOR"].default_value = 1.5
gb.inputs["Base Color"].default_value = (0.95, 0.97, 0.96, 1)
glass.diffuse_color = (0.9, 0.95, 0.95, 0.2)
WD = D.collections["11_WallDecor"]
for art in ("WD_PosterL_Art", "WD_PosterB_Art", "WD_FrameS1_Art", "WD_FrameS2_Art"):
    o = D.objects[art]
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    thin = min(range(3), key=lambda i: hi[i] - lo[i])
    me = D.meshes.new(art.replace("_Art", "_Glass"))
    bm = bmesh.new()
    if thin == 0:  # 左の壁(+x 向き)
        x = hi.x + 0.004
        vs = [(x, lo.y - 0.02, lo.z - 0.02), (x, hi.y + 0.02, lo.z - 0.02), (x, hi.y + 0.02, hi.z + 0.02), (x, lo.y - 0.02, hi.z + 0.02)]
    else:  # 奥の壁(-y 向き)
        y = lo.y - 0.004
        vs = [(lo.x - 0.02, y, lo.z - 0.02), (lo.x - 0.02, y, hi.z + 0.02), (hi.x + 0.02, y, hi.z + 0.02), (hi.x + 0.02, y, lo.z - 0.02)]
    bm.faces.new([bm.verts.new(v) for v in vs])
    bm.to_mesh(me)
    bm.free()
    g = D.objects.new("WD_Glass_" + art.split("_")[1], me)
    WD.objects.link(g)
    me.materials.append(glass)
    g.visible_shadow = False

# ---- 4. 窓の外: 実写の夜景 HDRI(背景のイラストは非表示へ) ----
bd = D.objects.get("Backdrop_NightCampus")
old = D.collections.get("90_Replaced")
if bd and old and bd.name not in old.objects:
    for c in list(bd.users_collection):
        c.objects.unlink(bd)
    old.objects.link(bd)
w = SC.world
nt = w.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
tc = nt.nodes.new("ShaderNodeTexCoord")
mp = nt.nodes.new("ShaderNodeMapping")
mp.inputs["Rotation"].default_value = (0, 0, HDRI_ROT)
env = nt.nodes.new("ShaderNodeTexEnvironment")
env.image = img(HDRI)
bg_cam = nt.nodes.new("ShaderNodeBackground")
bg_cam.inputs["Strength"].default_value = 0.55   # 窓越しに見える明るさ
bg_lit = nt.nodes.new("ShaderNodeBackground")
bg_lit.inputs["Strength"].default_value = 0.12   # 部屋を照らす分は控えめ
lp = nt.nodes.new("ShaderNodeLightPath")
mix = nt.nodes.new("ShaderNodeMixShader")
out = nt.nodes.new("ShaderNodeOutputWorld")
nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
nt.links.new(env.outputs["Color"], bg_cam.inputs["Color"])
nt.links.new(env.outputs["Color"], bg_lit.inputs["Color"])
nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
nt.links.new(bg_lit.outputs[0], mix.inputs[1])
nt.links.new(bg_cam.outputs[0], mix.inputs[2])
nt.links.new(mix.outputs[0], out.inputs["Surface"])

# ---- 5. 空気中の霞(ランプと月光の光の筋) ----
for o in [o for o in D.objects if o.name == "Atmos_Haze"]:
    D.objects.remove(o, do_unlink=True)
hz = D.materials.get("atmos_haze") or D.materials.new("atmos_haze")
hz.use_nodes = True
hn = hz.node_tree
for n in list(hn.nodes):
    hn.nodes.remove(n)
pv = hn.nodes.new("ShaderNodeVolumePrincipled")
pv.inputs["Density"].default_value = 0.014
pv.inputs["Anisotropy"].default_value = 0.55
pv.inputs["Color"].default_value = (0.95, 0.92, 0.88, 1)
ho = hn.nodes.new("ShaderNodeOutputMaterial")
hn.links.new(pv.outputs["Volume"], ho.inputs["Volume"])
me = D.meshes.new("Atmos_Haze")
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1)
bmesh.ops.scale(bm, vec=(4.30, 4.60, 2.66), verts=bm.verts)
bm.to_mesh(me)
bm.free()
hzo = D.objects.new("Atmos_Haze", me)
D.collections["01_Room"].objects.link(hzo)
hzo.location = (-0.585, 2.68, 1.34)
me.materials.append(hz)
hzo.visible_shadow = False
SC.cycles.volume_bounces = 1
SC.cycles.volume_step_rate = 4.0
print("atmosphere ok")
