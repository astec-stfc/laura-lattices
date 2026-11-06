"""
Start-to-end plasma end-station for JFEL (Lattices/jfel_plasma.def, PWA layout):
the linac from the saved injector beam (elegant, wakes + CSR), the S13 final
focus matched to a round waist at the plasma entrance (Ocelot), a single-bunch
PWFA stage (Wake-T, or FBPIC with --plasma-code fbpic), and the spectrometer
(elegant) onto its screen.

    python JFEL/Scripts/run_plasma.py                  # ~minutes on a CPU
    python JFEL/Scripts/run_plasma.py --bc-angle 0.125 --plot

Reports the beam at the plasma entrance, the energy gained and lost along the
bunch in the plasma, and the energy spectrum reconstructed from the
spectrometer screen (x / R16) against the true one.
"""

import argparse
import os

import numpy as np

JFEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRANCE, EXIT, SCREEN = "JFEL-PWA-SIM-START-01", "JFEL-PWA-SIM-END-01", "JFEL-PWA-DIA-SCR-01"
R16 = -0.4403   # [m], plasma exit -> screen (imaging doublet + 15 deg dipole)


def load(directory, name):
    import simba.Modules.Beams as rbf

    return rbf.load_file(os.path.join(directory, f"{name}.openpmd.hdf5"))


def slices(beam, n=8):
    """Mean energy [MeV] in n equal-charge slices, head first."""
    t = np.asarray(beam.t.val)
    e = np.asarray(beam.cp.val) * 1e-6
    order = np.argsort(t)
    return [float(np.mean(s)) for s in np.array_split(e[order], n)]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bc-angle", type=float, default=None, help="chicane angle [rad]")
    parser.add_argument("--plasma-code", default="waket", choices=["waket", "fbpic"])
    parser.add_argument("--dir", default="jfel_plasma")
    parser.add_argument("--runtime", default="docker")
    parser.add_argument("--plot", action="store_true", help="save jfel_plasma.png in --dir")
    args = parser.parse_args()

    import simba.Framework as fw

    directory = os.path.abspath(args.dir)
    runtime = None if args.runtime.lower() == "none" else args.runtime
    f = fw.Framework(master_lattice=JFEL + "/", directory=directory, clean=True,
                     verbose=False, container_runtime=runtime)
    f.loadSettings("Lattices/jfel_plasma.def")
    if args.bc_angle is not None:
        f["bunch_compressor"].set_angle(args.bc_angle)
    if args.plasma_code != "waket":
        f.change_Lattice_Code("Plasma", args.plasma_code)
    f.track(check_lattice=False)

    b0, b1, b2 = (load(directory, n) for n in (ENTRANCE, EXIT, SCREEN))
    tw = b0.twiss
    print(f"\nplasma entrance: {np.mean(b0.cp.val) * 1e-6:.1f} MeV, sigma_x {b0.Sx * 1e6:.1f} um, "
          f"sigma_y {b0.Sy * 1e6:.1f} um, sigma_z {np.std(b0.t.val) * 2.998e14:.1f} um; "
          f"beta_x {tw.beta_x.val:.3f} m, beta_y {tw.beta_y.val:.3f} m")
    e0, e1 = (np.asarray(b.cp.val) * 1e-6 for b in (b0, b1))
    print(f"plasma exit: mean {np.mean(e1):.1f} MeV (was {np.mean(e0):.1f}); 1-99% range "
          f"{np.percentile(e1, 1):.1f}-{np.percentile(e1, 99):.1f} MeV "
          f"(was {np.percentile(e0, 1):.1f}-{np.percentile(e0, 99):.1f}); "
          f"charge {abs(b1.Q) * 1e12:.0f} pC")
    print("  slice energy [MeV], head -> tail: entrance", " ".join(f"{e:.0f}" for e in slices(b0)))
    print("                                    exit    ", " ".join(f"{e:.0f}" for e in slices(b1)))

    # The screen: the doublet images the plasma exit, so x depends on energy
    # alone. The dipole deflects as 1 / (1 + delta), so x = R16 delta / (1 + delta),
    # about the beam's mean momentum (which the magnets are set to).
    x = np.asarray(b2.x.val)
    e_screen = np.mean(e1) / (1 - x / R16)
    e2 = np.asarray(b2.cp.val) * 1e-6
    print(f"screen: energy from x/R16 vs true, rms difference {np.std(e_screen - e2):.2f} MeV; "
          f"spot sigma_y {b2.Sy * 1e6:.0f} um")

    if args.plot:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(1, 2, figsize=(10, 4))
        z1 = (np.asarray(b1.t.val) - np.mean(b1.t.val)) * -2.998e8 * 1e6
        z0 = (np.asarray(b0.t.val) - np.mean(b0.t.val)) * -2.998e8 * 1e6
        ax[0].plot(z0, e0, ",", alpha=0.3, label="entrance")
        ax[0].plot(z1, e1, ",", alpha=0.3, label="exit")
        ax[0].set(xlabel="z [um] (head at +)", ylabel="E [MeV]", title="longitudinal phase space")
        ax[0].legend(markerscale=20)
        ax[1].hist2d(x * 1e3, np.asarray(b2.y.val) * 1e3, bins=200, cmap="viridis", norm="log")
        ax[1].set(xlabel="x [mm]", ylabel="y [mm]", title="spectrometer screen")
        fig.tight_layout()
        fig.savefig(os.path.join(directory, "jfel_plasma.png"), dpi=150)


if __name__ == "__main__":
    main()
