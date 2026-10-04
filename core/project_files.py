import json 

class Project:
    def __init__(self, parent_directory: str, circuit_json_file: str, netlist_file: str, spice_circuit_file: str, spice_json_file: str, questions_json_file: str, datasheet_files: list):
        self.parent_directory = parent_directory
        self.circuit_json_file = circuit_json_file
        self.netlist_file = netlist_file
        self.spice_circuit_file = spice_circuit_file
        self.spice_json_file = spice_json_file
        self.questions_json_file = questions_json_file
        self.datasheet_files = datasheet_files

    def _find_datasheet_file_for_component(self, component_ref: str) -> str:
        for datasheet_file in self.datasheet_files:
            if component_ref in datasheet_file:
                return datasheet_file

        return ""

class ProjectFiles: 
    """
    This class defines the locations of all relevant project files, which are needed for the framework to run the helper functions successfully. 
    """
    def __init__(self):
        self.project_files = {
            "AcornRobotElectronics": self.initialise_acorn_robot_project(),
            "CF-Chef": self.initialise_cf_chef_project(),
            "fan_controller": self.initialise_fan_controller_project(),
            "HadesFCS": self.initialise_hades_fcs_project(),
            "Meshinger": self.initialise_meshinger_project(),
            "OPNhydro-r2": self.initialise_opn_hydro_r2_project(),
            "PortalHardware": self.initialise_portal_hardware_project(),
            "stack-chan": self.initialise_stack_chan_project(),
        }
        
    def initialise_acorn_robot_project(self) -> Project:
        """
        Initialise the AcornRobotElectronics project.
        """

        project_datasheet_files = [
            "./outputs/AcornRobotElectronics/datasheets/C18.pdf",
            "./outputs/AcornRobotElectronics/datasheets/U3.pdf",
            "./outputs/AcornRobotElectronics/datasheets/U6.pdf",
            "./outputs/AcornRobotElectronics/datasheets/U12.pdf",
            "./outputs/AcornRobotElectronics/datasheets/U25.pdf",
            "./outputs/AcornRobotElectronics/datasheets/U28.pdf",
            "./outputs/AcornRobotElectronics/datasheets/U32.pdf",
            "./outputs/AcornRobotElectronics/datasheets/U33.pdf"
        ]

        project = Project(
            parent_directory="./outputs/AcornRobotElectronics",
            circuit_json_file="./outputs/AcornRobotElectronics/cm4-robot.json",
            netlist_file="./outputs/AcornRobotElectronics/cm4-robot.net",
            spice_circuit_file="./outputs/AcornRobotElectronics/cm4_robot_board.cir",
            spice_json_file="./outputs/AcornRobotElectronics/cm4-robot_SPICE_circuit.json",
            questions_json_file="./outputs/AcornRobotElectronics/cm4-robot_60_questions.json",
            datasheet_files=project_datasheet_files
        )

        return project

    def initialise_cf_chef_project(self) -> Project:
        """
        Initialise the CF-Chef project.
        """
        project_datasheet_files = [
            "./outputs/CF-Chef/datasheets/D1.pdf",
            "./outputs/CF-Chef/datasheets/U1.pdf",
            "./outputs/CF-Chef/datasheets/U2.pdf",
            "./outputs/CF-Chef/datasheets/U3.pdf",
            "./outputs/CF-Chef/datasheets/U8.pdf"
        ]

        return Project(
            parent_directory="./outputs/CF-Chef",
            circuit_json_file="./outputs/CF-Chef/controller.json",
            netlist_file="./outputs/CF-Chef/controller.net",
            spice_circuit_file="./outputs/CF-Chef/CF-Chef.cir",
            spice_json_file="./outputs/CF-Chef/CF-Chef_SPICE_circuit.json",
            questions_json_file="./outputs/CF-Chef/CF-Chef_60_questions.json",
            datasheet_files=project_datasheet_files
        )

    def initialise_fan_controller_project(self) -> Project:
        """
        Initialise the fan controller project.
        """

        project_datasheet_files = [
            "./outputs/fan_controller/datasheets/C1.pdf",
            "./outputs/fan_controller/datasheets/C2.pdf",
            "./outputs/fan_controller/datasheets/R2.pdf",
            "./outputs/fan_controller/datasheets/R3.pdf",
            "./outputs/fan_controller/datasheets/R4.pdf",
            "./outputs/fan_controller/datasheets/U1.pdf",
            "./outputs/fan_controller/datasheets/U2.pdf",
            "./outputs/fan_controller/datasheets/U3.pdf"
        ]

        return Project(
            parent_directory="./outputs/fan_controller",
            circuit_json_file="./outputs/fan_controller/fan_controller.json",
            netlist_file="./outputs/fan_controller/fan_controller.net",
            spice_circuit_file="./outputs/fan_controller/fan_controller.cir",
            spice_json_file="./outputs/fan_controller/fan_controller_SPICE_circuit.json",
            questions_json_file="./outputs/fan_controller/fan_controller_60_questions.json",
            datasheet_files=project_datasheet_files
        )

    def initialise_hades_fcs_project(self) -> Project:
        """
        Initialise the Hades Flight Controller System project.
        """

        project_datasheet_files = [
            "./outputs/HadesFCS/datasheets/REG1.pdf",
            "./outputs/HadesFCS/datasheets/REG2.pdf",
            "./outputs/HadesFCS/datasheets/SW2.pdf",
            "./outputs/HadesFCS/datasheets/SW3.pdf",
            "./outputs/HadesFCS/datasheets/U2.pdf",
            "./outputs/HadesFCS/datasheets/U3.pdf",
            "./outputs/HadesFCS/datasheets/U4.pdf",
            "./outputs/HadesFCS/datasheets/U8.pdf",
            "./outputs/HadesFCS/datasheets/U9.pdf"
        ]

        return Project(
            parent_directory="./outputs/HadesFCS",
            circuit_json_file="./outputs/HadesFCS/Hades.json",
            netlist_file="./outputs/HadesFCS/Hades.net",
            spice_circuit_file="./outputs/HadesFCS/Hades.cir",
            spice_json_file="./outputs/HadesFCS/Hades_SPICE_circuit.json",
            questions_json_file="./outputs/HadesFCS/Hades_60_questions.json",
            datasheet_files=project_datasheet_files
        )

    def initialise_meshinger_project(self) -> Project:
        """
        Initialise the Meshinger project.
        """

        project_datasheet_files = [
            "./outputs/Meshinger/datasheets/J2.pdf",
            "./outputs/Meshinger/datasheets/S1.pdf",
            "./outputs/Meshinger/datasheets/U5.pdf",
            "./outputs/Meshinger/datasheets/U6.pdf"
        ]

        return Project(
            parent_directory="./outputs/Meshinger",
            circuit_json_file="./outputs/Meshinger/Meshinger.json",
            netlist_file="./outputs/Meshinger/Meshinger.net",
            spice_circuit_file="./outputs/Meshinger/Meshinger.cir",
            spice_json_file="./outputs/Meshinger/Meshinger_SPICE_circuit.json",
            questions_json_file="./outputs/Meshinger/Meshinger_60_questions.json",
            datasheet_files=project_datasheet_files
        )

    def initialise_opn_hydro_r2_project(self) -> Project:
        """
        Initialise the OPN Hydro R2 project.
        """

        project_datasheet_files = [
            "./outputs/OPNhydro-r2/datasheets/M1.pdf",
            "./outputs/OPNhydro-r2/datasheets/M2.pdf",
            "./outputs/OPNhydro-r2/datasheets/M3.pdf",
            "./outputs/OPNhydro-r2/datasheets/M4.pdf",
            "./outputs/OPNhydro-r2/datasheets/U5.pdf",
        ]

        return Project(
            parent_directory="./outputs/OPNhydro-r2",
            circuit_json_file="./outputs/OPNhydro-r2/OPNhydro_r2.json",
            netlist_file="./outputs/OPNhydro-r2/OPNhydro_r2.net",
            spice_circuit_file="./outputs/OPNhydro-r2/OPNhydro_r2.cir",
            spice_json_file="./outputs/OPNhydro-r2/OPNhydro_r2_SPICE_circuit.json",
            questions_json_file="./outputs/OPNhydro-r2/OPNhydro_r2_60_questions.json",
            datasheet_files=project_datasheet_files
        )

    def initialise_portal_hardware_project(self) -> Project:
        """
        Initialise the Portal Hardware Wallet project.
        """

        project_datasheet_files = [
            "./outputs/PortalHardware/datasheets/C2.pdf",
            "./outputs/PortalHardware/datasheets/J1.pdf",
            "./outputs/PortalHardware/datasheets/R5.pdf",
            "./outputs/PortalHardware/datasheets/U2.pdf",
            "./outputs/PortalHardware/datasheets/U3.pdf",
            "./outputs/PortalHardware/datasheets/U4.pdf",
        ]

        return Project(
            parent_directory="./outputs/PortalHardware",
            circuit_json_file="./outputs/PortalHardware/PCB.json",
            netlist_file="./outputs/PortalHardware/PCB.net",
            spice_circuit_file="./outputs/PortalHardware/PortalHardware.cir",
            spice_json_file="./outputs/PortalHardware/PortalHardware_SPICE_circuit.json",
            questions_json_file="./outputs/PortalHardware/PortalHardware_60_questions.json",
            datasheet_files=project_datasheet_files
        )

    def initialise_stack_chan_project(self) -> Project:
        """
        Initialise the Stack Chan project.
        """

        project_datasheet_files = [
            "./outputs/stack-chan/datasheets/Q1.pdf",
            "./outputs/stack-chan/datasheets/Q2.pdf",
            "./outputs/stack-chan/datasheets/U1.pdf",
        ]

        return Project(
            parent_directory="./outputs/stack-chan",
            circuit_json_file="./outputs/stack-chan/m5-pantilt.json",
            netlist_file="./outputs/stack-chan/m5-pantilt.net",
            spice_circuit_file="./outputs/stack-chan/m5-pantilt.cir",
            spice_json_file="./outputs/stack-chan/m5-pantilt_SPICE_circuit.json",
            questions_json_file="./outputs/stack-chan/m5-pantilt_60_questions.json",
            datasheet_files=project_datasheet_files
        )

