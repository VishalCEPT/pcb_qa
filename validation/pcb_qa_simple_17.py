from simp_sexp import Sexp
from skidl.netlist_to_skidl import legalize_name
from collections import defaultdict

import os
import re
import json

def map_net_usage(nets, components):
    """Reproduce the first part of PCB-QA analyze_nets()."""

    net_usage = defaultdict(lambda: defaultdict(set))

    for net in nets:
        for pin in net["pins"]:
            component_ref = pin["pin"]["name"]

            for component in components:
                if component["ref"] == component_ref:
                    sheet_path = component["sheetpath"]

                    net_usage[net["name"]][sheet_path].add(
                        f"{component_ref}.{pin['pin']['number']}"
                    )

    return net_usage

def find_lowest_common_ancestor(sheet1, sheet2):
    """Reproduce PCB-QA's lowest-common-ancestor logic."""

    path1 = sheet1.rstrip("/").split("/")
    path2 = sheet2.rstrip("/").split("/")

    common = []

    for part1, part2 in zip(path1, path2):
        if part1 != part2:
            break
        common.append(part1)

    if not common:
        return "/"

    return "/".join(common) + "/"


def find_net_hierarchy(net_usage):
    """Reproduce the net hierarchy calculation for the current board."""

    net_hierarchy = {}

    for net_name, sheet_pins in net_usage.items():
        used_sheets = list(sheet_pins.keys())

        origin_sheet = used_sheets[0]

        for sheet in used_sheets[1:]:
            origin_sheet = find_lowest_common_ancestor(
                origin_sheet,
                sheet
            )

        destination_sheets = [
            sheet for sheet in used_sheets
            if sheet != origin_sheet
        ]

        net_hierarchy[net_name] = {
            "origin_sheet": origin_sheet,
            "destination_sheets": destination_sheets,
        }

    return net_hierarchy

def classify_nets_by_sheet(net_usage, net_hierarchy, sheets):
    """Reproduce PCB-QA's local/imported net classification."""

    for net_name, sheet_pins in net_usage.items():

        if net_name.startswith("unconnected"):
            continue

        origin_sheet = net_hierarchy[net_name]["origin_sheet"]
        destination_sheets = net_hierarchy[net_name]["destination_sheets"]

        if origin_sheet in sheets:
            sheets[origin_sheet]["local_nets"].add(net_name)

        for destination_sheet in destination_sheets:
            if destination_sheet in sheets:
                sheets[destination_sheet]["imported_nets"].add(net_name)

def cull_from_top(sheets):
    """Reproduce the top-level culling stage for sheet contents."""

    if "/" not in sheets:
        return

    top_sheet = sheets["/"]

    for child_path in top_sheet["children"]:
        if child_path in sheets:
            child_sheet = sheets[child_path]

            for component in child_sheet["components"]:
                if component in top_sheet["components"]:
                    top_sheet["components"].remove(component)

            for net_name in child_sheet["local_nets"]:
                top_sheet["local_nets"].discard(net_name)


def select_netlist_file():
    """Ask the user for a folder and locate the KiCad .net file."""

    folder = input("Enter folder containing the .net file: ").strip()

    if not os.path.isdir(folder):
        print("Error: Folder does not exist.")
        return None

    netlist_files = [
        file for file in os.listdir(folder)
        if file.lower().endswith(".net")
    ]

    if len(netlist_files) == 0:
        print("Error: No .net file found in the folder.")
        return None

    if len(netlist_files) == 1:
        netlist_file = os.path.join(folder, netlist_files[0])
        print()
        print("Found .net file:")
        print(netlist_files[0])
        return netlist_file

    print()
    print("Multiple .net files found:")

    for index, file in enumerate(netlist_files, start=1):
        print(f"{index}. {file}")

    choice = input("Select the .net file number: ").strip()

    try:
        index = int(choice)
        if index < 1 or index > len(netlist_files):
            print("Invalid selection.")
            return None
    except ValueError:
        print("Invalid selection.")
        return None

    return os.path.join(folder, netlist_files[index - 1])

def read_netlist(netlist_file):
    """Read a KiCad .net file and convert it into an S-expression object."""

    with open(netlist_file, "r", encoding="latin_1") as f:
        text = f.read()

    return Sexp(text)

