"""
Track the ERL (Lattices/erl.def) from the injected beam to the dump, in one or
more codes, and summarise both passes through the linac and the energy
recovery.

    python ERL/Scripts/run_erl.py                          # elegant and Ocelot, no CSR/SR
    python ERL/Scripts/run_erl.py --physics all            # CSR and synchrotron radiation
    python ERL/Scripts/run_erl.py --codes elegant --scan-phase -10 -5 0 5 10
    python ERL/Scripts/run_erl.py --plot erl.png

--scan-phase shifts the return pass's RF phase from 180 deg (a recirculation
path a little off (n + 1/2) RF wavelengths) and reports what reaches the dump.
"""

import argparse
import os

import numpy as np

ERL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POINTS = {
    "injected": "ERL-LIN-SIM-START-01.1",
    "top (linac exit, pass 1)": "ERL-LIN-SIM-END-01.1",
    "return (linac entrance, pass 2)": "ERL-LIN-SIM-START-01.2",
    "dump (linac exit, pass 2)": "ERL-LIN-SIM-END-01.2",
    "dump screen": "ERL-DMP-DIA-SCR-01",
}
PHYSICS = {
    "none": dict(csr=False, radiation="off"),
    "csr": dict(csr=True, radiation="off"),
    "all": dict(csr=True, radiation="quantum"),
}


def run(code, physics, directory, phase_offset=0.0, runtime="docker", libtao=None):
    """Track the ERL (racetrack and dump line, both in `code`); returns {point: beam}."""
    import simba.Framework as fw
    import simba.Modules.Beams as rbf

    f = fw.Framework(master_lattice=ERL + "/", directory=directory, clean=True,
                     verbose=False, container_runtime=runtime)
    if libtao:
        f.executables.define_tao_command(location=[libtao])
    native = code == "bmad_native"     # Bmad multipass: one line, the whole path
    f.loadSettings("Lattices/erl_bmad_multipass.def" if native else "Lattices/erl.def")
    settings = PHYSICS[physics]
    for name in f.latticeObjects:
        if not native:
            f.change_Lattice_Code(name, code)
        line = f.latticeObjects[name]
        line.csr_enable = settings["csr"]
        if settings["csr"]:
            line.file_block.setdefault("csr", {})      # Ocelot adds CSR only with a csr: block
        line.file_block.setdefault("tracking", {})["radiation"] = settings["radiation"]
    if phase_offset:
        for name, element in f.latticeObjects["ERL"].elements.items():
            if name.startswith("ERL-LIN-RF-CAV") and name.endswith(".2"):
                element.cavity.phase = 180.0 + phase_offset
    f.track(check_lattice=False)
    return {label: rbf.load_file(os.path.join(directory, f"{name}.openpmd.hdf5"))
            for label, name in POINTS.items()}


def stats(beam):
    p = np.asarray(beam.cp.val) * 1e-6
    return dict(p=float(np.mean(p)), dp=float(np.std(p) / np.mean(p)),
                enx=beam.normalized_horizontal_emittance * 1e6,
                eny=beam.normalized_vertical_emittance * 1e6,
                sx=beam.Sx * 1e3, sy=beam.Sy * 1e3, st=float(np.std(beam.t.val)) * 1e12,
                s=float(np.atleast_1d(beam.s)[0]), q=abs(float(beam.Q)) * 1e12)


