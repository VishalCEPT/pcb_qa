import json

class CircuitJSON:
    def __init__(self, circuit_file: str = None):
        self.top_level_circuit = {}

        self.passive_components = []

        self.active_keywords = ['mcu', 'processor', 'controller', 'regulator', 'opamp', 'transistor', 'diode', 'logic', 'memory', 'sensor', 'adc', 'dac', 'fpga', 'asic', 'ic', 'amplifier', 'switching', 'microcontroller', 'crystal', 'stm32', 'ina219', 'pca9685']
        self.passive_keywords = ['resistor', 'capacitor', 'inductor', 'ferrite', 'bead', 'jumper', 'testpoint']
        self.power_keywords = ['gnd', 'vcc', '_p']

        if circuit_file is not None:
            with open(circuit_file, encoding="utf-8") as f:
                self.top_level_circuit = json.load(f)
        
            self._initialise_component_lists()
            # print(f"Passive conn: {self.passive_components}")

    def _populate_empty_circuit(self) -> dict:
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

    def _initialise_component_lists(self):
        for subcircuit in self.top_level_circuit["subcircuits"]:
            connections = self.get_net_connections("GND", subcircuit["name"])
            for conn in connections:
                if conn["pin"]["type"] == "passive":
                    if conn["component"] not in self.passive_components:
                        self.passive_components.append(conn["component"])

        connections = self.get_net_connections("GND")
        for conn in connections:
            if conn["pin"]["type"] == "passive":
                if conn["component"] not in self.passive_components:
                    self.passive_components.append(conn["component"])

    def generate_circuit_dict_from_attributes(self, sheet_attributes: dict) -> dict: 
        sheet_contents = self._populate_empty_circuit()

        for attribute, value in sheet_attributes.items(): 
            sheet_contents[attribute] = value

        return sheet_contents

    def get_net_connections(self, net_name, subcircuit_name=None) -> list:
        target_nets = None
        if subcircuit_name is None:
            target_nets = self.top_level_circuit["nets"]
        else:
            for subcircuit in self.top_level_circuit["subcircuits"]:
                if subcircuit["name"] == subcircuit_name:
                    target_nets = subcircuit["nets"]
                    break
        if target_nets and net_name in target_nets:
            return target_nets[net_name]
        return []

    def find_component_from_circuit(self, component_ref: str) -> tuple[str | None, dict | None]:
        """
        Given a component reference as input, obtain the component (as a dict) from the circuit if it exists. 

        Returns a tuple: 
            str: Subcircuit name as a string, None if top circuit  
            dict: If a component exists in the circuit, None if no such component exists
        """
        if self.top_level_circuit is not None:
            if component_ref in self.top_level_circuit["components"]: 
                return None, self.top_level_circuit["components"][component_ref]
            else: 
                for subcircuit in self.top_level_circuit["subcircuits"]:
                    if component_ref in subcircuit["components"]: 
                        return subcircuit["name"], subcircuit["components"][component_ref]
        return None, None

    def is_component_in_net_from_circuit(self, component_ref: str, net_name) -> bool:
        """
        Checks if a component (determined by its reference) is connected to a net in the circuit.

        Returns: 
            bool: True if they are connected and False otherwise
        """
        if self.top_level_circuit is not None:
            if component_ref in self.top_level_circuit["components"] and net_name in self.top_level_circuit["nets"]:
                for connections in self.top_level_circuit["nets"][net_name]:
                    if connections["component"] == component_ref:
                        return True
            else: 
                for subcircuit in self.top_level_circuit["subcircuits"]:
                    if component_ref in subcircuit["components"] and net_name in subcircuit["nets"]:
                        for connections in subcircuit["nets"][net_name]:
                            if connections["component"] == component_ref:
                                return True
        return False