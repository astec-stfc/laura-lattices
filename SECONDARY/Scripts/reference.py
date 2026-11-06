"""
The reference for each SECONDARY lattice: the same physics written by hand in
gmad and run in BDSIM directly, summarised as run_example.py does.

    python SECONDARY/Scripts/reference.py brems_target
    python SECONDARY/Scripts/reference.py positron_conversion
    python SECONDARY/Scripts/reference.py crystal_channelling

One lattice per run: reading a second BDSIM file in the same process has
crashed ROOT.
"""

import argparse
import os
import subprocess

import numpy as np

SECONDARY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SI220 = os.path.join(SECONDARY, "Data_Files", "Si220pl")
GAUSS = "distrType=\"gauss\", sigmaX=0.1*mm, sigmaY=0.1*mm, sigmaXp=1e-4, sigmaYp=1e-4, sigmaE=1e-3"
# name: (gmad, sampler, events); the samplers are where run_example.py reports
REFERENCES = {
    "brems_target": (
        't1: target, l=1*mm, material="tungsten", horizontalWidth=2*cm;\n'
        "l1: line=(t1);\nuse, l1;\nsample, range=t1;\n"
        f'beam, particle="e-", energy=100*MeV, {GAUSS};\n'
        'option, physicsList="em", beampipeMaterial="vacuum";\n',
        "t1", 2000,
    ),
    "positron_conversion": (
        "d1: drift, l=0.49825*m;\n"
        't1: target, l=3.5*mm, material="tungsten", horizontalWidth=2*cm;\n'
        "d2: drift, l=0.09825*m;\ns1: marker;\n"
        "l1: line=(d1, t1, d2, s1);\nuse, l1;\nsample, range=s1;\n"
        f'beam, particle="e-", energy=1*GeV, {GAUSS};\n'
        'option, physicsList="em", beampipeMaterial="vacuum";\n',
        "s1", 2000,
    ),
    "crystal_channelling": (
        f'c1: crystal, material="G4_Si", data="{SI220}", shape="box",\n'
        "    lengthY=1*cm, lengthX=0.5*mm, lengthZ=30*um,\n"
        "    sizeA=5.431*ang, sizeB=5.431*ang, sizeC=5.431*ang, alpha=pi/2, beta=pi/2, gamma=pi/2,\n"
        "    spaceGroup=227, bendingAngleYAxis=900*urad, bendingAngleZAxis=0;\n"
        'col1: crystalcol, l=40*um, apertureType="rectangular", aper1=0.5*mm, aper2=1*cm,\n'
        '    crystalLeft="c1", crystalAngleYAxisLeft=450*urad, xsize=-0.25*mm;\n'
        "d1: drift, l=0.5*m;\ns1: marker;\nl1: line=(col1, d1, s1);\nuse, l1;\nsample, range=s1;\n"
        'beam, particle="e-", energy=855*MeV, distrType="gauss", sigmaX=20*um, sigmaY=20*um,\n'
        "    sigmaXp=1e-7, sigmaYp=1e-7, sigmaE=1e-6;\n"
        'option, physicsList="completechannelling", stopSecondaries=1;\n',
        "s1", 2000,
    ),
}
SPECIES = {11: "electron", 22: "photon", -11: "positron"}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("lattice", choices=sorted(REFERENCES))
    parser.add_argument("--dir", help="output directory (default: ./<lattice>_reference)")
    args = parser.parse_args()

    from simba.Modules.Beams import bdsim

    gmad, sampler, events = REFERENCES[args.lattice]
    directory = os.path.abspath(args.dir or f"{args.lattice}_reference")
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, "hand.gmad"), "w") as f:
        f.write(gmad)
    subprocess.run(["bdsim", f"--file={directory}/hand.gmad", f"--outfile={directory}/hand", "--batch",
                    f"--ngenerate={events}"], check=True, capture_output=True)
    raw = bdsim.read_bdsim_sampler_arrays(f"{directory}/hand.root", samplers=[sampler])[sampler]
    primary = raw["parentID"] == 0
    print(f"\n{args.lattice} reference, hand-written gmad ({directory}):")
    for pdg, species in SPECIES.items():
        hits = (raw["partID"] == pdg) & (primary if pdg == 11 else ~primary)
        if not hits.any():
            continue
        xp = raw["xp"][hits] * 1e3
        print(f"    {species:9s} {hits.sum():6d} hits  {hits.sum() / events:7.3f} per e-  "
              f"<E> {np.mean(raw['energy'][hits]) * 1e3:8.2f} MeV  "
              f"x' median {np.median(xp):7.3f} mrad, rms {np.std(xp):7.3f} mrad")
    if args.lattice == "crystal_channelling":
        print(f"    channelled (x' within 0.15 mrad of the 0.9 mrad bend): "
              f"{np.mean(np.abs(raw['xp'][primary] * 1e3 - 0.9) < 0.15):.3f}")


if __name__ == "__main__":
    main()
