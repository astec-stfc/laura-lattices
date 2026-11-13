"""
Make the input beams for the SECONDARY lattices, in Data_Files/:

    brems_electrons      100 MeV, 10 pC, 0.1 mm rms round        (brems_target)
    conv_electrons       1 GeV, 10 pC, 0.1 mm rms round          (positron_conversion)
    crystal_electrons    855 MeV pencil: 20 um, 0.1 urad rms     (crystal_channelling)

    python SECONDARY/Generators/make_beams.py
"""

import os

import numpy as np
from simba.Codes.Generators import frameworkGenerator

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Data_Files")
BEAMS = {
    # name: (momentum [eV/c], sigma_x = sigma_y [m], divergence [rad], number)
    "brems_electrons": (100e6, 1e-4, 1e-4, 2000),
    "conv_electrons": (1e9, 1e-4, 1e-4, 2000),
    "crystal_electrons": (855e6, 2e-5, 1e-7, 2000),
}

if __name__ == "__main__":
    for name, (p, size, angle, n) in BEAMS.items():
        np.random.seed(1)   # the generator draws from numpy's global generator
        frameworkGenerator(
            global_parameters={"master_subdir": DATA}, filename=f"{name}.openpmd.hdf5",
            initial_momentum=p, sigma_x=size, sigma_y=size, sigma_px=angle * p, sigma_py=angle * p,
            sigma_z=1e-4, sigma_pz=1e-3 * p, charge=10e-12, number_of_particles=n,
        ).write()
        print(f"wrote {DATA}/{name}.openpmd.hdf5")
