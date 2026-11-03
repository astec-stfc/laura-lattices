# ERL: example energy-recovery linac

Not a real accelerator: a single-turn energy-recovery linac (ERL), and an
example of a LAURA **multipass** layout, where the beam passes through the
same hardware more than once.

One 1.3 GHz SRF cryomodule (8 x 9-cell cavities, 11.25 MV each) is crossed
twice. The injected 10 MeV/c bunch is accelerated on crest to 100 MeV/c, goes
round a racetrack (a 180 deg arc, a return straight, a second 180 deg arc), and
comes back through the same cavities half an RF period late. It is
decelerated back to 10 MeV/c, handing its energy back to the RF, and goes to
the dump.

```
          ARC2 <------------ RET ------------- ARC1
           |                                     ^
           v                                     |
 INJ ---> LIN (pass 1: 10 -> 100 MeV/c) --------->+
          LIN (pass 2: 100 -> 10 MeV/c) ---------> DMP
```

## How the machine is defined

- `elements.yaml`: every element in one file, using `_templates` and
  `inherits_from` (one quadrupole, cavity and arc-dipole template). Nothing
  states a position: every section is placed **sequentially**, by its order
  and the element lengths.
- `sections.yaml`: INJ, LIN, ARC1, RET, ARC2, DMP, each defined once. LIN
  holds the cavities only, so no magnet has to serve two energies.
- `layouts.yaml`: the beam path `INJ, LIN{multipass: 1}, ARC1, RET, ARC2,
  LIN{multipass: 2}, DMP`. The second pass sets `cavity.phase: 180` on each
  cavity through `overrides`. There is one set of cavities, and the second
  pass's phase belongs to the pass, not the cavity.
- The linac's elements are addressed per pass as `NAME#1` and `NAME#2`, e.g.
  `ERL-LIN-SIM-START-01#2` as a line's start. In a tracking line they appear
  as `NAME.1` and `NAME.2`, as do the beam files written there.
- The return straight is as long as the linac, so the racetrack closes: the
  second pass enters the linac where the first did. The merger and splitter are
  idealised. The injector and the second arc both end on the linac axis, and
  the first arc and the dump line both leave from the linac exit, bending
  opposite ways.

## Optics

`Scripts/match_erl.py` computes the linear optics from Ocelot transfer maps of
each section, translated from the LAURA lattice:

