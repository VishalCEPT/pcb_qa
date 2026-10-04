import json
from sklearn.metrics import confusion_matrix, accuracy_score, precision_score, recall_score, f1_score

import file_helpers
from file_helpers import CSVFileOperator, JSONFileOperator
import project_files

class EvaluateResults:
    def __init__(self):
        self.llm_models = ["claude-sonnet-4.6", "gemini-3-flash-preview", "gpt-5.4-nano", "llama-3.3-70b-instruct"]
        self.actual_responses = []
        self.predicted_responses = []

        self.csv_file_operator = CSVFileOperator()
        self.json_file_operator = JSONFileOperator()

        self.project_files_dict = self.json_file_operator.read_from_json_file(read_file="project_files.json")

    def _evaluate_n_responses_for_mode(self, num_questions: int, mode: str, models: list = None):
        if models is None:
            models = self.llm_models

        for model in models: 

            print (f"\n--- For model: {model} ---\n")

            for project_key in self.project_files_dict:
                self.actual_responses = []
                self.predicted_responses = []

                project = self.project_files_dict[project_key]

                target_csv = f'{project["parent_directory"]}/results/{mode}/{model}_{project_key}.csv'
                self.csv_file_operator.create_header_for_csv(csv_file=target_csv, fields = ['Model', 'Question', 'Category', 'Actual_Response', 'Predicted_Response'])

                # Load the questions JSON file
                questions = self._load_questions_from_file(project["questions_json_file"])
                
                # Save question[0]["answer"] as a variable
                for idx in range(0, num_questions): 
                    category = questions[idx]["category"]
                    self.actual_responses.append(questions[idx]["answer"])

                    # Load the results JSON file
                    results_file = f"{project["parent_directory"]}/results/{mode}/{model}/{category}/{idx+1}.json"
                    self._read_response_from_file(results_file)

                    row = [f'{model}', f'Q{idx+1}', f'{category}', f'{questions[idx]["answer"]}', f'{self.predicted_responses[idx]}']
                    self.csv_file_operator.write_row_to_csv(target_csv, row)

                cm = confusion_matrix(self.actual_responses[:num_questions], self.predicted_responses[:num_questions], labels=["YES", "NO"])

                # Calculate metrics
                accuracy = accuracy_score(self.actual_responses[:num_questions], self.predicted_responses[:num_questions])
                precision = precision_score(self.actual_responses[:num_questions], self.predicted_responses[:num_questions], labels=["YES", "NO"], pos_label = "YES", average="macro", zero_division=0)
                recall = recall_score(self.actual_responses[:num_questions], self.predicted_responses[:num_questions], labels=["YES", "NO"], pos_label = "YES", average="macro", zero_division=0)
                f1 = f1_score(self.actual_responses[:num_questions], self.predicted_responses[:num_questions], labels=["YES", "NO"], pos_label = "YES", average="macro", zero_division=0)

                print(f'Accuracy: {accuracy}')
                print(f'Precision: {precision}')
                print(f'Recall: {recall}')
                print(f'F1 Score: {f1}')

                self.csv_file_operator.write_row_to_csv(csv_file=target_csv, row=['Accuracy', 'Precision', 'Recall', 'F1 Score'])
                row = [f'{accuracy}', f'{precision}', f'{recall}', f'{f1}']
                self.csv_file_operator.write_row_to_csv(target_csv, row)

    def _load_questions_from_file(self, questions_file_path: str) -> dict: 
        return self.json_file_operator.read_from_json_file(questions_file_path)

    def _read_response_from_file(self, results_file: str):
        try:
            result = self.json_file_operator.read_from_json_file(results_file)
            self.predicted_responses.append(result["response"]["answer"])

        except FileNotFoundError as e:
            print(e)
            self.predicted_responses.append("N/A")

    def write_nnet_and_ncir_responses_to_csv(self, num_questions: int = 60, mode: str = "NNet&NCir", models: list = None):
        """
        This function writes responses from 'results/NNet&NCir' for each model into CSV.  
        """
        if models is None:
            models = self.llm_models

        self._evaluate_n_responses_for_mode(num_questions, mode, models)

    def write_nnet_and_pcir_responses_to_csv(self, num_questions: int = 15, mode: str = "NNet&PCir", models: list = None):
        """
        This function writes responses from 'results/NNet&PCir' for each model into CSV.  
        """
        if models is None:
            models = self.llm_models

        self._evaluate_n_responses_for_mode(num_questions, mode, models)

    def write_pnet_and_ncir_responses_to_csv(self, num_questions: int = 15, mode: str = "PNet&NCir", models: list = None):
        """
        This function writes responses from 'results/PNet&NCir' for each model into CSV.  
        """     
        if models is None:
            models = self.llm_models   

        self._evaluate_n_responses_for_mode(num_questions, mode, models)

    def write_pnet_and_pcir_responses_to_csv(self, num_questions: int = 60, mode: str = "PNet&PCir", models: list = None):
        """
        This function writes responses from 'results/PNet&PCir' for each model into CSV.  
        """     
        if models is None:
            models = self.llm_models  

        self._evaluate_n_responses_for_mode(num_questions, mode, models)

    def write_schematic_as_pdfs_responses_to_csv(self, num_questions: int = 15, mode: str = "PDF", models: list = ["gpt-5.4-nano"]):
        """
        This function writes responses from 'results/PDF' for each model into CSV.  
        """   

        self._evaluate_n_responses_for_mode(num_questions, mode, models)

if __name__ == "__main__":
    evaluate_results = EvaluateResults()

    evaluate_results.write_nnet_and_ncir_responses_to_csv()
    evaluate_results.write_nnet_and_pcir_responses_to_csv()
    evaluate_results.write_pnet_and_ncir_responses_to_csv()
    evaluate_results.write_pnet_and_pcir_responses_to_csv()
    evaluate_results.write_schematic_as_pdfs_responses_to_csv()