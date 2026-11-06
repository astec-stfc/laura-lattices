"""
Linear optics of the ERL, from Ocelot transfer maps of each section
(Lattices/erl_sections.def, translated by SIMBA/LAURA):

1. Linac: the Twiss at its entrance for which the first, accelerating pass
   delivers a waist (alpha 0, beta --arc-beta) at its exit, found by taking
   that waist back through the linac's transfer map.
2. Injector: four quadrupoles match the injected beam (beta 5 m, alpha 0)
   to it.
3. Arcs: the five quadrupole families minimise the peak beta in the arc,
   subject to it being achromatic (D' = 0 at its centre, so D = D' = 0 at
   its exit), isochronous (R56 = 0), and symmetric in its optics (alpha = 0
   at its centre, so it hands the beam on as the mirror image).
   Then the two sextupole families make it a second-order achromat:
   T566 = 0 and T166 = 0, from second-order tracking at momentum offsets.
4. Return straight: its three quadrupole families minimise the peak beta
   with alpha = 0 at its centre, which makes the racetrack mirror-symmetric: the beam re-enters
   the linac with the mirror image of the Twiss it left with, and, the
   decelerating pass being the accelerating one run backwards, leaves it
   for the dump with the injected optics.
5. With --fel, the FEL return straight (ERL_FEL layout): its four families
   match the beam into the undulator's own (helical) focusing, and, being
   mirror-symmetric, hand it on as the mirror image too.

    python ERL/Scripts/match_erl.py
    python ERL/Scripts/match_erl.py --fel

Prints the K1L to put in elements.yaml, and the Twiss at every section exit.
"""

import argparse
import os

import numpy as np
from scipy.optimize import fsolve, least_squares, minimize

ERL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P_INJ, P_TOP = 10e6, 100e6   # [eV/c]
TWISS_INJ = dict(beta_x=5.0, alpha_x=0.0, beta_y=5.0, alpha_y=0.0)
INJ = [f"ERL-INJ-MAG-QUAD-0{i}" for i in range(1, 5)]
ARC = [f"ERL-ARC1-MAG-QUAD-0{i}" for i in range(1, 6)]
RET = [f"ERL-RET-MAG-QUAD-0{i}" for i in range(1, 4)]
RETF = [f"ERL-RETF-MAG-QUAD-0{i}" for i in range(1, 5)]
SEXT = ["ERL-ARC1-MAG-SEXT-01", "ERL-ARC1-MAG-SEXT-02"]
LINES = (("INJ", P_INJ), ("LIN1", P_INJ), ("ARC1", P_TOP), ("RET", P_TOP),
         ("ARC2", P_TOP), ("LIN2", P_TOP), ("DMP", P_INJ))


class Optics:
    """Ocelot lattices of the ERL's sections, translated once by SIMBA/LAURA;
    a quadrupole family is set on every copy (repeats in a section, ARC2's
    inherited quadrupoles) directly on the Ocelot elements."""

    def __init__(self, f):
        self.f = f
        self.lattices = {}
        self.k1l = {}   # element base name -> K1L, applied to every lattice

    def set(self, family, k1l):
        base = family.replace("ARC1", "ARC{}")
        for name in ({base.format(1), base.format(2)} if "{}" in base else {family}):
            self.k1l[name] = float(k1l)
        for lat in self.lattices.values():
            self._apply(lat)

    def get(self, family):
        line = family.split("-")[1]    # ERL-<SECTION>-MAG-QUAD-0N
        lat = self.lattice(line, P_INJ if line == "INJ" else P_TOP)
        element = next(e for e in lat.sequence if e.id.split(".")[0] == family)
        return (element.k2 if "SEXT" in family else element.k1) * element.l

    def _apply(self, lat):
        """Set every family on `lat`: K1L on quadrupoles, K2L on sextupoles."""
        for element in lat.sequence:
            value = self.k1l.get(element.id.split(".")[0])
            if value is not None:
                if "SEXT" in element.id:
                    element.k2 = value / element.l
                else:
                    element.k1 = value / element.l
        lat.update_transfer_maps()

    def second_order(self, line, p0, deltas=(-0.02, -0.01, 0.0, 0.01, 0.02)):
        """(T566, T166, T266) of `line`, fitted to second-order tracking of
        on-axis particles at momentum offsets `deltas`."""
        from ocelot.cpbd.beam import ParticleArray
        from ocelot.cpbd.magnetic_lattice import MagneticLattice
        from ocelot.cpbd.track import track
        from ocelot.cpbd.transformations.second_order import SecondTM

        lat = MagneticLattice(self.lattice(line, p0).sequence, method={"global": SecondTM})
        p = ParticleArray(len(deltas))
        p.E = self.energy(p0)
        p.rparticles[:] = 0.0
        p.rparticles[5] = deltas
        track(lat, p, print_progress=False)
        return np.array([np.polyfit(deltas, p.rparticles[i], 2)[0] for i in (4, 0, 1)])

    def lattice(self, line, p0):
        """A line's Ocelot lattice, or a machine section's if no line is called that."""
        if line not in self.lattices:
            if line in self.f.latticeObjects:
                section = self.f.latticeObjects[line].section
            else:
                from laura.translator.converters.section import SectionLatticeTranslator

                section = SectionLatticeTranslator.from_section(self.f.machine.sections[line])
            self.lattices[line] = section.to_ocelot(Brho=p0 / 299792458.0)
            self._apply(self.lattices[line])
        return self.lattices[line]

    @staticmethod
    def energy(p0):
        return np.hypot(p0, 0.51099895e6) * 1e-9

    def twiss(self, line, p0, start):
        """Twiss along `line` from `start` (dict); a list of Ocelot Twiss."""
        from ocelot.cpbd.beam import Twiss
        from ocelot.cpbd.optics import twiss

        return twiss(self.lattice(line, p0), Twiss(**start, E=self.energy(p0)))

    def r(self, line, p0):
        from ocelot.cpbd.optics import lattice_transfer_map

        return lattice_transfer_map(self.lattice(line, p0), energy=self.energy(p0))