def extract_component_fields(comp):
    """Extract component fields following PCB-QA FieldsSexp behavior."""

    fields = {}

    field_sexps = comp.search("/comp/fields/field")

    for field in field_sexps:

        field_name = field.search("/field/name").value

        result = re.split(
            r"[\(\)]\s*",
            field.to_str(break_inc=0)[:-1]
        )

        field_value = result[-1]

        fields[field_name] = field_value

    return fields

def extract_component_properties(comp):
    properties = {}

    property_sexps = comp.search("/comp/property")

    for prop in property_sexps:
        property_name = prop.search("/property/name").value
        property_value = prop.search("/property/value").value
        properties[property_name] = property_value

    return properties



def create_pin_dict(node):
    """Create a pin dictionary following PCB-QA PinSexp behavior."""

    name = node.search("/node/ref").value
    number = node.search("/node/pin").value
    pin_type = node.search("/node/pintype").value

    return {
        "name": name,
        "number": number,
        "type": pin_type
    }

def map_pin_to_net_dict(pin_dict, component_name):
    """Map a pin dictionary into the PCB-QA net representation."""

    return {
        "component": component_name,
        "pin": pin_dict
    }

def component_exists(component_list, component_ref):
    """Check whether a component reference exists in the component list."""
    
    for component in component_list:
        if component["ref"] == component_ref:
            return True

    return False

def parse_components(sexp):
    """Extract components from the KiCad netlist."""

    components = []



    component_sexps = sexp.search("components/comp")

    for comp in component_sexps:

        ref = comp.search("/comp/ref").value
        value = comp.search("/comp/value").value
        footprint = comp.search("/comp/footprint").value
        sheetpath = comp.search("/comp/sheetpath/names").value
        symbol = comp.search("/comp/libsource/lib").value
        fields = extract_component_fields(comp)

        datasheet = fields.get("Datasheet", "")
        description = fields.get("Description", "")

        properties = extract_component_properties(comp)
        tstamps = comp.search("/comp/tstamps").value        

        component = {
            "ref": ref,
            "value": value,
            "footprint": footprint,
            "symbol": symbol,
            "datasheet": datasheet,
            "description": description,
            "properties": properties,
            "tstamps": tstamps,
            "fields": fields,
            "pins": [],
            "sheetpath": sheetpath
        }

        components.append(component)

    return components



def parse_nets(sexp, components):
    """Extract nets and their pin connections from the KiCad netlist."""

    nets = []

    net_sexps = sexp.search("nets/net")
    
    for net in net_sexps:

        net_name = net.search("/net/name").value

        pins = []

        for node in net.search("node"):

            component_ref = node.search("/node/ref").value

            if not component_exists(components, component_ref):
                continue

            pin_dict = create_pin_dict(node)
            pin = map_pin_to_net_dict(
                pin_dict,
                legalize_name(component_ref)
            )

            pins.append(pin)

        nets.append({
            "name": net_name,
            "pins": pins
        })


    return nets

def extract_sheet_info(sexp):
    """Reproduce PCB-QA HierarchicalReader.extract_sheet_info()."""

    sheets = []

    sheet_sexps = sexp.search("design/sheet")

    for sheet in sheet_sexps:
        sheet_num = sheet.search("/sheet/number").value
        sheet_path = sheet.search("/sheet/name").value

        parent = os.path.dirname(sheet_path.rstrip("/"))

        if parent:
            if not parent.endswith("/"):
                parent += "/"
            name = os.path.basename(sheet_path.rstrip("/"))
        else:
            name = ""

        sheets.append({
            "number": sheet_num,
            "path": sheet_path,
            "name": name,
            "source": sheet.search("/sheet/title_block/source").value,
            "parent": parent,
            "components": [],
            "local_nets": set(),
            "imported_nets": set(),
            "children": []
        })

    return sheets

def assign_components_to_sheets(components, sheets):
    """Reproduce PCB-QA HierarchicalReader.assign_components_to_sheets()."""

    for component in components:
        sheet_path = component["sheetpath"]

        if sheet_path in sheets:
            sheets[sheet_path]["components"].append(component)


def assign_components_to_sheets(components, sheets):
    """Reproduce PCB-QA HierarchicalReader.assign_components_to_sheets()."""

    for component in components:
        component_ref = component["ref"]

        # The original ComponentSexp stores the sheet path.
        sheet_path = component["sheetpath"]

        if sheet_path in sheets:
            sheets[sheet_path]["components"].append(component)



