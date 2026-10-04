from kicad_spice_circuit_processer import KiCadSPICECircuitProcesser
import os

# Original PCB-QA SPICE circuit
input_cir = "Boards/stack-chan/Input_Files/m5-pantilt.cir"

# Keep generated files separate from the original PCB-QA files
output_dir = "outputs/spice_reproduction"
os.makedirs(output_dir, exist_ok=True)

# Create the PCB-QA SPICE processor
processor = KiCadSPICECircuitProcesser(
    spice_circuit_path=input_cir,
    output_dir=output_dir,
    project_name=None,
    output_file=None
)

# Use the existing PCB-QA conversion function
processor.convert_project_spice_to_circuit(
    "m5-pantilt_generated"
)

print("Simulation-ready SPICE circuit generated.")
print("Output: outputs/spice_reproduction/m5-pantilt_generated.cir")