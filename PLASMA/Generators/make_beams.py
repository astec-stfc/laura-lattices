"""
Write the incoming beams for the PLASMA examples, as SIMBA openPMD files in
Data_Files/ (needs SIMBA and Wake-T):

pwfa_driver_witness
    The drive and witness bunches of Wake-T's tests/test_multibunch.py, each
    matched to n_p = 1e23 m^-3 and generated in the same order with the same
    seed, so pwfa_single.def should reproduce that test (driver gamma
    2000 -> 1702.1, witness 200 -> 636.8).
ppc_driver
    The drive bunch for plasma_photocathode.def: 200 pC, 1 GeV, matched to
    1e23 m^-3. Its peak field (~20 GV/m) and that of its wake (~40 GV/m) stay
    well below the ~105 GV/m that ionizes helium, which is left to the laser.

    ~/venv/bin/python3 PLASMA/Generators/make_beams.py
"""

import os

import numpy as np
from simba.Modules import Beams as rbf
from simba.Modules.Beams.wake_t import particle_bunch_to_beam
from wake_t import ParticleBunch
from wake_t.utilities.bunch_generation import get_matched_bunch

N_P = 1e23
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Data_Files")


def write(name, bunches, total_charge):
    combined = ParticleBunch(
        *(np.concatenate([getattr(b, k) for b in bunches])
          for k in ("w", "x", "y", "xi", "px", "py", "pz")),
    )
    beam = rbf.beam()
    particle_bunch_to_beam(beam, combined, zpos=0.0)
    path = os.path.normpath(os.path.join(DATA, f"{name}.openpmd.hdf5"))
    rbf.openpmd.write_openpmd_beam_file(beam, path)
    check = rbf.beam()
    rbf.openpmd.read_openpmd_beam_file(check, path)
    assert np.isclose(check.Particles.total_charge.val, total_charge)
    print(f"wrote {path}: {len(check.x.val)} macroparticles, "
          f"{check.Particles.total_charge.val * 1e12:.1f} pC")


np.random.seed(1)
driver = get_matched_bunch(en_x=10e-6, en_y=10e-6, ene=2000, ene_sp=1, s_t=10,
                           xi_c=0, q_tot=500, n_part=1e4, n_p=N_P)
witness = get_matched_bunch(en_x=1e-6, en_y=1e-6, ene=200, ene_sp=0.1, s_t=3,
                            xi_c=-80e-6, q_tot=50, n_part=1e4, n_p=N_P)
write("pwfa_driver_witness", [driver, witness], -550e-12)

np.random.seed(2)
ppc = get_matched_bunch(en_x=20e-6, en_y=20e-6, ene=2000, ene_sp=1, s_t=33,
                        xi_c=0, q_tot=200, n_part=2e4, n_p=N_P)
write("ppc_driver", [ppc], -200e-12)
