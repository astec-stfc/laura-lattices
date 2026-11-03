"""
A simulated energy-spectrum measurement at the JFEL plasma spectrometer, from
the beam that Scripts/run_plasma.py tracked to JFEL-PWA-DIA-SCR-01.

1. Camera image: the beam's charge on the screen, blurred by the screen and
   optics resolution, on the pixels of JFEL-PWA-DIA-CAM-01 (its LAURA sensor:
   pixel count, mm per pixel, bit depth), exposed to a given fraction of full
   scale, with photo-electron shot noise, a dark offset and read noise, then
   digitised and clipped. A dark frame (no beam) is taken the same way.
2. Analysis, as for real data: dark-frame subtraction, a region of interest
   about the beam in y, projection onto x, and x -> energy with the
   spectrometer calibration E = E_set / (1 - x / R16); the charge per count is
   taken as calibrated.
3. The measured spectrum and its moments against the tracked beam's.

    python JFEL/Scripts/run_plasma.py               # tracks the beam (~30 s)
    python JFEL/Scripts/measure_spectrum.py --plot  # measures it (seconds)
"""

import argparse
import os

import numpy as np
from scipy.ndimage import gaussian_filter

from run_plasma import ENTRANCE, EXIT, JFEL, R16, SCREEN, load

CAMERA = "JFEL-PWA-DIA-CAM-01"


def camera_image(x, y, q, sensor, resolution_mm, exposure, electrons_per_count,
                 offset, read_noise, rng):
    """Raw camera frame [counts] and the counts per coulomb, for charges q at (x, y) [m]."""
    nx, ny = sensor.x_pixels // sensor.x_scale_factor, sensor.y_pixels // sensor.y_scale_factor
    px = sensor.x_pixels_to_mm * sensor.x_scale_factor * 1e-3
    py = sensor.y_pixels_to_mm * sensor.y_scale_factor * 1e-3
    edges_x = (np.arange(nx + 1) - nx / 2) * px
    edges_y = (np.arange(ny + 1) - ny / 2) * py
    ideal, _, _ = np.histogram2d(y, x, bins=[edges_y, edges_x], weights=q)
    ideal = gaussian_filter(ideal, [resolution_mm * 1e-3 / py, resolution_mm * 1e-3 / px])
    full = 2 ** sensor.bit_depth - 1
    per_coulomb = exposure * (full - offset) / ideal.max()
    signal = rng.poisson(ideal * per_coulomb * electrons_per_count) / electrons_per_count
    raw = np.clip(np.round(signal + offset + rng.normal(0, read_noise, ideal.shape)), 0, full)
    dark = np.clip(np.round(offset + rng.normal(0, read_noise, ideal.shape)), 0, full)
    centres_x = 0.5 * (edges_x[1:] + edges_x[:-1])
    centres_y = 0.5 * (edges_y[1:] + edges_y[:-1])
    return raw, dark, per_coulomb, centres_x, centres_y, edges_x


