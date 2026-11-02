# PLASMA: example plasma-wakefield lattices

Not a real machine. Example plasma-acceleration stages that run through
[SIMBA](https://github.com/astec-stfc/simba) in both
[Wake-T](https://github.com/Wake-T/Wake-T) (quasi-static, fast) and
[FBPIC](https://github.com/fbpic/fbpic) (full PIC, GPU), from one LAURA element
definition.

| Lattice | Stage | Based on |
|---|---|---|
| `Lattices/pwfa_single.def` | Beam-driven: 500 pC / 1 GeV driver, 50 pC / 100 MeV witness, 1 cm at 1e23 m⁻³, then 0.5 m drift to a screen (Ocelot) | Wake-T `tests/test_multibunch.py` |
| `Lattices/plasma_photocathode.def` | Plasma photocathode: 200 pC / 1 GeV driver in H plasma doped with He; a collinear a0 = 0.025 laser ionizes He inside the wake (1 mm, FBPIC), the witness is accelerated over 2 cm (Wake-T), then a 0.5 m drift to a screen (Ocelot) | Collinear Trojan-horse injection |

## Running

```python
import simba.Framework as fw
from laura_lattices import PLASMA

f = fw.Framework(master_lattice=PLASMA.dirname, directory="pwfa")
f.loadSettings("Lattices/pwfa_single.def")
# f.change_Lattice_Code("PWFA", "fbpic")   # full PIC instead of Wake-T
f.track()
```

Expected at `PLA-PWFA-SIM-END-01`, γ of driver / witness:

| | driver | witness |
|---|---|---|
| Wake-T reference (test_multibunch) | 1702.1 | 636.8 |
| SIMBA + Wake-T | 1702.3 | 636.7 |
| SIMBA + FBPIC | see below | see below |

## Plasma photocathode

`PPC_INJ` needs FBPIC: Wake-T models neither ionization nor an injection laser,
and leaves both out (with a warning) if the section is switched to it.

At the element's resolution (dz = λ/16, dr = 0.2 µm, ~2.4M grid cells with two
modes, ~25k steps) the injection stage wants a large GPU. For a quick check
on a small one, coarsen the grid before tracking -- the laser is then
under-resolved, so treat the injected charge and emittance as indicative only:

```python
f.loadSettings("Lattices/plasma_photocathode.def")
f.apply_changes({"PLA-PPC-PLASMA-01": {"n_longitudinal": 1500, "n_radial": 100}})
f.track()
```

Electrons freed from the helium are kept in their own FBPIC species and
written out with the drive bunch if their γβ exceeds `injected_uz_min`
(default 2), i.e. if they were trapped. FBPIC warns if the drive bunch's own
field could ionize the helium.

## Conventions

- **Beam-driven vs laser-driven.** A `Plasma` element whose `laser` has
  `role: driver` (the default) is laser-driven. Without a laser, or with
  `role: injector`, the wake is driven by the incoming beam.
- **Box coordinates.** `simulation.min/max_longitudinal_position` and
  `laser.initial_position` are relative to the incoming beam's reference
  particle if it has one, otherwise to its charge-weighted centroid (in both
  codes; shift with the lattice setting `bunch_z_position`).
  `pwfa_driver_witness` has no reference particle; its centroid is 7.3 µm
  behind the driver, so the driver sits at +7.3 µm and the witness at −72.7 µm.
- **Density profile.** `z` is the distance from the element entrance. The
  element `length` must cover `density_profile_start + ramp_up + plateau +
  ramp_down`; LAURA warns if it does not.
- **One plasma per section.** FBPIC simulates a single plasma per lattice
  section, so each stage gets its own section and its own `files:` entry.
- **FBPIC frame.** Beam-driven stages run in the lab frame (`boost: False`);
  the boosted-frame set-up is derived from the laser.

## Data files

`Data_Files/*.openpmd.hdf5` are written by `Generators/make_beams.py`
(needs SIMBA and Wake-T).