def acorn_robot_project(project_files: dict) -> dict:
    project_files["AcornRobotElectronics"] = {
        "parent_directory": "./outputs/AcornRobotElectronics",
        "circuit_json_file": "./outputs/AcornRobotElectronics/cm4-robot.json",
        "netlist_file": "./outputs/AcornRobotElectronics/cm4-robot.net",
        "spice_circuit_file": "./outputs/AcornRobotElectronics/cm4_robot_board.cir",
        "spice_json_file": "./outputs/AcornRobotElectronics/cm4-robot_SPICE_circuit.json",
        "questions_json_file": "./outputs/AcornRobotElectronics/cm4-robot_60_questions.json"
    }

    project_files["AcornRobotElectronics"]["datasheet_files"] = [
        "./outputs/AcornRobotElectronics/datasheets/C18.pdf",
        "./outputs/AcornRobotElectronics/datasheets/U3.pdf",
        "./outputs/AcornRobotElectronics/datasheets/U6.pdf",
        "./outputs/AcornRobotElectronics/datasheets/U12.pdf",
        "./outputs/AcornRobotElectronics/datasheets/U25.pdf",
        "./outputs/AcornRobotElectronics/datasheets/U28.pdf",
        "./outputs/AcornRobotElectronics/datasheets/U32.pdf",
        "./outputs/AcornRobotElectronics/datasheets/U33.pdf"
    ]

    return project_files