def filter_nets(nets):
    """Remove unconnected nets, following PCB-QA behavior."""

    filtered_nets = []

    for net in nets:

        net_name = net["name"]

        if net_name.startswith("unconnected"):
            continue

        filtered_nets.append(net)

    return filtered_nets

def legalize_net_name(net_name):
    """Use the same name legalization function as PCB-QA."""
    return legalize_name(net_name)

def populate_empty_circuit():
    """Reproduce CircuitJSON._populate_empty_circuit()."""
    circuit = {}

    circuit["name"] = ""
    circuit["description"] = ""
    circuit["source_file"] = ""
    circuit["tstamps"] = ""
    circuit["components"] = {}
    circuit["nets"] = {}
    circuit["subcircuits"] = []
    circuit["annotations"] = []

    return circuit

def generate_circuit_dict_from_attributes(sheet_attributes):
    """Reproduce CircuitJSON.generate_circuit_dict_from_attributes()."""
    sheet_contents = populate_empty_circuit()

    for attribute, value in sheet_attributes.items():
        sheet_contents[attribute] = value

    return sheet_contents

def component_to_dict(component):
    """Reproduce PCB-QA ComponentSexp.component_sexp_to_dict()."""

    return {
        "symbol": component["symbol"],
        "ref": component["ref"],
        "value": component["value"],
        "footprint": component["footprint"],
        "datasheet": component["datasheet"],
        "description": component["description"],
        "properties": component["properties"],
        "tstamps": component["tstamps"],
        "fields": component["fields"],
        "pins": component["pins"],
    }


def create_circuit(components, nets, netlist_file):
    """Reproduce HierarchicalReader.create_circuit_dict_from_sheet()."""

    board_name = os.path.splitext(
        os.path.basename(netlist_file)
    )[0]

    sheet_attributes = {}

    sheet_attributes["name"] = board_name
    sheet_attributes["source_file"] = os.path.basename(netlist_file)

    component_dict = {}

    for component in components:
        ref = component["ref"]
        component_dict[ref] = component_to_dict(component)

    sheet_attributes["components"] = component_dict

    net_dict = {}

    for net in nets:
        legal_name = legalize_name(net["name"])
        net_dict[legal_name] = net["pins"]

    sheet_attributes["nets"] = net_dict

    return generate_circuit_dict_from_attributes(sheet_attributes)

