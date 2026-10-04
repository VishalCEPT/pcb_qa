import file_helpers
import kicad_cli_helpers
import os

# ngspice imports
import re 
import subprocess
import sys


class KiCadSPICECircuitProcesser:
    def __init__(self, spice_circuit_path: str, output_dir: str = os.getcwd(), project_name: str = None, output_file: str = None):
        self.kicad_cli_interface = None
        self.spice_circuit_path = spice_circuit_path
        self.output_dir = output_dir
        self.json_file_operations = file_helpers.JSONFileOperator()
        if output_file:
            self.spice_json_file = output_file
        else:
            self.spice_json_file = os.path.join(self.output_dir, self.spice_circuit_path.split("/")[-1])

        self.project_name = project_name
        if project_name is not None:
            self.kicad_cli_interface = kicad_cli_helpers.KiCadInterface()
            self.export_project_spice()

    def _convert_voltage_str(self, voltage_str):
        """
        Parse a KiCad power-rail net name's voltage magnitude. Real-world
        nets use several conventions: 'V' as the decimal point with no
        separate decimal ('3V3' -> 3.3), a real decimal point plus a
        trailing 'V' unit ('3.3V' -> 3.3), and non-numeric suffixes that
        annotate the rail rather than change its value ('24VF' -> 24,
        '24' being "filtered 24V").
        """
        s = voltage_str.strip().upper()

        match = re.match(r'^(\d+)V(\d+)$', s)
        if match:
            return float(f"{match.group(1)}.{match.group(2)}")

        match = re.match(r'^(\d+(?:\.\d+)?)V', s)
        if match:
            return float(match.group(1))

        return float(s)

    def _parse_spice_netlist(self) -> dict:
        """
        Parses a simplified SPICE netlist (.cir) content into a structured dictionary.
        Focuses on extracting basic component definitions (R, C, L, D, Q, U, X) and their connections.

        Args:
            cir_content (str): The raw content of the KiCad generated SPICE .cir file.

        Returns:
            dict: A dictionary containing 'components' and 'nets' information.
        """
        parsed_data = {
            "components": {},
            "nets": {}
        }

        with open(self.spice_circuit_path, 'r', encoding="utf-8") as f:
            spice_circuit_content = f.read()

        for line in spice_circuit_content.split('\n'):
            line = line.strip()
            if not line or line.startswith('*') or line.startswith('.') or line.lower().startswith('.end'):
                continue

            # Rxxx N1 N2 Value
            # Cxxx N1 N2 Value
            # Lxxx N1 N2 Value
            match_rcl = re.match(r'^(R|C|L)(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$', line, re.IGNORECASE)
            if match_rcl:
                comp_type = match_rcl.group(1).upper()
                ref_id = match_rcl.group(1).upper() + match_rcl.group(2)
                node1 = match_rcl.group(3)
                node2 = match_rcl.group(4)
                value = match_rcl.group(5)

                parsed_data["components"][ref_id] = {
                    "type": comp_type,
                    "value": value,
                    "nodes": [node1, node2]
                }
                # Add to nets
                for node in [node1, node2]:
                    if node not in parsed_data["nets"]:
                        parsed_data["nets"][node] = []
                    parsed_data["nets"][node].append({"component": ref_id, "pin": node})

            
            # Dxxx N1 N2 ModelName (Diode)
            match_d = re.match(r'^(LED)(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$', line, re.IGNORECASE)
            if match_d:
                comp_type = match_d.group(1).upper()
                ref_id = match_d.group(1).upper() + match_d.group(2)
                node1 = match_d.group(3)
                node2 = match_d.group(4)
                model_name = match_d.group(5)

                parsed_data["components"][ref_id] = {
                    "type": comp_type,
                    "model": model_name,
                    "nodes": [node1, node2]
                }
                for node in [node1, node2]:
                    if node not in parsed_data["nets"]:
                        parsed_data["nets"][node] = []
                    parsed_data["nets"][node].append({"component": ref_id, "pin": node})

            # Generic U/X components (ICs/Subcircuits) - very simplified, just noting presence
            # This assumes format like: Uxxx Node1 Node2 ... ModelName
            match_ux_type = re.match(r'^(U|X)(\S+)', line, re.IGNORECASE)
            if match_ux_type:
                # For U and X components, we'll try to extract ref_id and model name (last field)
                parts = line.split()
                if len(parts) >= 3: # At least U_REF_ID Node1 ModelName
                    comp_type = parts[0][0].upper()
                    ref_id = parts[0].upper()
                    model_name = parts[-1] # Assume last part is model name
                    nodes = parts[1:-1] # Nodes are between ref_id and model name

                    parsed_data["components"][ref_id] = {
                        "type": comp_type,
                        "model": model_name,
                        "nodes": nodes
                    }
                    for node in nodes:
                        if node not in parsed_data["nets"]:
                            parsed_data["nets"][node] = []
                        parsed_data["nets"][node].append({"component": ref_id, "pin": node})

        return parsed_data
    
    def _find_component_spice_models(self) -> list:
        """
        Identifies components in the parsed SPICE netlist data that likely require
        explicit SPICE model definitions for successful simulation.

        Returns:
            list: A list of dictionaries, where each dictionary represents a component
                needing a model, including its 'ref_id', 'type', and 'identifier' (or model name).
        """
        self.components_needing_models = []

        parsed_cir_data = self._parse_spice_netlist()
        components = parsed_cir_data['components']

        for ref_id, comp_data in components.items():
            comp_type = comp_data['type'].upper()

            # Components that inherently need models in SPICE (Diodes, Transistors, ICs/Subcircuits)
            if comp_type in ['D', 'LED', 'Q', 'U', 'X']:
                comp_value = comp_data.get('value', None)
                comp_model = comp_data['model'] if comp_data['model'] is not None else None # For U/X components
                self.components_needing_models.append({
                    'ref_id': ref_id,
                    'type': comp_type,
                    'identifier': comp_model if comp_model else comp_value,
                    'reason': f"Type '{comp_type}' inherently requires a SPICE model definition (e.g., .model, .subckt)."
                })

            # Handle LED components explicitly as they might be defined with 'L' prefix in some netlists
            elif comp_type == 'L' and 'LED' in ref_id.upper():
                comp_value = comp_data['value'] if comp_data['value'] is not None else None 
                self.components_needing_models.append({
                    'ref_id': ref_id,
                    'type': 'LED', # Categorize specifically as LED
                    'identifier': comp_value,
                    'reason': f"LED component '{ref_id}' with value '{comp_value}' requires a SPICE diode model."
                })
            # Passive components (R, C, L) might need models if their value is not a simple numeric string
            elif comp_type in ['R', 'C', 'L']:
                comp_value = comp_data['value'] if comp_data['value'] is not None else None 

                # Check if the value is non-numeric (e.g., a part number or descriptive text)
                if comp_value is not None and not re.fullmatch(r'[\d\.]+[MGTKmunpfa]?', str(comp_value), re.IGNORECASE):
                    self.components_needing_models.append({
                        'ref_id': ref_id,
                        'type': comp_type,
                        'identifier': comp_value,
                        'reason': f"Value '{comp_value}' for component type '{comp_type}' is non-standard and may require a SPICE model."
                    })

        return self.components_needing_models

    def export_project_spice(self):
        print("Exporting project SPICE circuit using KiCad CLI...")
        self.kicad_cli_interface.export_spice_with_kicad_cli(self.project_name, self.spice_circuit_path)

    def convert_project_spice_to_circuit(self, output_file_name: str) -> dict:
        new_lines = []
        spice_commands = "\n \n"
        power_lines = {}

        with open(self.spice_circuit_path, 'r', encoding="utf-8") as f:
            original_content = f.readlines()

        first_line = original_content[0]
        last_line = original_content[-1]

        spice_model_defs = self.generate_spice_models(self._find_component_spice_models())

        in_control_block = False
        for line in original_content[1:-1]:
            stripped = line.strip()
            if stripped.lower().startswith(".control"):
                # Some KiCad-exported .cir inputs already carry a full
                # .control/.endc block (simulation commands + a now-stale
                # output path). Drop the whole block here instead of just the
                # .control/.endc wrapper lines, so the tran/set/write commands
                # inside it don't leak through as bare, unwrapped netlist
                # lines (ngspice then misparses them as element cards, e.g.
                # "set filetype=ascii" looks like an "S" switch needing a
                # .model). We append our own, correctly-pathed block below.
                in_control_block = True
                continue
            if stripped.lower().startswith(".endc"):
                in_control_block = False
                continue
            if in_control_block:
                continue

            entries = line.split(" ")
            if (len(entries)) == 2:
                pass
            else:
                # Replace GND with 0 in line
                line = re.sub(r"\bGND\b", "0", line, flags=re.IGNORECASE)
                # Only rewrite genuine "LEDxx ..." refs into the "DLEDxx ...
                # LED_D_<color>" diode form. Use startswith (not "in") so an
                # already-converted "DLEDxx ... LED_D_<color>" line (e.g. from
                # a board whose input .cir is itself a prior conversion
                # output) isn't matched and double-prefixed into a bogus
                # "LED_D_LED_D_<color>" model reference.
                if line.split(" ")[0].upper().startswith("LED"):
                    first_word = re.sub(r"LED", "DLED", line.split(" ")[0] + " ", flags=re.IGNORECASE)
                    last_token = line.split(" ")[-1]
                    last_word = f"LED_D_{last_token}"
                    line = first_word + " ".join(map(str, line.split(" ")[1:-1])) + " " + last_word
                new_lines.append(line)

        # Find power rails from new_lines
        for line in new_lines:
            entries = line.split(" ")
            for entry in entries:
                matches = re.findall(r"\+\d+", entry)
                if len(matches) > 0 and not entry.startswith("Net"): 
                    power_lines[entry] = True

        # Some input .cir files already carry an explicit independent
        # voltage source for a power rail (e.g. a prior run of this same
        # converter, or a manually-added SPICE directive in the schematic).
        # Skip regenerating one for any rail that's already driven, or
        # ngspice rejects the duplicate element with "device already exists".
        rails_with_existing_source = set()
        for line in new_lines:
            entries = [e for e in line.split(" ") if e]
            if len(entries) >= 2 and entries[0].upper().startswith("V"):
                rails_with_existing_source.add(entries[1])

        for power in power_lines.keys():
            if power in rails_with_existing_source:
                continue
            # power is the raw net token (e.g. "+3V3" or, for a hierarchical
            # net, "/+24VF"), so split on '+' rather than assuming it's
            # always the first character.
            magnitude_str = power.split("+", 1)[-1]
            spice_commands = spice_commands + f"V_{magnitude_str} {power} 0 DC {self._convert_voltage_str(magnitude_str)}" + "\n"

        spice_commands = spice_commands + "\n\n" \
        ".control \n" + \
        "tran 100u 10m \n" + \
        "set filetype=ascii \n" + \
        f"write {self.output_dir}/{output_file_name}_raw.raw all \n" + \
        ".endc \n\n"
 
        new_lines = first_line + "\n" + "\n".join(map(str, spice_model_defs)) + "\n\n" + "".join(map(str, new_lines)) + spice_commands + last_line

        with open(os.path.join(self.output_dir, f"{output_file_name}.cir"), 'w', encoding="utf-8") as f:
            f.writelines(new_lines)

    def run_ngspice_simulation(self, input_spice_path: str, output_spice_logs: str,
                               output_raw_path: str, ngspice_executable: str = "ngspice"):
        """
        Runs ngspice on a simulation-ready .cir file (as produced by
        convert_project_spice_to_circuit), then parses the ASCII .raw file it
        writes (output_raw_path, matching the `write ..._raw.raw` command
        embedded in that .cir) and persists the result to self.spice_json_file
        so check_steady_state_average_matches_expected_voltage can read it back.
        """
        subprocess.run(
            [ngspice_executable, "-b", "-o", output_spice_logs, input_spice_path],
            capture_output=True,
            check=True,
            timeout=120,
        )
        if not os.path.exists(output_raw_path):
            # ngspice's batch mode (`-b`) commonly exits 0 even when it aborts
            # partway through the .control script (e.g. a component references
            # a .model that was never defined), so a missing .raw file is the
            # only reliable signal that the simulation never actually ran.
            log_tail = ""
            if os.path.exists(output_spice_logs):
                with open(output_spice_logs, 'r', encoding="utf-8", errors="replace") as f:
                    log_tail = f.read()[-1000:]
            raise RuntimeError(
                f"ngspice exited successfully but did not produce the expected .raw output "
                f"({output_raw_path}); the simulation likely aborted. ngspice log tail:\n{log_tail}"
            )
        ngspice_contents = self.parse_spice_simulated_data(output_raw_path)
        self.json_file_operations.write_to_json_file(ngspice_contents, self.spice_json_file)
        return ngspice_contents

    def generate_spice_models(self, components_needing_spice_models: list) -> list:
        generated_models = []

        for comp in components_needing_spice_models:
            if comp['type'] == 'LED':
                # Use a generic model name for each LED based on its identifier
                model_name = f"LED_D_{comp['identifier']}"
                # Use default values for other parameters for simplicity
                led_model = self._generate_led_model(model_name)
                generated_models.append(led_model)

        # print("--- Generated LED SPICE Models ---")
        return list(dict.fromkeys(generated_models))   

    def _generate_led_model(self, model_name, is_val='1p', rs_val='10', n_val='1.7') -> str:
        """
        Generates a SPICE .model definition for an LED (as a diode model).

        Args:
            model_name (str): The name for the SPICE model (e.g., 'LED_GENERIC').
            is_val (str): Saturation current (Is), e.g., '1p'.
            rs_val (str): Series resistance (Rs), e.g., '10'.
            n_val (str): Emission coefficient (N), e.g., '1.7'.
        Returns:
            str: The SPICE .model definition string.
        """
        return f".model {model_name} D (Is={is_val} Rs={rs_val} N={n_val})"

    def parse_spice_simulated_data(self, output_raw_file_path: str):
        with open(output_raw_file_path, 'r', encoding="utf-8", errors="replace") as f:
            raw_content = f.read()

        num_vars = re.search(r'No\. Variables:\s*(\d+)', raw_content, re.IGNORECASE)
        num_points = re.search(r'No\. Points:\s*(\d+)', raw_content, re.IGNORECASE)

        print(f"No. of variables from SPICE simulated file: {int(num_vars.group(1))}")
        print(f"No. of points from SPICE simulated file: {int(num_points.group(1))}")

        ngspice_contents = {}

        variables_section_match = re.search(r'Variables:\n(.*?)(?:\n[\w ]+:\s*\S+|\Z)', raw_content, re.DOTALL)

        if variables_section_match:
            variables_text = variables_section_match.group(1).strip()
            for var_line in variables_text.split('\n'):
                if var_line.strip():
                    parts = var_line.strip().split('\t')
                    if len(parts) >= 3:
                        idx = parts[0]
                        name = parts[1]
                        ngspice_contents[idx] = {'name': name, 'values': {}}

        values_section_match = re.search(r'Values:\n(.*)', raw_content, re.DOTALL) 
        
        if values_section_match:
            values_text = values_section_match.group(1).strip()
            data_point = None
            variable_index = 0
            for val_line in values_text.split('\n'):
                if val_line.strip():
                    values = val_line.strip().split('\t')
                    if (len(values) > 1):
                        # Start of a new data point: first variable's value
                        data_point = values[0]
                        variable_index = 0
                        ngspice_contents[f"{variable_index}"]['values'][f"{data_point}"] = values[1]
                    else:
                        variable_index += 1
                        ngspice_contents[f"{variable_index}"]['values'][f"{data_point}"] = values[0]

        return ngspice_contents

    def check_steady_state_average_matches_expected_voltage(self,
                                                            spice_json_file: str,
                                                            net_name: str,
                                                            expected_voltage: str,
                                                            tolerance: float = 0.05) -> bool:
        """
        Check whether the steady state values for a net (calculated approximately as the average of the last 10 voltage values) match the expected voltage.

        Args:
            spice_json_file: Path to the SPICE circuit JSON file
            net_name: Name of the net we care about
            expected_voltage: Voltage value represented as a string (with decimal points) and units (e.g: 3.3V)
            tolerance: Absolute voltage tolerance allowed between simulated and expected values

        Returns:
            True when the expected voltage value (for the chosen net) matches average of the last 10 values within tolerance, and False otherwise
        """

        json_file_operations = file_helpers.JSONFileOperator()
        spice_circuit_contents = json_file_operations.read_from_json_file(spice_json_file)

        for entry in spice_circuit_contents:
            signal_match = re.search(r"v\(([^)]+)\)", spice_circuit_contents[entry]["name"])

            if signal_match and signal_match.group(1).lower() == net_name.lower():

                # Convert last 10 values (for steady-state analysis) to floats and calculate average
                values = [float(v) for v in spice_circuit_contents[entry]["values"].values()][-10:]
                rounded_avg = round((sum(values) / len(values)), 2)

                return abs(rounded_avg - float(expected_voltage.replace("V", ""))) <= tolerance

        return False

    def find_all_entries_from_SPICE_circuit_with(self, net_name: str):
        round_one_relevant_lines = []
        relevant_lines = []
        attributes = []

        with open(self.spice_circuit_path, encoding="utf-8") as scf:
            spice_contents = scf.readlines()

        for line in spice_contents:
            if net_name.upper() in line:
                relevant_lines.append(line)

        # Remove duplicate lines
        print("".join(list(set(relevant_lines))))