def cf_chef_project(project_files: dict) -> dict:
    project_files["CF-Chef"] = {
        "parent_directory": "./outputs/CF-Chef",
        "circuit_json_file": "./outputs/CF-Chef/controller.json",
        "netlist_file": "./outputs/CF-Chef/controller.net",
        "spice_circuit_file": "./outputs/CF-Chef/CF-Chef.cir",
        "spice_json_file": "./outputs/CF-Chef/CF-Chef_SPICE_circuit.json",
        "questions_json_file": "./outputs/CF-Chef/CF-Chef_60_questions.json"
    }

    project_files["CF-Chef"]["datasheet_files"] = [
        "./outputs/CF-Chef/datasheets/D1.pdf",
        "./outputs/CF-Chef/datasheets/U1.pdf",
        "./outputs/CF-Chef/datasheets/U2.pdf",
        "./outputs/CF-Chef/datasheets/U3.pdf",
        "./outputs/CF-Chef/datasheets/U8.pdf"
    ]

    return project_files

def fan_controller_project(project_files: dict) -> dict:
    project_files["fan_controller"] = {
        "parent_directory": "./outputs/fan_controller",
        "circuit_json_file": "./outputs/fan_controller/fan_controller.json",
        "netlist_file": "./outputs/fan_controller/fan_controller.net",
        "spice_circuit_file": "./outputs/fan_controller/fan_controller.cir",
        "spice_json_file": "./outputs/fan_controller/fan_controller_SPICE_circuit.json",
        "questions_json_file": "./outputs/fan_controller/fan_controller_60_questions.json"
    }

    project_files["fan_controller"]["datasheet_files"] = [
        "./outputs/fan_controller/datasheets/C1.pdf",
        "./outputs/fan_controller/datasheets/C2.pdf",
        "./outputs/fan_controller/datasheets/R2.pdf",
        "./outputs/fan_controller/datasheets/R3.pdf",
        "./outputs/fan_controller/datasheets/R4.pdf",
        "./outputs/fan_controller/datasheets/U1.pdf",
        "./outputs/fan_controller/datasheets/U2.pdf",
        "./outputs/fan_controller/datasheets/U3.pdf"
    ]

    return project_files

