# SECONDARY: example lines that make secondary particles

Not a real machine. These are example lines where the beam hits material and makes secondaries.
They run in [BDSIM](https://bdsim-collaboration.github.io/web/) (Geant4) through
[SIMBA](https://github.com/astec-stfc/simba), from LAURA `Target` and `Crystal` elements. The
secondaries come out as their own species, in the openPMD beam files next to the primaries.

| Lattice | Line | Exercises |
|---|---|---|
| `Lattices/brems_target.def` | 100 MeV, 10 pC e⁻ through 1 mm of tungsten (0.29 X₀), then 0.5 m to a screen; the photons and positrons kept, at the target's exit (its sampler) and at the screen | `Target`, `physics_list`, `secondaries`, `samplers` |
| `Lattices/positron_conversion.def` | 1 GeV e⁻ shower in 3.5 mm of tungsten (1 X₀) (BDSIM); the positrons alone go on to a screen in Xsuite (`input: species: positron`), and the photons are carried through untracked | as above, plus handing one species on to another code |
| `Lattices/crystal_channelling.def` | 855 MeV e⁻ pencil beam on 30 µm of bent Si(220) (0.9 mrad bend), then 0.5 m to a screen | `Crystal`, channelling physics |

The input beams come from `Generators/make_beams.py`, and are in `Data_Files/`. So is BDSIM's
Si(220) channelling data (`Si220pl_*`, from BDSIM's examples).

## Running

```bash
python SECONDARY/Scripts/run_example.py brems_target          # ~30 s each
python SECONDARY/Scripts/run_example.py positron_conversion
python SECONDARY/Scripts/run_example.py crystal_channelling
python SECONDARY/Scripts/run_example.py crystal_channelling --set SEC-CRY-CRY-01.entrance_angle=-0.0005
python SECONDARY/Scripts/reference.py brems_target            # the hand-written gmad
```

`run_example.py` summarises every species at the end of each line, and at each extra sampler.
Numbers are per incoming electron. `reference.py` runs the same case written by hand in gmad
and prints the same summary. The scripts are run from a checkout; they are not installed with
the package.

### Requirements

- BDSIM with its ROOT Python bindings and pybdsim. Source ROOT's `thisroot.sh` and BDSIM's
  `bdsim.sh` first.
- SIMBA >= 0.7.1 and LAURA >= 1.1.3: `Target`, `Crystal`, `tracking: {physics_list,
  secondaries, samplers, options}`, and weighted `userfile` beams.
- Xsuite for `positron_conversion`. Its line is pinned to the CPU (`tracking: {context: cpu}`).

### Reference results

Run with 2000 electrons and compared with `reference.py`. BDSIM's seed changes every run. The
spread between seeds is about ±0.02 in the yields and ±3 MeV in the positron mean energy: the
mean is dominated by a few energetic positrons from each shower, while the median (about
30 MeV) is steady.

`brems_target`, at the target's exit:

| | e⁻ per e⁻ (⟨E⟩) | γ per e⁻ (⟨E⟩) | e⁺ per e⁻ (⟨E⟩) |
|---|---|---|---|
| hand-written gmad | 0.989 (75.6 MeV) | 2.10 (10.2 MeV) | 0.033 (13 MeV) |
| SIMBA + BDSIM | 0.989 (75.7 MeV) | 2.03 (10.2 MeV) | 0.038 (16 MeV) |

`positron_conversion`, 0.1 m after the converter (the Xsuite line leaves these as they are):

| | γ per e⁻ (⟨E⟩) | e⁺ per e⁻ (⟨E⟩) |
|---|---|---|
| hand-written gmad (3 seeds) | 11.9 (39.2 MeV) | 0.82–0.86 (76.5–80.6 MeV) |
| SIMBA + BDSIM (3 runs) | 11.7–11.9 (40.2–41.5 MeV) | 0.84–0.87 (71.6–75.5 MeV) |
| SIMBA's gmad run directly in BDSIM (3 seeds) | | 0.86–0.92 (75.9–80.0 MeV) |

`crystal_channelling`, at the screen: the fraction of electrons within 0.15 mrad of the
0.9 mrad bend, which were channelled through the whole crystal. Without channelling it is
0.4%.

| | channelled | median x′ |
|---|---|---|
| hand-written gmad | 0.082 | 0.108 mrad |
| SIMBA + BDSIM | 0.093 | 0.107 mrad |

These agree within statistics (±0.006 on each fraction). The x′ rms values printed by the two
scripts differ in the wide-angle tails because they define x′ differently: SIMBA uses p_x/p_z,
while BDSIM's sampler uses p_x/|p|.

Known BDSIM issues these examples work around:

- The default steel beam pipe showers the wide-angle secondaries as well, so photons double
  between the target and the screen. `brems_target` and `positron_conversion` set
  `options: {beampipeMaterial: vacuum}`.
- With channelling physics, BDSIM records garbage particle weights (1e-41, 0). SIMBA takes
  each particle's weight from its own input beam instead.
