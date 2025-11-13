#!/usr/bin/env python3

"""
load_seeds.py — Load all Django fixtures from a folder (recursively, deterministic order).

Usage:
  python load_seeds.py /path/to/seeds \
    [--settings mentoroai.settings] \
    [--database default] \
    [--pattern "*.json"] \
    [--recursive] \
    [--dry-run] \
    [--verbosity 1]

Examples:
  python load_seeds.py ./seeds --settings mentoroai.settings --recursive
  python load_seeds.py ./glossary --pattern "*.json" --dry-run
  python load_seeds.py ./fixtures --database default --verbosity 2

Notes:
- Supports .json, .yaml/.yml, .xml and their .gz variants.
- Loads files in a stable, lexicographic order (so 01_... before 11_...).
- With --dry-run, all database changes are rolled back at the end.
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

# --- Arg parsing ------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load all Django fixtures from a folder.")
    parser.add_argument("folder", type=str, help="Folder containing seed files (fixtures).")
    parser.add_argument("--settings", type=str, default=os.environ.get("DJANGO_SETTINGS_MODULE", "mentoroai.settings"),
                        help="Django settings module (default: %(default)s or env DJANGO_SETTINGS_MODULE).")
    parser.add_argument("--database", type=str, default="default", help="Database alias to use (default: default).")
    parser.add_argument("--pattern", type=str, default="*",
                        help="Glob filter (applied to filenames after extension check), e.g. '*.json'.")
    parser.add_argument("--recursive", action="store_true", help="Search folder recursively.")
    parser.add_argument("--dry-run", action="store_true", help="Do not persist changes (wrap in atomic rollback).")
    parser.add_argument("--verbosity", type=int, choices=[0,1,2,3], default=1, help="Django verbosity (default: 1).")
    return parser.parse_args()


# --- Discovery --------------------------------------------------------------

VALID_EXTS = {
    ".json", ".json.gz",
    ".yaml", ".yml", ".yaml.gz", ".yml.gz",
    ".xml", ".xml.gz",
}

def discover_files(root: Path, recursive: bool, pattern: str) -> List[Path]:
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"[ERROR] Folder not found or not a directory: {root}")
    files: List[Path] = []
    it = root.rglob("*") if recursive else root.glob("*")
    for p in it:
        if not p.is_file():
            continue
        # extension filter
        suffix = p.suffix.lower()
        # handle .gz double suffix
        if suffix == ".gz":
            suffix = (p.stem and "." + p.stem.split(".")[-1].lower()) + ".gz" if "." in p.stem else ".gz"
        if suffix not in VALID_EXTS:
            continue
        # filename pattern
        if not fnmatch.fnmatch(p.name, pattern):
            continue
        files.append(p)
    files.sort(key=lambda x: str(x).lower())
    return files


# --- Django bootstrap -------------------------------------------------------

def bootstrap_django(settings_module: str) -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
    try:
        import django  # noqa
        django.setup()
    except Exception as e:
        raise SystemExit(f"[ERROR] Could not set up Django with settings '{settings_module}': {e}")


# --- Loading ----------------------------------------------------------------

def load_files(files: Iterable[Path], db_alias: str, verbosity: int, dry_run: bool) -> Tuple[int, int]:
    """
    Returns: (ok_count, fail_count)
    """
    from django.core.management import call_command
    from django.db import transaction

    ok = 0
    fail = 0

    def _run():
        nonlocal ok, fail
        for i, path in enumerate(files, start=1):
            rel = str(path)
            print(f"[{i}] loaddata: {rel}")
            try:
                with transaction.atomic(using=db_alias):
                    call_command("loaddata", rel, database=db_alias, verbosity=verbosity)
                ok += 1
            except SystemExit as se:  # call_command may raise SystemExit on certain errors
                fail += 1
                print(f"[ERROR] loaddata failed for {rel}: {se}", file=sys.stderr)
            except Exception as e:
                fail += 1
                print(f"[ERROR] loaddata failed for {rel}: {e}", file=sys.stderr)

    if dry_run:
        from django.db import transaction
        print("[INFO] Dry-run enabled — wrapping all loads in a single atomic transaction and rolling back at the end.")
        with transaction.atomic(using=db_alias):
            _run()
            # Roll back everything intentionally
            transaction.set_rollback(True, using=db_alias)
            print("[INFO] Dry-run complete — all changes rolled back.")
    else:
        _run()

    return ok, fail


# --- Main -------------------------------------------------------------------

def main() -> int:
    args = parse_args()
    root = Path(args.folder).resolve()
    files = discover_files(root, args.recursive, args.pattern)

    if not files:
        print(f"[WARN] No fixtures found in: {root} (pattern={args.pattern}, recursive={args.recursive})")
        return 0

    print(f"[INFO] Found {len(files)} fixture(s) in {root}")
    for p in files:
        print(f"  • {p.relative_to(root)}")

    bootstrap_django(args.settings)

    ok, fail = load_files(files, args.database, args.verbosity, args.dry_run)

    print("\n[SUMMARY]")
    print(f"  OK:    {ok}")
    print(f"  FAIL:  {fail}")
    print(f"  TOTAL: {ok + fail}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
