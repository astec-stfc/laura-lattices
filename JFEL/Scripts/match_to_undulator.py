"""
Match the JFEL linac into the undulator through the S13 quadrupoles.

1. The undulator's periodic Twiss at its entrance, from Ocelot's transfer map
   of the 10 FODO cells -- including the natural focusing of the helical
   undulator segments (both planes).
2. Track the saved injector beam to the start of S13, then match the four S13
   quadrupoles to that Twiss at the undulator entrance (SIMBA's `match` block,
   Ocelot's matcher).
3. Track through the undulator and check the beam stays periodic.

    python JFEL/Scripts/match_to_undulator.py
    python JFEL/Scripts/match_to_undulator.py --bc-angle 0.12

Prints the matched K1L, to be copied into the S13 quadrupole YAML files.
"""

import argparse
import os

import numpy as np

JFEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUADS = [f"JFEL-S13-MAG-QUAD-0{i}" for i in range(1, 5)]
ENTRANCE, EXIT = "JFEL-FEL-SIM-MARK-01", "JFEL-FEL-SIM-MARK-02"


def periodic_twiss(f, energy_gev):
    """The undulator's periodic Twiss (Ocelot) at its entrance."""
    from ocelot.cpbd.beam import Twiss
    from ocelot.cpbd.optics import lattice_transfer_map, periodic_twiss as periodic

    brho = np.sqrt((energy_gev * 1e9) ** 2 - 0.51099895e6 ** 2) / 299792458.0
    lattice = f.latticeObjects["Undulator"].section.to_ocelot(Brho=brho)
    start = Twiss()
    start.E = energy_gev
    tws = periodic(start, lattice_transfer_map(lattice, energy=energy_gev))
    if tws is None:
        raise RuntimeError("the undulator lattice has no periodic solution")
    return {k: float(getattr(tws, k)) for k in ("beta_x", "alpha_x", "beta_y", "alpha_y")}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bc-angle", type=float, default=None, help="chicane angle [rad]")
    parser.add_argument("--dir", default="jfel_match")
    parser.add_argument("--runtime", default="docker")
    args = parser.parse_args()

    import simba.Framework as fw
    import simba.Modules.Beams as rbf

    directory = os.path.abspath(args.dir)
    runtime = None if args.runtime.lower() == "none" else args.runtime
    f = fw.Framework(master_lattice=JFEL + "/", directory=directory, clean=True,
                     verbose=False, container_runtime=runtime)
    f.loadSettings("Lattices/jfel_match_undulator.def")
    if args.bc_angle is not None:
        f["bunch_compressor"].set_angle(args.bc_angle)

    # Linac first, for the beam energy at the undulator.
    f.track(files=["Linac"], check_lattice=False)
    beam = rbf.load_file(os.path.join(directory, "JFEL-S13-SIM-MARK-01.openpmd.hdf5"))
    energy = float(np.mean(beam.cp.val)) * 1e-9
    target = periodic_twiss(f, energy)
    print(f"undulator periodic Twiss at {energy * 1e3:.1f} MeV: "
          + ", ".join(f"{k} {v:.4f}" for k, v in target.items()))

    f.latticeObjects["Match"].file_block["match"]["targets"] = {ENTRANCE: target}
    f.track(files=["Match", "Undulator"], check_lattice=False)

    print("\nmatched S13 (K1L [1/m]):")
    for name in QUADS:
        print(f"  {name}: {float(f.getElement(name).magnetic.multipoles.K1L.normal):.5f}")
    print("\nbeam Twiss:")
    for name in (ENTRANCE, EXIT):
        t = rbf.load_file(os.path.join(directory, f"{name}.openpmd.hdf5")).twiss
        print(f"  {name}: beta_x {t.beta_x.val:.3f} alpha_x {t.alpha_x.val:+.3f}  "
              f"beta_y {t.beta_y.val:.3f} alpha_y {t.alpha_y.val:+.3f}")


if __name__ == "__main__":
    main()
