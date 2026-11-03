"""
Start-to-end FEL for JFEL (Lattices/jfel_fel.def): the linac from the saved
injector beam (elegant, with structure wakes and CSR), then Genesis 4 through
the undulator, steady-state and/or time-dependent.

    python JFEL/Scripts/run_fel.py                 # linac + steady-state (seconds)
    python JFEL/Scripts/run_fel.py --mode td       # linac + time-dependent SASE (~1 min)
    python JFEL/Scripts/run_fel.py --mode both --bc-angle 0.125

Reports the radiation wavelength, power gain length (fitted to the exponential
regime), saturation point and power, the pulse energy (time-dependent), and the
Ming Xie estimate of the gain length from the beam at the undulator entrance.
"""

import argparse
import os

import numpy as np

JFEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRANCE = "JFEL-FEL-SIM-MARK-01"
IA = 17045.0                                   # Alfven current [A]
MX = [0.45, 0.57, 0.55, 1.6, 3, 2, 0.35, 2.9, 2.4, 51, 0.95, 3, 5.4, 0.7, 1.9, 1140, 2.2, 2.9, 3.2]


def ming_xie(beam_file, period, K, helical=True):
    """3D power gain length [m] from Ming Xie's fit, for the beam in `beam_file`."""
    import simba.Modules.Beams as rbf

    b = rbf.load_file(beam_file)
    q = np.abs(np.asarray(b.Particles.charge.val))
    t = np.asarray(b.t.val)
    counts, edges = np.histogram(t, bins=max(int(np.sqrt(len(t))), 20), weights=q)
    current = np.convolve(counts / (edges[1] - edges[0]), np.ones(3) / 3, "same").max()
    gamma = float(np.mean(b.cp.val)) / 0.51099895e6
    sigma_d = float(np.std(b.cp.val) / np.mean(b.cp.val))
    sigma = np.sqrt(b.Sx * b.Sy)
    eps = np.sqrt(b.normalized_horizontal_emittance * b.normalized_vertical_emittance) / gamma
    beta = sigma ** 2 / eps
    ku = 2 * np.pi / period
    if helical:  # [JJ] = 1, and K^2 -> 2K^2 for the planar-K formula below
        k2jj = 2 * K ** 2
    else:
        from scipy.special import j0, j1
        xi = K ** 2 / (4 + 2 * K ** 2)
        k2jj = K ** 2 * (j0(xi) - j1(xi)) ** 2
    rho = (current / IA * k2jj / (16 * gamma ** 3 * sigma ** 2 * ku ** 2)) ** (1 / 3)
    lam = period * (1 + (K ** 2 if helical else K ** 2 / 2)) / (2 * gamma ** 2)
    lg1d = period / (4 * np.pi * np.sqrt(3) * rho)
    eta_d = lg1d * lam / (4 * np.pi * sigma ** 2)
    eta_e = lg1d * 4 * np.pi * eps / (beta * lam)
    eta_g = 4 * np.pi * lg1d * sigma_d / period
    a = MX
    eta = (a[0] * eta_d ** a[1] + a[2] * eta_e ** a[3] + a[4] * eta_g ** a[5]
           + a[6] * eta_e ** a[7] * eta_g ** a[8] + a[9] * eta_d ** a[10] * eta_g ** a[11]
           + a[12] * eta_d ** a[13] * eta_e ** a[14]
           + a[15] * eta_d ** a[16] * eta_e ** a[17] * eta_g ** a[18])
    return {"current_A": current, "gamma": gamma, "rho": rho, "lambda_m": lam,
            "Lg1D_m": lg1d, "eta": eta, "Lg_m": lg1d * (1 + eta)}