def end(tws):
    t = tws[-1]
    return dict(beta_x=t.beta_x, alpha_x=t.alpha_x, beta_y=t.beta_y, alpha_y=t.alpha_y)


def at(tws, marker):
    return next(t for t in tws if t.id == marker)


def peak(tws):
    return max(max(t.beta_x, t.beta_y) for t in tws)


def back_through(r, beta, alpha):
    """Twiss (beta, alpha) at the entrance of a 2x2 map `r` (which may change
    the energy) that gives (beta, alpha) at its exit."""
    gamma = (1 + alpha ** 2) / beta
    sigma_out = np.array([[beta, -alpha], [-alpha, gamma]])
    rinv = np.linalg.inv(r)
    sigma = rinv @ sigma_out @ rinv.T
    sigma /= np.sqrt(np.linalg.det(sigma))
    return sigma[0, 0], -sigma[0, 1]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--arc-beta", type=float, default=10.0, help="beta of the waist at the linac exit [m]")
    parser.add_argument("--fel", action="store_true", help="also match the FEL return straight (ERL_FEL)")
    args = parser.parse_args()

    import simba.Framework as fw

    f = fw.Framework(master_lattice=ERL + "/", directory=os.path.abspath("erl_match"),
                     clean=True, verbose=False)
    f.loadSettings("Lattices/erl_sections.def")
    o = Optics(f)
    k = {}

    # 1. linac entrance Twiss for a waist at its exit
    r = o.r("LIN1", P_INJ)
    bx, ax = back_through(r[:2, :2], args.arc_beta, 0.0)
    by, ay = back_through(r[2:4, 2:4], args.arc_beta, 0.0)
    target = np.array([bx, ax, by, ay])

    # 2. injector -> linac entrance
    def inj(x):
        for n, v in zip(INJ, x):
            o.set(n, v)
        t = end(o.twiss("INJ", P_INJ, TWISS_INJ))
        return np.array([t["beta_x"], t["alpha_x"], t["beta_y"], t["alpha_y"]]) - target

    rng = np.random.default_rng(0)
    starts = [[o.get(n) for n in INJ]] + [rng.uniform(-3, 3, 4) for _ in range(30)]
    best = min((least_squares(inj, x0, xtol=1e-14, ftol=1e-14) for x0 in starts),
               key=lambda res: (res.cost, np.sum(res.x ** 2)))
    if best.cost > 1e-12:
        raise RuntimeError(f"injector not matched: residual {inj(best.x)}")
    inj(best.x)
    k.update(zip(INJ, best.x))
    arc_in = end(o.twiss("LIN1", P_INJ, end(o.twiss("INJ", P_INJ, TWISS_INJ))))

    # 3. arcs: lowest peak beta, achromatic, isochronous, alpha = 0 at the centre
    def arc(x):
        for n, v in zip(ARC, x):
            o.set(n, v)
        return o.twiss("ARC1", P_TOP, arc_in)

    def arc_conditions(x):
        mid = at(arc(x), "ERL-ARC1-SIM-MID-01")
        return np.array([mid.Dxp, o.r("ARC1", P_TOP)[4, 5], mid.alpha_x, mid.alpha_y])

    x0 = np.array([o.get(n) for n in ARC])
    sols = []
    for trial in range(6):
        res = minimize(lambda x: peak(arc(x)), x0 + (rng.normal(0, 0.3, len(x0)) if trial else 0),
                       method="SLSQP", constraints=[{"type": "eq", "fun": arc_conditions}],
                       options=dict(maxiter=500, ftol=1e-10))
        if np.max(np.abs(arc_conditions(res.x))) < 1e-8:
            sols.append((peak(arc(res.x)), tuple(res.x)))
    if not sols:
        raise RuntimeError("no achromatic, isochronous, symmetric arc found")
    x = min(sols)[1]
    arc(x)
    k.update(zip(ARC, x))

    # 3b. arcs, second order: the sextupoles make T566 = 0 (isochronous to
    # second order) and close the second-order dispersion (T166 = 0)
    def arc_second_order(x):
        for n, v in zip(SEXT, x):
            o.set(n, v)
        return o.second_order("ARC1", P_TOP)[:2]

    x = fsolve(arc_second_order, [o.get(n) for n in SEXT] if any(o.get(n) for n in SEXT) else [50.0, 300.0],
               xtol=1e-12)
    if np.max(np.abs(arc_second_order(x))) > 1e-6:
        raise RuntimeError("the sextupoles could not make the arc a second-order achromat")
    k.update(zip(SEXT, x))

    # 4. return straight: alpha = 0 at its centre
    ret_in = end(o.twiss("ARC1", P_TOP, arc_in))

    def ret(x):
        for n, v in zip(RET, x):
            o.set(n, v)
        return o.twiss("RET", P_TOP, ret_in)

    def ret_conditions(x):
        mid = at(ret(x), "ERL-RET-SIM-MID-01")
        return np.array([mid.alpha_x, mid.alpha_y])

    sols = []
    for guess in [[o.get(n) for n in RET]] + [rng.uniform(-1, 1, len(RET)) for _ in range(10)]:
        res = minimize(lambda x: peak(ret(x)), guess, method="SLSQP",
                       constraints=[{"type": "eq", "fun": ret_conditions}], options=dict(ftol=1e-10))
        if np.max(np.abs(ret_conditions(res.x))) < 1e-8:
            sols.append((peak(ret(res.x)), tuple(res.x)))
    if not sols:
        raise RuntimeError("no mirror-symmetric return straight found")
    x = min(sols)[1]
    ret(x)
    k.update(zip(RET, x))

    # 5. the FEL return straight (ERL_FEL): matched into the undulator's own
    # focusing; mirror-symmetric, so the beam leaves as it came in
    if args.fel:
        from ocelot.cpbd.beam import Twiss
        from ocelot.cpbd.magnetic_lattice import MagneticLattice
        from ocelot.cpbd.optics import lattice_transfer_map, periodic_twiss

        ids = [e.id for e in o.lattice("RETF", P_TOP).sequence]
        half = MagneticLattice(o.lattice("RETF", P_TOP).sequence[
            ids.index("ERL-RETF-SIM-MARK-01"):ids.index("ERL-RETF-SIM-MID-01")])
        t0 = Twiss()
        t0.E = o.energy(P_TOP)
        und = periodic_twiss(t0, lattice_transfer_map(half, energy=o.energy(P_TOP)))
        target = np.array([und.beta_x, und.alpha_x, und.beta_y, und.alpha_y])
        print(f"undulator matched Twiss: beta_x {und.beta_x:.3f} alpha_x {und.alpha_x:+.3f} "
              f"beta_y {und.beta_y:.3f} alpha_y {und.alpha_y:+.3f}")

        def retf(x):
            for n, v in zip(RETF, x):
                o.set(n, v)
            return o.twiss("RETF", P_TOP, ret_in)

        def retf_conditions(x):
            t = at(retf(x), "ERL-RETF-SIM-MARK-01")
            return np.array([t.beta_x, t.alpha_x, t.beta_y, t.alpha_y]) - target

        sols = []
        for guess in [[o.get(n) for n in RETF]] + [rng.uniform(-3, 3, len(RETF)) for _ in range(30)]:
            res = least_squares(retf_conditions, guess, xtol=1e-14, ftol=1e-14)
            if np.max(np.abs(retf_conditions(res.x))) < 1e-8:
                sols.append((peak(retf(res.x)), np.max(np.abs(res.x)), tuple(res.x)))
        if not sols:
            raise RuntimeError("the FEL return straight could not be matched")
        x = min(sols)[2]
        retf(x)
        k.update(zip(RETF, x))

    print("K1L [1/m] (quadrupoles) and K2L [1/m^2] (sextupoles) for elements.yaml:")
    for name, v in k.items():
        print(f"  {name}: {v:.5f}")
    print("\nTwiss at each section exit (beta_x alpha_x beta_y alpha_y), peak beta, D, D':")
    t = TWISS_INJ
    for line, p0 in LINES:
        line = "RETF" if (args.fel and line == "RET") else line
        tws = o.twiss(line, p0, t)
        t = end(tws)
        print(f"  {line:5s} {t['beta_x']:7.3f} {t['alpha_x']:+7.3f} {t['beta_y']:7.3f} {t['alpha_y']:+7.3f}"
              f"   peak {peak(tws):6.1f} m   D {tws[-1].Dx:+.1e} D' {tws[-1].Dxp:+.1e}")
    t566, t166, t266 = o.second_order("ARC1", P_TOP)
    print(f"  arc R56 {o.r('ARC1', P_TOP)[4, 5]:+.1e} m, T566 {t566:+.1e} m, T166 {t166:+.1e} m, T266 {t266:+.1e}")


if __name__ == "__main__":
    main()
