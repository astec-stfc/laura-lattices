"""
Run one of the SECONDARY example lattices through SIMBA and summarise every
species at the end of each section (and at each extra sampler).

    python SECONDARY/Scripts/run_example.py brems_target
    python SECONDARY/Scripts/run_example.py positron_conversion
    python SECONDARY/Scripts/run_example.py crystal_channelling
    python SECONDARY/Scripts/run_example.py crystal_channelling --set SEC-CRY-CRY-01.entrance_angle=-0.0005

Numbers are per incoming electron. README.md lists the reference results.
"""

import argparse
import os

import numpy as np
import yaml

SECONDARY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E = 1.602176634e-19


def summarise(path, electrons):
    """One line per species: real particles per incoming electron, <E>, x' (median, rms)."""
    import simba.Modules.Beams as rbf

    beam = rbf.load_file(path)
    lines = []
    for species, b in {beam.species: beam, **beam.others}.items():
        n = np.asarray(b.Particles.nmacro.val, dtype=float)
        n = np.broadcast_to(n, (len(b.x),))
        energy = np.asarray(b.energy.val) / 1e6
        xp = np.asarray(b.xp.val) * 1e3
        lines.append(
            f"    {species:9s} {len(b.x):6d} macroparticles  {n.sum() / electrons:7.3f} per e-  "
            f"<E> {np.average(energy, weights=n):8.2f} MeV  "
            f"x' median {np.median(xp):7.3f} mrad, rms {np.sqrt(np.cov(xp, aweights=n)) if len(xp) > 1 else 0:7.3f} mrad"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("lattice", help="Lattices/<lattice>.def, e.g. brems_target")
    parser.add_argument("--dir", help="output directory (default: ./<lattice>)")
    parser.add_argument("--set", action="append", default=[], metavar="ELEMENT.PARAM=VALUE",
                        help="override an element parameter, e.g. SEC-BREMS-TGT-01.length=2e-3")
    args = parser.parse_args()

    import simba.Framework as fw

    directory = os.path.abspath(args.dir or args.lattice)
    f = fw.Framework(master_lattice=SECONDARY + "/", directory=directory, clean=True, verbose=False)
    f.loadSettings(f"Lattices/{args.lattice}.def")
    changes = {}
    for item in args.set:
        target, value = item.split("=", 1)
        element, param = target.rsplit(".", 1)
        changes.setdefault(element, {})[param] = yaml.safe_load(value)
    if changes:
        f.apply_changes(changes)
    f.track()

    lines = [lattice for name, lattice in f.latticeObjects.items() if name != "generator"]
    electrons = None
    print(f"\n{args.lattice} ({directory}):")
    for lattice in lines:
        if electrons is None:  # the incoming beam, for "per e-"
            import simba.Modules.Beams as rbf

            stem = lattice.file_block["input"]["particle_definition"].replace("$master_lattice$", SECONDARY + "/")
            first = rbf.load_file(stem + ".openpmd.hdf5")
            electrons = abs(float(first.Particles.total_charge)) / E
        for name in list((lattice.file_block.get("tracking") or {}).get("samplers") or []) + [lattice.end]:
            path = os.path.join(directory, f"{name}.openpmd.hdf5")
            print(f"  {lattice.objectname} [{lattice.code}] -> {name}")
            print(summarise(path, electrons) if os.path.isfile(path) else "    (no output beam)")
    if args.lattice == "crystal_channelling":
        import simba.Modules.Beams as rbf

        xp = rbf.load_file(os.path.join(directory, f"{lines[-1].end}.openpmd.hdf5")).xp.val * 1e3
        print(f"    channelled (x' within 0.15 mrad of the 0.9 mrad bend): {np.mean(np.abs(xp - 0.9) < 0.15):.3f}")


if __name__ == "__main__":
    main()