def hades_fcs_project(project_files: dict) -> dict:
    project_files["HadesFCS"] = {
        "parent_directory": "./outputs/HadesFCS",
        "circuit_json_file": "./outputs/HadesFCS/Hades.json",
        "netlist_file": "./outputs/HadesFCS/Hades.net",
        "spice_circuit_file": "./outputs/HadesFCS/Hades.cir",
        "spice_json_file": "./outputs/HadesFCS/Hades_SPICE_circuit.json",
        "questions_json_file": "./outputs/HadesFCS/Hades_60_questions.json"
    }

    project_files["HadesFCS"]["datasheet_files"] = [
        "./outputs/HadesFCS/datasheets/REG1.pdf",
        "./outputs/HadesFCS/datasheets/REG2.pdf",
        "./outputs/HadesFCS/datasheets/SW2.pdf",
        "./outputs/HadesFCS/datasheets/SW3.pdf",
        "./outputs/HadesFCS/datasheets/U2.pdf",
        "./outputs/HadesFCS/datasheets/U3.pdf",
        "./outputs/HadesFCS/datasheets/U4.pdf",
        "./outputs/HadesFCS/datasheets/U8.pdf",
        "./outputs/HadesFCS/datasheets/U9.pdf"
    ]

    return project_files

def meshinger_project(project_files: dict) -> dict:
    project_files["Meshinger"] = {
        "parent_directory": "./outputs/Meshinger",
        "circuit_json_file": "./outputs/Meshinger/Meshinger.json",
        "netlist_file": "./outputs/Meshinger/Meshinger.net",
        "spice_circuit_file": "./outputs/Meshinger/Meshinger.cir",
        "spice_json_file": "./outputs/Meshinger/Meshinger_SPICE_circuit.json",
        "questions_json_file": "./outputs/Meshinger/Meshinger_60_questions.json"
    }

    project_files["Meshinger"]["datasheet_files"] = [
        "./outputs/Meshinger/datasheets/J2.pdf",
        "./outputs/Meshinger/datasheets/S1.pdf",
        "./outputs/Meshinger/datasheets/U5.pdf",
        "./outputs/Meshinger/datasheets/U6.pdf"
    ]

    return project_files

