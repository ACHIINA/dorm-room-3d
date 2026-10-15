"""リアル版 段階R8: 箱っぽい家具を Poly Haven の実物スキャンに置き換える。r7_spaces.py の後に Blender 内で exec する。
家具は実寸でスキャンされているので縮尺は 1 のまま。置き換えた物は 90_Replaced(非表示・書き出し対象外)へ移す。"""
import bpy, os, math
from mathutils import Vector

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


F = coll("27_Furniture")
OLD = coll("90_Replaced", hide=True)
for o in list(F.objects):
    D.objects.remove(o, do_unlink=True)
_src = {}


def retire(*names):
    for n in names:
        o = D.objects.get(n)
        if o is None:
            continue
        for x in [o] + list(o.children_recursive):
            for c in list(x.users_collection):
                c.objects.unlink(x)
            OLD.objects.link(x)


def retire_prefix(prefix):
    retire(*[o.name for o in D.objects if o.name.startswith(prefix) and o.parent is None and o.name not in OLD.objects])


def source(asset):
    """1 度だけ読み込み、底面中央を原点にした非表示の元データを作る"""
    if asset in _src:
        return _src[asset]
    if D.objects.get(f"SRC_{asset}"):  # 前回の実行で読み込み済み
        _src[asset] = D.objects[f"SRC_{asset}"]
        return _src[asset]
    path = next(os.path.join(MOD, asset, f) for f in os.listdir(os.path.join(MOD, asset)) if f.endswith(".gltf"))
    before = set(D.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in D.objects if o not in before]
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in new if o.type == 'MESH' for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    root = D.objects.new(f"SRC_{asset}", None)
    OLD.objects.link(root)
    root.location = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)
    bpy.context.view_layer.update()
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        OLD.objects.link(o)
        if o.parent is None:
            mw = o.matrix_world.copy()
            o.parent = root
            o.matrix_world = mw
    _src[asset] = root
    print(asset, "size", tuple(round(v, 2) for v in (hi - lo)))
    return root


def place(asset, name, loc, rotz_deg=0.0, scale=1.0):
    """元データのメッシュを共有した複製を置く"""
    src = source(asset)
    e = D.objects.new(name, None)
    F.objects.link(e)

    def rec(o, parent):
        d = o.copy()
        F.objects.link(d)
        d.parent = parent
        d.matrix_parent_inverse = o.matrix_parent_inverse.copy()
        d.matrix_basis = o.matrix_basis.copy()
        d.name = f"{name}_{o.name.split('.')[0]}"
        for ch in o.children:
            rec(ch, d)

    for ch in src.children:
        rec(ch, e)
    # 子は元データの原点(底面中央)からの相対位置で付いているので、Empty の位置がそのまま底面中央になる
    e.location = Vector(loc)
    e.rotation_euler.z = math.radians(rotz_deg)
    e.scale = (scale, scale, scale)
    return e


# ---- 315 号室: 机の椅子(学校の椅子)とベッドの間のサイドテーブル ----
retire("R315_Chair0", "R315_Chair1")
place("SchoolChair_01", "F315_Chair0", (2.27, 1.40, 0.0), 180)
place("SchoolChair_01", "F315_Chair1", (4.66, 1.42, 0.0), 175)
place("side_table_01", "F315_SideTable", (3.00, 3.80, 0.0), 90)

# ---- ラウンジ: ダイニングチェア・収納棚・テレビ台・クッション ----
retire("Lounge_DiningChair0", "Lounge_DiningChair1", "Lounge_DiningChair2", "Lounge_DiningChair3")
for i, (x, y, r) in enumerate(((2.40, -4.85, 180), (2.90, -4.85, 180), (2.40, -6.05, 0), (2.90, -6.05, 0))):
    place("SchoolChair_01", f"FLounge_Chair{i}", (x, y, 0.0), r)
retire("Lounge_Shelf")
retire_prefix("Lounge_Shelf_Board")
retire_prefix("Lounge_Game")
place("wooden_display_shelves_01", "FLounge_Shelves", (6.68, -2.27, 0.0), 0)  # 両面から使える格子棚
retire("Lounge_TV_Stand")
place("modern_wooden_cabinet", "FLounge_TVCabinet", (6.66, -4.02, 0.0), 90)  # 棚と重ならない位置
retire("Lounge_Sofa_Pillow0", "Lounge_Sofa_Pillow1")
place("throw_pillows_01", "FLounge_Pillows", (3.88, -4.30, 0.42), -90)
# 格子棚の中身: 百科事典の束、花瓶、ボードゲームの箱
exec(open(os.path.join(ROOT, "scripts", "helpers.py")).read())


def copy_obj_tree(src_name, new_name, loc, rotz_deg=0.0, scale=1.0):
    src = D.objects.get(src_name)
    if src is None:
        return None
    e = D.objects.new(new_name, None)
    F.objects.link(e)

    def rec(o, parent):
        d = o.copy()
        F.objects.link(d)
        d.parent = parent
        d.matrix_parent_inverse = o.matrix_parent_inverse.copy()
        d.matrix_basis = o.matrix_basis.copy()
        d.name = f"{new_name}_{o.name.split('.')[0]}"
        for ch in o.children:
            rec(ch, d)

    rec(src, e)
    e.children[0].location = (0, 0, 0)
    e.location = loc
    e.rotation_euler.z = math.radians(rotz_deg)
    e.scale = (scale, scale, scale)
    return e


sx, sy = 6.68, -2.27
rows = (0.445, 0.815, 1.185)   # 各段の棚板の高さ
cols = (-0.35, 0.0, 0.35)
copy_obj_tree("PH_FloorBooks", "FLounge_ShelfBooks", (sx, sy + cols[0], rows[2]), 90, 0.62)
copy_obj_tree("PH_Vase", "FLounge_ShelfVase", (sx, sy + cols[1], rows[2]), 20, 1.0)
copy_obj_tree("PH_SillPlant1", "FLounge_ShelfPlant", (sx, sy + cols[2], rows[1]), 0, 1.0)
for i, (c, r, h) in enumerate(((0, 1, 0.06), (0, 1, 0.05), (1, 0, 0.07), (1, 0, 0.05), (1, 0, 0.06), (2, 0, 0.08))):
    z = rows[r] + 0.004 + sum(hh for (cc, rr, hh) in ((0, 1, 0.06), (0, 1, 0.05), (1, 0, 0.07), (1, 0, 0.05), (1, 0, 0.06), (2, 0, 0.08))[:i] if cc == c and rr == r)
    w = 0.27 - 0.02 * (i % 3)
    box(f"FLounge_Game{i}", (-0.15, -w / 2, 0), (0.15, w / 2, h), F, book_mat(i), 0.003, at=(sx, sy + cols[c], z), rot=(0, 0, math.radians(3 * (i % 3) - 3)))
print("furniture ok", len(F.objects))
