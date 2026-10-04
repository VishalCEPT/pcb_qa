import json

import pytest

from kicad_spice_circuit_processer import KiCadSPICECircuitProcesser

RAW_TEMPLATE = """Title: KiCad schematic
Date: Thu Jan  1 00:00:00 2026
Plotname: Transient Analysis
Flags: real
No. Variables: 3
No. Points: {n_points}
Variables:
\t0\ttime\ttime
\t1\tv(+3v3)\tvoltage
\t2\tv(out)\tvoltage
Values:
{values}
"""


def make_raw(path, rail_values, out_values):
    lines = []
    for i, (rail, out) in enumerate(zip(rail_values, out_values)):
        lines.append(f" {i}\t{i * 1e-4:.15e}")
        lines.append(f"\t{rail:.15e}")
        lines.append(f"\t{out:.15e}")
    path.write_text(RAW_TEMPLATE.format(n_points=len(rail_values), values="\n".join(lines)))
    return str(path)


@pytest.mark.parametrize("text, expected", [("3V3", 3.3), ("5V", 5.0), ("12V", 12.0), ("1v8", 1.8)])
def test_convert_voltage_str(text, expected):
    assert KiCadSPICECircuitProcesser("", output_file="x")._convert_voltage_str(text) == pytest.approx(expected)


def test_convert_project_spice_to_circuit(tmp_path):
    cir = tmp_path / "board.cir"
    cir.write_text(
        ".title test\n"
        "R1 +3V3 SIGNAL_GND_SENSE 10k\n"
        "R2 SIGNAL_GND_SENSE GND 10k\n"
        "J1 __J1\n"
        "R3 A B 1k\n"
        ".end\n"
    )
    processor = KiCadSPICECircuitProcesser(str(cir), output_dir=str(tmp_path), output_file=str(tmp_path / "out.json"))
    processor.convert_project_spice_to_circuit("board_generated")

    generated = (tmp_path / "board_generated.cir").read_text()

    assert "R2 SIGNAL_GND_SENSE 0 10k" in generated
    assert "SIGNAL_0_SENSE" not in generated
    assert "V_3V3 +3V3 0 DC 3.3" in generated
    # Regression: the line just before .end used to be dropped unconditionally.
    assert "R3 A B 1k" in generated
    assert "__J1" not in generated
    assert ".control" in generated and "board_generated_raw.raw" in generated
    assert generated.rstrip().endswith(".end")


def test_parse_raw_and_check_voltage(tmp_path):
    raw = make_raw(tmp_path / "sim.raw", rail_values=[3.3] * 12, out_values=[0.0] * 2 + [1.2] * 10)
    processor = KiCadSPICECircuitProcesser("", output_file=str(tmp_path / "sim.json"))

    data = processor.parse_spice_simulated_data(raw)

    assert data["1"]["name"] == "v(+3v3)"
    assert len(data["1"]["values"]) == 12
    assert len(data["2"]["values"]) == 12

    json_path = tmp_path / "sim.json"
    json_path.write_text(json.dumps(data))
    check = processor.check_steady_state_average_matches_expected_voltage

    assert check(str(json_path), "+3V3", "3.3V") is True
    assert check(str(json_path), "+3v3", "3.27V") is True
    assert check(str(json_path), "+3V3", "3.0V") is False
    assert check(str(json_path), "OUT", "1.2V") is True
    assert check(str(json_path), "OUT", "1.2V", tolerance=0.0) is True
    assert check(str(json_path), "no_such_net", "1.2V") is False