def opn_hydro_r2_project(project_files: dict) -> dict:
    project_files["OPNhydro-r2"] = {
        "parent_directory": "./outputs/OPNhydro-r2",
        "circuit_json_file": "./outputs/OPNhydro-r2/OPNhydro_r2.json",
        "netlist_file": "./outputs/OPNhydro-r2/OPNhydro_r2.net",
        "spice_circuit_file": "./outputs/OPNhydro-r2/OPNhydro_r2.cir",
        "spice_json_file": "./outputs/OPNhydro-r2/OPNhydro_r2_SPICE_circuit.json",
        "questions_json_file": "./outputs/OPNhydro-r2/OPNhydro_r2_60_questions.json"
    }

    project_files["OPNhydro-r2"]["datasheet_files"] = [
        "./outputs/OPNhydro-r2/datasheets/M1.pdf",
        "./outputs/OPNhydro-r2/datasheets/M2.pdf",
        "./outputs/OPNhydro-r2/datasheets/M3.pdf",
        "./outputs/OPNhydro-r2/datasheets/M4.pdf",
        "./outputs/OPNhydro-r2/datasheets/U5.pdf",
    ]

    return project_files

def portal_hardware_project(project_files: dict) -> dict:
    project_files["PortalHardware"] = {
        "parent_directory": "./outputs/PortalHardware",
        "circuit_json_file": "./outputs/PortalHardware/PCB.json",
        "netlist_file": "./outputs/PortalHardware/PCB.net",
        "spice_circuit_file": "./outputs/PortalHardware/PortalHardware.cir",
        "spice_json_file": "./outputs/PortalHardware/PortalHardware_SPICE_circuit.json",
        "questions_json_file": "./outputs/PortalHardware/PortalHardware_60_questions.json"
    }

    project_files["PortalHardware"]["datasheet_files"] = [
        "./outputs/PortalHardware/datasheets/C2.pdf",
        "./outputs/PortalHardware/datasheets/J1.pdf",
        "./outputs/PortalHardware/datasheets/R5.pdf",
        "./outputs/PortalHardware/datasheets/U2.pdf",
        "./outputs/PortalHardware/datasheets/U3.pdf",
        "./outputs/PortalHardware/datasheets/U4.pdf",
    ]

    return project_files

def stack_chan_project(project_files: dict) -> dict:
    project_files["stack-chan"] = {
        "parent_directory": "./outputs/stack-chan",
        "circuit_json_file": "./outputs/stack-chan/m5-pantilt.json",
        "netlist_file": "./outputs/stack-chan/m5-pantilt.net",
        "spice_circuit_file": "./outputs/stack-chan/m5-pantilt.cir",
        "spice_json_file": "./outputs/stack-chan/m5-pantilt_SPICE_circuit.json",
        "questions_json_file": "./outputs/stack-chan/m5-pantilt_60_questions.json"
    }

    project_files["stack-chan"]["datasheet_files"] = [
        "./outputs/stack-chan/datasheets/Q1.pdf",
        "./outputs/stack-chan/datasheets/Q2.pdf",
        "./outputs/stack-chan/datasheets/U1.pdf",
    ]

    return project_files


if __name__ == "__main__":
    project_files = ProjectFiles().project_files

    with open("project_files.json", 'w', encoding='utf-8') as pf:
        pf.write(json.dumps(project_files, default=lambda o: o.__dict__, indent=3))
