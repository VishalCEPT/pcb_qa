import json

from circuit_json import CircuitJSON

from backend import board_service


def _circuit_file(tmp_path, circuit):
    path = tmp_path / "circuit.json"
    path.write_text(json.dumps(circuit))
    return str(path)


def test_component_match_is_exact_not_substring(tmp_path):
    circuit = {
        "components": {"R1": {}, "R10": {}},
        "nets": {"PWM1": [{"component": "R10", "pin": {}}]},
        "subcircuits": [],
    }
    cj = CircuitJSON(circuit_file=_circuit_file(tmp_path, circuit))

    assert cj.is_component_in_net_from_circuit("R10", "PWM1") is True
    assert cj.is_component_in_net_from_circuit("R1", "PWM1") is False


def test_subcircuit_lookup(tmp_path):
    circuit = {
        "components": {},
        "nets": {},
        "subcircuits": [{
            "name": "power",
            "components": {"U1": {}},
            "nets": {"VCC": [{"component": "U1", "pin": {}}]},
        }],
    }
    cj = CircuitJSON(circuit_file=_circuit_file(tmp_path, circuit))

    assert cj.is_component_in_net_from_circuit("U1", "VCC") is True
    assert cj.is_component_in_net_from_circuit("U1", "GND") is False


def test_real_board_connections(board):
    circuit = board_service.load_or_generate_circuit(board)
    cj = CircuitJSON(circuit_file=circuit.circuit_json_path)

    # From the board's own question bank: "Is the component D2 connected to Net__D2_K_?" -> YES
    assert cj.is_component_in_net_from_circuit("D2", "Net__D2_K_") is True
    assert cj.is_component_in_net_from_circuit("C5", "_p_3V3") is True
    assert cj.is_component_in_net_from_circuit("R1", "PWM1") is False