def recovery(beams):
    """Energy given by the RF on pass 1, taken back on pass 2 (mean momenta, MeV/c)."""
    s = {k: stats(b) for k, b in beams.items()}
    gained = s["top (linac exit, pass 1)"]["p"] - s["injected"]["p"]
    returned = s["return (linac entrance, pass 2)"]["p"] - s["dump (linac exit, pass 2)"]["p"]
    return gained, returned


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--codes", nargs="+", default=["elegant", "ocelot"],
                        help="elegant, ocelot, bmad, impactx, madx, xsuite, or bmad_native (Bmad multipass)")
    parser.add_argument("--physics", choices=PHYSICS, default="none")
    parser.add_argument("--scan-phase", nargs="+", type=float, default=None,
                        help="return-pass phase offsets from 180 deg [deg]")
    parser.add_argument("--dir", default="erl")
    parser.add_argument("--runtime", default="docker")
    parser.add_argument("--plot", default=None, help="save momentum and beam size along the path")
    acc_root = os.environ.get("ACC_ROOT_DIR")
    parser.add_argument("--libtao", default=os.path.join(acc_root, "production", "lib", "libtao.so") if acc_root else None,
                        help="Bmad's libtao.so (default: $ACC_ROOT_DIR/production/lib/libtao.so)")
    args = parser.parse_args()
    runtime = None if args.runtime.lower() == "none" else args.runtime

    results = {}
    for code in args.codes:
        beams = run(code, args.physics, os.path.abspath(os.path.join(args.dir, code)), runtime=runtime,
                    libtao=args.libtao)
        results[code] = beams
        print(f"\n{code} ({args.physics}):")
        print(f"  {'':34s}{'p [MeV/c]':>10s}{'dp/p':>10s}{'enx':>7s}{'eny':>7s}{'sx':>7s}{'sy':>7s}{'st':>7s}")
        print(f"  {'':34s}{'':>10s}{'':>10s}{'[um]':>7s}{'[um]':>7s}{'[mm]':>7s}{'[mm]':>7s}{'[ps]':>7s}")
        for label, beam in beams.items():
            s = stats(beam)
            print(f"  {label:34s}{s['p']:10.3f}{s['dp']:10.2e}{s['enx']:7.3f}{s['eny']:7.3f}"
                  f"{s['sx']:7.3f}{s['sy']:7.3f}{s['st']:7.3f}")
        gained, returned = recovery(beams)
        top, dump = stats(beams["top (linac exit, pass 1)"])["p"], stats(beams["dump (linac exit, pass 2)"])["p"]
        print(f"  RF gives {gained:.3f} MeV/c on pass 1 and takes back {returned:.3f} on pass 2 "
              f"({100 * returned / gained:.3f}%); the dump gets {dump:.3f} MeV/c, "
              f"{100 * dump / top:.1f}% of the top energy")

    if args.scan_phase:
        print("\nreturn-pass phase scan (dump):")
        print(f"  {'code':8s}{'offset [deg]':>13s}{'p [MeV/c]':>11s}{'dp/p':>10s}{'recovered':>11s}")
        for code in args.codes:
            for offset in args.scan_phase:
                beams = run(code, args.physics, os.path.abspath(os.path.join(args.dir, f"{code}_scan")),
                            phase_offset=offset, runtime=runtime, libtao=args.libtao)
                s = stats(beams["dump (linac exit, pass 2)"])
                gained, returned = recovery(beams)
                print(f"  {code:8s}{offset:13.1f}{s['p']:11.3f}{s['dp']:10.2e}{100 * returned / gained:10.2f}%")

    if args.plot:
        import glob

        import matplotlib.pyplot as plt
        import simba.Modules.Beams as rbf

        fig, ax = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
        for code in args.codes:
            rows = sorted((stats(rbf.load_file(fn)) for fn in
                           glob.glob(os.path.join(args.dir, code, "*.openpmd.hdf5"))), key=lambda r: r["s"])
            s = [r["s"] for r in rows]
            ax[0].plot(s, [r["p"] for r in rows], "o-", ms=3, label=code)
            ax[1].plot(s, [r["sx"] for r in rows], "o-", ms=3, label=f"{code} x")
            ax[1].plot(s, [r["sy"] for r in rows], "s--", ms=3, label=f"{code} y")
        ax[0].set(ylabel="p [MeV/c]", title=f"ERL ({args.physics})")
        ax[1].set(xlabel="s along the beam path [m]", ylabel="rms size [mm]")
        ax[0].legend()
        ax[1].legend(ncol=2)
        fig.tight_layout()
        fig.savefig(args.plot, dpi=150)


if __name__ == "__main__":
    main()
