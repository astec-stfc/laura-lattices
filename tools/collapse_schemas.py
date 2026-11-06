#!/usr/bin/env python3
"""Collapse a machine's repeated ``controls`` blocks into shared schema files.

Elements of the same hardware type (every Quadrupole, every BPM, ...) carry
near-identical ``controls.variables`` blocks that differ only in the element's
own name inside each ``identifier``. LAURA can load these from a shared
template instead::

    controls:
      schema: _schema.yaml            # {name}-templated variables, per directory
      identifier_pattern: <prefix>    # only when the PVs are not under the
                                      # element's own name
      variables: {...}                # only the genuine per-element overrides

This script drives LAURA's own tooling to produce that form for a machine:

1. Copy the machine's per-element YAML tree into a staging directory, and
   make implicit defaults explicit where needed: if another element in the
   same directory spells out a variable field this element leaves to LAURA's
   default (e.g. ``read_only``), write in the value LAURA loads for it. The
   extractor compares raw YAML, so it otherwise sees "field missing" -- which
   no override can express -- rather than "field overridden to its default",
   and refuses to share that variable at all.
2. ``laura.utils.controls_schema_extract`` writes a ``_schema.yaml`` (plus
   ``_schema_<n>.yaml`` for a second interface shape) per hardware-type
   directory and rewrites each element down to its overrides.
3. ``laura.utils.controls_identifier_pattern`` folds per-variable
   ``identifier`` overrides into a single ``identifier_pattern`` where safe.
4. Every element is loaded through LAURA from both the original and the
   staged file, and the two models are compared. An element that does not
   load identically keeps its original file (so the run can never change what
   LAURA sees), and is reported. So does one that ended up with no schema to
   reference, so step 1 never rewrites a file for nothing.
5. The verified files and the schema files they use are written out.

Usage
-----
    python tools/collapse_schemas.py CLARA                # rewrite CLARA/YAML in place
    python tools/collapse_schemas.py CLARA --dry-run      # report only
    python tools/collapse_schemas.py CLARA -o out/CLARA   # write a collapsed copy
    python tools/collapse_schemas.py path/to/YAML         # any element tree
    python tools/collapse_schemas.py CLARA --overwrite-schemas
                                       # regenerate existing schemas from scratch

By default, elements that already reference a schema are left as they are,
and the run stops rather than replace an existing ``_schema*.yaml``. With
``--overwrite-schemas`` those elements are first expanded back to full
``controls`` blocks (checked to load identically), the old schema files are
dropped, and the whole tree is collapsed again.

Machines that load from ``summary.yaml`` / ``summary.json`` need those
regenerated afterwards (``python tools/sync_summaries.py``), which embeds the
schemas so the summary stays self-contained.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import logging
import shutil
import sys
import tempfile
import warnings
from collections import Counter
from pathlib import Path

# LAURA's own utilities still import through its legacy, deprecated paths.
warnings.filterwarnings("ignore", category=FutureWarning, module="laura")

try:
    import yaml
    from laura.importers.yaml_loader import read_yaml_element_file, resolve_controls_schema
    from laura.utils.controls_identifier_pattern import collapse_identifier_patterns
    from laura.utils.controls_schema_extract import extract_schemas
except ImportError as exc:  # pragma: no cover - dependency guard
    sys.exit(f"{exc}\nThis script needs a LAURA with controls-schema support "
             "(laura.utils.controls_schema_extract).")

REPO = Path(__file__).resolve().parent.parent
SUMMARY_NAMES = ("summary.yaml", "summary.json")


def resolve_yaml_dir(target: str) -> Path:
    """``CLARA`` -> ``<repo>/CLARA/YAML``; a directory path is used as-is."""
    machine_yaml = REPO / target / "YAML"
    if machine_yaml.is_dir():
        return machine_yaml
    path = Path(target)
    if path.is_dir():
        return path.resolve()
    raise SystemExit(f"{target!r} is neither a machine name nor a directory")


def tree_files(root: Path) -> list[Path]:
    """Every file under *root* that belongs in the element tree (relative)."""
    return sorted(
        p.relative_to(root) for p in root.rglob("*")
        if p.is_file() and p.name not in SUMMARY_NAMES
    )


def is_schema_file(rel: Path) -> bool:
    return rel.name.startswith("_") and rel.suffix in (".yaml", ".yml")


def quiet(fn, *args, **kwargs):
    """Call *fn* with its stdout swallowed (LAURA prints import chatter)."""
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def load_comparable(path: Path):
    """The element at *path* as LAURA sees it, minus how its controls were
    spelled -- i.e. what must not change. ``None`` if it does not load."""
    ele = quiet(read_yaml_element_file, str(path))
    if ele is None:
        return None
    dump = ele.model_dump()
    controls = dump.get("controls")
    if isinstance(controls, dict):
        controls.pop("schema", None)
        controls.pop("identifier_pattern", None)
    return dump


def inline_variables(data) -> dict | None:
    """An element's inline ``controls.variables``, or ``None`` if it has none
    or already references a schema."""
    if not isinstance(data, dict) or "hardware_type" not in data:
        return None
    controls = data.get("controls")
    if not isinstance(controls, dict) or controls.get("schema"):
        return None
    return controls.get("variables") or None


def fill_implicit_defaults(staging: Path) -> int:
    """Write in, per directory, any variable field an element leaves implicit
    but a sibling spells out, using the value LAURA loads for it. Returns the
    number of element files changed."""
    by_dir: dict[Path, list[tuple[Path, dict]]] = {}
    for rel in tree_files(staging):
        if is_schema_file(rel) or rel.suffix not in (".yaml", ".yml"):
            continue
        data = yaml.safe_load((staging / rel).read_text())
        if inline_variables(data):
            by_dir.setdefault(rel.parent, []).append((rel, data))

    changed = 0
    for members in by_dir.values():
        if len(members) < 2:
            continue
        fields: dict[str, set] = {}
        for _rel, data in members:
            for key, var in inline_variables(data).items():
                if isinstance(var, dict):
                    fields.setdefault(key, set()).update(var)
        for rel, data in members:
            loaded = None
            dirty = False
            for key, var in inline_variables(data).items():
                missing = fields.get(key, set()) - set(var) if isinstance(var, dict) else set()
                if not missing:
                    continue
                if loaded is None:
                    ele = quiet(read_yaml_element_file, str(staging / rel))
                    if ele is None or ele.controls is None:
                        break
                    loaded = ele.controls.variables
                full = loaded[key].unstripped_dump() if key in loaded else {}
                for field in missing & set(full):
                    var[field] = full[field]
                    dirty = True
            if dirty:
                (staging / rel).write_text(
                    yaml.safe_dump(data, sort_keys=True, default_flow_style=False)
                )
                changed += 1
    return changed


def replace_in_strings(value, old: str, new: str):
    """Replace *old* with *new* in every string inside *value*."""
    if isinstance(value, str):
        return value.replace(old, new)
    if isinstance(value, dict):
        return {k: replace_in_strings(v, old, new) for k, v in value.items()}
    if isinstance(value, list):
        return [replace_in_strings(v, old, new) for v in value]
    return value


def contains_string(value, needle: str) -> bool:
    if isinstance(value, str):
        return needle in value
    if isinstance(value, dict):
        return any(contains_string(v, needle) for v in value.values())
    if isinstance(value, list):
        return any(contains_string(v, needle) for v in value)
    return False


def foreign_prefix(data: dict) -> str | None:
    """The most common PV device prefix (``PREFIX:...``) among the
    ``identifier``s of an element whose PVs are *not* under its own name --
    e.g. a cavity driven through its RF controller -- else ``None``.

    An element can address more than one device (a cavity also has
    modulator and related PVs); ``identifier_pattern`` can only stand for one,
    so the dominant one is used and the rest stay literal, becoming
    per-element overrides (see :func:`hoist_single_owner_fields`)."""
    variables = inline_variables(data)
    name = data.get("name")
    if not variables or not name or contains_string(variables, name):
        return None
    counts = Counter(
        var["identifier"].split(":", 1)[0]
        for var in variables.values()
        if isinstance(var, dict) and isinstance(var.get("identifier"), str)
        and ":" in var["identifier"]
    ).most_common(2)
    if not counts or (len(counts) == 2 and counts[0][1] == counts[1][1]):
        return None  # no prefix, or no single dominant one
    return counts[0][0] or None


def mask_foreign_prefixes(staging: Path) -> dict[Path, str]:
    """Rewrite each element's foreign PV prefix to its own name, so LAURA's
    extractor (which only templates an element's own name) turns it into
    ``{name}``. Returns ``{relative path: prefix}`` for
    :func:`unmask_foreign_prefixes` to turn into ``identifier_pattern``."""
    masked = {}
    for rel in tree_files(staging):
        if is_schema_file(rel) or rel.suffix not in (".yaml", ".yml"):
            continue
        data = yaml.safe_load((staging / rel).read_text())
        prefix = foreign_prefix(data) if isinstance(data, dict) else None
        if prefix is None:
            continue
        controls = data["controls"]
        controls["variables"] = replace_in_strings(controls["variables"], prefix, data["name"])
        (staging / rel).write_text(
            yaml.safe_dump(data, sort_keys=True, default_flow_style=False)
        )
        masked[rel] = prefix
    return masked


def unmask_foreign_prefixes(staging: Path, masked: dict[Path, str]) -> None:
    """Undo :func:`mask_foreign_prefixes` after extraction: an element that
    now references a schema gets ``identifier_pattern: <prefix>`` (so the
    schema's ``{name}`` resolves to its PVs) and any overrides it kept inline
    get their literal prefix back. Elements that ended up without a schema are
    restored to their original file by :func:`verify`."""
    for rel, prefix in masked.items():
        data = yaml.safe_load((staging / rel).read_text())
        controls = data["controls"]
        if not controls.get("schema"):
            continue
        controls["identifier_pattern"] = prefix
        if controls.get("variables"):
            controls["variables"] = replace_in_strings(
                controls["variables"], data["name"], prefix
            )
        (staging / rel).write_text(
            yaml.safe_dump(data, sort_keys=True, default_flow_style=False)
        )


def contains_placeholder(value) -> bool:
    return contains_string(value, "{name}")


def hoist_single_owner_fields(source: Path, staging: Path) -> int:
    """Move schema values that really belong to one element back into it.

    LAURA's extractor puts the most common value of each field in the schema
    even when every element's value differs -- e.g. a cavity's modulator PV,
    which ``identifier_pattern`` cannot also stand for. That leaves one
    element's literal value in the schema and an override in every *other*
    element. Where a non-templated schema value is overridden by all members
    but one, drop it from the schema and give that one an explicit override,
    so the schema only holds what is genuinely shared. Only schema files
    generated in this run (absent from *source*) are touched. Returns the
    number of fields moved."""
    members: dict[Path, list[tuple[Path, dict]]] = {}
    for rel in tree_files(staging):
        if is_schema_file(rel) or rel.suffix not in (".yaml", ".yml"):
            continue
        data = yaml.safe_load((staging / rel).read_text())
        controls = data.get("controls") if isinstance(data, dict) else None
        if isinstance(controls, dict) and controls.get("schema"):
            schema_rel = rel.parent / controls["schema"]
            if not (source / schema_rel).exists():
                members.setdefault(schema_rel, []).append((rel, data))

    moved = 0
    for schema_rel, group in members.items():
        if len(group) < 2:
            continue
        schema_doc = yaml.safe_load((staging / schema_rel).read_text())
        schema_vars = schema_doc.get("variables", schema_doc)
        dirty = set()
        for var_key, var_def in schema_vars.items():
            if not isinstance(var_def, dict):
                continue
            for field in list(var_def):
                value = var_def[field]
                if contains_placeholder(value):
                    continue
                owners = [
                    (rel, data) for rel, data in group
                    if field not in ((data["controls"].get("variables") or {})
                                     .get(var_key) or {})
                ]
                if len(owners) != 1:
                    continue
                rel, data = owners[0]
                overrides = data["controls"].setdefault("variables", {})
                overrides.setdefault(var_key, {})[field] = value
                del var_def[field]
                dirty.add(rel)
                moved += 1
        if not dirty:
            continue
        (staging / schema_rel).write_text(
            yaml.safe_dump(schema_doc, sort_keys=True, default_flow_style=False)
        )
        for rel, data in group:
            if rel in dirty:
                (staging / rel).write_text(
                    yaml.safe_dump(data, sort_keys=True, default_flow_style=False)
                )
    return moved


def stage(source: Path, staging: Path) -> tuple[dict, dict]:
    """Run LAURA's schema extraction on a copy of *source* in *staging*.

    Returns LAURA's extraction report and ``{relative path: identifier
    pattern}`` for every element given one."""
    for rel in tree_files(source):
        (staging / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / rel, staging / rel)
    fill_implicit_defaults(staging)
    masked = mask_foreign_prefixes(staging)
    report = quiet(extract_schemas, str(staging), apply=True)
    unmask_foreign_prefixes(staging, masked)
    patterns = quiet(collapse_identifier_patterns, str(staging), apply=True)
    hoist_single_owner_fields(source, staging)
    found ={rel.as_posix(): prefix for rel, prefix in masked.items()}
    found.update({Path(rel).as_posix(): pattern for rel, _name, pattern, _keys in patterns})
    return report, found


def verify(source: Path, staging: Path) -> tuple[list[Path], list[Path], list[Path]]:
    """Compare every rewritten element against its original through LAURA.

    Returns ``(accepted, rejected, unloadable)`` relative element paths.
    Rejected elements are restored to their original file in *staging*.
    """
    accepted, rejected, unloadable = [], [], []
    for rel in tree_files(staging):
        if is_schema_file(rel) or rel.suffix not in (".yaml", ".yml"):
            continue
        original, staged = source / rel, staging / rel
        if original.read_bytes() == staged.read_bytes():
            continue
        controls = (yaml.safe_load(staged.read_text()) or {}).get("controls") or {}
        if not controls.get("schema"):
            # Only touched by fill_implicit_defaults, and nothing came of it.
            shutil.copy2(original, staged)
            continue
        before = load_comparable(original)
        if before is None:
            # LAURA can't load the original either, so there's nothing to
            # verify against -- leave it exactly as it was.
            unloadable.append(rel)
            shutil.copy2(original, staged)
            continue
        try:
            after = load_comparable(staged)
        except Exception:  # noqa: BLE001 - any failure means "not equivalent"
            after = None
        if after == before:
            accepted.append(rel)
        else:
            rejected.append(rel)
            shutil.copy2(original, staged)
    return accepted, rejected, unloadable


def uncollapsed_dirs(staging: Path) -> dict[Path, int]:
    """Directories still holding 2+ elements with inline controls, with counts.
    LAURA's extractor reports nothing for a directory where no variable at all
    could be shared, so without this they would be skipped silently."""
    counts: dict[Path, int] = {}
    for rel in tree_files(staging):
        if is_schema_file(rel) or rel.suffix not in (".yaml", ".yml"):
            continue
        if inline_variables(yaml.safe_load((staging / rel).read_text())):
            counts[rel.parent] = counts.get(rel.parent, 0) + 1
    return {d: n for d, n in sorted(counts.items()) if n > 1}


def used_schemas(staging: Path, elements: list[Path]) -> set[Path]:
    """Schema files (relative) referenced by *elements*."""
    used = set()
    for rel in elements:
        data = yaml.safe_load((staging / rel).read_text())
        schema = (data.get("controls") or {}).get("schema")
        if schema:
            used.add(rel.parent / schema)
    return used


def expand_tree(source: Path, baseline: Path) -> int:
    """Copy *source* to *baseline* with every existing schema reference
    expanded back to inline ``controls.variables`` (via LAURA's own
    ``resolve_controls_schema``) and the old schema files left out, so the
    tree can be collapsed again from scratch. Each expanded element is checked
    to load identically to its original. Returns the number expanded."""
    expanded = 0
    for rel in tree_files(source):
        if is_schema_file(rel):
            continue
        (baseline / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / rel, baseline / rel)
        if rel.suffix not in (".yaml", ".yml"):
            continue
        data = yaml.safe_load((source / rel).read_text())
        controls = data.get("controls") if isinstance(data, dict) else None
        if not isinstance(controls, dict) or not controls.get("schema"):
            continue
        resolved = resolve_controls_schema(
            controls, data.get("name", ""), str((source / rel).parent)
        )
        resolved.pop("schema", None)
        resolved.pop("identifier_pattern", None)
        data["controls"] = resolved
        (baseline / rel).write_text(
            yaml.safe_dump(data, sort_keys=True, default_flow_style=False)
        )
        if load_comparable(baseline / rel) != load_comparable(source / rel):
            raise SystemExit(f"{rel}: expanding its controls schema changed how "
                             "LAURA loads it; not overwriting schemas.")
        expanded += 1
    return expanded


def check_existing_schemas(source: Path, staging: Path) -> None:
    """``extract_schemas`` names its output ``_schema.yaml``; refuse to run if
    that would clobber a schema the tree already had."""
    clobbered = [
        rel for rel in tree_files(source)
        if is_schema_file(rel)
        and (source / rel).read_bytes() != (staging / rel).read_bytes()
    ]
    if clobbered:
        raise SystemExit(
            "Refusing to overwrite existing schema file(s):\n"
            + "".join(f"  - {rel}\n" for rel in clobbered)
            + "Re-run with --overwrite-schemas to regenerate them from scratch."
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target", help="machine name (e.g. CLARA) or element YAML directory")
    ap.add_argument("-o", "--output", type=Path,
                    help="write the collapsed tree here instead of in place")
    ap.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    ap.add_argument("-v", "--verbose", action="store_true", help="list every file")
    ap.add_argument("--overwrite-schemas", action="store_true",
                    help="expand elements that already use a schema and regenerate "
                         "every schema from scratch, replacing the existing "
                         "_schema*.yaml files (default: leave them alone)")
    args = ap.parse_args()

    # LAURA logs a line per element it can't parse; we report those ourselves.
    logging.getLogger("laura").setLevel(logging.CRITICAL)

    source = resolve_yaml_dir(args.target)
    dest = args.output.resolve() if args.output else source

    with tempfile.TemporaryDirectory(prefix="collapse_schemas_") as tmp:
        baseline, staging = source, Path(tmp) / "staging"
        if args.overwrite_schemas:
            baseline = Path(tmp) / "baseline"
            n = expand_tree(source, baseline)
            print(f"Expanded {n} element(s) from their existing schemas.")
        report, patterns = stage(baseline, staging)
        check_existing_schemas(baseline, staging)
        accepted, rejected, unloadable = verify(baseline, staging)
        schemas = used_schemas(staging, accepted)

        n_before = sum(before for _, _, before in report["files_rewritten"])
        n_after = sum(
            after for path, after, _ in report["files_rewritten"]
            if Path(path).relative_to(staging) in accepted
        ) + sum(
            before for path, _, before in report["files_rewritten"]
            if Path(path).relative_to(staging) not in accepted
        )
        print(f"{source}")
        print(f"  schema files:          {len(schemas)}")
        print(f"  elements collapsed:    {len(accepted)}")
        print(f"  identifier_pattern:    "
              f"{sum(1 for r in accepted if r.as_posix() in patterns)}")
        print(f"  variable entries:      {n_before} -> {n_after} inline")
        for path, n_elements, shared, outliers in report["schema_files"]:
            rel = Path(path).relative_to(staging)
            if rel not in schemas:
                continue
            print(f"    {rel}: {n_elements} elements, {len(shared)} shared keys"
                  + (f", kept inline: {outliers}" if outliers else ""))
        if args.verbose:
            for rel in accepted:
                pat = patterns.get(rel.as_posix())
                print(f"      {rel}" + (f"  [identifier_pattern={pat}]" if pat else ""))
        if rejected:
            print(f"  [!] {len(rejected)} element(s) did not reload identically "
                  "and were left untouched:")
            for rel in rejected:
                print(f"      {rel}")
        if unloadable:
            print(f"  [!] {len(unloadable)} element(s) LAURA cannot load "
                  "were left untouched:")
            for rel in unloadable:
                print(f"      {rel}")
        leftover = uncollapsed_dirs(staging)
        if leftover:
            print(f"  [!] {len(leftover)} director(ies) still have inline controls "
                  "(no variable could be shared safely):")
            for rel, n in leftover.items():
                print(f"      {rel}: {n} elements")

        if args.dry_run:
            print("\nDry run: nothing written.")
            return 0

        # Schema files to keep: the ones just generated and used, plus any
        # pre-existing ones still in the baseline (none with --overwrite-schemas).
        keep = [rel for rel in tree_files(staging)
                if not is_schema_file(rel) or rel in schemas
                or (baseline / rel).exists()]
        if dest != source:
            # A full, self-contained copy: everything, collapsed where verified.
            to_write, to_delete = keep, []
        else:
            to_write = [rel for rel in keep
                        if not (source / rel).exists()
                        or (source / rel).read_bytes() != (staging / rel).read_bytes()]
            to_delete = [rel for rel in tree_files(source)
                         if is_schema_file(rel) and rel not in keep]
        for rel in to_write:
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staging / rel, dest / rel)
        for rel in to_delete:
            (dest / rel).unlink()
        print(f"\nWrote {len(to_write)} file(s) to {dest}"
              + (f", removed {len(to_delete)} unused schema file(s)" if to_delete else ""))

    if dest == source and any((source / n).exists() for n in SUMMARY_NAMES):
        print("This tree has summary files; regenerate them with:\n"
              "    python tools/sync_summaries.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
