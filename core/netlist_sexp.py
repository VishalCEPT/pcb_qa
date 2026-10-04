from collections import defaultdict
import os
import re 
from simp_sexp import Sexp
from skidl.netlist_to_skidl import Sheet, find_common_path_prefix, legalize_name
from skidl.logger import active_logger  # Import the active_logger

class ComponentSexp:
    """
    This class delivers attributes from a component S-expression.
    Inspired by `simp_sexp` package. 
    """

    def __init__(self, sexp):
        self.sheetpath = sexp.search("/comp/sheetpath/names").value
        self.ref = sexp.search("/comp/ref").value
        self.value = sexp.search("/comp/value").value
        self.footprint = sexp.search("/comp/footprint").value
        self.fields = [FieldsSexp(field) for field in sexp.search("/comp/fields/field")]
        self.name = sexp.search("/comp/libsource/part").value
        self.lib = sexp.search("/comp/libsource/lib").value
        self.properties = [PropertySexp(prop) for prop in sexp.search("/comp/property")]
        self.tstamps = sexp.search("/comp/tstamps").value

    def component_sexp_to_dict(self) -> dict:
        component_defs = {}
        props = {}
        fields = {}

        for prop in self.properties:
            props[prop.name] = prop.value

        for field in self.fields:
            fields[field.name] = field.value
        
        component_defs["symbol"] = self.lib
        component_defs["ref"] = self.ref
        component_defs["value"] = self.value
        component_defs["footprint"] = self.footprint

        if "Datasheet" in fields:
            component_defs["datasheet"] = fields["Datasheet"]
        else: 
            component_defs["datasheet"] = ""

        if "Description" in fields:
            component_defs["description"] = fields["Description"]
        else: 
            component_defs["description"] = ""
                
        component_defs["properties"] = props
        component_defs["tstamps"] = self.tstamps
        component_defs["fields"] = fields
        component_defs["pins"] = []
        return component_defs

class FieldsSexp:
    """
    This class delivers attributes from a fields S-expression.
    Inspired by `simp_sexp` package. 
    """

    def __init__(self, sexp):
        self.name = sexp.search("/field/name").value
        result = re.split(r"[\(\)]\s*", sexp.to_str(break_inc=0)[:-1])
        self.value = result[-1]

class NetlistSexp:
    """
    Represents a KiCad netlist.

    This class encapsulates the structure of a KiCad netlist, including its parts,
    nets, and sheets. It provides methods to access and manipulate the netlist data.

    Attributes:
        components (List): List of components in the netlist
        nets (List): List of electrical nets in the netlist
        sheets (List): List of hierarchical sheets in the netlist
    """

    def __init__(self, sexp):
        self.sheets = [SheetSexp(sht) for sht in sexp.search("design/sheet")]
        self.components = [ComponentSexp(comp) for comp in sexp.search("components/comp")]
        self.nets = [NetSexp(net) for net in sexp.search("nets/net")]

class NetSexp:
    """
    This class delivers attributes from a net S-expression.
    """

    def __init__(self, sexp):
        self.name = sexp.search("/net/name").value
        self.pins = [PinSexp(node) for node in sexp.search("/net/node")]

    def net_sexp_to_dict(self, component_list: list) -> dict:
        # Definition: 
        # {
        #   "component": "U1",          // Component reference
        #   "pin": {                    // Alternative pin format (object)
        #     "number": "1",
        #     "name": "~",
        #     "type": "passive"
        #   }
        # }
        pins = []

        for pin in self.pins:
            entry = {}
            if any(comp.ref == pin.name for comp in component_list):

                pin_obj = pin.create_pin_dict()
                entry = pin.map_pin_to_net_dict(legalize_name(pin.name))

                pins.append(entry)
        return pins

class PinSexp:
    """
    This class delivers attributes from a pin S-expression.
    """

    def __init__(self, sexp):
        self.name = sexp.search("/node/ref").value
        self.number = sexp.search("/node/pin").value
        self.type = sexp.search("/node/pintype").value

    def create_pin_dict(self) -> dict:
        # {                    
        #     "number": "1",
        #     "name": "~",
        #     "type": "passive"
        # }
        pin_obj = {}
        pin_obj["name"] = self.name
        pin_obj["number"] = self.number
        pin_obj["type"] = self.type
        return pin_obj

    def map_pin_to_net_dict(self, component_name: str) -> dict:
        mapped_entry = {}
        mapped_entry["component"] = component_name
        mapped_entry["pin"] = self.create_pin_dict()
        return mapped_entry

class PropertySexp:
    """
    This class delivers attributes from a property S-expression.
    """

    def __init__(self, sexp):
        self.name = sexp.search("/property/name").value
        self.value = sexp.search("/property/value").value

class SheetSexp:
    """
    This class delivers attributes from a sheet S-expression.
    """

    def __init__(self, sexp):
        self.num = sexp.search("/sheet/number").value
        self.name = sexp.search("/sheet/name").value
        self.source = sexp.search("/sheet/title_block/source").value

    def sheet_sexp_to_dict(self) -> dict:
        sheet_obj = {}
        sheet_obj["num"] = self.num
        sheet_obj["name"] = self.name
        sheet_obj["source"] = self.source
        return sheet_obj

