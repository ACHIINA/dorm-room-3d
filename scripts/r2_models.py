"""リアル版 段階R2: Poly Haven の実物スキャンのモデルを置く。Blender 内で exec する。
置き換えた自作の物は消さずに 90_Replaced コレクションへ移して非表示にする(戻せるように)。"""
import bpy, os, math
from mathutils import Vector, Matrix

D = bpy.data
SC = bpy.context.scene
ROOT = os.path.dirname(D.filepath)
MOD = os.path.join(ROOT, "assets_polyhaven", "models")


def coll(n, hide=False):
    c = D.collections.get(n)
    if not c:
        c = D.collections.new(n)
        SC.collection.children.link(c)
    c.hide_render = hide
    c.hide_viewport = hide
    return c


PH = coll("20_PolyHaven")
OLD = coll("90_Replaced", hide=True)
_cache = {}


def bbox(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs if o.type == 'MESH' for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return lo, hi


def import_asset(asset):
    """1 度だけ読み込んで原点を底面中央にそろえた Empty を返す(以降はその複製)"""
    if asset in _cache:
        return _cache[asset]
    path = next(os.path.join(MOD, asset, f) for f in os.listdir(os.path.join(MOD, asset)) if f.endswith(".gltf"))
    before = set(D.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in D.objects if o not in before]
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        PH.objects.link(o)
    root = D.objects.new(f"PH_{asset}_src", None)
    PH.objects.link(root)
    bpy.context.view_layer.update()
    lo, hi = bbox(new)
    root.location = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)
    bpy.context.view_layer.update()
    for o in new:
        if o.parent is None:
            mw = o.matrix_world.copy()
            o.parent = root
            o.matrix_world = mw
    root["height"] = hi.z - lo.z
    root["width"] = max(hi.x - lo.x, hi.y - lo.y)
    _cache[asset] = root
    return root


def place(asset, name, loc, height=None, width=None, rotz=0.0):
    src = import_asset(asset)
    if name == f"PH_{asset}_src":
        e = src
    elif not src.get("placed"):
        e = src
        e.name = name
    else:
        # 2 個目以降はメッシュを共有した複製
        e = D.objects.new(name, None)
        PH.objects.link(e)
        for ch in src.children:
            d = ch.copy()
            PH.objects.link(d)
            d.parent = e
            d.matrix_parent_inverse = ch.matrix_parent_inverse.copy()
            d.matrix_basis = ch.matrix_basis.copy()
        e["height"], e["width"] = src["height"], src["width"]
    src["placed"] = True
    s = 1.0
    if height:
        s = height / e["height"]
    elif width:
        s = width / e["width"]
    e.location = loc
    e.rotation_euler = (0, 0, rotz)
    e.scale = (s, s, s)
    return e


def retire(*prefixes):
    """自作の物を非表示のコレクションへ移す(親子ごと)"""
    for o in [o for o in D.objects if o.name.startswith(prefixes) and o.parent is None]:
        for x in [o] + list(o.children_recursive):
            for c in list(x.users_collection):
                c.objects.unlink(x)
            OLD.objects.link(x)


# ---- 植物 ----
retire("BigPlant", "MS_SillPlant", "Shelf_Plant", "DP_Plant", "MS_CabPlant")
place("pachira_aquatica_01", "PH_BigPlant", (-2.46, 4.10, 0.0), height=1.45, rotz=math.radians(30))
place("potted_plant_02", "PH_SillPlant1", (-0.70, 5.07, 0.93), height=0.32, rotz=0.4)
place("potted_plant_01", "PH_SillPlant2", (0.66, 5.07, 0.93), height=0.36, rotz=1.2)
place("potted_plant_04", "PH_SillPlant3", (1.30, 5.07, 0.93), height=0.24, rotz=2.0)
place("calathea_orbifolia_01", "PH_ShelfPlant", (-1.02, 4.80, 0.84), height=0.36, rotz=0.8)
place("potted_plant_04", "PH_DeskPlant", (-2.60, 1.99, 0.76), height=0.26, rotz=-0.6)
place("potted_plant_01", "PH_CabPlant", (0.62, 1.42, 0.58), height=0.26, rotz=0.3)

# ---- 小物 ----
retire("Shelf_Vase", "DP_PenCup", "DP_Pen")
place("ceramic_vase_01", "PH_Vase", (-2.05, 4.77, 0.84), height=0.17, rotz=0.5)
place("stationery_supplies", "PH_Stationery", (-2.62, 3.46, 0.76), width=0.20, rotz=math.radians(80))
place("office_notepads", "PH_Notepads", (-2.24, 2.44, 0.763), width=0.18, rotz=math.radians(-20))
place("round_spectacles", "PH_Spectacles", (-2.20, 3.24, 0.775), width=0.13, rotz=math.radians(35))
place("alarm_clock_01", "PH_AlarmClock", (0.27, 1.40, 0.58), height=0.11, rotz=math.radians(-120))
place("postcard_set_01", "PH_Postcards", (-1.62, 4.80, 0.845), width=0.16, rotz=math.radians(10))
place("book_encyclopedia_set_01", "PH_FloorBooks", (-1.30, 4.62, 0.0), width=0.40, rotz=math.radians(95))
place("wicker_basket_02", "PH_Basket", (1.27, 2.30, 0.0), width=0.42, rotz=math.radians(15))

for o in PH.objects:
    if o.type == 'MESH':
        o.visible_shadow = True
print("placed", sorted(o.name for o in PH.objects if o.type == 'EMPTY'))
