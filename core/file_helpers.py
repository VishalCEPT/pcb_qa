import csv
import json

class JSONFileOperator: 
    def __init__(self):
        pass

    def read_from_json_file(self, read_file: str) -> dict:
        with open(read_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def write_to_json_file(self, contents: dict, output_file: str):
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(contents, f, indent=4, ensure_ascii=False)


class CSVFileOperator: 
    def __init__(self):
        pass

    def create_header_for_csv(self, csv_file: str, fields: list):
        with open(csv_file, 'w', newline='', encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()  # Writes the header row

    def write_row_to_csv(self, csv_file: str, row: list):
        with open(csv_file, 'a', newline='\n', encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(row)
