"""
The full ERL (Lattices/erl_fel.def, ERL_FEL layout): the injected bunch is
accelerated to 100 MeV/c (elegant), lases in a 10 um SASE FEL in the return
straight (Genesis 4, time-dependent), and the spent beam is decelerated
through the same linac (elegant) and dumped.

    python ERL/Scripts/run_erl_fel.py              # ~12 min, mostly Genesis
    python ERL/Scripts/run_erl_fel.py --plot erl_fel.png

Reports the FEL (wavelength, gain length, saturation, pulse energy, with the
Ming Xie estimate), what the FEL does to the beam, the energy recovery, and
the energy range the dump has to accept.
"""

import argparse
import os
import sys

import numpy as np

ERL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(ERL), "JFEL", "Scripts"))
from run_fel import genesis_summary, ming_xie  # noqa: E402

POINTS = {
    "injected": "ERL-LIN-SIM-START-01.1",
    "top (linac exit, pass 1)": "ERL-LIN-SIM-END-01.1",
    "undulator entrance": "ERL-RETF-SIM-MARK-01",
    "undulator exit": "ERL-RETF-SIM-MARK-02",
    "return (linac entrance, pass 2)": "ERL-LIN-SIM-START-01.2",
    "dump (linac exit, pass 2)": "ERL-LIN-SIM-END-01.2",
}


def stats(beam):
    p = np.asarray(beam.cp.val) * 1e-6
    q = np.abs(np.asarray(beam.Particles.charge.val))
    return dict(p=float(np.average(p, weights=q)), dp=float(np.sqrt(np.cov(p, aweights=q)) / np.average(p, weights=q)),
                pmin=float(np.min(p)), pmax=float(np.max(p)),
                enx=beam.normalized_horizontal_emittance * 1e6, eny=beam.normalized_vertical_emittance * 1e6,
                sx=beam.Sx * 1e3, sy=beam.Sy * 1e3, q=float(q.sum()) * 1e12,
                st=float(np.sqrt(np.cov(np.asarray(beam.t.val), aweights=q))) * 1e12)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", default="erl_fel")
    parser.add_argument("--runtime", default="docker")
    parser.add_argument("--plot", default=None, help="save the FEL gain curve and the phase spaces")
    args = parser.parse_args()

    import simba.Framework as fw
    import simba.Modules.Beams as rbf

    directory = os.path.abspath(args.dir)
    runtime = None if args.runtime.lower() == "none" else args.runtime
    f = fw.Framework(master_lattice=ERL + "/", directory=directory, clean=True,
                     verbose=False, container_runtime=runtime)
    f.loadSettings("Lattices/erl_fel.def")
    f.track(check_lattice=False)

    beams = {label: rbf.load_file(os.path.join(directory, f"{name}.openpmd.hdf5"))
             for label, name in POINTS.items()}
    wiggler = f.getElement("ERL-RETF-MAG-WIGG-01").magnetic
    mx = ming_xie(os.path.join(directory, "ERL-RETF-SIM-MARK-01.openpmd.hdf5"),
                  float(wiggler.period), float(wiggler.strength), bool(wiggler.helical))
    fel = genesis_summary(os.path.join(directory, "FEL.out.h5"), time_dependent=True)
    print(f"\nFEL: lambda {fel['lambda_m'] * 1e6:.2f} um, L_g {fel['Lg_m']:.3f} m (Ming Xie {mx['Lg_m']:.3f} m, "
          f"rho {mx['rho']:.4f}, I {mx['current_A']:.0f} A), saturation at z = {fel['z_sat_m']:.2f} m "
          f"of {2 * float(wiggler.length):.1f} m")
    print(f"     pulse energy {fel['E_sat_J'] * 1e6:.1f} uJ at saturation, {fel['E_end_J'] * 1e6:.1f} uJ at the exit; "
          f"peak power {fel['P_peak_W'] / 1e6:.1f} MW")

    print(f"\n  {'':34s}{'p [MeV/c]':>10s}{'dp/p':>10s}{'p range [MeV/c]':>18s}{'enx':>7s}{'eny':>7s}"
          f"{'sx':>7s}{'sy':>7s}{'st':>7s}{'Q':>7s}")
    print(f"  {'':34s}{'':>10s}{'':>10s}{'':>18s}{'[um]':>7s}{'[um]':>7s}{'[mm]':>7s}{'[mm]':>7s}{'[ps]':>7s}{'[pC]':>7s}")
    s = {}
    for label, beam in beams.items():
        s[label] = r = stats(beam)
        print(f"  {label:34s}{r['p']:10.3f}{r['dp']:10.2e}{r['pmin']:9.2f}-{r['pmax']:<8.2f}{r['enx']:7.2f}{r['eny']:7.2f}"
              f"{r['sx']:7.3f}{r['sy']:7.3f}{r['st']:7.3f}{r['q']:7.1f}")
    lost = s["undulator entrance"]["p"] - s["undulator exit"]["p"]
    gained = s["top (linac exit, pass 1)"]["p"] - s["injected"]["p"]
    returned = s["return (linac entrance, pass 2)"]["p"] - s["dump (linac exit, pass 2)"]["p"]
    print(f"\n  the FEL takes {lost * 1e3:.1f} keV/c per electron ({100 * lost / s['undulator entrance']['p']:.2f}%); "
          f"the RF gives {gained:.3f} MeV/c and takes back {returned:.3f} ({100 * returned / gained:.2f}%)")
    dump = s["dump (linac exit, pass 2)"]
    print(f"  the dump gets {dump['p']:.3f} MeV/c with a {100 * dump['dp']:.1f}% rms spread, "
          f"{dump['pmin']:.2f} to {dump['pmax']:.2f} MeV/c")

    if args.plot:
        import h5py
        import matplotlib.pyplot as plt

        with h5py.File(os.path.join(directory, "FEL.out.h5")) as h:
            z = h["Lattice/zplot"][()]
            power = h["Field/power"][()]
            slen = float(h["Global/slen"][()][0])
        energy = power.sum(axis=1) * (slen / power.shape[1]) / 2.99792458e8
        fig, ax = plt.subplots(1, 3, figsize=(14, 4))
        ax[0].semilogy(z, energy * 1e6)
        ax[0].set(xlabel="z in the undulator [m]", ylabel="pulse energy [uJ]", title="SASE gain")
        for label, colour in (("undulator entrance", "C0"), ("undulator exit", "C1")):
            b = beams[label]
            t = (np.asarray(b.t.val) - np.mean(b.t.val)) * 1e12
            ax[1].plot(t, np.asarray(b.cp.val) * 1e-6, ",", color=colour, alpha=0.3, label=label)
        ax[1].set(xlabel="t [ps]", ylabel="p [MeV/c]", title="through the FEL")
        ax[1].legend(markerscale=20)
        b = beams["dump (linac exit, pass 2)"]
        t = (np.asarray(b.t.val) - np.mean(b.t.val)) * 1e12
        ax[2].plot(t, np.asarray(b.cp.val) * 1e-6, ",", alpha=0.3)
        ax[2].set(xlabel="t [ps]", ylabel="p [MeV/c]", title="at the dump (after deceleration)")
        fig.tight_layout()
        fig.savefig(args.plot, dpi=150)


if __name__ == "__main__":
    main()
