"""
Run one of the JFEL lattices through SIMBA and summarise the beam at the end
of each section: charge, energy, energy spread, emittance, beam size, bunch
length and peak current.

    python JFEL/Scripts/run_example.py jfel_linac_codes
    python JFEL/Scripts/run_example.py jfel_linac_codes --code Linac=ocelot
    python JFEL/Scripts/run_example.py jfel_linac_codes --set JFEL-L4H-LIN-CAV-01.phase=190

Codes run in containers (ASTRA, elegant, OPAL, Genesis, ...) use --runtime
(docker by default); the Python codes run in-process. See README.md.
"""

import argparse
import os

import numpy as np
import yaml

JFEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Energy (MeV) separating two bunches in the summary, per lattice
# (e.g. driver and witness downstream of a plasma stage).
SPLIT = {}


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
        # Phase-space (momentum) emittance: x against u_x = p_x / (m c).
        x = beam.x.val[sel]
        ux = beam.cpx.val[sel] / 0.51099895e6
        cov = np.cov(np.vstack([x, ux]), aweights=w)
        eps_n = np.sqrt(max(np.linalg.det(cov), 0.0))
        t = beam.t.val[sel]
        sigma_t = np.sqrt(np.cov(t, aweights=w))
        # Peak current from a charge-weighted histogram of arrival time.
        counts, edges = np.histogram(t, bins=max(int(np.sqrt(sel.sum())), 10), weights=w)
        peak_current = counts.max() / (edges[1] - edges[0])
        lines.append(
            f"    {label}: {-q[sel].sum() * 1e12:7.1f} pC  <E> {mean:7.1f} MeV  "
            f"spread {spread * 100:5.2f}%  eps_nx {eps_n * 1e6:6.3f} um  "
            f"sigma_x {np.sqrt(cov[0, 0]) * 1e6:7.1f} um  sigma_t {sigma_t * 1e15:7.1f} fs  "
            f"I_peak {peak_current:7.1f} A"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("lattice", help="Lattices/<lattice>.def, e.g. jfel_linac_codes")
    parser.add_argument("--dir", help="output directory (default: ./<lattice>)")
    parser.add_argument("--code", action="append", default=[], metavar="SECTION=CODE",
                        help="run a section in another code, e.g. Linac=ocelot")
    parser.add_argument("--set", action="append", default=[], metavar="ELEMENT.PARAM=VALUE",
                        help="override an element parameter, e.g. JFEL-L4H-LIN-CAV-01.phase=190")
    parser.add_argument("--bc-angle", type=float, default=None,
                        help="bunch compressor dipole angle [rad] (default: the lattice's)")
    parser.add_argument("--runtime", default="docker",
                        help="container runtime for compiled codes: docker, apptainer or none")
    parser.add_argument("--split", type=float, default=None,
                        help="energy (MeV) splitting two bunches in the summary")
    parser.add_argument("--summary-only", action="store_true",
                        help="summarise an existing run in --dir without tracking")
    args = parser.parse_args()

    import simba.Framework as fw

    directory = os.path.abspath(args.dir or args.lattice)
    runtime = None if args.runtime.lower() == "none" else args.runtime
    f = fw.Framework(master_lattice=JFEL + "/", directory=directory,
                     clean=not args.summary_only, verbose=True, container_runtime=runtime)
    f.loadSettings(f"Lattices/{args.lattice}.def")
    if args.bc_angle is not None:
        f["bunch_compressor"].set_angle(args.bc_angle)
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
