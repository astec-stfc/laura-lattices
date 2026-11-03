"""
Optimise the JFEL bunch compressor for a target peak current with a flat
current profile, varying the chicane angle and the linearizer (L4H) phase and
amplitude, then check the result in another code (elegant, with CSR, by
default).

    python JFEL/Scripts/optimise_compression.py --target 1000
    python JFEL/Scripts/optimise_compression.py --target 600 --no-verify

The objective is ((I_peak - I_target) / I_target)^2 + w * (spikiness - 1), where
spikiness is the peak current over that of a flat-top of the same rms length
(1 for a flat-top): the linearizer is what removes the current spike that
the RF curvature otherwise produces. Nelder-Mead in normalised variables, with
Ocelot by default (~2 s per evaluation).

The model has to include what shapes the compression. Ocelot and elegant model
the S- and X-band structure wakes; Cheetah and MAD-X do not, and an optimum
found without wakes (871 A in Cheetah) is fully compressed (~13 kA) once they
are included -- try --code cheetah to see it.
"""

import argparse

import numpy as np
from scipy.optimize import minimize

from compression import Compressor

# Normalisation: (nominal, scale) per variable.
SCALES = {"angle": 0.005, "l4h_phase": 5.0, "l4h_amplitude": 2e6}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", type=float, default=1000.0, help="target peak current [A]")
    parser.add_argument("--weight", type=float, default=0.3, help="weight on spikiness")
    parser.add_argument("--maxiter", type=int, default=60)
    parser.add_argument("--code", default="ocelot", help="code to optimise in")
    parser.add_argument("--dir", default="jfel_optimise")
    parser.add_argument("--runtime", default="docker")
    parser.add_argument("--verify-code", default="elegant")
    parser.add_argument("--no-verify", action="store_true")
    args = parser.parse_args()

    comp = Compressor(f"{args.dir}/{args.code}", code=args.code, runtime=args.runtime, csr=False)
    names = list(SCALES)
    x0 = np.zeros(len(names))
    history = []

    def settings(x):
        return {k: comp.nominal[k] + SCALES[k] * xi for k, xi in zip(names, x)}

    def objective(x):
        m = comp.track(**settings(x))
        value = ((m["peak_current_A"] - args.target) / args.target) ** 2 + args.weight * (m["spikiness"] - 1)
        history.append((value, m))
        print(f"  angle {m['angle']:.5f}  L4H {m['l4h_phase']:7.2f} deg {m['l4h_amplitude'] / 1e6:6.2f} MV/m  "
              f"-> I_peak {m['peak_current_A']:7.0f} A  sigma_t {m['sigma_t_fs']:6.1f} fs  "
              f"spikiness {m['spikiness']:.2f}  f = {value:.4f}", flush=True)
        return value

    print(f"nominal: {comp.nominal}; target {args.target:.0f} A")
    result = minimize(objective, x0, method="Nelder-Mead",
                      options={"maxiter": args.maxiter, "xatol": 0.02, "fatol": 1e-3,
                               "initial_simplex": np.vstack([x0, np.eye(len(x0))])})
    best = min(history, key=lambda h: h[0])[1]
    print(f"\nbest after {len(history)} evaluations ({result.message}):")
    for k in names:
        print(f"  {k:14s} {best[k]:.6g}   (nominal {comp.nominal[k]:.6g})")
    print(f"  I_peak {best['peak_current_A']:.0f} A, sigma_t {best['sigma_t_fs']:.1f} fs, "
          f"spikiness {best['spikiness']:.2f}, spread {best['spread_pct']:.3f}%")

    if not args.no_verify:
        check = Compressor(f"{args.dir}/{args.verify_code}", code=args.verify_code,
                           runtime=args.runtime, csr=True)
        m = check.track(**{k: best[k] for k in names})
        print(f"\n{args.verify_code} (CSR on) at the optimum: I_peak {m['peak_current_A']:.0f} A, "
              f"sigma_t {m['sigma_t_fs']:.1f} fs, spikiness {m['spikiness']:.2f}, spread {m['spread_pct']:.3f}%")


if __name__ == "__main__":
    main()
