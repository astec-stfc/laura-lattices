# JFEL: JANUS FEL example machine

Not a real accelerator: an S-band linac FEL used as the example case for
[JANUS](https://github.com/astec-stfc/janus), and here as a test bed for
running the same lattice through many tracking codes with
[SIMBA](https://github.com/astec-stfc/simba) and
[LAURA](https://github.com/astec-stfc/laura).

HRRG gun + L01 (injector, ~35 MeV), L02/L03, the X-band linearizer L4H, the VBC
four-dipole chicane, L04-L09 (~577 MeV), the S13 matching section and a
10-segment undulator (FEL). A TDC sits in S07.

## Layouts

| Layout | Path |
|---|---|
| `JFELFULL` (default) | gun -> linac -> VBC -> linac -> S13 -> FEL |
| `SP2` | ... -> VBC -> S06 (to the 30 deg SP2 dipole) -> SP2 spectrometer |
| `SP3` | ... -> L04 -> S07 (with the TDC) -> SP3 spectrometer |

A `.def` picks a layout other than the default with a top-level
`default_layout: SP2` (SIMBA `feature/impactx` or later).

## Lattices and scripts

| File | What |
|---|---|
| `Lattices/jfel_combined.def` | ASTRA injector -> elegant linac -> Genesis (steady-state) FEL |
| `Lattices/jfel_linac_codes.def` | Linac + VBC + main linac from the saved injector beam to the undulator entrance |
| `Lattices/jfel_compression.def` | From the saved injector beam to just after the VBC (S06) |
| `Lattices/jfel_match_undulator.def` | Linac to S13, S13 matched into the undulator, and the undulator |
| `Lattices/jfel_fel.def` | Start-to-end FEL: linac (elegant, wakes + CSR) from the saved injector beam, then Genesis 4 steady-state (`FEL_ST`) or time-dependent (`FEL_TD`) |
| `Generators/make_injector_beam.py` | Runs the ASTRA injector (32768 particles) and saves `Data_Files/jfel_injector_S02.openpmd.hdf5`, the input to the two lattices above |
| `Scripts/run_example.py` | Runs any lattice; summarises the beam after each section (charge, energy, spread, emittance, size, length, peak current) |
| `Scripts/compare_codes.py` | `jfel_linac_codes` in several codes from the same beam, compared at every common screen (SIMBA's `test_jfel_code_comparison` as a script) |
| `Scripts/scan_compression.py` | Chicane angle x L4H phase scan of the compression |
| `Scripts/optimise_compression.py` | Nelder-Mead for a target peak current with a flat profile, checked in elegant with CSR |
| `Scripts/match_to_undulator.py` | Computes the undulator's periodic Twiss and matches S13 to it |
| `Scripts/run_fel.py` | Runs `jfel_fel`; reports wavelength, gain length, saturation and pulse energy, with the Ming Xie estimate |

```bash
python JFEL/Scripts/compare_codes.py --physics none --plot none.png
python JFEL/Scripts/compare_codes.py --physics csr --codes elegant ocelot impactx bmad
python JFEL/Scripts/scan_compression.py --plot scan.png
python JFEL/Scripts/optimise_compression.py --target 1000
python JFEL/Scripts/match_to_undulator.py
python JFEL/Scripts/run_fel.py --mode both
python JFEL/Scripts/run_example.py jfel_linac_codes --code Linac=ocelot --bc-angle 0.12
```

`--bc-angle` sets the chicane through SIMBA's `chicane.set_angle`, which also
lays out its geometry for the new angle, so every code -- including those that
follow the global geometry, such as Bmad -- sees the same chicane.

### Requirements

- ASTRA, elegant (and Genesis, OPAL, CSRTrack) through a container runtime:
  `--runtime docker` (default) or `apptainer`.
- Bmad: `export ACC_ROOT_DIR=<bmad-ecosystem>` so that
  `$ACC_ROOT_DIR/production/lib/libtao.so` is found (or `--libtao`).
- ImpactX CSR needs ImpactX built with FFT (`-DImpactX_FFT=ON`;
  `impactx.Config.have_fft`).
- Xsuite runs on the GPU when cupy is installed; `SIMBA_XSUITE_CONTEXT=cpu`
  keeps it on the CPU.

## Code comparison

From `Data_Files/jfel_injector_S02` (250 pC, 35 MeV, eps_n 0.81 um, 3 ps
flat-top) through to the undulator entrance, 68 screens in common. Values at
`JFEL-FEL-SIM-MARK-01`; "worst" is the largest difference between two codes
anywhere along the line.

### Single-particle optics (`--physics none`)

| Code | E [MeV] | dE [%] | eps_nx [um] | eps_ny [um] | sigma_x [um] | sigma_y [um] | sigma_z [um] |
|---|---|---|---|---|---|---|---|
| elegant | 576.9 | 0.056 | 0.762 | 0.798 | 49.3 | 40.6 | 82.7 |
| Ocelot | 576.8 | 0.075 | 0.762 | 0.812 | 48.5 | 40.1 | 88.2 |
| Cheetah | 576.8 | 0.069 | 0.762 | 0.797 | 48.4 | 39.5 | 86.7 |
| MAD-X | 576.7 | 0.070 | 0.762 | 0.798 | 48.5 | 39.5 | 87.1 |
| Xsuite | 576.8 | 0.057 | 0.756 | 0.814 | 49.1 | 40.4 | 82.9 |
| ImpactX | 576.8 | 0.074 | 0.756 | 0.796 | 48.6 | 39.6 | 87.6 |
| Bmad | 576.9 | 0.076 | 0.762 | 0.812 | 48.3 | 40.1 | 88.2 |

All seven agree to 0.2% in energy and a few percent in emittance and size
along the whole line. Two systematic differences remain:

- **Bunch length**: elegant and Xsuite compress ~6% more (sigma_z ~83 um) than
  the other five (86-88 um, which agree to ~1.5%), with a 0.1% energy offset
  -- consistent with a different RF model giving a slightly different chirp
  into the chicane.
- **Vertical emittance**: Ocelot, Xsuite and Bmad grow eps_ny by ~2% at the
  chicane (dipole edge/fringe treatment in y); the others do not.

### Collective effects

What each code models through SIMBA's switches (a code that does not model an
effect gives its single-particle result unchanged):

| Effect (`--physics`) | SIMBA switch | Modelled by |
|---|---|---|
| Structure wakes (`wakes`) | `wakefield_enable` | elegant, Ocelot |
| CSR (`csr`) | `csr_enable` (+ a `csr:` block for Ocelot) | elegant, Ocelot, ImpactX, Bmad |
| Longitudinal space charge (`lsc`) | `lsc_enable` | elegant, Ocelot |
| 3D space charge (`sc3d`) | `charge: space_charge_mode: 3d` | Ocelot, ImpactX, Bmad |

Values at the undulator entrance (MAD-X, no collective effects, for reference:
sigma_z 87.1 um, eps_nx 0.762 um, sigma_x 48.5 um, sigma_y 39.5 um):

| Effect | Code | dE [%] | eps_nx [um] | eps_ny [um] | sigma_x [um] | sigma_y [um] | sigma_z [um] |
|---|---|---|---|---|---|---|---|
| wakes | elegant | 0.146 | 0.762 | 0.792 | 49.5 | 40.6 | 48.2 |
| wakes | Ocelot | 0.118 | 0.759 | 0.806 | 48.6 | 39.5 | 55.3 |
| CSR | ImpactX | 0.067 | 1.68 | 0.796 | 81.5 | 39.6 | 85.9 |
| CSR | Bmad | 0.072 | 2.00 | 0.812 | 98.3 | 40.0 | 87.1 |
| CSR | elegant | 0.051 | 2.33 | 0.797 | 109.3 | 40.6 | 81.5 |
| CSR | Ocelot | 0.070 | 3.31 | 0.812 | 154.8 | 40.1 | 87.2 |
| LSC | elegant | 0.046 | 0.798 | 0.798 | 53.0 | 40.6 | 80.4 |
| LSC | Ocelot | 0.052 | 0.871 | 0.812 | 56.4 | 40.1 | 82.9 |
| 3D SC | Ocelot | 0.053 | 1.00 | 0.802 | 74.5 | 39.1 | 82.9 |
| 3D SC | ImpactX | 0.066 | 0.904 | 0.728 | 61.8 | 40.7 | 86.0 |
| 3D SC | Bmad | 0.059 | 1.06 | 0.729 | 74.6 | 33.9 | 84.8 |

- **Wakes** (S- and X-band structures) reduce the chirp and almost halve the
  bunch length; elegant and Ocelot agree to ~14%.
- **CSR** in the chicane triples the horizontal emittance. ImpactX, Bmad and
  elegant agree within ~20% (ImpactX: steady-state CSR in the bends; elegant
  and Bmad also downstream of them); Ocelot gives about twice ImpactX's growth
  and is the outlier.
- **3D space charge** matters for this 250 pC, 3 ps beam at 35-120 MeV: eps_nx
  grows 20-40% and the beam arrives at the undulator mismatched (sigma_x
  62-75 um against 48.5 um). The three codes agree to 10-25% along the line;
  ImpactX and Bmad both show eps_ny falling to 0.73 um (Ocelot: flat), and Bmad
  and Ocelot agree on sigma_x (ImpactX lower).

## Bunch compression

`scan_compression.py` (Ocelot, so the structure wakes are included), bunch
just after the chicane. The full-compression valley runs diagonally:

| Chicane angle [rad] | 0.105 | 0.110 | 0.115 | 0.120 | 0.125 | 0.130 | 0.135 | 0.140 |
|---|---|---|---|---|---|---|---|---|
| L4H phase at full compression [deg] | -200 | -200 | -195 | -190 | -185 | -180 | -175 | -170 |
| minimum sigma_t [fs] | 163 | 29 | 20 | 47 | 60 | 57 | 37 | 14 |

The nominal setting (0.13 rad, L4H -184 deg) is on the over-compressed side of
the valley: sigma_t ~190 fs, ~450 A after the chicane.

`optimise_compression.py --target 1000` (Ocelot) finds 0.12983 rad, L4H
-181.7 deg at 23.3 MV/m: 1010 A, sigma_t 88 fs, flat profile (spikiness 1.23).
Two lessons, both visible by re-running with other codes:

- **The model must include what shapes the compression.** Cheetah and MAD-X do
  not model the structure wakes; the same optimisation in Cheetah finds 871 A,
  which is a ~13 kA spike once the wakes are included (elegant). In Ocelot the
  optimum is 1388 A in elegant with CSR -- within ~40%.
- **The optimum sits on the edge of full compression**: a 1e-4 rad change in the
  chicane angle takes the peak current from 1 kA to 8 kA, so the optimiser
  stops on its iteration limit rather than converging, and any real operating
  point needs to be judged against that tolerance.

## Matching into the undulator

The undulator is a FODO lattice of 5 m cells (undulator segment, defocusing
quad, segment, focusing quad). Its helical segments (82 mm period, K = 8.52)
focus naturally in both planes, k_beta = K k_u / (sqrt(2) gamma) ~ 0.41 /m at
577 MeV, which the matched Twiss has to include.

`match_to_undulator.py` takes the periodic Twiss of the undulator from
Ocelot's transfer map, tracks the saved injector beam through the linac to
S13, and matches the four S13 quadrupoles to it with SIMBA's `match` block:

| | beta_x [m] | alpha_x | beta_y [m] | alpha_y |
|---|---|---|---|---|
| Undulator periodic Twiss (577.6 MeV) | 3.448 | +0.185 | 2.208 | -0.274 |
| Beam at the undulator entrance | 3.460 | +0.184 | 2.211 | -0.280 |
| Beam at the undulator exit | 3.461 | +0.181 | 2.204 | -0.283 |

S13 K1L = +1.168, -1.471, +0.732, -1.483 /m (~19 T/m), as now set in the
lattice. Every code delivers the matched beam to the undulator entrance
(`compare_codes.py --physics none`):

| Code | beta_x [m] | alpha_x | beta_y [m] | alpha_y | sigma_x [um] | sigma_y [um] |
|---|---|---|---|---|---|---|
| elegant | 3.60 | +0.182 | 2.33 | -0.270 | 49.3 | 40.6 |
| Ocelot | 3.48 | +0.180 | 2.24 | -0.297 | 48.5 | 40.1 |
| Cheetah | 3.47 | +0.184 | 2.21 | -0.238 | 48.4 | 39.5 |
| MAD-X | 3.49 | +0.179 | 2.21 | -0.234 | 48.5 | 39.5 |
| Xsuite | 3.60 | +0.168 | 2.27 | -0.339 | 49.1 | 40.4 |
| ImpactX | 3.52 | +0.181 | 2.22 | -0.250 | 48.5 | 39.6 |
| Bmad | 3.45 | +0.199 | 2.24 | -0.288 | 48.3 | 40.1 |

The match is made for the nominal compression (energy spread ~0.07% at the
undulator). A barely compressed beam (e.g. `--bc-angle 0.1`, ~0.9% spread)
grows its vertical emittance chromatically in the strong S13 focusing, to
~2.5 um, in every code alike.

## Start-to-end FEL

`run_fel.py` tracks the saved injector beam through the linac in elegant (with
the structure wakes and CSR) to the undulator entrance, then runs Genesis 4
through the ten undulator segments. The beam arrives at 575.6 MeV with ~560 A
peak current, eps_nx 3.8 um (CSR in the chicane), eps_ny 0.79 um.

| | lambda [um] | L_g [m] | saturation | power / pulse | run time |
|---|---|---|---|---|---|
| Ming Xie estimate (beam at the undulator) | 2.380 | 0.50 | | rho = 0.018 | |
| Genesis steady-state (1 kW seed) | 2.380 | 0.76 | 15.7 m | 1.3 GW (1.7 GW at the end) | seconds |
| Genesis time-dependent (SASE) | 2.380 | 0.66 | 15.2 m | 1.6 GW mean, 4.5 GW peak, ~1 mJ | ~1 min |

- The wavelength follows from K = 8.52 (helical), the 82 mm period and
  gamma = 1126: lambda = lambda_u (1 + K^2) / (2 gamma^2).
- Genesis' gain length is 30-50% longer than Ming Xie's, which treats the beam
  as round with averaged parameters; here the horizontal emittance is ~5x the
  vertical after CSR, and the projected horizontal optics carry the CSR
  correlations.
- The time-dependent run resolves every wavelength (`sample: 1`): the
  cooperation length, lambda / (4 pi sqrt(3) rho), is only ~8 wavelengths. The
  SASE pulse energy changes from run to run with the shot noise (0.8-1.2 mJ).
- Genesis settings are in the `fel:` block of each line (`steady_state`,
  `beam_type`, `npart`, `nbins`, `sample`, seed `field_power` and
  `waist_size`).

## Open items

- A reference CSR calculation (e.g. CSRTrack) for the chicane, to set against
  the spread between codes above.
- RF-structure wakefields in ImpactX (not modelled at present).
- Time-dependent Genesis: the simulation window is set by the imported bunch
  (~0.2 mm), shorter than the slippage over the undulator (~0.57 mm), so the
  radiation leaves the window ahead of the bunch after saturation. A window
  extended ahead of the bunch (Genesis' `settimewindow = false` with a longer
  `&time` window) would follow the pulse to the undulator exit.