def main():

    netlist_file = select_netlist_file()

    if netlist_file is None:
        return


    print()
    print("Using netlist:")
    print(netlist_file)

    sexp = read_netlist(netlist_file)

    sheets = extract_sheet_info(sexp)

    sheet_dict = {}

    for sheet in sheets:
        sheet_dict[sheet["path"]] = sheet

    print()
    print("--- Sheet information ---")
    print("Sheets found:", len(sheet_dict))

    for sheet in sheet_dict.values():
        print(sheet)

    print()
    print("--- Sheet source ---")
    for sheet in sheet_dict.values():
        print("Sheet:", sheet["path"])
        print("Source:", sheet["source"])

    component_sexps = sexp.search("components/comp")

    first_component = component_sexps[0]

    fields = extract_component_fields(first_component)

    print()
    print("--- Fields of first component ---")
    print(fields)

    symbol = first_component.search("/comp/libsource/lib").value
    part = first_component.search("/comp/libsource/part").value

    print()
    print("--- Libsource of first component ---")
    print("symbol:", symbol)
    print("part:", part)

    components = parse_components(sexp)

    assign_components_to_sheets(components, sheet_dict)

    native_nets = parse_nets(sexp, components)

    net_usage = map_net_usage(native_nets, components)

    net_hierarchy = find_net_hierarchy(net_usage)

    classify_nets_by_sheet(
        net_usage,
        net_hierarchy,
        sheet_dict
    )

    cull_from_top(sheet_dict)

    print()
    print("--- After cull_from_top ---")

    for path, sheet in sheet_dict.items():
        print("Sheet:", repr(path))
        print("Components:", len(sheet["components"]))
        print("Local nets:", len(sheet["local_nets"]))
        print("Imported nets:", len(sheet["imported_nets"]))

    print()
    print("--- Local / Imported nets ---")

    for path, sheet in sheet_dict.items():
        print("Sheet:", repr(path))
        print("Local nets:", len(sheet["local_nets"]))
        print("Imported nets:", len(sheet["imported_nets"]))

    print()
    print("--- Net hierarchy ---")
    print("Nets processed:", len(net_hierarchy))

    for net_name in list(net_hierarchy.keys())[:10]:
        print()
        print("Net:", net_name)
        print(
            "  Origin sheet:",
            repr(net_hierarchy[net_name]["origin_sheet"])
        )
        print(
            "  Destination sheets:",
            net_hierarchy[net_name]["destination_sheets"]
        )

    print()
    print("--- Net usage across sheets ---")
    print("Nets analyzed:", len(net_usage))

    for net_name in list(net_usage.keys())[:10]:
        print()
        print("Net:", net_name)
        for sheet_path, pins in net_usage[net_name].items():
            print("  Sheet:", repr(sheet_path))
            print("  Pins:", sorted(pins))

    print()
    print("--- Components per sheet ---")

    for path, sheet in sheet_dict.items():
        print("Sheet:", repr(path))
        print("Component count:", len(sheet["components"]))

        print("First 10 components:")
        for component in sheet["components"][:10]:
            print(" ", component["ref"], "sheetpath =", component["sheetpath"])

    print()
    print("--- Component assignment ---")

    for path, sheet in sheet_dict.items():
        print("Sheet:", repr(path))
        print("Components assigned:", len(sheet["components"]))

    print()
    print("--- Component membership test ---")
    print("C5:", component_exists(components, "C5"))
    print("R13:", component_exists(components, "R13"))
    print("UNKNOWN:", component_exists(components, "UNKNOWN"))

    # Temporary test: inspect one native net node
    net_sexps = sexp.search("nets/net")
    first_net = net_sexps[0]
    first_node = first_net.search("node")[0]

    pin = create_pin_dict(first_node)
    component_ref = first_node.search("/node/ref").value
    pin_net = map_pin_to_net_dict(pin, component_ref)

    print()
    print("--- First net node ---")
    print("Net:", first_net.search("/net/name").value)
    print("Pin dictionary:", pin)
    print("Net mapping:", pin_net)

    r13 = next(c for c in components if c["ref"] == "R13")

    print()
    print("--- R13 Datasheet and Description ---")
    print("Datasheet:", r13["fields"].get("Datasheet", ""))
    print("Description:", r13["fields"].get("Description", ""))

    r13_sexp = next(
        c for c in component_sexps
        if c.search("/comp/ref").value == "R13"
    )

    r13_properties = extract_component_properties(r13_sexp)
    r13_tstamps = r13_sexp.search("/comp/tstamps").value

    print()
    print("--- R13 ComponentSexp data ---")
    print("Properties:", r13_properties)
    print("Timestamps:", r13_tstamps)
    print("Pins:", [])

    nets = parse_nets(sexp, components)

    print()
    print("Native nets:", len(nets))

    nets = filter_nets(nets)

    print("Filtered nets:", len(nets))

    circuit = create_circuit(components, nets, netlist_file)

    generated_json = os.path.join(os.path.dirname(netlist_file), "m5-pantilt_generated_from_16.json")

    with open(generated_json, "w", encoding="utf-8") as f:
        json.dump(circuit, f, indent=2)

    print()
    print("--- Generated circuit JSON ---")
    print(generated_json)

    print()
    print("--- R13 in final circuit ---")
    print(circuit["components"]["R13"])

    print()

    print("Board name:", circuit["name"])
    print("Source file:", circuit["source_file"])
    print("Components:", len(circuit["components"]))
    print("Nets:", len(circuit["nets"]))

    print()

    print("--- Net name normalization ---")

    for original_name in ["+3V3", "+5V", "/BAT", "Net-(J8-Pin_3)"]:
        print(
            original_name,
            "->",
            legalize_net_name(original_name)
        )

    print()
    print("--- PCB-QA legalize_name() test ---")

    test_names = [
        "+3V3",
        "+5V",
        "/BAT",
        "/PWM1",
        "Net-(J8-Pin_3)",
        "Net-(Q2-B)",
    ]

    for name in test_names:
        print(name, "->", legalize_name(name))

    print("Subcircuits:", len(circuit["subcircuits"]))

    print()
    print("--- R13 ---")
    print(next(c for c in components if c["ref"] == "R13"))

    print()
    print("--- Net _p_3V3 ---")
    print(circuit["nets"]["_p_3V3"])

if __name__ == "__main__":
    main()