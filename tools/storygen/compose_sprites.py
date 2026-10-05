"""Parse the `layeredimage` definition out of syq.rpyc and composite sprites.

Layered-image draw order follows the declaration order of the groups in the
.rpy file: skin -> feet -> clothes/posture (base) -> face.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image  # noqa: E402

from rpyc_probe import load_rpyc  # noqa: E402
from rpyc_dump import slots_of  # noqa: E402


class Entry(object):
    def __init__(self, attr, image, when, default, line):
        self.attr = attr
        self.image = image
        self.when = when
        self.default = bool(default)
        self.line = line

    def __repr__(self):
        return "<%s %s when=%s>" % (self.attr, self.image, self.when)


def parse_layeredimage(rpyc_path):
    """Returns (name, group_order, groups) where groups is {group: [Entry]}."""
    data, stmts = load_rpyc(rpyc_path)

    li = None
    for st in stmts:
        for node in slots_of(st).get("block", []) or []:
            parsed = slots_of(node).get("parsed")
            if isinstance(parsed, tuple) and len(parsed) == 2:
                cand = parsed[1]
                if type(cand).__name__ == "RawLayeredImage":
                    li = cand
    if li is None:
        raise RuntimeError("no layeredimage found in %s" % rpyc_path)

    sl = slots_of(li)
    name = sl["name"]

    group_order = []
    groups = {}
    for g in sl["children"]:
        gs = slots_of(g)
        gname = gs["group_name"]
        group_order.append(gname)
        entries = []
        for a in gs["children"]:
            sa = slots_of(a)
            img = sa["image"]
            args = img.__dict__.get("_args") or ()
            expr = args[0] if args else None
            if isinstance(expr, str):
                expr = expr.strip()
                if (expr.startswith('"') and expr.endswith('"')) or \
                   (expr.startswith("'") and expr.endswith("'")):
                    expr = expr[1:-1]
            fp = sa.get("final_properties") or {}
            when = fp.get("when")
            if when is not None and not isinstance(when, dict):
                when = slots_of(when)
            entries.append(Entry(sa["name"], expr, when or None,
                                 fp.get("default"), sa.get("linenumber")))
        groups[gname] = entries

    return name, group_order, groups


def when_matches(when, attrs):
    if not when:
        return True
    for key, val in when.items():
        vals = val if isinstance(val, (list, tuple, set)) else [val]
        vals = set(vals)
        if key == "attribute":
            if not (vals & attrs):
                return False
        elif key == "all":
            if not vals <= attrs:
                return False
        elif key == "any":
            if not (vals & attrs):
                return False
        elif key == "not":
            if vals & attrs:
                return False
    return True


def resolve(groups, group_order, requested):
    """Return ({group: Entry}, full_attr_set) for a requested attribute set.

    Returns (None, full) when an explicitly requested attribute cannot be
    satisfied for the active view. A *defaulted* group whose conditional
    entry does not apply simply drops out (e.g. the `feet` group has no
    layers for the uniform/cos poses, which bake the shoes into the base).
    """
    requested = set(a for a in requested if a)
    selected = {}

    # Pass 1: which attribute does each group contribute?
    for gname in group_order:
        entries = groups[gname]
        attrs_in_order = []
        for e in entries:
            if e.attr not in attrs_in_order:
                attrs_in_order.append(e.attr)

        pick, is_explicit = None, False
        for a in attrs_in_order:
            if a in requested:
                pick, is_explicit = a, True
                break
        if pick is None:
            for a in attrs_in_order:
                if any(e.default for e in entries if e.attr == a):
                    pick = a
                    break
        if pick is None:
            for a in attrs_in_order:
                if any(e.when is None for e in entries if e.attr == a):
                    pick = a
                    break
        if pick is not None:
            selected[gname] = (pick, is_explicit)

    # `full` must be the attributes that actually win, not everything that was
    # asked for: one group's request can overwrite another's (e.g. asking for
    # both clothes1_front and clothes2_front), and a stale request would then
    # wrongly satisfy a `when` condition on a layer from the losing view.
    full = set(a for a, _ in selected.values())

    # Pass 2: choose the concrete entry for the selected attribute.
    chosen = {}
    for gname, (attr, is_explicit) in selected.items():
        cands = [e for e in groups[gname] if e.attr == attr]
        pick = None
        for e in cands:
            if e.when is not None and when_matches(e.when, full):
                pick = e
                break
        if pick is None:
            for e in cands:
                if e.when is None:
                    pick = e
                    break
        if pick is None:
            if is_explicit:
                return None, full
            continue
        chosen[gname] = pick
    return chosen, full


def build_name_map(fg_root):
    m = {}
    for dirpath, _dirs, files in os.walk(fg_root):
        for fn in files:
            if fn.lower().endswith(".png"):
                m[os.path.splitext(fn)[0]] = os.path.join(dirpath, fn)
    return m


def composite(chosen, name_map, group_order):
    base = None
    used = []
    for gname in group_order:
        e = chosen.get(gname)
        if e is None:
            continue
        if not e.image or e.image.startswith("Null") or e.image.lower() == "null":
            used.append((gname, e.attr, None))
            continue
        path = name_map.get(e.image)
        if path is None:
            used.append((gname, e.attr, "MISSING:" + e.image))
            continue
        layer = Image.open(path).convert("RGBA")
        if base is None:
            base = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        base = Image.alpha_composite(base, layer)
        used.append((gname, e.attr, e.image))
    return base, used


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--fg", default="原始解包/images_rpa/images/fg")
    ap.add_argument("--rpyc", default="原始解包/scripts_rpa/scripts/roles/syq.rpyc")
    ap.add_argument("--out", default=None)
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()

    name, group_order, groups = parse_layeredimage(args.rpyc)
    print("layeredimage %r groups: %s" % (name, group_order))
    for g in group_order:
        attrs = []
        for e in groups[g]:
            if e.attr not in attrs:
                attrs.append(e.attr)
        print("   %-16s %s" % (g, attrs))

    name_map = build_name_map(args.fg)
    print("layer files: %d" % len(name_map))

    if args.test:
        os.makedirs("tmp_preview", exist_ok=True)
        for tag, req in [
            ("A_front_smile", ["clothes1_front", "smile"]),
            ("B_side_smile", ["clothes1_side", "smile"]),
            ("C_cos_front_smile", ["clothes2_front", "smile"]),
            ("D_cos_front_mask", ["clothes2_front", "mask"]),
            ("E_side_feet_silk", ["clothes1_side", "white_silk", "smile"]),
        ]:
            chosen, full = resolve(groups, group_order, req)
            if chosen is None:
                print(tag, "-> UNSATISFIABLE", req)
                continue
            img, used = composite(chosen, name_map, group_order)
            print(tag, "->", [(g, a, i) for g, a, i in used])
            small = img.copy()
            small.thumbnail((420, 660))
            small.save("tmp_preview/%s.png" % tag)
        return

    if args.out:
        chosen, full = resolve(groups, group_order, ["clothes1_front", "smile"])
        img, used = composite(chosen, name_map, group_order)
        img.save(args.out)


if __name__ == "__main__":
    main()
