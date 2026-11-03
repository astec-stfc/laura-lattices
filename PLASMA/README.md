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
| `Lattices/pwfa_ramps.def` | `pwfa_single`'s stage between 2 mm inverse-square matching ramps (n0/25 at the ends), beams matched at the ramp entrance; then 0.5 m drift to a screen (Ocelot) | Adiabatic matching (β ∝ n^-1/2) |
| `Lattices/lwfa_single.def` | Laser-driven, external injection: a0 = 3, w0 = 40 µm, 30 fs laser guided in a matched parabolic channel, 1 mm ramps + 1 cm plateau at 1e23 m⁻³, 30 pC / 100 MeV witness; then 0.5 m drift to a screen (Ocelot) | Wake-T tutorial 01, part 3 |
| `Lattices/lwfa_staging.def` | Two laser-driven stages (a0 = 3, w0 = 40 µm, 2 cm each at 1e23 m⁻³, each with its own laser) coupled by 0.1 m drift + 2 cm, 950 T/m active plasma lens + 0.1 m drift that images stage 1 into stage 2; then 0.5 m drift to a screen (Ocelot) | Wake-T tutorial 02, extended to a second stage |
| `Lattices/lwfa_ionization.def` | Laser-driven ionization injection: a0 = 4, w0 = 5 µm laser in He/N (N⁵⁺ → N⁷⁺ inside the wake), 0.5 mm (FBPIC), no incoming beam; then 0.5 m drift to a screen (Ocelot). Small enough for a laptop GPU (~45 min on an RTX A400) | FBPIC `ionization_script.py` |

## Running

`Scripts/run_example.py` runs any of the lattices and summarises the beam at
the end of each section (charge, energy, spread, εn,x, σx; split into driver
and witness where there are two bunches):

```bash
python PLASMA/Scripts/run_example.py pwfa_single
python PLASMA/Scripts/run_example.py pwfa_single --code PWFA=fbpic
python PLASMA/Scripts/run_example.py lwfa_single --code LWFA=fbpic \
    --set PLA-LWFA-PLASMA-01.n_longitudinal=3250 --set PLA-LWFA-PLASMA-01.n_radial=200
python PLASMA/Scripts/run_example.py plasma_photocathode \
    --set PLA-PPC-PLASMA-01.n_longitudinal=1500 --set PLA-PPC-PLASMA-01.n_radial=100
python PLASMA/Scripts/run_example.py pwfa_single --dir pwfa_single --summary-only
```

`--code SECTION=CODE` switches a section's code, `--set ELEMENT.PARAM=VALUE`
overrides an element parameter, `--dir` sets the output directory (default
`./<lattice>`), `--split MEV` separates two bunches by energy in the summary.
The scripts are run from a checkout; they are not installed with the package.

Or directly from Python:

```python
import simba.Framework as fw
from laura_lattices import PLASMA

f = fw.Framework(master_lattice=PLASMA.dirname, directory="pwfa")
f.loadSettings("Lattices/pwfa_single.def")
# f.change_Lattice_Code("PWFA", "fbpic")   # full PIC instead of Wake-T
f.track()
```

### Reference results

`pwfa_ramps`, witness (reference: the same profile written by hand in Wake-T,
which SIMBA + Wake-T matches to every printed digit):

| | ⟨γ⟩ | spread | εn,x at exit | β at exit | εn,x at screen |
|---|---|---|---|---|---|
| `pwfa_single` (no ramps) | 636.7 | 0.71% | 0.987 µm | 0.59 mm | 2.000 µm |
| `pwfa_ramps` | 648.4 | 0.79% | 0.991 µm | 3.01 mm | 1.829 µm |

The down-ramp grows β 5x as designed, cutting the exit divergence and the
emittance growth in the following drift.

`lwfa_single`, witness at `PLA-LWFA-SIM-END-01` (reference: the tutorial's
guided stage run directly in Wake-T with the same witness):

| | ⟨γ⟩ | energy spread | εn,x |
|---|---|---|---|
| Wake-T reference | 520.5 | 1.02% | 1.021 µm |
| SIMBA + Wake-T | 520.4 | 1.02% | 1.019 µm |

`lwfa_staging`, witness (reference: the same line run directly in Wake-T):

| | after stage 1 | at stage 2 entry | after stage 2 |
|---|---|---|---|
| Wake-T reference ⟨γ⟩ | 577.1 | 577.1 | 957.9* |
| SIMBA + Wake-T ⟨γ⟩ | 577.0 | 577.0 | 957.8 |
| Wake-T reference εn,x | 1.139 µm | 2.076 µm (β 2.75 mm) | 2.115 µm |
| SIMBA + Wake-T εn,x | 1.141 µm | 2.075 µm (β 2.74 mm) | 2.097 µm |

\* With the witness re-centred at stage 2 entry, as SIMBA does: each stage's
laser is timed to the arriving witness. Keeping the 0.5 µm the witness slips
in stage 1 and the transport instead gives 966.8. The lens doubles the
emittance through chromatic aberration (1.24% energy spread), the usual
staging problem.

`pwfa_single`, γ of driver / witness at `PLA-PWFA-SIM-END-01`:

| | driver | witness |
|---|---|---|
| Wake-T reference (test_multibunch) | 1702.1 | 636.8 |
| SIMBA + Wake-T | 1702.3 | 636.7 |
| SIMBA + FBPIC (lab frame, at 1 cm) | 1707.5 | 570.8 |

The FBPIC wake matches Wake-T's to ~1 GV/m from the driver to 75 µm behind
it; the witness, just ahead of the field spike at the back of the bubble, sees
~15% less field there, which needs a resolution scan to settle.

## LWFA in FBPIC

The `lwfa_single` element's grid is Wake-T's, where the laser is an envelope.
FBPIC resolves the laser itself, so refine the grid (to λ/20 here) when
switching; the `.def` already selects a boosted frame (γ = 6, Galilean,
antenna injection, with ions):

```python
f.loadSettings("Lattices/lwfa_single.def")
f.change_Lattice_Code("LWFA", "fbpic")
f.apply_changes({"PLA-LWFA-PLASMA-01": {"n_longitudinal": 3250, "n_radial": 200}})
f.track()
```

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

## Stages without an incoming beam

`input: {particle_definition: null}` in a `files:` entry means the stage has
no incoming beam (FBPIC only): the laser drives the wake, the box is measured
from the stage entrance, and the output beam is the electrons the stage
injects. `lwfa_ionization.def` works this way.

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