| Section | Matching |
|---|---|
| Linac | The entrance Twiss that gives a waist (beta 10 m, alpha 0) at the end of the accelerating pass |
| Injector (4 quadrupoles) | The injected beam (beta 5 m, alpha 0) to that entrance Twiss |
| Arcs (5 families, mirror-symmetric) | Achromatic (D = D' = 0 at the exit), isochronous (R56 = 0), and alpha = 0 at the centre, with the lowest peak beta (28 m) |
| Arc sextupoles (2 families) | A second-order achromat: T566 = 0 and T166 = 0 (T266 = 0.003), from second-order tracking at momentum offsets |
| Return straight (3 families) | alpha = 0 at its centre, lowest peak beta (14 m) |

The whole racetrack is then mirror-symmetric. The beam re-enters the linac
with the mirror image of the Twiss it left with. The decelerating pass is the
accelerating one run backwards, so the beam leaves for the dump with the
injected optics: in the tracking below, the dump beam is the injected beam
again.

## Lattices and scripts

| File | What |
|---|---|
| `Lattices/erl.def` | The ERL in two lines (elegant): the racetrack, injector to the end of the linac's second pass (`ERL-LIN-SIM-END-01#2`), and the dump line |
| `Lattices/erl_bmad_multipass.def` | The whole ERL as one Bmad line written as **Bmad multipass**: each cavity defined once (a multipass lord), entered twice (slaves `NAME\1`, `NAME\2`), the return pass's phase set per slave (`phi0_multipass`) |
| `Lattices/erl_fel.def` | The full ERL (`ERL_FEL` layout): injector to undulator in elegant, the FEL in Genesis 4 (time-dependent SASE), the spent beam through the decelerating pass and dump in elegant |
| `Lattices/erl_sections.def` | One line per section (Ocelot), for matching or for running sections in different codes |
| `Generators/make_beam.py` | Writes `Data_Files/erl_injector.openpmd.hdf5`: 10 MeV/c, 100 pC, 2 ps rms, 1 um normalised emittance, 0.1% momentum spread (20000 particles); and `erl_injector_fel.openpmd.hdf5`, the same at 0.75 ps rms, for the FEL |
| `Scripts/match_erl.py` | The optics above; prints the quadrupole K1L for `elements.yaml` and the Twiss at each section exit |
| `Scripts/run_erl_fel.py` | Runs `erl_fel`: the FEL (wavelength, gain length, saturation, pulse energy, with the Ming Xie estimate), the spent beam, the energy recovery, and the energy range at the dump; plots the gain curve and the phase spaces |
| `Scripts/run_erl.py` | Tracks the ERL in one or more codes, summarises both passes and the energy recovery; scans the return-pass phase; plots momentum and beam size along the path |

```bash
python ERL/Scripts/match_erl.py                             # add --fel for the FEL return straight
python ERL/Scripts/run_erl_fel.py --plot erl_fel.png         # the full ERL, with the FEL
python ERL/Scripts/run_erl.py --plot erl.png                 # elegant and Ocelot
python ERL/Scripts/run_erl.py --codes elegant ocelot bmad impactx madx
python ERL/Scripts/run_erl.py --codes bmad bmad_native            # flattened vs Bmad multipass
python ERL/Scripts/run_erl.py --physics csr --codes elegant ocelot bmad impactx
python ERL/Scripts/run_erl.py --physics all                  # CSR and synchrotron radiation
python ERL/Scripts/run_erl.py --codes elegant --scan-phase -10 -5 0 5 10
```

Requirements: LAURA and SIMBA with multipass layouts; elegant through a
container runtime (`--runtime docker`, the default, or `apptainer`); Ocelot;
for Bmad, `export ACC_ROOT_DIR=<bmad-ecosystem>` (or `--libtao`); ImpactX
(built with FFT for CSR); MAD-X through cpymad.

## Results

### Single-particle (no CSR or synchrotron radiation)

Momentum [MeV/c] and rms relative momentum spread; at the dump also the
normalised emittances, rms sizes and bunch length:

| | elegant | Ocelot | Bmad | ImpactX | MAD-X |
|---|---|---|---|---|---|
| injected | 10.000, 1.00e-3 | 10.000, 1.00e-3 | 10.000, 1.00e-3 | 10.000, 1.00e-3 | 10.000, 1.00e-3 |
| top (linac exit, pass 1) | 99.999, 2.00e-4 | 100.000, 1.98e-4 | 100.000, 1.98e-4 | 100.000, 1.98e-4 | 100.000, 1.98e-4 |
| dump (linac exit, pass 2) | 10.000, 1.01e-3 | 10.000, 1.00e-3 | 10.000, 1.00e-3 | 10.000, 1.00e-3 | 10.000, 1.00e-3 |
| energy taken back by the RF | 100.000% | 100.000% | 100.000% | 100.000% | 100.000% |
| dump eps_nx / eps_ny [um] | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 |
| dump sigma_x / sigma_y [mm] | 0.581 / 0.581 | 0.580 / 0.581 | 0.579 / 0.580 | 0.579 / 0.580 | 0.579 / 0.582 |
| dump sigma_t [ps] | 2.01 | 2.01 | 2.01 | 2.01 | 2.01 |

The five codes agree to 0.5% or better at every point along the path. The
other codes track a flattened lattice, with a copy of each cavity per pass.
Bmad can hold the shared hardware itself: in a SIMBA line, `multipass:
native` writes LAURA's Bmad multipass export, with one lord per cavity and
one slave per pass (`Lattices/erl_bmad_multipass.def`). That gives results
identical to Bmad's flattened run, with and without CSR. The
bunch returns to the dump with its injected energy, spread, emittance, size
and length, and the dump receives 10% of the beam power at the top of the
linac.

### CSR in the arcs (`--physics csr`)

| | elegant | Ocelot | Bmad | ImpactX |
|---|---|---|---|---|
| energy lost round the racetrack [keV] | 47 | 44 | 45 | 33 |
| eps_nx after the arcs [um] | 1.50 | 1.34 | 1.39 | 1.47 |
| dump momentum [MeV/c], rms spread | 9.951, 3.15e-3 | 9.955, 2.60e-3 | 9.954, 2.74e-3 | 9.967, 2.45e-3 |

The RF still takes back the full 90 MeV/c, and the energy lost in the arcs
reaches the dump. CSR raises the horizontal emittance by 35-50%. The energy
spread it adds at 100 MeV/c is magnified tenfold, relative to the energy, by
the deceleration to 10 MeV/c. The codes' CSR models spread by about as much
as they do in JFEL's chicane. Adding synchrotron radiation (`--physics all`,
elegant and Ocelot) changes these by less than 1 keV.

### Return-pass phase (`--scan-phase`, elegant, no CSR/SR)

The second pass is decelerating only if the recirculation path is (n + 1/2)
RF wavelengths. A phase offset from 180 deg stands for a path that is off by
that fraction of a wavelength:

