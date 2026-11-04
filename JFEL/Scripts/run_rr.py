"""
Start-to-end radiation-reaction end-station for JFEL (Lattices/jfel_rr.def, RRX
layout): the linac from the saved injector beam (elegant), the S13 final focus
matched to a waist at the laser focus (Ocelot), the head-on collision with an
a0 = 6.8 laser pulse (Ptarmigan), and the PWA spectrometer (elegant).

    python JFEL/Scripts/run_rr.py --ptarmigan ~/ptarmigan/target/release/ptarmigan
    python JFEL/Scripts/run_rr.py --no-rr        # the same, radiation reaction off

Reports the beam at the IP, the electrons' energy loss and the photons emitted,
and the energy spectrum reconstructed from the spectrometer screen (x / R16)
against the true one.
"""

import argparse
import os

import numpy as np

JFEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRANCE, EXIT, SCREEN = "JFEL-PWA-SIM-START-01", "JFEL-RRX-SIM-END-01", "JFEL-RRX-DIA-SCR-01"
R16 = -0.4403   # [m], JFEL-RRX-SIM-END-01 -> screen (imaging doublet + 15 deg dipole)


def load(directory, name):
    import simba.Modules.Beams as rbf

    return rbf.load_file(os.path.join(directory, f"{name}.openpmd.hdf5"))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ptarmigan", default="ptarmigan", help="Ptarmigan executable")
    parser.add_argument("--no-rr", action="store_true", help="switch radiation reaction off")
    parser.add_argument("--dir", default="jfel_rr")
    parser.add_argument("--runtime", default="docker")
    args = parser.parse_args()

    import simba.Framework as fw

    directory = os.path.abspath(args.dir)
    runtime = None if args.runtime.lower() == "none" else args.runtime
    f = fw.Framework(master_lattice=JFEL + "/", directory=directory, clean=True,
                     verbose=False, container_runtime=runtime)
    f.loadSettings("Lattices/jfel_rr.def")
    f.executables.ptarmigan = [os.path.expanduser(args.ptarmigan)]
    if args.no_rr:
        f["IP"].file_block["tracking"]["radiation_reaction"] = False
    f.track(check_lattice=False)

    b0, b1, b2 = (load(directory, n) for n in (ENTRANCE, EXIT, SCREEN))
    e0, e1, e2 = (np.asarray(b.cp.val) * 1e-6 for b in (b0, b1, b2))
    print(f"\nIP entrance: {np.mean(e0):.1f} MeV, sigma_x {b0.Sx * 1e6:.1f} um, "
          f"sigma_y {b0.Sy * 1e6:.1f} um, {abs(b0.Q) * 1e12:.0f} pC")
    print(f"after the IP: electrons {np.mean(e1):.2f} MeV (lost {np.mean(e0) - np.mean(e1):.2f}); "
          f"rms spread {np.std(e0):.2f} -> {np.std(e1):.2f} MeV")
    photons = b1.others.get("photon")
    if photons is not None:
        n = np.asarray(photons.Particles.nmacro.val)
        k = np.asarray(photons.energy.val) * 1e-6
        electrons = abs(b1.Q) / 1.602176634e-19
        print(f"  photons: {n.sum() / electrons:.2f} per electron, mean {np.average(k, weights=n):.2f} MeV, "
              f"carrying {np.sum(n * k) / electrons:.2f} MeV per electron")

    # The doublet images the IP region onto the screen, so x depends on energy
    # alone: x = R16 delta / (1 + delta) about the reference momentum.
    x = np.asarray(b2.x.val)
    e_screen = np.mean(e1) / (1 - x / R16)
    print(f"screen: energy from x/R16 vs true, rms difference {np.std(e_screen - e2):.2f} MeV; "
          f"spectrum mean {np.mean(e_screen):.2f} MeV, rms {np.std(e_screen):.2f} MeV")


if __name__ == "__main__":
    main()
