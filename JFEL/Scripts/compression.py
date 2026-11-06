"""
Shared set-up for the JFEL compression scripts: a SIMBA framework for
Lattices/jfel_compression.def that can be re-tracked with a different chicane
angle and linearizer (L4H) setting, and the longitudinal figures of merit.
"""

import os

import numpy as np

JFEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L4H = "JFEL-L4H-LIN-CAV-01"
END = "JFEL-S06-SIM-MARK-01"


class Compressor:
    """Track the Compressor line for given chicane / L4H settings."""

    def __init__(self, directory, code="cheetah", runtime="docker", csr=None):
        import simba.Framework as fw

        self.directory = os.path.abspath(directory)
        runtime = None if str(runtime).lower() == "none" else runtime
        self.f = fw.Framework(master_lattice=JFEL + "/", directory=self.directory,
                              clean=True, verbose=False, container_runtime=runtime)
        self.f.loadSettings("Lattices/jfel_compression.def")
        if code != "cheetah":
            self.f.change_Lattice_Code("Compressor", code)
        if csr is not None:
            line = self.f.latticeObjects["Compressor"]
            line.csr_enable = csr
            if csr:
                # SIMBA's Ocelot only adds CSR when the line also has a `csr:`
                # block; other codes need only csr_enable.
                line.file_block.setdefault("csr", {})
        cavity = self.f.getElement(L4H)
        self.nominal = {
            "angle": float(self.f["bunch_compressor"].angle),
            "l4h_phase": float(cavity.phase),
            "l4h_amplitude": float(cavity.field_amplitude),
        }

    def track(self, angle=None, l4h_phase=None, l4h_amplitude=None):
        """Track with the given settings (None keeps the nominal); return figures of merit."""
        angle = self.nominal["angle"] if angle is None else angle
        phase = self.nominal["l4h_phase"] if l4h_phase is None else l4h_phase
        amplitude = self.nominal["l4h_amplitude"] if l4h_amplitude is None else l4h_amplitude
        self.f["bunch_compressor"].set_angle(float(angle))
        self.f.modifyElement(L4H, "phase", float(phase))
        self.f.modifyElement(L4H, "field_amplitude", float(amplitude))
        self.f.track(files=["Compressor"], check_lattice=False)
        merit = figures_of_merit(os.path.join(self.directory, f"{END}.openpmd.hdf5"))
        merit.update(angle=angle, l4h_phase=phase, l4h_amplitude=amplitude)
        return merit


def figures_of_merit(path, bins=200):
    """Charge, energy, spread, rms length, peak current and flatness of a beam."""
    import simba.Modules.Beams as rbf

    beam = rbf.load_file(path)
    q = np.abs(np.asarray(beam.Particles.charge.val))
    t = np.asarray(beam.t.val)
    energy = beam.cp.val / 1e6
    mean_e = np.average(energy, weights=q)
    sigma_t = np.sqrt(np.cov(t, aweights=q))
    counts, edges = np.histogram(t, bins=bins, weights=q)
    # Light smoothing so single noisy bins do not set the peak.
    current = np.convolve(counts / (edges[1] - edges[0]), np.ones(3) / 3, mode="same")
    peak = current.max()
    # A flat-top of the same rms length has I = Q / (sqrt(12) sigma_t).
    flat = q.sum() / (np.sqrt(12) * sigma_t)
    return {
        "charge_pC": q.sum() * 1e12,
        "energy_MeV": mean_e,
        "spread_pct": 100 * np.sqrt(np.cov(energy, aweights=q)) / mean_e,
        "sigma_t_fs": sigma_t * 1e15,
        "peak_current_A": peak,
        "spikiness": peak / flat,   # 1 for a flat-top; > 1 for a spike
    }
