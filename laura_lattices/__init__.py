"""
laura-lattices: Lattice data files for the LAURA accelerator modelling framework.

Usage::

    from laura_lattices import JFEL
    from laura.laura import LAURA

    # Use path attributes directly
    lattice = LAURA(
        layout=JFEL.layout,
        section=JFEL.section,
        element_list=JFEL.element_list,
    )

    # Or pass the module directly (requires laura >= 2.0)
    lattice = LAURA(lattice=JFEL)

Available machines: JFEL

Each machine module exposes:
    - layout: str       — path to layouts.yaml
    - section: str      — path to sections.yaml
    - element_list: str — path to element data (summary file or YAML directory)
    - data_files: str   — path to Data_Files directory (if present)
    - generators: str   — path to Generators directory
    - lattices: str     — path to Lattices directory
"""

from typing import List
import importlib

MACHINES: List[str] = ["JFEL"]


def _lazy_import_machine(name: str):
    """Lazily import a machine module by name.

    Tries multiple import paths to handle different installation scenarios:
    - As a subpackage: laura_lattices.JFEL
    - As a root-level module: JFEL (for PYTHONPATH-based development)
    """
    # First try as subpackage (installed via pip)
    try:
        return importlib.import_module(f"laura_lattices.{name}")
    except ImportError:
        pass

    # Fall back to root-level import (for development with PYTHONPATH)
    try:
        return importlib.import_module(name)
    except ImportError:
        raise ImportError(
            f"Cannot import machine '{name}'. Install with: "
            f"pip install laura-lattices-{name.lower()}"
        )


# Lazy-load machine modules on first access
def __getattr__(name: str):
    """Lazily import machine modules when accessed as attributes."""
    if name in MACHINES:
        return _lazy_import_machine(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def get_machine(name: str):
    """Import and return a machine module by name.

    Args:
        name: One of the entries in ``MACHINES``.

    Returns:
        The machine module with ``layout``, ``section``, and ``element_list`` attributes.
    """
    if name not in MACHINES:
        raise ValueError(f"Unknown machine '{name}'. Available: {MACHINES}")
    return _lazy_import_machine(name)


__all__ = ["JFEL", "get_machine", "MACHINES"]
