"""
Track the JFEL linac + bunch compressor (Lattices/jfel_linac_codes.def) in
several codes from the same saved injector beam, and compare the beam at every
screen they have in common -- SIMBA's unit_tests/test_jfel_code_comparison.py
as an example.

    python JFEL/Scripts/compare_codes.py
    python JFEL/Scripts/compare_codes.py --codes elegant ocelot impactx --physics csr
    python JFEL/Scripts/compare_codes.py --physics none --check --plot compare.png

--physics selects the collective effects, the same in every code (a code that
does not model one ignores it, with a warning from SIMBA):
    none   single-particle optics only
    wakes  RF-structure wakefields
    csr    coherent synchrotron radiation in the bends
    lsc    longitudinal space charge (elegant, Ocelot)
    sc3d   3D space charge (Ocelot, ImpactX), which also acts transversely
    all    wakes + CSR + LSC
--check applies the pairwise ceilings from the SIMBA test (measured with its
default settings) and exits 1 if any pair disagrees by more.
"""

import argparse
import itertools
import os
import shutil
import sys

import numpy as np

JFEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
END = "JFEL-FEL-SIM-MARK-01"
SUFFIX = ".openpmd.hdf5"

# label: (function of the beam, compare relatively)
QUANTITIES = {
    "E": (lambda b: 1e-6 * np.mean(b.Particles.cp), True),           # MeV
    "dE": (lambda b: 100 * np.std(b.Particles.cp) / np.mean(b.Particles.cp), False),  # %
    "enx": (lambda b: 1e6 * b.normalized_horizontal_emittance, True),  # um
    "eny": (lambda b: 1e6 * b.normalized_vertical_emittance, True),
    "sx": (lambda b: 1e6 * b.Sx, True),                                 # um
    "sy": (lambda b: 1e6 * b.Sy, True),
    "sz": (lambda b: 1e6 * b.Sz, True),
}
UNITS = {"E": "MeV", "dE": "%", "enx": "um", "eny": "um", "sx": "um", "sy": "um", "sz": "um"}

# Pairwise ceilings from SIMBA's test (E, dE, enx, eny, sx, sy, sz).
TOLERANCES = {
    ("madx", "ocelot"): (0.19, 0.10, 10.0, 18.0, 9.0, 3.0, 17.0),
    ("cheetah", "madx"): (0.05, 0.05, 12.0, 20.0, 14.0, 10.0, 5.0),
    ("cheetah", "ocelot"): (0.19, 0.09, 12.0, 34.0, 14.0, 12.0, 17.0),
    ("cheetah", "elegant"): (0.20, 0.20, 35.0, 16.0, 30.0, 19.0, 24.0),
    ("elegant", "madx"): (0.25, 0.20, 42.0, 14.0, 38.0, 9.0, 22.0),
    ("elegant", "ocelot"): (0.25, 0.20, 42.0, 28.0, 38.0, 8.0, 22.0),
}

PHYSICS = {
    "none": dict(csr_enable=False, lsc_enable=False, wakefield_enable=False),
    "wakes": dict(csr_enable=False, lsc_enable=False, wakefield_enable=True),
    "csr": dict(csr_enable=True, lsc_enable=False, wakefield_enable=False),
    "lsc": dict(csr_enable=False, lsc_enable=True, wakefield_enable=False),
    "sc3d": dict(csr_enable=False, lsc_enable=False, wakefield_enable=False),
    "all": dict(csr_enable=True, lsc_enable=True, wakefield_enable=True),
}
SPACE_CHARGE_3D = {"sc3d"}   # physics settings that switch on 3D space charge


def disagreement(a, b, relative):
    if not relative:
        return abs(a - b)
    mean = 0.5 * (a + b)
    return 100 * abs(a - b) / abs(mean) if mean else 0.0


