from enum import Enum, auto
from functools import lru_cache
import os
import faiss
import json
import pdfplumber

from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter

import circuit_json, kicad_netlist_processer, kicad_spice_circuit_processer, project_files

from circuit_json import CircuitJSON
from kicad_netlist_processer import KiCadNetlistProcesser
from kicad_spice_circuit_processer import KiCadSPICECircuitProcesser 
from project_files import ProjectFiles


@lru_cache(maxsize=1)
def _embedding_model() -> SentenceTransformer:
    # Loading the model re-checks the HF Hub each time; load it once per process.
    return SentenceTransformer("all-MiniLM-L6-v2")


class ToolCaller:
    # Any file path supplied via an LLM tool-call argument must resolve inside one
    # of these directories. This prevents a tool-call argument from being used to
    # read arbitrary files on disk (path traversal / arbitrary file read).
    _ALLOWED_ROOT_DIRS = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Boards")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outputs")),
    ]

    @classmethod
    def _resolve_and_validate_path(cls, path: str) -> str:
        resolved = os.path.realpath(path)
        for root in cls._ALLOWED_ROOT_DIRS:
            if resolved == root or resolved.startswith(root + os.sep):
                return resolved
        raise PermissionError(
            f"Refusing to access path outside allowed project directories: {path}"
        )

    class Mode(Enum):
        JSON_CIRCUIT_AND_SPICE_JSON = 1 # .JSON.net & .JSON.cir
        PRIMITIVE = 2 # .net and .cir
        JSON_CIRCUIT_AND_SPICE_CONTENTS = 3 # .JSON.net & .cir
        SPICE_JSON_AND_NETLIST_CONTENTS = 4 # .JSON.cir & .net
        JSON_NET = 5 # .JSON.net
        JSON_CIRCUIT = 6 # .JSON.cir (not enough information though)
        NET = 7 # .net 
        CIRCUIT = 8 # .cir (not enough information though)
        SCHEMATIC_PDF = 9 # .sch as PDF
        INVALID = auto()


    def __init__(self):
        self.llm_tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_relevant_context_from_question",
                    "description": "Check component specifications in datasheet and see if they match the question",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string", "description": "The question to answer"},
                            "project_context": {
                                "type": "object", 
                                "description": "Context of the project, including file paths for circuit JSON, spice JSON, and datasheet files", 
                                "properties": {  
                                    "circuit_json_file": {"type": "string", "description": "Path to circuit JSON"},
                                    "spice_json_file": {"type": "string", "description": "Path to SPICE netlist JSON"},
                                    "datasheet_files": {
                                        "type": "array",
                                        "items": {"type": "string", "description": "Path to datasheet files associated with the project"}
                                    }
                                },
                                "required": ["circuit_json_file", "spice_json_file", "datasheet_files"],  
                                "additionalProperties": False  
                            },
                            "component_ref": {"type": "string", "description": "Reference designator (e.g., R1, U2)"},
                        },
                        "required": ["question", "project_context", "component_ref"],
                        "additionalProperties": False 
                    },
                    "strict": True  
                }
            },
            {
                "type": "function", 
                "function": {
                    "name": "calculate_spice_behaviour",
                    "description": "Analyse signal behavior in SPICE simulation and answer the question based on voltage characteristics",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "net_name": {"type": "string", "description": "Net name (e.g. SWDIO, net-_u4-vcomh_, net-_a2-btn_, GND)"},
                            "spice_json_file": {"type": "string", "description": "Path to the SPICE JSON file"},
                            "expected_voltage": {"type": "string", "description": "Expected voltage level (e.g. 3.3V)"}
                        },
                        "required": ["net_name", "spice_json_file", "expected_voltage"],
                        "additionalProperties": False  
                    },
                    "strict": True  
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "find_connections_for_component",
                    "description": "Check if a component is connected to a net in the layout and answer the question based on the connections",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "circuit_json_file": {"type": "string", "description": "Path to the circuit JSON file"},
                            "component_ref": {"type": "string", "description": "Component reference (e.g. C1, U2)"},
                            "net_name": {"type": "string", "description": "Net name (e.g. GND, VCC, SWDIO)"}
                        },
                        "required": ["circuit_json_file", "component_ref", "net_name"],
                        "additionalProperties": False 
                    },
                    "strict": True  
                }
            }
        ]

        self.available_functions = {
            "get_relevant_context_from_question": self.get_relevant_context_from_question,
            "calculate_spice_behaviour": self.calculate_spice_behaviour,
            "find_connections_for_component": self.find_connections_for_component
        }

    def _ensure_datasheet_index(self, datasheet_file: str):
        """
        Create the FAISS index and chunk store if they do not exist.
        Otherwise, reuse the existing RAG artifacts.
        """

        datasheet_file = self._resolve_and_validate_path(datasheet_file)

        datasheet_dir = os.path.dirname(datasheet_file)

        datasheet_name = os.path.splitext(
            os.path.basename(datasheet_file)
        )[0]

        embeddings_dir = os.path.join(
            os.path.dirname(datasheet_dir),
            "embeddings"
        )

        os.makedirs(embeddings_dir, exist_ok=True)

        chunks_store_file_path = os.path.join(
            embeddings_dir,
            f"{datasheet_name}_chunks.json"
        )

        index_file_path = os.path.join(
            embeddings_dir,
            f"{datasheet_name}_embeddings.index"
        )

        # Reuse existing index and chunks
        if (
            os.path.exists(index_file_path)
            and os.path.exists(chunks_store_file_path)
        ):
            print(f"Using existing RAG index for {datasheet_file}")
            return index_file_path, chunks_store_file_path

        # Build index if it does not exist
        print(f"Creating RAG index for {datasheet_file}...")

        text = ""

        with pdfplumber.open(datasheet_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()

                if page_text:
                    text += page_text + "\n"

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50
        )

        chunks = splitter.split_text(text)

        print(f"Created {len(chunks)} chunks")

        model = _embedding_model()

        embeddings = model.encode(
            chunks,
            convert_to_numpy=True
        )

        dimension = embeddings.shape[1]

        index = faiss.IndexFlatL2(dimension)

        index.add(embeddings)

        chunked_data = []

        for i, chunk in enumerate(chunks):
            chunked_data.append({
                "faiss_index_id": i,
                "text": chunk
            })

        with open(
            chunks_store_file_path,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                chunked_data,
                f,
                ensure_ascii=False,
                indent=2
            )

        faiss.write_index(
            index,
            index_file_path
        )

        print(f"Chunks saved to: {chunks_store_file_path}")
        print(f"FAISS index saved to: {index_file_path}")

        return index_file_path, chunks_store_file_path

    def find_and_embed_datasheets_for_project(self, project_files: dict, project_name: str):
        for datasheet_file in project_files[project_name]["datasheet_files"]:
            self._ensure_datasheet_index(datasheet_file)

    def get_relevant_context_from_question(self,
                                           question: str,
                                           project_context: dict,
                                           component_ref: str) -> list:

        try:
            print("Project context:", project_context)

            # Find the datasheet corresponding to this component
            datasheet_file = None

            for file_path in project_context["datasheet_files"]:
                file_name = os.path.splitext(
                    os.path.basename(file_path)
                )[0]

                if file_name == component_ref:
                    datasheet_file = file_path
                    break

            if datasheet_file is None:
                raise FileNotFoundError(
                    f"No datasheet found for component {component_ref}"
                )

            # Make sure the FAISS index exists.
            index_file_path, chunks_store_file_path = (
                self._ensure_datasheet_index(datasheet_file)
            )

            # Load FAISS index
            loaded_index = faiss.read_index(
                index_file_path
            )

            # Load corresponding chunks
            with open(
                chunks_store_file_path,
                "r",
                encoding="utf-8"
            ) as f:
                stored_data = json.load(f)

            model = _embedding_model()
            query_embedding = model.encode([question], convert_to_numpy=True)

            # Search for the top 3 nearest neighbors
            distances, indices = loaded_index.search(query_embedding, 3)

            relevant_context = []

            for i, idx in enumerate(indices[0]):
                item = stored_data[idx] 
                relevant_context.append(item["text"])

            return relevant_context
        
        except Exception as e:
            print(
                f"Error retrieving context for datasheets in "
                f"{project_context['datasheet_files']}:",
                e
            )
            return []

    def calculate_spice_behaviour(self,
                                  spice_json_file: str,
                                  net_name: str,
                                  expected_voltage: str):
        try:
            spice_json_file = self._resolve_and_validate_path(spice_json_file)
            spice_circuit_processer = KiCadSPICECircuitProcesser(spice_circuit_path="", project_name=None, output_file=spice_json_file)
            return spice_circuit_processer.check_steady_state_average_matches_expected_voltage(spice_json_file=spice_json_file, net_name=net_name, expected_voltage=expected_voltage)

        except Exception as e:
            print("Error in calculating SPICE behaviour:", e)
            return False

    def find_connections_for_component(self,
                                       circuit_json_file: str,
                                       component_ref: str,
                                       net_name: str) -> bool:

        try:
            circuit_json_file = self._resolve_and_validate_path(circuit_json_file)
            circuit_json_object = CircuitJSON(circuit_file=circuit_json_file)
            return circuit_json_object.is_component_in_net_from_circuit(component_ref, net_name)
        except Exception as e:
            print("Error in finding connections for component:", e)
            return False

    def find_all_entries_from_netlist_file_with(self, project_context: dict, component_ref: str) -> str:
        netlist_processer = KiCadNetlistProcesser(netlist_path=project_context["netlist_file"], output_dir=project_context["parent_directory"]+"/dry_run")
        return netlist_processer.find_all_entries_from_netlist_file_with(component_ref).to_str()

    def find_all_entries_from_SPICE_circuit_with(self, project_context: dict, net_name: str):
        spice_circuit_processer = KiCadSPICECircuitProcesser(spice_circuit_path=project_context["spice_circuit_file"], project_name=None, output_file=project_context["spice_json_file"])
        spice_circuit_processer.find_all_entries_from_SPICE_circuit_with(net_name)

if __name__ == "__main__":
    tool_caller = ToolCaller()
    acorn_robot_project = vars(ProjectFiles().initialise_acorn_robot_project())
    # print(acorn_robot_project)
    tool_caller.find_all_entries_from_SPICE_circuit_with(acorn_robot_project, "SERIAL_CAN_PWR_3.3V")

    # ans = tool_caller.calculate_spice_behaviour(spice_json_file=acorn_robot_project["spice_json_file"], net_name="ser_select", expected_voltage="0.0V")
    # print(ans)

    # # Returns True
    # ans = tool_caller.calculate_spice_behaviour(spice_json_file=acorn_robot_project["spice_json_file"], net_name="ser_select", expected_voltage="3.3V")
    # print(ans)

    # # Returns True
    # ans = tool_caller.find_connections_for_component(circuit_json_file=acorn_robot_project["circuit_json_file"], component_ref="C18", net_name="GND")
    # print(ans)

    # ans = tool_caller.find_connections_for_component(circuit_json_file=acorn_robot_project["circuit_json_file"], component_ref="C18", net_name="FB")
    # print(ans)