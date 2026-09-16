#!/usr/bin/env python3
"""Pre-deletion safety probe. Run BEFORE any rm -rf / del of a suspect path.

Exit code 0  => no live-mutation / lock / reference evidence; still confirm with user.
Exit code 2  => LIVE EVIDENCE FOUND (mutation, lock, or external reference). DO NOT DELETE.
"""
import os, sys, subprocess, time

def inventory(root):
    files = {}
    for dp, _, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                st = os.stat(p); files[p] = st.st_size
            except FileNotFoundError:
                pass
    return files

def lock_test(path):
    try:
        fd = os.open(path, os.O_RDWR)
        os.close(fd); return "unlocked"
    except PermissionError:
        return "LOCKED(process-open)"
    except FileNotFoundError:
        return "vanished"
    except Exception as e:
        return "err:%s" % type(e).__name__

def ref_check(root, ref_dirs):
    hit_files = []
    needle = root.replace("/", "\\") if "\\" not in root else root
    for rd in ref_dirs:
        if not os.path.isdir(rd):
            continue
        try:
            out = subprocess.run(
                ["grep", "-rIl", "-e", needle, rd],
                capture_output=True, text=True, timeout=45)
            for line in out.stdout.splitlines():
                hit_files.append(line)
        except subprocess.TimeoutExpired:
            hit_files.append("TIMEOUT:%s" % rd)
        except Exception:
            pass
    return hit_files

def main():
    if len(sys.argv) < 2:
        print("usage: safe_delete_probe.py <path> [ref_dir1 ref_dir2 ...]"); sys.exit(1)
    root = sys.argv[1]
    ref_dirs = sys.argv[2:] or [os.path.join(os.environ.get("LOCALAPPDATA",""),"hermes\\logs")]
    if not os.path.exists(root):
        print("MISSING path:", root); sys.exit(0)

    snap1 = inventory(root)
    time.sleep(2)                      # window to catch mutation
    snap2 = inventory(root)

    mut = [p for p in set(list(snap1)+list(snap2))
           if snap1.get(p) != snap2.get(p) or p not in snap1 or p not in snap2]
    locks = {p: lock_test(p) for p in snap2}
    refs = ref_check(root, ref_dirs)

    print("=== SAFE-DELETE PROBE:", root, "===")
    print("files now:", len(snap2))
    print("MUTATION (live-write) hits:", mut if mut else "none")
    print("LOCKS:", {k:v for k,v in locks.items() if v!="unlocked"} or "none locked")
    print("EXTERNAL REFS:", refs if refs else "none")

    live = bool(mut) or any(v!="unlocked" for v in locks.values()) or bool(refs)
    print("VERDICT:", "LIVE — DO NOT DELETE" if live else "no live evidence; confirm with user")
    sys.exit(2 if live else 0)

if __name__ == "__main__":
    main()
