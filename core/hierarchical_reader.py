#Extract Heirarchical info of the Nets list

from collections import defaultdict
import circuit_json
import netlist_sexp
import os
import random
from simp_sexp import Sexp
from skidl.logger import active_logger  # Import the active_logger
from skidl.netlist_to_skidl import find_common_path_prefix, legalize_name, Sheet


class HierarchicalReader:
    """
    Converts a KiCad netlist into a hierarchical format.

    This class analyzes a KiCad netlist and preserves the hierarchical structure of the original schematic.
    """

    def __init__(self, src):
        """
        Initialize the converter with a KiCad netlist.

        Args:
            src: Path to a KiCad netlist file or a string containing netlist data
        """
        try:
            text = src.read()
        except Exception:
            try:
                text = open(src, "r", encoding="latin_1").read()
            except Exception:
                text = src
        
        # Changed self.netlist definition and added an object of CircuitJSON type
        self.netlist = netlist_sexp.NetlistSexp(Sexp(text))
        self.circuit_json = circuit_json.CircuitJSON()

        self.sheets = {}
        self.tab = " " * 4

        self._initialise_converter()

    def find_lowest_common_ancestor(self, sheet1, sheet2):
        """
        Return the lowest common ancestor (LCA) of two sheets.

        This method finds the sheet that is the closest common parent of two sheets
        in the schematic hierarchy.

        Args:
            sheet1 (str): Path to the first sheet
            sheet2 (str): Path to the second sheet

        Returns:
            str: Path to the lowest common ancestor sheet
        """
        return find_common_path_prefix(
            self.sheets[sheet1].path, self.sheets[sheet2].path
        )

    def extract_sheet_info(self):
        """
        Populate self.sheets with Sheet objects built from the netlist.

        This method examines the netlist to identify all sheets and their
        hierarchical relationships, creating Sheet objects to represent them.
        """
        active_logger.info("=== Extracting Sheet Info ===")

        if getattr(self.netlist, "sheets", None):
            sheet_numbers_paths = [
                (sheet.num, sheet.name) for sheet in self.netlist.sheets
            ]
            sheet_paths = [
                sheet_number_path[1] for sheet_number_path in sheet_numbers_paths
            ]
        else:
            sheet_paths = list(set([part.sheetpath for part in self.netlist.components]))
            sheet_numbers_paths = enumerate(sheet_paths)

        for sheet_number, sheet_path in sheet_numbers_paths:
            parent = os.path.dirname(sheet_path.rstrip("/"))
            if parent:
                if not parent.endswith("/"):
                    parent += "/"
                name = os.path.basename(sheet_path.rstrip("/"))
            else:
                name = ""
            sheet = Sheet(
                number=sheet_number,
                path=sheet_path,
                name=name,
                parent=parent,
                components=[],
                local_nets=set(),
                imported_nets=set(),
                children=[],
            )
            if not parent:
                self.top_sheet = sheet
            self.sheets[sheet_path] = sheet
            active_logger.info(
                f"  Found sheet: original_name='{sheet.path}', final='{sheet.name}', parent='{sheet.parent}'"
            )

        # Set up parent-child relationships
        for sheet in self.sheets.values():
            parent_sheet = self.sheets.get(sheet.parent)
            if parent_sheet:
                parent_sheet.children.append(sheet.path)

        # for sheet_path, sheet in self.sheets.items():
        #     active_logger.info(
        #         f"   sheet path='{sheet_path}', parent='{sheet.parent}', children={sheet.children}"
        #     )

        active_logger.info("=== Completed extracting sheet info ===")

    def assign_components_to_sheets(self):
        """
        Assign each component from the netlist to its appropriate sheet.

        This method assigns components to their respective sheets based on the
        sheet path information in the netlist.
        """
        active_logger.info("=== Assigning Components to Sheets ===")

        for comp in self.netlist.components:
            sheet_path = comp.sheetpath
            if sheet_path in self.sheets:
                self.sheets[sheet_path].components.append(comp)
                # active_logger.info(
                #     f"  Assigning component {comp.ref} to sheet {sheet_path}"
                # )
            # else:
            #     active_logger.warning(
            #         f"Sheet {sheet_path} not found for component {comp.ref}"
            #     )

        active_logger.info("=== Completed assigning components to sheets ===")

    def analyze_nets(self):
        """
        Analyze net usage to determine origins and required connections.

        This method examines how nets are used across sheets to determine which
        sheets need to pass nets to their children, which nets are local, and
        which are imported.
        """

        def find_net_src_dests(net_sheets):
            """
            Return the top-most sheet where the net is used and a list of all
            sheets that the net passes through to its stopping points.
            """

            src = net_sheets[0]
            for sheet in net_sheets[1:]:
                src = self.find_lowest_common_ancestor(src, sheet)

            dests = set()
            src_len = len(src)
            for sheet in set(net_sheets) - {src}:
                sheet = sheet.rstrip("/")
                path_src_to_sheet = sheet[src_len:]
                path_pieces = path_src_to_sheet.split("/")
                path = src
                for piece in path_pieces:
                    path += piece + "/"
                    dests.add(path)

            return src, dests

        active_logger.info("=== Starting Net Analysis ===")

        net_usage = defaultdict(lambda: defaultdict(set))

        active_logger.info("1. Mapping Net Usage Across Sheets:")

        # Map which nets are used in which sheets
        for net in self.netlist.nets:
            # active_logger.info(f"\nAnalyzing net: {net.name}")
            for pin in net.pins:
                for comp in self.netlist.components:
                    if comp.ref == pin.name:
                        comp_sht_pth = comp.sheetpath
                        net_usage[net.name][comp_sht_pth].add(f"{comp.ref}.{pin.number}")
                        # active_logger.info(
                        #     f"  - Used in sheet '{comp_sht_pth}' by pin {comp.ref}.{pin.number}"
                        # )

        active_logger.info("2. Analyzing Net Origins and Hierarchy:")

        net_hierarchy = {}
        for net_name, sheet_pins in net_usage.items():
            used_sheets = list(sheet_pins.keys())
            origin_sheet, destination_sheets = find_net_src_dests(used_sheets)
            destination_sheets = list(set(used_sheets) - {origin_sheet})
            net_hierarchy[net_name] = {
                "origin_sheet": origin_sheet,
                "destination_sheets": destination_sheets,
            }
            # active_logger.info(f"\nNet: {net_name}")
            # active_logger.info(f"  - Origin sheet: {origin_sheet}")
            # active_logger.info(f"  - Destination sheets: {destination_sheets}")

        active_logger.info("3. Classifying local vs imported nets:")

        # Clear any existing net classifications
        for sheet in self.sheets.values():
            sheet.local_nets.clear()
            sheet.imported_nets.clear()

        for net_name, hierarchy in net_hierarchy.items():
            if net_name.startswith("unconnected"):
                continue
            self.sheets[hierarchy["origin_sheet"]].local_nets.add(net_name)
            # active_logger.info(
            #     f"  Net {net_name} is local to sheet {hierarchy['origin_sheet']}"
            # )
            for dest_sheet in hierarchy["destination_sheets"]:
                self.sheets[dest_sheet].imported_nets.add(net_name)
                # active_logger.info(
                #     f"  Net {net_name} is imported in sheet {dest_sheet}"
                # )

        self.net_hierarchy = net_hierarchy
        self.net_usage = net_usage
        active_logger.info("=== Completed net analysis ===")

        # # Print summary for each sheet
        # for sheet_path, sheet in self.sheets.items():
        #     active_logger.info(
        #         f"Sheet '{sheet_path}': local_nets={sheet.local_nets}, imported_nets={sheet.imported_nets}"
        #     )

    def cull_from_top(self):
        """
        Remove top-level sheets that are not needed.

        This method simplifies the hierarchy by removing unnecessary empty top-level
        sheets, making the resulting SKiDL code more concise.
        """
        top_sheet = self.top_sheet
        while (
            not top_sheet.parent
            and not (top_sheet.components or top_sheet.local_nets)
            and len(top_sheet.children) == 1
        ):
            top_sheet = self.sheets[self.top_sheet.children[0]]
            top_sheet.name = self.top_sheet.name
            del self.sheets[self.top_sheet.path]
            top_sheet.parent = ""
            self.top_sheet = top_sheet

        sheet_names = [sheet.name for sheet in self.sheets.values() if sheet.parent]
        top_sheet_name = "top"
        while top_sheet_name in sheet_names:
            top_sheet_name += str(random.randint(0, 9))
        self.top_sheet.name = top_sheet_name

    # --------------------- Custom function definitions ---------------------
    def _assign_components_for_sheet_components(self, components_list: list) -> dict:
        current_sheet_comps = {}
        for comp in components_list:
            current_sheet_comps[comp.ref] = comp.component_sexp_to_dict()
        return current_sheet_comps
    
    def _assign_connected_nets_for_sheet_components(self, components_list: list) -> dict:
        current_sheet_nets = {}
        for net in self.netlist.nets:
            legal_name = legalize_name(net.name)
            if (not legal_name.startswith("unconnected")):
                net_obj = net.net_sexp_to_dict(components_list)
                if len(net_obj) != 0:     
                    current_sheet_nets[legal_name] = net_obj
        return current_sheet_nets

    def create_circuit_dict_from_sheet(self, sheet: Sheet) -> dict:
        sheet_attributes = {}
 
        sheet_sexp = self.get_sheet_sexp_from_sheet(sheet) 
        if sheet_sexp is not None: 
            sheet_attributes["name"] = sheet.name 
            sheet_attributes["source_file"] = sheet_sexp.source 

        sheet_components = self.retrieve_components_for_sheet(sheet)
        sheet_attributes["components"] = self._assign_components_for_sheet_components(sheet_components)
        sheet_attributes["nets"] = self._assign_connected_nets_for_sheet_components(sheet_components)

        return self.circuit_json.generate_circuit_dict_from_attributes(sheet_attributes)

    def generate_subcircuits_for_top_sheet_circuit(self) -> dict:
        subcircuits = []
        for sheet in self.sheets.values():
            if (sheet.name != "top"):
                subcircuits.append(self.create_circuit_dict_from_sheet(sheet))
        return subcircuits

    def generate_top_sheet_circuit(self) -> dict: 
        top_sheet_circuit = {}
        subcircuits = self.generate_subcircuits_for_top_sheet_circuit()

        for sheet in self.sheets.values():
            if (sheet.name == "top"):
                top_sheet_circuit = self.create_circuit_dict_from_sheet(sheet)

        top_sheet_circuit["subcircuits"] = subcircuits
        return top_sheet_circuit

    def get_sheet_sexp_from_sheet(self, sheet: Sheet) -> netlist_sexp.SheetSexp:
        for sheet_obj in self.netlist.sheets:
            if (sheet.path == sheet_obj.name):
                return sheet_obj
        return None

    def get_top_sheet_source_file(self) -> str:
        return self.generate_top_sheet_circuit()["source_file"]

    def _initialise_converter(self):
        self.extract_sheet_info()
        self.assign_components_to_sheets()
        self.analyze_nets()
        self.cull_from_top()

    def retrieve_components_for_sheet(self, sheet: Sheet) -> list:
        return sheet.components

    