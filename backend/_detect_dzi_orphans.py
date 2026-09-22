"""DZI 孤儿检测（只读）——服务器/本地通用，路径按参数传入。

分类输出：
  headless : 有 _files 无 .dzi（生成中断的碎片）
  broken   : 有 .dzi 无 _files（头缺瓦片）
  orphan   : 头+瓦片齐全，但两个数据库全表扫描零引用
  kept     : 有引用，保留
"""
import os
import re
import sqlite3
import sys

dzi_dir = sys.argv[1] if len(sys.argv) > 1 else "/app/data/dzi"
dbs = sys.argv[2:4] if len(sys.argv) > 3 else ["/app/data/calligraphy.db", "/app/data/knowledge.db"]

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def tokens_from_db(path):
    toks = set()
    c = sqlite3.connect(path)
    tabs = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    for t in tabs:
        cols = [r[1] for r in c.execute(f'PRAGMA table_info("{t}")')]
        for col in cols:
            try:
                cur = c.execute(f'SELECT DISTINCT "{col}" FROM "{t}" WHERE "{col}" IS NOT NULL')
                for (v,) in cur:
                    s = str(v)
                    toks.update(UUID_RE.findall(s))
                    if len(s) < 500:
                        toks.add(os.path.splitext(os.path.basename(s))[0])
                        toks.add(s)
            except Exception:
                pass
    c.close()
    return toks


def referenced(head, tokens):
    if head in tokens:
        return True
    # 名字内嵌 uuid 的（photo_{uuid}、{uuid}_thumb）：按 uuid 级匹配，
    # 只要该 uuid 被任何表引用即算被引用（防误杀重建/缩略变体）
    us = UUID_RE.findall(head)
    return any(u in tokens for u in us)


toks = set()
for d in dbs:
    if os.path.exists(d):
        toks |= tokens_from_db(d)
        print(f"tokens from {os.path.basename(d)}: total {len(toks)}")

names = os.listdir(dzi_dir)
heads = {f[:-4] for f in names if f.endswith(".dzi")}
tiles = {n[:-6] for n in names
         if n.endswith("_files") and os.path.isdir(os.path.join(dzi_dir, n))}

headless = sorted(tiles - heads)
broken = sorted(heads - tiles)
paired = heads & tiles
kept = sorted(h for h in paired if referenced(h, toks))
orphans = sorted(h for h in paired if not referenced(h, toks))

print(f"\nheads={len(heads)} tiles={len(tiles)} paired={len(paired)}")
print(f"headless={len(headless)}: {headless}")
print(f"broken_heads={len(broken)}: {broken}")
print(f"orphan_pairs={len(orphans)}")
uploads_dir = os.path.join(os.path.dirname(dzi_dir.rstrip("/")), "uploads")
for h in orphans:
    orig = any(os.path.exists(os.path.join(uploads_dir, h + e))
               for e in (".jpg", ".jpeg", ".png"))
    print(f"  {h}  orig={'Y' if orig else 'N'}")
print(f"kept(referenced)={len(kept)}")