def moments(e, w):
    """Charge-weighted mean, rms, and the 1% / 99% points of a spectrum."""
    mean = np.average(e, weights=w)
    rms = np.sqrt(np.average((e - mean) ** 2, weights=w))
    order = np.argsort(e)
    cdf = np.cumsum(w[order]) / np.sum(w)
    return mean, rms, *np.interp([0.01, 0.99], cdf, e[order])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", default="jfel_plasma", help="run_plasma.py's output directory")
    parser.add_argument("--resolution", type=float, default=0.1, help="screen + optics rms resolution [mm]")
    parser.add_argument("--exposure", type=float, default=0.8, help="peak pixel as a fraction of full scale")
    parser.add_argument("--electrons-per-count", type=float, default=2.0)
    parser.add_argument("--offset", type=float, default=100.0, help="dark offset [counts]")
    parser.add_argument("--read-noise", type=float, default=3.0, help="rms [counts]")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--plot", action="store_true", help="save measure_spectrum.png in --dir")
    args = parser.parse_args()

    import simba.Framework as fw

    directory = os.path.abspath(args.dir)
    f = fw.Framework(master_lattice=JFEL + "/", directory=directory, clean=False, verbose=False)
    f.loadSettings("Lattices/jfel_plasma.def")
    sensor = f.getElement(CAMERA).diagnostic.sensor

    beam = load(directory, SCREEN)
    x, y = np.asarray(beam.x.val), np.asarray(beam.y.val)
    q = np.abs(np.asarray(beam.Particles.charge.val))
    e_true = np.asarray(beam.cp.val) * 1e-6
    e_in = float(np.mean(load(directory, ENTRANCE).cp.val)) * 1e-6
    e_set = float(np.mean(load(directory, EXIT).cp.val)) * 1e-6   # the dipole's set energy

    rng = np.random.default_rng(args.seed)
    raw, dark, per_coulomb, cx, cy, edges_x = camera_image(
        x, y, q, sensor, args.resolution, args.exposure, args.electrons_per_count,
        args.offset, args.read_noise, rng)

    # --- the analysis sees only raw, dark and the calibrations ---
    image = raw - dark
    profile_y = np.clip(image.sum(axis=1), 0, None)
    y0 = np.average(cy, weights=profile_y)
    sy = np.sqrt(np.average((cy - y0) ** 2, weights=profile_y))
    roi = np.abs(cy - y0) < 4 * sy
    counts_x = image[roi].sum(axis=0)
    e_edges = e_set / (1 - edges_x / R16)
    e_pix = 0.5 * (e_edges[1:] + e_edges[:-1])
    q_pix = counts_x / per_coulomb                       # [C] per pixel column
    dqde = q_pix / np.abs(np.diff(e_edges))              # [C / MeV]
    w = np.clip(q_pix, 0, None)

    full = 2 ** sensor.bit_depth - 1
    seen = (np.abs(x) < cx[-1]) & (np.abs(y) < cy[-1])
    print(f"camera {raw.shape[1]} x {raw.shape[0]} px, {sensor.x_pixels_to_mm} mm/px, "
          f"{sensor.bit_depth} bit; peak {raw.max():.0f} / {full} counts, "
          f"{np.sum(raw >= full)} saturated px; ROI |y - {y0 * 1e3:.2f} mm| < {4 * sy * 1e3:.1f} mm; "
          f"{100 * np.sum(q[seen]) / np.sum(q):.1f}% of the charge in the field of view")
    print(f"energy per pixel: {np.abs(np.diff(e_edges)).min():.3f}-{np.abs(np.diff(e_edges)).max():.3f} MeV "
          f"(dipole set to {e_set:.1f} MeV, R16 {R16} m)")

    m_meas = moments(e_pix, w)
    m_true = moments(e_true, q)
    acc_meas = np.sum(w[e_pix > e_in]) * 1e12
    acc_true = np.sum(q[e_true > e_in]) * 1e12
    print(f"\n{'':24s}{'measured':>10s}{'tracked':>10s}")
    for label, a, b in (("charge [pC]", np.sum(q_pix) * 1e12, np.sum(q) * 1e12),
                        ("mean energy [MeV]", m_meas[0], m_true[0]),
                        ("rms spread [MeV]", m_meas[1], m_true[1]),
                        ("1% point [MeV]", m_meas[2], m_true[2]),
                        ("99% point [MeV]", m_meas[3], m_true[3]),
                        (f"charge > {e_in:.0f} MeV [pC]", acc_meas, acc_true)):
        print(f"{label:24s}{a:10.1f}{b:10.1f}")

    if args.plot:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(2, 1, figsize=(8, 7), sharex=True,
                               gridspec_kw={"height_ratios": [1, 1.4]})
        order = np.argsort(e_pix)
        ax[0].pcolormesh(e_pix[order], cy * 1e3, np.clip(image, 1, None)[:, order],
                         norm="log", cmap="viridis", shading="auto")
        ax[0].axhspan((y0 - 4 * sy) * 1e3, (y0 + 4 * sy) * 1e3, fill=False, ec="w", ls="--")
        ax[0].set(ylabel="y [mm]", ylim=(-8, 8), title=f"{CAMERA} (dark-subtracted, log scale)")
        ax[1].plot(e_pix[order], dqde[order] * 1e12, lw=0.8, label="measured")
        h, he = np.histogram(e_true, bins=200, weights=q)
        ax[1].stairs(h / np.diff(he) * 1e12, he, label="tracked", color="k", alpha=0.6)
        ax[1].axvline(e_in, color="grey", ls=":", label="plasma entrance energy")
        ax[1].set(xlabel="E [MeV]", ylabel="dQ/dE [pC / MeV]", xlim=(440, 720))
        ax[1].legend()
        fig.tight_layout()
        fig.savefig(os.path.join(directory, "measure_spectrum.png"), dpi=150)


if __name__ == "__main__":
    main()