def genesis_summary(out_file, time_dependent):
    """Gain length, saturation and (time-dependent) pulse energy from Genesis' output."""
    import h5py

    with h5py.File(out_file) as h:
        z = h["Lattice/zplot"][()]
        power = h["Field/power"][()]
        lam = float(h["Global/lambdaref"][()][0])
        slen = float(h["Global/slen"][()][0])
    p = power.mean(axis=1) if power.ndim == 2 and power.shape[1] > 1 else power.reshape(len(z))
    i_max = int(np.argmax(p))
    # exponential regime: between 1e-4 and 1e-2 of the maximum power
    window = (p > 1e-4 * p[i_max]) & (p < 1e-2 * p[i_max]) & (np.arange(len(z)) < i_max)
    lg = 1 / np.polyfit(z[window], np.log(p[window]), 1)[0] if window.sum() > 3 else float("nan")
    # saturation: where the growth rate, past the exponential regime, falls
    # below a fifth of it (a seeded run keeps growing slowly beyond)
    i_sat = i_max
    if np.isfinite(lg) and window.any():
        rate = np.gradient(np.log(np.maximum(p, 1e-30)), z)
        rate = np.convolve(rate, np.ones(5) / 5, "same")
        after = np.where((np.arange(len(z)) > np.where(window)[0][-1]) & (rate < 1 / (5 * lg)))[0]
        if after.size:
            i_sat = int(after[0])
    out = {"lambda_m": lam, "Lg_m": lg, "z_sat_m": float(z[i_sat]), "P_sat_W": float(p[i_sat]),
           "P_end_W": float(p[-1])}
    if time_dependent:
        energy = power.sum(axis=1) * (slen / power.shape[1]) / 2.99792458e8
        out.update(E_pulse_max_J=float(energy.max()), z_Emax_m=float(z[np.argmax(energy)]),
                   P_peak_W=float(power[i_sat].max()))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["st", "td", "both"], default="st")
    parser.add_argument("--bc-angle", type=float, default=None, help="chicane angle [rad]")
    parser.add_argument("--dir", default="jfel_fel")
    parser.add_argument("--runtime", default="docker")
    args = parser.parse_args()

    import simba.Framework as fw

    directory = os.path.abspath(args.dir)
    runtime = None if args.runtime.lower() == "none" else args.runtime
    f = fw.Framework(master_lattice=JFEL + "/", directory=directory, clean=True,
                     verbose=False, container_runtime=runtime)
    f.loadSettings("Lattices/jfel_fel.def")
    if args.bc_angle is not None:
        f["bunch_compressor"].set_angle(args.bc_angle)
    f.track(files=["Linac"], check_lattice=False)

    wiggler = f.getElement("JFEL-FEL-MAG-WIGG-01").magnetic
    mx = ming_xie(os.path.join(directory, f"{ENTRANCE}.openpmd.hdf5"),
                  float(wiggler.period), float(wiggler.strength), bool(wiggler.helical))
    print(f"\nbeam at the undulator: I_peak {mx['current_A']:.0f} A, gamma {mx['gamma']:.1f}; "
          f"lambda {mx['lambda_m'] * 1e6:.3f} um, rho {mx['rho']:.4f}")
    print(f"Ming Xie: L_g1D {mx['Lg1D_m']:.3f} m, eta {mx['eta']:.2f}, L_g {mx['Lg_m']:.3f} m")

    for mode, line in (("st", "FEL_ST"), ("td", "FEL_TD")):
        if args.mode not in (mode, "both"):
            continue
        f.track(files=[line], check_lattice=False)
        s = genesis_summary(os.path.join(directory, f"{line}.out.h5"), mode == "td")
        print(f"\nGenesis {line}: lambda {s['lambda_m'] * 1e6:.3f} um, L_g {s['Lg_m']:.3f} m, "
              f"saturation at z = {s['z_sat_m']:.2f} m, <P> {s['P_sat_W']:.3e} W")
        if mode == "td":
            print(f"  peak slice power {s['P_peak_W']:.3e} W; pulse energy {s['E_pulse_max_J'] * 1e3:.3f} mJ "
                  f"at z = {s['z_Emax_m']:.2f} m")


if __name__ == "__main__":
    main()