| offset [deg] | 0 | +-2 | +-5 | +-10 | +-20 |
|---|---|---|---|---|---|
| dump momentum [MeV/c] | 10.00 | 10.05-10.06 | 10.33-10.35 | 11.35-11.39 | 15.40-15.46 |
| dump rms spread | 1.0e-3 | 5e-3 | 1.2e-2 | 2.2e-2 | 3.2e-2 |
| energy recovered | 100% | 99.9% | 99.6% | 98.5% | 94% |

The dump momentum rises as 90 MeV/c x (1 - cos offset). The spread grows as
90 MeV/c x sin(offset) x the bunch's RF phase spread (2 pi x 1.3 GHz x 2 ps =
0.016 rad): at 1.3 GHz, a 1 mm error in the recirculation path costs 1.6 deg.

## The full ERL: an FEL in the return straight

The `ERL_FEL` layout replaces the return straight with `RETF`, the same
length, so the racetrack still closes. It holds an infrared SASE FEL: a
7.2 m helical undulator (2 x 90 periods of 40 mm, K = 4.26), lasing at
10 um at 100 MeV/c. The undulator's own focusing gives a matched beta of
0.41 m in both planes, and four quadrupole families either side match the
arc's beta = 10 m waist into it, mirror-symmetrically (`match_erl.py --fel`).
The bunch is accelerated, lases, and is then decelerated through the same
cavities and dumped. `run_erl_fel.py` runs it all in about 12 minutes, mostly
Genesis.

For the gain, this layout injects a 0.75 ps bunch (53 A peak) rather than
the ERL's 2 ps one (`erl_injector_fel`).

| | |
|---|---|
| wavelength | 10.01 um |
| gain length | 0.31 m (Ming Xie 0.27 m, rho = 0.023) |
| saturation | at 6.8 m: 23 uJ, 28 uJ at the undulator exit, 18 MW peak. SASE starts from shot noise, so these vary from run to run (25-35 uJ at the exit over several) |
| energy balance | the beam loses 27.7 uJ in Genesis, the field holds 27.8 uJ |

| | p [MeV/c] | rms spread | range [MeV/c] | eps_nx / eps_ny [um] | sigma_t [ps] |
|---|---|---|---|---|---|
| injected | 10.000 | 1.0e-3 | 9.96-10.03 | 1.00 / 1.00 | 0.75 |
| top (linac exit, pass 1) | 100.009 | 1.0e-4 | 99.96-100.05 | 1.00 / 1.00 | 0.75 |
| undulator entrance | 99.931 | 4.8e-4 | 99.85-100.06 | 2.79 / 1.00 | 0.75 |
| undulator exit | 99.653 | 5.5e-3 | 97.77-101.22 | 2.79 / 0.95 | 0.75 |
| linac entrance, pass 2 | 99.578 | 5.7e-3 | 97.71-101.16 | 3.55 / 1.42 | 0.74 |
| dump | 9.562 | 6.0e-2 | 7.69-11.14 | 3.67 / 1.59 | 0.85 |

- The FEL takes 0.3% of the beam's energy, a few times less than rho, as
  expected for a 3D, diffraction-dominated FEL (Ming Xie eta = 3.4). It
  leaves the bunch with a +-2% energy spread.
- Genesis' field grid is +-2.5 mm (`dgrid`, 501 points, in `erl_fel.def`):
  the 10 um radiation diffracts beyond the default +-1 mm, which then loses
  about 20% of the field energy.
- The RF still takes back the full 90 MeV/c it gave. The energy spread the
  FEL put in at 100 MeV/c is magnified tenfold, relative to the energy, by
  the deceleration: the dump has to accept 7.7 to 11.1 MeV/c, +-18% of its
  mean, where the ERL alone needs +-0.4%. That spread is the central design
  constraint of an ERL-FEL.
- The arcs are second-order achromats (T566 = T166 = 0, from the sextupoles),
  so the spent beam returns to the linac at one RF phase whatever its energy,
  and with its bunch length kept. Without the sextupoles (K2L = 0) T566 =
  1.6 m puts 2 ps, more than twice the bunch length, between the +-2% ends of
  the spread beam, curving its phase space at the dump, and the open
  second-order dispersion takes eps_nx to about 9 um after the second arc
  rather than about 4 um. The sextupoles add a little vertical emittance in
  return (about 1.1 -> 1.4-1.8 um on the spent beam).
- The tilt left at the dump (`--plot`) is velocity slip: near 10 MeV, +-20%
  in energy is enough for the electrons to separate in time over the end of
  the linac.
- CSR in the arcs, much stronger for the 0.75 ps bunch, raises eps_nx from
  1.0 to 2.8 um before the undulator.

## Open items

- CSR-optimised arcs, for the short bunch the FEL needs.
- Two recirculations (multipass arcs at two energies).
- Space charge at injection, and a real merger and splitter.
