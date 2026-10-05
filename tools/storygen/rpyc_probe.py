"""Read a Ren'Py .rpyc (RPYC2) file and unpickle its AST with a permissive loader.

We don't have the real renpy package importable, so unknown classes are
materialized as generic attribute bags. That is enough to walk the AST and
pull text out of Say/Translate nodes.
"""

import argparse
import io
import json
import pickle
import struct
import sys
import zlib

RPYC2_HEADER = b"RENPY RPC2"


def read_rpyc_data(f, slot):
    header_data = f.read(1024)
    if header_data[: len(RPYC2_HEADER)] != RPYC2_HEADER:
        if slot != 1:
            return None
        f.seek(0)
        return zlib.decompress(f.read())

    pos = len(RPYC2_HEADER)
    while True:
        header_slot, start, length = struct.unpack("III", header_data[pos:pos + 12])
        if slot == header_slot:
            break
        if header_slot == 0:
            return None
        pos += 12

    f.seek(start)
    return zlib.decompress(f.read(length))


class StateMixin(object):
    def __setstate__(self, state):
        if isinstance(state, dict):
            self.__dict__.update(state)
        elif isinstance(state, tuple) and len(state) == 2 and isinstance(state[0], (dict, type(None))):
            d, slots = state
            if d:
                self.__dict__.update(d)
            if slots:
                self.__dict__["_slots"] = slots
        else:
            self.__dict__["_state"] = state

    def __repr__(self):
        return "<%s %s>" % (type(self).__name__, self.__dict__.get("name", ""))


class Generic(StateMixin):
    """Permissive stand-in for any renpy class found in the pickle."""

    def __new__(cls, *a, **kw):
        return object.__new__(cls)

    def __init__(self, *a, **kw):
        self.__dict__["_args"] = a


_cache = {}


def _base_for(name):
    # Ren'Py's revertable containers are reconstructed with SETITEMS/APPENDS/ADD,
    # so the stand-in must subclass the matching builtin.
    if name.endswith("Dict"):
        return dict
    if name.endswith("List"):
        return list
    if name.endswith("Set") or name == "set":
        return set
    return Generic


class Loader(pickle.Unpickler):
    def find_class(self, module, name):
        name = str(name)
        # Let builtins through untouched.
        if module == "builtins":
            import builtins
            if hasattr(builtins, name):
                return getattr(builtins, name)

        key = (module, name)
        cls = _cache.get(key)
        if cls is None:
            cls = type(name, (_base_for(name), StateMixin), {"__module__": str(module)})
            _cache[key] = cls
        return cls


def load_rpyc(path, verbose=False):
    with open(path, "rb") as f:
        bindata = None
        for slot in (2, 1):
            try:
                bindata = read_rpyc_data(f, slot)
            except Exception:
                bindata = None
            if bindata:
                if verbose:
                    print("  slot %d, %d bytes" % (slot, len(bindata)), file=sys.stderr)
                break
            f.seek(0)
        if not bindata:
            raise RuntimeError("no data slot in %s" % path)
    return Loader(io.BytesIO(bindata)).load()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rpyc")
    ap.add_argument("--dump", action="store_true")
    args = ap.parse_args()

    obj = load_rpyc(args.rpyc, verbose=True)
    data, stmts = obj
    print("data keys:", sorted(data) if hasattr(data, "keys") else type(data))
    print("top-level stmts:", len(stmts))
    for s in stmts[:80]:
        print("   ", type(s).__name__, getattr(s, "name", ""), sorted(s.__dict__)[:8])


if __name__ == "__main__":
    main()
