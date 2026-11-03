"""
Run one of the PLASMA example lattices through SIMBA and summarise the beam at
the end of each section.

    python PLASMA/Scripts/run_example.py pwfa_single
    python PLASMA/Scripts/run_example.py pwfa_single --code PWFA=fbpic
    python PLASMA/Scripts/run_example.py lwfa_single --code LWFA=fbpic \
        --set PLA-LWFA-PLASMA-01.n_longitudinal=3250 --set PLA-LWFA-PLASMA-01.n_radial=200
    python PLASMA/Scripts/run_example.py plasma_photocathode \
        --set PLA-PPC-PLASMA-01.n_longitudinal=1500 --set PLA-PPC-PLASMA-01.n_radial=100

``--split`` separates two bunches by energy in the summary (e.g. a driver and a
witness): ``--split 900`` reports particles above and below 900 MeV apart.
Defaults for each lattice are below; README.md lists the reference results.
"""

import argparse
import os

import numpy as np
import yaml

PLASMA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Energy (MeV) separating driver from witness in the summary, per lattice.
SPLIT = {
    "pwfa_single": 500,
    "pwfa_ramps": 500,
    "plasma_photocathode": 900,
}


def summarise(path, split=None):
    import simba.Modules.Beams as rbf

    beam = rbf.load_file(path)
    q = np.asarray(beam.Particles.charge.val)
    energy = beam.cp.val / 1e6
    groups = {"all": np.ones(len(q), bool)}
    if split is not None:
        groups = {f"> {split:g} MeV": energy > split, f"< {split:g} MeV": energy <= split}
    lines = []
    for label, sel in groups.items():
        if sel.sum() < 2:
            lines.append(f"    {label}: {sel.sum()} particles")
            continue
        w = np.abs(q[sel])
        mean = np.average(energy[sel], weights=w)
        spread = np.sqrt(np.cov(energy[sel], aweights=w)) / mean
        # Phase-space (momentum) emittance, as Wake-T and FBPIC report it:
        # x against u_x = p_x / (m c), not against the slope x'.
        x = beam.x.val[sel]
        ux = beam.cpx.val[sel] / 0.51099895e6
        cov = np.cov(np.vstack([x, ux]), aweights=w)
        eps_n = np.sqrt(max(np.linalg.det(cov), 0.0))
        lines.append(
            f"    {label}: {-q[sel].sum() * 1e12:8.2f} pC  <E> {mean:8.1f} MeV  "
            f"spread {spread * 100:5.2f}%  eps_nx {eps_n * 1e6:7.3f} um  "
            f"sigma_x {np.sqrt(cov[0, 0]) * 1e6:7.2f} um"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("lattice", help="Lattices/<lattice>.def, e.g. pwfa_single")
    parser.add_argument("--dir", help="output directory (default: ./<lattice>)")
    parser.add_argument("--code", action="append", default=[], metavar="SECTION=CODE",
                        help="run a section in another code, e.g. PWFA=fbpic")
    parser.add_argument("--set", action="append", default=[], metavar="ELEMENT.PARAM=VALUE",
                        help="override an element parameter, e.g. PLA-PWFA-PLASMA-01.n_radial=100")
    parser.add_argument("--split", type=float, default=None,
                        help="energy (MeV) splitting two bunches in the summary")
    parser.add_argument("--summary-only", action="store_true",
                        help="summarise an existing run in --dir without tracking")
    args = parser.parse_args()

    import simba.Framework as fw

    directory = os.path.abspath(args.dir or args.lattice)
    f = fw.Framework(master_lattice=PLASMA + "/", directory=directory,
                     clean=not args.summary_only, verbose=True)
    f.loadSettings(f"Lattices/{args.lattice}.def")
    for item in args.code:
        section, code = item.split("=", 1)
        f.change_Lattice_Code(section, code)
    changes = {}
    for item in args.set:
        target, value = item.split("=", 1)
        element, param = target.rsplit(".", 1)
        changes.setdefault(element, {})[param] = yaml.safe_load(value)
    if changes:
        f.apply_changes(changes)
    if not args.summary_only:
        f.track()

    split = args.split if args.split is not None else SPLIT.get(args.lattice)
    print(f"\n{args.lattice} ({directory}):")
    for name, lattice in f.latticeObjects.items():
        if name == "generator":
            continue
        path = os.path.join(directory, f"{lattice.end}.openpmd.hdf5")
        print(f"  {name} [{lattice.code}] -> {lattice.end}")
        print(summarise(path, split) if os.path.isfile(path) else "    (no output beam)")


if __name__ == "__main__":
    main()
