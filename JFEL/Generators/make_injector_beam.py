"""
Track the JFEL injector (HRRG gun + L01, ASTRA with 2D space charge from the
cathode) and save its output at JFEL-S02-SIM-APER-01 as
Data_Files/jfel_injector_S02.openpmd.hdf5, the incoming beam for the JFEL
examples downstream of the injector -- so they need neither ASTRA nor a
container runtime.

    python JFEL/Generators/make_injector_beam.py [--particles 32768] [--runtime docker]
"""

import argparse
import os
import shutil

import simba.Framework as fw

JFEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(JFEL, "Data_Files", "jfel_injector_S02.openpmd.hdf5")

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--particles", type=int, default=32768)
parser.add_argument("--runtime", default="docker", help="docker, apptainer, or none (local ASTRA)")
parser.add_argument("--seed", type=int, default=1234)
parser.add_argument("--dir", default="jfel_injector")
args = parser.parse_args()

f = fw.Framework(
    master_lattice=JFEL + "/",
    generator_defaults="/jfel.yaml",
    directory=os.path.abspath(args.dir),
    clean=True,
    verbose=True,
    container_runtime=None if args.runtime.lower() == "none" else args.runtime,
)
f.loadSettings("Lattices/jfel_combined.def")
f["generator"].number_of_particles = args.particles
f.setSeedValue(args.seed)
f.track(endfile="injector400")

shutil.copy(os.path.join(f.subdirectory, "JFEL-S02-SIM-APER-01.openpmd.hdf5"), OUTPUT)
print(f"wrote {OUTPUT}")
