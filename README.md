# laura-lattices

Lattice data files for the [LAURA](https://github.com/astec-stfc/laura) accelerator modelling framework.
Each accelerator is stored in its own directory and can be installed as part of the full collection or individually.

**Available machines:**

| Package | Machine | Install individually |
|---|---|---|
| `laura-lattices` (main) | All machines below | `pip install laura-lattices` |

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

## Repository structure

```
laura-lattices/
├── pyproject.toml              # Main package build config
├── MANIFEST.in                 # Source distribution includes
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
