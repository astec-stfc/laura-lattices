import os

dirname = os.path.dirname(os.path.abspath(__file__))

layout = os.path.join(dirname, "layouts.yaml")
section = os.path.join(dirname, "sections.yaml")
element_list = os.path.join(dirname, "YAML")
data_files = os.path.join(dirname, "Data_Files")
generators = os.path.join(dirname, "Generators/jfel.yaml")
lattices = os.path.join(dirname, "Lattices")
