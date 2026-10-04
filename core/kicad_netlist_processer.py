# Current package imports 
import hierarchical_reader 
import file_helpers
import kicad_cli_helpers 
import netlist_sexp
from netlist_sexp import SheetSexp

# netlist processer imports
import os
from simp_sexp import Sexp
from skidl.netlist_to_skidl import find_common_path_prefix, legalize_name, Sheet
from skidl.logger import active_logger  # Import the active_logger


class KiCadNetlistProcesser:
    """
    This class deals with the preprocessing and subsequent modification of all the open-source hardware projects accumulated for the Complex Automatic Trojan Insertion and Detection System. 
    """
    def __init__(self, netlist_path: str, output_dir: str = os.getcwd(), project_name: str = None):        
        self.output_dir = output_dir
        self.project_name = project_name
        self.netlist_path = netlist_path

        self.kicad_cli_interface = None
        if project_name is not None:
            self.kicad_cli_interface = kicad_cli_helpers.KiCadInterface()
            self.export_project_netlist()
        
        self.json_file_operations = file_helpers.JSONFileOperator()

        self._top_sheet_attributes = {}

        self.converter = hierarchical_reader.HierarchicalReader(netlist_path)

    def convert_project_netlist_to_circuit(self):
        """
        Convert the KiCad netlist (.net) to a JSON object following the definition:
        {
            "name": "string",                 // Required: Circuit name
            "description": "string",          // Optional: Circuit description
            "tstamps": "string",             // Optional: KiCad timestamp path
            "source_file": "string",         // Optional: Source schematic file
            "components": {},                // Component dictionary (see below)
            "nets": {},                      // Net connectivity (see below)
            "subcircuits": [],               // Array of nested circuits
            "annotations": []                // Optional: Circuit annotations
        }

        Here, each subsequent sheet of components becomes its own circuit and is stored inside "subcircuits."
        """
        self._top_sheet_attributes = self.converter.generate_top_sheet_circuit()

    def get_top_sheet_attributes(self): 
        return self._top_sheet_attributes

    def get_number_of_components(self):
        return self.find_number_of_components()

    def export_project_netlist(self):
        print("Exporting project netlist using KiCad CLI...")
        self.kicad_cli_interface.export_netlist_with_kicad_cli(self.project_name, self.netlist_path)

    def export_circuit_to_file(self, output_file: str = None):
        if (output_file is None):
            output_file = os.path.join(self.output_dir, self.converter.get_top_sheet_source_file().split(".")[0] + ".json")
        print("Writing top sheet circuit to file destination: ", output_file)
        self.json_file_operations.write_to_json_file(self._top_sheet_attributes, output_file)

    def find_connections_for_trace(self, target_trace: str) -> list:
        # Definition format of resultant list: 
        # [{'component': 'U1', 
        #   'pin': {'name': 'U1', 'number': '6', 'type': 'bidirectional'}}]
        for name, net_connections in self._top_sheet_attributes["nets"].items():
            if (name == target_trace):
                return name, net_connections
        return None

    def find_number_of_components(self) -> int:
        total_components = 0
        for subcircuit in self._top_sheet_attributes["subcircuits"]:
            total_components += len(subcircuit["components"])
        
        total_components += len(self._top_sheet_attributes["components"])

        return total_components

    def find_number_of_nets(self) -> int:
        total_nets = 0
        for subcircuit in self._top_sheet_attributes["subcircuits"]:
            total_nets += len(subcircuit["nets"])
        
        total_nets += len(self._top_sheet_attributes["nets"])

        return total_nets

    def load_circuit_from_file(self, read_file: str = None):
        if (read_file is None):
            read_file = os.path.join(self.output_dir, self._top_sheet_attributes["source_file"].split(".")[0] + ".json")
        self._top_sheet_attributes = self.json_file_operations.read_from_json_file(read_file)

    def _find_component_from_netlist_file(self, component_ref: str) -> str:
        # We can retrieve netlist contents in S-exp format 
        with open(self.netlist_path, 'r', encoding="utf-8") as nf:
            netlist_contents = Sexp(nf.read())

        # Find whether a component reference matches input
        for comp in netlist_contents.search("components/comp"):
            if comp.search("comp/ref").value == component_ref:
                return comp.to_str()

    def _find_all_nets_from_netlist_file(self, component_ref: str) -> str:
        contents = ['nets']

        with open(self.netlist_path, 'r', encoding="utf-8") as nf:
            netlist_contents = Sexp(nf.read())
        
        # One net can have multiple nodes, so we need to iterate over them
        for net in netlist_contents.search("nets/net"):
            for node in net.search("net/node"):
                if (node.search("node/ref").value == component_ref):
                    contents.append(["net", ["name", net.search("net/name").value], node.to_str()])

        return contents

    def find_all_entries_from_netlist_file_with(self, component_ref: str) -> Sexp:
        contents = Sexp()

        contents.append(self._find_component_from_netlist_file(component_ref))
        contents.append(self._find_all_nets_from_netlist_file(component_ref))

        return Sexp(contents)
