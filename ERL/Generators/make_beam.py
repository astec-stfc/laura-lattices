"""
The ERL's injected bunches: 10 MeV/c, 100 pC, 1 um normalised emittance,
0.1% rms momentum spread, at ERL-INJ-SIM-START-01 with beta = 5 m, alpha = 0
in both planes.

- Data_Files/erl_injector.openpmd.hdf5: 2 ps rms (20 A), for the ERL.
- Data_Files/erl_injector_fel.openpmd.hdf5: 0.75 ps rms (53 A), for the
  ERL_FEL layout, where the FEL needs the peak current to saturate.

    python ERL/Generators/make_beam.py
"""

import os

import numpy as np
from ocelot.cpbd.beam import Twiss, generate_parray
from simba.Modules import Beams as rbf
from simba.Modules import constants
from simba.Modules.Beams.ocelot import particle_array_to_beam

ERL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P0 = 10e6           # [eV/c]
CHARGE = 100e-12    # [C]
EMIT_N = 1e-6       # [m]
N = 20000

energy = np.hypot(P0, constants.m_e * constants.speed_of_light ** 2 / constants.elementary_charge)
gamma = energy / 0.51099895e6
tws = Twiss(beta_x=5.0, beta_y=5.0, alpha_x=0.0, alpha_y=0.0,
            emit_x=EMIT_N / gamma, emit_y=EMIT_N / gamma, E=energy * 1e-9)
for name, sigma_t in (("erl_injector", 2e-12), ("erl_injector_fel", 0.75e-12)):
    np.random.seed(1)   # generate_parray draws from numpy's global generator
    parray = generate_parray(sigma_tau=sigma_t * constants.speed_of_light, sigma_p=1e-3, chirp=0.0,
                             charge=CHARGE, nparticles=N, energy=energy * 1e-9, tws=tws)
    beam = rbf.beam()
    particle_array_to_beam(beam, parray)
    beam.set_mass_and_charge(constants.m_e, -constants.elementary_charge, N)  # the species, per particle
    path = os.path.join(ERL, "Data_Files", f"{name}.openpmd.hdf5")
    rbf.openpmd.write_openpmd_beam_file(beam, path)

    check = rbf.beam()
    rbf.openpmd.read_openpmd_beam_file(check, path)
    print(f"{path}: {len(check.x)} particles, {check.Particles.total_charge.val * 1e12:.1f} pC, "
          f"{np.mean(check.cp.val) * 1e-6:.3f} MeV/c, eps_n {check.normalized_horizontal_emittance * 1e6:.3f} / "
          f"{check.normalized_vertical_emittance * 1e6:.3f} um, sigma_t {np.std(check.t.val) * 1e12:.2f} ps")
