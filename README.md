# laura-lattices

Lattice data files for the [LAURA](https://github.com/astec-stfc/laura) accelerator modelling framework.
Each accelerator is stored in its own directory and can be installed as part of the full collection or individually.

**Available machines:**

| Package | Machine | Install individually |
|---|---|---|
| `laura-lattices` (main) | All machines below | `pip install laura-lattices` |
| `laura-lattices-jfel` | JANUS FEL | `pip install laura-lattices-jfel` |

Note: JFEL (JANUS Free-Electron Laser) is not a real accelerator: it is primarily used as an example case for the [JANUS](https://github.com/astec-stfc/janus) digital shadow.

---

## Installation

Requires Python >= 3.10.

### Install all machines

```bash
pip install laura-lattices
```

### Install a single machine

Each machine is also published as its own package. These install into the same
`laura_lattices` namespace so they can be mixed freely:

```bash
pip install laura-lattices-jfel
```

The individual packages carry only their own data, so `MACHINES` and
`get_machine` come from the main package. Install both together with the
matching extra:

```bash
pip install "laura-lattices[jfel]"
```

### Install from source (editable / development)

```bash
git clone https://github.com/astec-stfc/laura-lattices.git
cd laura-lattices
pip install -e .
```

---

## Usage with LAURA

After installing, each machine is available as a Python module under
`laura_lattices`. Every module exposes the paths LAURA needs:

| Attribute | Description |
|---|---|
| `layout` | Path to `layouts.yaml` |
| `section` | Path to `sections.yaml` |
| `element_list` | Path to element data (summary file or YAML directory) |
| `data_files` | Path to the `Data_Files/` directory (if present) |
| `generators` | Path to the `Generators/` directory |
| `lattices` | Path to the `Lattices/` directory |

### Pass the module directly

The simplest approach — pass the machine module as the `lattice` keyword:

```python
from laura_lattices import JFEL
from laura.laura import LAURA

machine = LAURA(lattice=JFEL)
print(machine.elements)   # 438 CLARA elements
print(machine.sections)   # dict of SectionLattice objects
```

### Pass paths explicitly

You can also unpack the paths yourself, which works with any version of LAURA:

```python
from laura_lattices import JFEL
from laura.laura import LAURA

machine = LAURA(
    layout=JFEL.layout,
    section=JFEL.section,
    element_list=JFEL.element_list,
)
```

---

## Building packages

All packages are built with `build` and uploaded with `twine`.

```bash
pip install build twine
```

### Build the main package (all machines)

From the repository root:

```bash
python -m build
```

This produces `dist/laura_lattices-<version>-py3-none-any.whl` and a source
tarball containing every machine's data files.

### Build an individual machine package

Each machine directory contains its own `pyproject.toml`. Build from inside
that directory:

```bash
cd JFEL
python -m build
```

This produces `dist/laura_lattices_jfel-<version>-py3-none-any.whl`.

### Upload to a package index

```bash
# Upload to PyPI (or your private index)
twine upload dist/*

# Upload to a private index
twine upload --repository-url http://your-index/simple/ dist/*
```

---

## Adding a new accelerator

Follow these steps to add a new machine (e.g. `DIAMOND`) to the repository.

### 1. Create the directory structure

```
DIAMOND/
├── layouts.yaml          # Beam path definitions
├── sections.yaml         # Section-to-element mappings
├── Data_Files/           # Field maps, wake files (.hdf5, .gdf, etc.)
├── Generators/           # Generator config (.yaml)
├── Lattices/             # Lattice definition files (.def)
└── YAML/                 # Element definitions (.yaml / .json)
    ├── summary.yaml      # (Optional) combined element file
    ├── Diagnostic/
    │   └── Screen/
    ├── Magnet/
    │   ├── Quadrupole/
    │   └── Dipole/
    └── RFCavity/
        └── RFCavity/
```

The `YAML/` directory can contain either:
- A flat **summary file** (`summary.yaml` or `summary.json`) with all elements, or
- A tree of individual `.yaml` files (one per element) which LAURA will discover recursively.

Where both are present, see **[Keeping the summary files in sync](#keeping-the-summary-files-in-sync)**
below — the summary is a derived cache and must be regenerated whenever an
element file changes.

### 2. Create `__init__.py`

Create `DIAMOND/__init__.py` to expose the standard attributes:

```python
"""DIAMOND lattice data for the LAURA accelerator modelling framework."""
import os as _os

_here = _os.path.dirname(_os.path.abspath(__file__))

layout = _os.path.join(_here, "layouts.yaml")
section = _os.path.join(_here, "sections.yaml")

# Point to a summary file or to the YAML directory:
element_list = _os.path.join(_here, "YAML")
# element_list = _os.path.join(_here, "YAML", "summary.json")

data_files = _os.path.join(_here, "Data_Files")
generators = _os.path.join(_here, "Generators")
lattices = _os.path.join(_here, "Lattices")
```

### 3. Register in the main package

**`pyproject.toml`** — add your machine to `packages`, `package-dir`, and
optionally to `optional-dependencies`:

```toml
[project.optional-dependencies]
diamond = ["laura-lattices-diamond"]

[tool.setuptools]
packages = [
    # ... existing machines ...
    "laura_lattices.DIAMOND",
]

[tool.setuptools.package-dir]
"laura_lattices.DIAMOND" = "DIAMOND"
```

**`laura_lattices/__init__.py`** — add the name to the `MACHINES` list:

```python
MACHINES: List[str] = ["CLARA", "FERMI", "ISIS", "UKXFEL", "UKXFEL_FEL", "DIAMOND"]
```

### 4. Create a per-machine `pyproject.toml`

Create `DIAMOND/pyproject.toml` so the machine can be built and installed
independently:

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "laura-lattices-diamond"
version = "1.0.0"
description = "DIAMOND lattice data for the LAURA accelerator modelling framework"
requires-python = ">= 3.10"

[tool.setuptools]
packages = ["laura_lattices.DIAMOND"]

[tool.setuptools.package-dir]
"laura_lattices.DIAMOND" = "."

[tool.setuptools.package-data]
"laura_lattices.DIAMOND" = [
    "**/*.yaml", "**/*.json", "**/*.hdf5", "**/*.gdf",
    "**/*.txt", "**/*.csv", "**/*.sdds", "**/*.dat",
    "**/*.opal", "**/*.astra", "**/*.T7", "**/*.def",
]
```

### 5. Verify

```bash
# Test the import
python -c "from laura_lattices import DIAMOND; print(DIAMOND.layout)"

# Test with LAURA
python -c "from laura_lattices import DIAMOND; from laura.laura import LAURA; m = LAURA(lattice=DIAMOND); print(len(m.elements), 'elements')"

# Build the individual package
cd DIAMOND
python -m build

# Build the full collection
cd ..
python -m build
```

### Data file types

The package-data configuration automatically includes the following extensions
in any subdirectory:

`.yaml` `.json` `.hdf5` `.gdf` `.txt` `.csv` `.sdds` `.dat` `.opal` `.astra` `.T7` `.def`

If your machine uses a file type not in this list, add the extension to the
`package-data` globs in both the root `pyproject.toml` and your machine's
`pyproject.toml`.

---

## Keeping the summary files in sync

The per-element YAML files under `<MACHINE>/YAML/` are the **source of truth**.
`summary.yaml` and `summary.json` beside them are a *derived cache*: a single
mapping of `element name -> that element's YAML document`, verbatim.

This matters because a machine can load the cache rather than the directory:

| Machine | `element_list` points at |
|---------|--------------------------|
| JFEL | `YAML/` (the directory — no summary to keep in sync) |

For any machine that points at a summary, **editing an element file has no
effect until the summary is regenerated**. Editing a summary by hand is worse:
the change is silently reverted the next time anyone regenerates.

### How to sync

After changing anything under a machine's `YAML/` tree:

```bash
python tools/sync_summaries.py          # rewrite every summary
python tools/sync_summaries.py JFEL     # or just one machine
```

Commit the regenerated summaries **in the same commit** as the element changes,
so the two never diverge in history. To see whether you need to:

```bash
python tools/sync_summaries.py --check  # exits 1 and lists anything stale
```

The script needs only PyYAML — it does not import `laura`, so it cannot break
because of an unrelated change to the LAURA schema, and the summaries cannot
drift into an older schema's shape.

### CI

`.github/workflows/checks.yml` runs `sync_summaries.py --check` on every pull
request and on `main`. If it fails, the fix is always the same: run
`python tools/sync_summaries.py`, commit the result, and push.

The same workflow installs the package and asserts that every path advertised
by every machine module exists on disk, and builds both the collection and each
individual machine wheel.

### Notes

- No machine in this repository currently uses a summary file, so the check
  reports that there is nothing to do and passes. It becomes active the moment
  a `summary.yaml`/`summary.json` is added — that is all it takes to opt a
  machine in. The script discovers whatever already exists and never invents a
  summary for a machine that loads its directory directly.
- Files that are not element documents are ignored, matching what LAURA itself
  does.
- If two element files declare the same `name:`, the summary can only keep one.
  The script visits files in sorted order, keeps the last, and warns — but the
  duplicate is a bug in the lattice data and should be fixed at source.

---

## Repository structure

```
laura-lattices/
├── pyproject.toml              # Main package build config
├── MANIFEST.in                 # Source distribution includes
├── .github/workflows/
│   └── checks.yml              # Summary sync, install and build checks
├── tools/
│   └── sync_summaries.py       # Regenerate/verify the derived summary files
├── laura_lattices/
│   └── __init__.py             # Top-level package with MACHINES list
├── JFEL/
│   ├── __init__.py             # Machine module
│   ├── pyproject.toml          # Individual package build config
│   ├── layouts.yaml
│   ├── sections.yaml
│   ├── Data_Files/
│   ├── Generators/
│   ├── Lattices/
│   └── YAML/
├── .../
│   └── ...
```