def track(code, args):
    """Track the Linac line in one code; return {screen: stats}."""
    import simba.Framework as fw
    import simba.Modules.Beams as rbf

    directory = os.path.abspath(os.path.join(args.dir, code))
    runtime = None if str(args.runtime).lower() == "none" else args.runtime
    f = fw.Framework(master_lattice=JFEL + "/", directory=directory, clean=True,
                     verbose=False, container_runtime=runtime)
    if args.libtao:
        f.executables.define_tao_command(location=[args.libtao])
    f.loadSettings("Lattices/jfel_linac_codes.def")
    if args.bc_angle is not None:
        f["bunch_compressor"].set_angle(args.bc_angle)
    f.change_Lattice_Code("Linac", code)
    line = f.latticeObjects["Linac"]
    for flag, value in PHYSICS[args.physics].items():
        setattr(line, flag, value)
    if args.physics in SPACE_CHARGE_3D:
        # SIMBA's Ocelot and ImpactX take 3D space charge from the line's
        # `charge: space_charge_mode`, not from a flag.
        line.file_block.setdefault("charge", {})["space_charge_mode"] = "3d"
    if PHYSICS[args.physics]["csr_enable"]:
        # SIMBA's Ocelot only adds CSR when the line also has a `csr:` block
        # (over the whole line if it gives no start/end); other codes need only
        # csr_enable.
        line.file_block.setdefault("csr", {})
    f.track(files=["Linac"], check_lattice=False)

    stats = {}
    for name in sorted(os.listdir(directory)):
        if not name.endswith(SUFFIX) or name.startswith("jfel_injector"):
            continue
        beam = rbf.load_file(os.path.join(directory, name))
        row = {"s": float(np.atleast_1d(beam.s)[0])}
        row.update({k: float(fn(beam)) for k, (fn, _) in QUANTITIES.items()})
        stats[name[: -len(SUFFIX)]] = row
    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # Bmad is left out by default: LAURA's Bmad export of the VBC chicane
    # (bends + patches) leaves the reference time 54 ps off the bent path, so
    # every cavity after it sees the beam ~58 deg off phase. Add it with
    # --codes ... bmad once that is fixed.
    parser.add_argument("--codes", nargs="+", default=["elegant", "ocelot", "cheetah", "madx", "xsuite", "impactx"])
    parser.add_argument("--physics", choices=PHYSICS, default="none")
    parser.add_argument("--bc-angle", type=float, default=None,
                        help="bunch compressor dipole angle [rad] (default: the lattice's)")
    parser.add_argument("--dir", default="jfel_compare")
    parser.add_argument("--runtime", default="docker",
                        help="container runtime for elegant/Bmad etc.: docker, apptainer or none")
    acc_root = os.environ.get("ACC_ROOT_DIR")
    parser.add_argument("--libtao", default=os.path.join(acc_root, "production", "lib", "libtao.so") if acc_root else None,
                        help="Bmad's libtao.so (default: $ACC_ROOT_DIR/production/lib/libtao.so)")
    parser.add_argument("--check", action="store_true", help="apply the SIMBA test's pairwise ceilings")
    parser.add_argument("--plot", metavar="FILE", help="save the quantities along s to FILE")
    args = parser.parse_args()

    results, failed = {}, {}
    for code in args.codes:
        try:
            results[code] = track(code, args)
        except Exception as exc:  # report and carry on with the other codes
            failed[code] = f"{type(exc).__name__}: {exc}"
            print(f"### {code} failed: {failed[code]}", file=sys.stderr)
    codes = list(results)
    if not codes:
        sys.exit("no code ran")

    common = sorted(set.intersection(*(set(r) for r in results.values())),
                    key=lambda n: results[codes[0]][n]["s"])
    print(f"\nphysics: {args.physics}; {len(common)} screens common to {', '.join(codes)}")
    if failed:
        print("failed: " + "; ".join(f"{c} ({m})" for c, m in failed.items()))

    print(f"\nAt {END}:")
    print("  " + "".join(f"{k + ' [' + UNITS[k] + ']':>14s}" for k in QUANTITIES))
    for code in codes:
        row = results[code].get(END)
        print(f"  {code:8s}" + ("".join(f"{row[k]:14.4g}" for k in QUANTITIES) if row else "  (no output)"))

    print("\nWorst disagreement along the line (% relative; dE in percentage points):")
    print("  " + " " * 18 + "".join(f"{k:>9s}" for k in QUANTITIES))
    violations = []
    for a, b in itertools.combinations(codes, 2):
        worst = {}
        for k, (_, relative) in QUANTITIES.items():
            worst[k] = max(disagreement(results[a][n][k], results[b][n][k], relative) for n in common)
        print(f"  {a + ' vs ' + b:18s}" + "".join(f"{worst[k]:9.2f}" for k in QUANTITIES))
        pair = (a, b) if (a, b) in TOLERANCES else (b, a)
        if args.check and pair in TOLERANCES:
            for k, ceiling in zip(QUANTITIES, TOLERANCES[pair]):
                if worst[k] > ceiling:
                    violations.append(f"{a} vs {b}: {k} {worst[k]:.3f} > {ceiling}")

    if args.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(len(QUANTITIES), 1, sharex=True, figsize=(8, 2 * len(QUANTITIES)))
        for code in codes:
            s = [results[code][n]["s"] for n in common]
            for ax, k in zip(axes, QUANTITIES):
                ax.plot(s, [results[code][n][k] for n in common], marker=".", label=code)
                ax.set_ylabel(f"{k} [{UNITS[k]}]")
        axes[0].legend(ncol=len(codes), fontsize="small")
        axes[-1].set_xlabel("s [m]")
        fig.tight_layout()
        fig.savefig(args.plot, dpi=120)
        print(f"\nplot: {args.plot}")

    if violations:
        print("\nCHECK FAILED:\n  " + "\n  ".join(violations))
        sys.exit(1)
    if args.check:
        print("\ncheck passed")


if __name__ == "__main__":
    main()
