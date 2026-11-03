"""
Scan the JFEL bunch compressor: chicane angle against linearizer (L4H) phase,
recording the bunch after the chicane -- rms length, peak current, energy
spread and how spiky the current profile is.

    python JFEL/Scripts/scan_compression.py
    python JFEL/Scripts/scan_compression.py --angles 0.10 0.14 9 --phases -200 -170 7 --plot scan.png
    python JFEL/Scripts/scan_compression.py --code elegant --csr     # slower, with CSR
    python JFEL/Scripts/scan_compression.py --code cheetah           # no structure wakes

Ocelot by default (~2 s per point), which models the structure wakes; Cheetah
and MAD-X do not, and put full compression at a different chicane angle.
Results go to --out as CSV.
"""

import argparse
import csv
import itertools

import numpy as np

from compression import Compressor


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--angles", nargs=3, type=float, default=[0.10, 0.14, 9],
                        metavar=("MIN", "MAX", "N"), help="chicane dipole angle [rad]")
    parser.add_argument("--phases", nargs=3, type=float, default=[-200.0, -170.0, 7],
                        metavar=("MIN", "MAX", "N"), help="L4H phase [deg]")
    parser.add_argument("--code", default="ocelot")
    parser.add_argument("--csr", action="store_true", help="enable CSR (codes that model it)")
    parser.add_argument("--dir", default="jfel_scan")
    parser.add_argument("--runtime", default="docker")
    parser.add_argument("--out", default="jfel_compression_scan.csv")
    parser.add_argument("--plot", metavar="FILE", help="save peak current and sigma_t maps to FILE")
    args = parser.parse_args()

    angles = np.linspace(args.angles[0], args.angles[1], int(args.angles[2]))
    phases = np.linspace(args.phases[0], args.phases[1], int(args.phases[2]))
    comp = Compressor(args.dir, code=args.code, runtime=args.runtime, csr=True if args.csr else False)
    print(f"nominal: {comp.nominal}")

    rows = []
    print(f"{'angle':>7s} {'L4H phase':>9s} {'sigma_t [fs]':>12s} {'I_peak [A]':>10s} {'spread [%]':>10s} {'spikiness':>9s}")
    for angle, phase in itertools.product(angles, phases):
        m = comp.track(angle=angle, l4h_phase=phase)
        rows.append(m)
        print(f"{angle:7.4f} {phase:9.1f} {m['sigma_t_fs']:12.1f} {m['peak_current_A']:10.0f} "
              f"{m['spread_pct']:10.3f} {m['spikiness']:9.2f}", flush=True)

    with open(args.out, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nwrote {args.out}")

    if args.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        shape = (len(angles), len(phases))
        current = np.array([r["peak_current_A"] for r in rows]).reshape(shape)
        sigma = np.array([r["sigma_t_fs"] for r in rows]).reshape(shape)
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
        extent = [phases[0], phases[-1], angles[0], angles[-1]]
        for ax, data, label in ((axes[0], np.log10(current), "log10 peak current [A]"),
                                (axes[1], np.log10(sigma), "log10 sigma_t [fs]")):
            im = ax.imshow(data, origin="lower", aspect="auto", extent=extent)
            fig.colorbar(im, ax=ax, label=label)
            ax.plot(comp.nominal["l4h_phase"], comp.nominal["angle"], "w+", ms=12, mew=2)
            ax.set_xlabel("L4H phase [deg]")
            ax.set_ylabel("chicane angle [rad]")
        fig.suptitle(f"JFEL compression after the chicane ({args.code}{', CSR' if args.csr else ''}); + nominal")
        fig.tight_layout()
        fig.savefig(args.plot, dpi=120)
        print(f"plot: {args.plot}")


if __name__ == "__main__":
    main()
