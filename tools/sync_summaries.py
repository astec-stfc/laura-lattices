#!/usr/bin/env python3
"""Keep the combined summary files in sync with the per-element YAML files.

The per-element YAML files under ``<MACHINE>/YAML/`` are the source of truth.
``summary.yaml`` / ``summary.json`` next to them are a *derived* cache: a single
mapping of ``element name -> that element's YAML document``, verbatim. Several
machines load from the cache rather than the directory (see the ``element_list``
line in each ``<MACHINE>/__init__.py``), so a stale cache means edits to the
element files silently have no effect.

Usage
-----
    python tools/sync_summaries.py            # rewrite every summary
    python tools/sync_summaries.py --check    # fail if any summary is stale (CI)
    python tools/sync_summaries.py CLARA JFEL # limit to named machines

Design notes
------------
* The summary is a *verbatim* union, so it is lossless and this script needs
  only PyYAML -- it never imports ``laura``. That is deliberate: CI then cannot
  break because of an unrelated change to the LAURA schema, and the summaries
  cannot drift into an older schema's shape (which is how they got out of sync
  in the first place).
* ``laura.Importers.YAML_Loader.read_YAML_Combined_File`` feeds each value
  straight to ``interpret_YAML_Element``, exactly as ``read_YAML_Element_File``
  does for a single file, so a verbatim union loads identically to loading the
  directory.
* The one exception to "verbatim": an element whose ``controls.schema`` names
  a schema file (see ``tools/collapse_schemas.py``) has that reference
  rewritten to its path relative to ``YAML/`` (e.g.
  ``Magnet/Quadrupole/_schema.yaml``), and the schema itself is embedded under
  the reserved ``_schemas`` key, which ``read_yaml_combined_file`` resolves in
  memory. Otherwise the reference would be looked up relative to the
  summary's directory, not the hardware-type directory it belongs to.
* Output is sorted and formatted deterministically, so ``--check`` can simply
  compare against a regenerated copy.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - dependency guard
    sys.exit("PyYAML is required: pip install pyyaml")

REPO = Path(__file__).resolve().parent.parent
SUMMARY_NAMES = ("summary.yaml", "summary.json")
# Must match laura.importers.yaml_loader.COMBINED_SCHEMAS_KEY.
SCHEMAS_KEY = "_schemas"


def embed_schema(doc: dict, path: Path, yaml_dir: Path, schemas: dict) -> None:
    """Point *doc*'s ``controls.schema`` (relative to *path*) at an entry in
    *schemas* keyed by its path relative to *yaml_dir*, loading it if new."""
    controls = doc.get("controls")
    if not isinstance(controls, dict) or not controls.get("schema"):
        return
    schema_path = (path.parent / controls["schema"]).resolve()
    if not schema_path.is_file():
        raise SystemExit(f"{path}: controls schema {controls['schema']!r} not found")
    key = schema_path.relative_to(yaml_dir.resolve()).as_posix()
    if key not in schemas:
        data = yaml.safe_load(schema_path.read_text()) or {}
        schemas[key] = data.get("variables", data)
    controls["schema"] = key


def element_files(yaml_dir: Path) -> list[Path]:
    """Every per-element YAML file under *yaml_dir*, summaries excluded."""
    return sorted(
        p for p in yaml_dir.rglob("*.yaml")
        if p.name not in SUMMARY_NAMES
    )


def build_summary(yaml_dir: Path) -> tuple[dict, list[str]]:
    """Return ``({name: document}, duplicate_names)`` for one machine.

    Files are visited in sorted order and the last occurrence of a name wins,
    so the result is deterministic even when the lattice data contains
    duplicate ``name:`` values.
    """
    summary: dict[str, dict] = {}
    schemas: dict[str, dict] = {}
    duplicates: list[str] = []
    for path in element_files(yaml_dir):
        try:
            doc = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            raise SystemExit(f"{path}: could not parse: {exc}") from exc
        if not isinstance(doc, dict) or "name" not in doc:
            continue
        embed_schema(doc, path, yaml_dir, schemas)
        name = doc["name"]
        if name in summary:
            duplicates.append(name)
        summary[name] = doc
    if schemas:
        summary[SCHEMAS_KEY] = schemas
    return summary, duplicates


def render(summary: dict, suffix: str) -> str:
    """Serialise *summary* deterministically for the given file suffix."""
    if suffix == ".json":
        return json.dumps(summary, sort_keys=True, indent=1, default=str) + "\n"
    return yaml.safe_dump(
        summary, sort_keys=True, default_flow_style=False, allow_unicode=True
    )


def machine_dirs(only: list[str]) -> list[Path]:
    """Machine directories that already carry at least one summary file."""
    found = []
    for init in sorted(REPO.glob("*/__init__.py")):
        machine = init.parent
        yaml_dir = machine / "YAML"
        if not yaml_dir.is_dir():
            continue
        if not any((yaml_dir / n).exists() for n in SUMMARY_NAMES):
            continue
        if only and machine.name not in only:
            continue
        found.append(machine)
    missing = set(only) - {m.name for m in found}
    if missing:
        raise SystemExit(
            f"no summary files for: {', '.join(sorted(missing))} "
            f"(machines without a summary load the YAML directory directly)"
        )
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("machines", nargs="*", help="limit to these machines")
    ap.add_argument("--check", action="store_true",
                    help="do not write; exit non-zero if any summary is stale")
    args = ap.parse_args()

    stale: list[str] = []
    written: list[str] = []
    for machine in machine_dirs(args.machines):
        yaml_dir = machine / "YAML"
        summary, duplicates = build_summary(yaml_dir)
        n_files = len(element_files(yaml_dir))
        note = ""
        if duplicates:
            note = (f"  [!] {len(duplicates)} duplicate name(s) collapsed, "
                    f"e.g. {min(set(duplicates))}")
        n_elements = len(summary) - (SCHEMAS_KEY in summary)
        print(f"{machine.name:10} {n_files:4} files -> {n_elements:4} elements{note}")

        for name in SUMMARY_NAMES:
            target = yaml_dir / name
            if not target.exists():
                continue
            new = render(summary, target.suffix)
            rel = target.relative_to(REPO)
            if target.read_text() == new:
                print(f"    {rel}: up to date")
                continue
            if args.check:
                stale.append(str(rel))
                print(f"    {rel}: STALE")
            else:
                target.write_text(new)
                written.append(str(rel))
                print(f"    {rel}: rewritten")

    if args.check and stale:
        print(
            "\nThese summary files no longer match the per-element YAML files:\n"
            + "".join(f"  - {s}\n" for s in stale)
            + "\nRegenerate them with:\n"
            "    python tools/sync_summaries.py\n"
            "and commit the result. The per-element YAML files are the source\n"
            "of truth; never hand-edit a summary.",
            file=sys.stderr,
        )
        return 1
    if args.check:
        print("\nAll summary files are in sync with the per-element YAML files.")
    elif written:
        print(f"\nRewrote {len(written)} summary file(s). Commit them alongside "
              "the element changes.")
    else:
        print("\nNothing to do -- every summary was already in sync.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
