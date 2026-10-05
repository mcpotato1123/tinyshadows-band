"""RPA (Ren'Py archive) lister/extractor.

Format per renpy/loader.py:
  RPA-3.0 <index_offset hex16> <key hex8>\n
  index = pickle.loads(zlib.decompress(bytes at index_offset))
  entry = (offset ^ key, dlen ^ key[, start_bytes])
  content = start_bytes + f.read(dlen)      # raw, uncompressed
"""

import argparse
import json
import os
import pickle
import struct
import sys
import zlib


def read_index(path):
    with open(path, "rb") as f:
        header = f.read(40)
        magic = header[:8]
        if magic == b"RPA-3.0 ":
            offset = int(header[8:24], 16)
            key = int(header[25:33], 16)
            f.seek(offset)
            index = pickle.loads(zlib.decompress(f.read()))
            out = {}
            for name, entries in index.items():
                fixed = []
                for ent in entries:
                    if len(ent) == 2:
                        o, d = ent
                        fixed.append((o ^ key, d ^ key, b""))
                    else:
                        o, d, start = ent
                        if not isinstance(start, bytes):
                            start = (start or "").encode("latin-1")
                        fixed.append((o ^ key, d ^ key, start))
                out[name] = fixed
            return magic.decode().strip(), out
        elif magic == b"RPA-2.0 ":
            offset = int(header[8:24], 16)
            f.seek(offset)
            index = pickle.loads(zlib.decompress(f.read()))
            return "RPA-2.0", {k: [(o, d, b"") for (o, d) in v] for k, v in index.items()}
        else:
            raise SystemExit("unsupported archive header: %r" % header[:16])


def read_entry(f, entries):
    parts = []
    for offset, dlen, start in entries:
        f.seek(offset)
        parts.append(start + f.read(dlen))
    return b"".join(parts)


def safe_join(root, name):
    name = name.replace("\\", "/").lstrip("/")
    dest = os.path.normpath(os.path.join(root, name))
    if not dest.startswith(os.path.normpath(root) + os.sep):
        raise SystemExit("refusing path escape: %s" % name)
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("archive")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--json", help="write full listing to this json file")
    ap.add_argument("--extract", help="extract into this directory")
    ap.add_argument("--filter", help="only names containing this substring")
    args = ap.parse_args()

    magic, index = read_index(args.archive)
    print("archive=%s entries=%d" % (magic, len(index)))

    names = sorted(index)
    if args.filter:
        names = [n for n in names if args.filter in n]

    if args.list:
        for n in names:
            print("%12d  %s" % (sum(len(p) for p in [b""]) + len(index[n]), n))

    if args.json:
        rows = []
        for n in sorted(index):
            rows.append({"name": n, "chunks": len(index[n])})
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        print("wrote listing -> %s" % args.json)

    if args.extract:
        total = 0
        with open(args.archive, "rb") as f:
            for i, n in enumerate(names, 1):
                data = read_entry(f, index[n])
                dest = safe_join(args.extract, n)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as out:
                    out.write(data)
                total += len(data)
                if i % 200 == 0:
                    print("  %d/%d files..." % (i, len(names)), flush=True)
        print("extracted %d files, %d bytes -> %s" % (len(names), total, args.extract))


if __name__ == "__main__":
    main()
