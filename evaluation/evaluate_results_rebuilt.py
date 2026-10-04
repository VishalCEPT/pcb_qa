import json
import csv
from pathlib import Path

from sklearn.metrics import (
    confusion_matrix,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
)


class EvaluateResults:

    def __init__(self):
        self.experiments = {
            "PDF": "gemini_pdf_20_results.json",
            "Circuit JSON": "gemini_json_20_results.json",
            "SPICE JSON": "gemini_spice_20_results.json",
            "Datasheet": "gemini_datasheet_20_results.json",
        }

    def _extract_answer(self, response: str) -> str:
        import re

        text = response.strip()

        # 1. Explicit YES/NO at the beginning of the response.
        match = re.match(
            r"^\s*(?:\*\*)?\s*(YES|NO)\b",
            text,
            re.IGNORECASE
        )

        if match:
            return match.group(1).upper()

        # 2. Explicit YES/NO anywhere in the response,
        # especially Markdown forms such as **Yes** or **No**.
        match = re.search(
            r"\*\*\s*(YES|NO)\s*\*\*",
            text,
            re.IGNORECASE
        )

        if match:
            return match.group(1).upper()

        # 3. Explicit answer declarations.
        match = re.search(
            r"(?:answer\s*(?:is|:)\s*)(?:\*\*)?\s*(YES|NO)\b",
            text,
            re.IGNORECASE
        )

        if match:
            return match.group(1).upper()

        # 4. Common negative connectivity wording.
        negative_patterns = [
            r"\bnot\s+connected\b",
            r"\bdoes\s+not\s+exist\b",
            r"\bdoes\s+not\s+connect\b",
            r"\bis\s+not\s+connected\b",
        ]

        for pattern in negative_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return "NO"

        # 5. Common positive connectivity wording.
        positive_patterns = [
            r"\bis\s+connected\b",
            r"\bconnected\s+to\b",
        ]

        for pattern in positive_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return "YES"

        return "UNKNOWN"
    def _load_results(self, file_path: str):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _calculate_metrics(self, actual, predicted):

        labels = ["YES", "NO"]

        cm = confusion_matrix(
            actual,
            predicted,
            labels=labels
        )

        accuracy = accuracy_score(actual, predicted)

        precision = precision_score(
            actual,
            predicted,
            labels=labels,
            average="macro",
            zero_division=0
        )

        recall = recall_score(
            actual,
            predicted,
            labels=labels,
            average="macro",
            zero_division=0
        )

        f1 = f1_score(
            actual,
            predicted,
            labels=labels,
            average="macro",
            zero_division=0
        )

        tn, fp, fn, tp = cm.ravel()

        return {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "tn": tn,
            "fp": fp,
            "fn": fn,
            "tp": tp,
        }

    def evaluate_experiment(self, experiment_name, file_path):

        print("\n" + "=" * 60)
        print(f"EXPERIMENT: {experiment_name}")
        print("=" * 60)

        results = self._load_results(file_path)

        actual = []
        predicted = []
        rows = []

        for item in results:

            # The PDF, Circuit JSON and SPICE JSON files use:
            #   expected_answer / gemini_response
            #
            # The Datasheet file uses:
            #   expected / predicted / response

            if "expected_answer" in item:
                expected = item["expected_answer"].strip().upper()
                response = item["gemini_response"]
                prediction = self._extract_answer(response)

            elif "expected" in item:
                expected = item["expected"].strip().upper()
                response = item.get("response", "")
                prediction = item.get(
                    "predicted",
                    self._extract_answer(response)
                ).strip().upper()

            else:
                raise KeyError(
                    "Unsupported result format: "
                    "expected answer field not found."
                )

            actual.append(expected)
            predicted.append(prediction)

            rows.append({
                "Question_Number": item["question_number"],
                "Category": item.get(
                    "category",
                    "component_datasheet"
                ),
                "Question": item["question"],
                "Expected_Answer": expected,
                "Predicted_Answer": prediction,
                "Gemini_Response": response,
            })

            status = "CORRECT" if expected == prediction else "WRONG"

            print(
                f"Q{item['question_number']:02d}: "
                f"Expected={expected:<3} "
                f"Predicted={prediction:<7} "
                f"{status}"
            )

        # Evaluate all questions.
        # An UNKNOWN prediction is an incorrect prediction.
        metric_actual = []
        metric_predicted = []

        for a, p in zip(actual, predicted):

            metric_actual.append(a)

            if p in ("YES", "NO"):
                metric_predicted.append(p)
            else:
                # Represent UNKNOWN as the opposite class so that
                # it is counted as an error in the binary metrics.
                metric_predicted.append(
                    "NO" if a == "YES" else "YES"
                )

        metrics = self._calculate_metrics(
            metric_actual,
            metric_predicted
        )

        print("\nMetrics")
        print("-" * 40)
        print(f"Questions evaluated : {len(actual)}")
        print(f"Valid predictions   : {sum(p in ("YES", "NO") for p in predicted)}")
        print(f"Unknown predictions: {sum(p == "UNKNOWN" for p in predicted)}")
        print(f"Accuracy            : {metrics['accuracy']:.4f}")
        print(f"Macro Precision     : {metrics['precision']:.4f}")
        print(f"Macro Recall        : {metrics['recall']:.4f}")
        print(f"Macro F1            : {metrics['f1']:.4f}")

        print("\nConfusion Matrix")
        print("-" * 40)
        print("                 Predicted")
        print("                 YES    NO")
        print(
            f"Actual YES       {metrics['tp']:3d}    {metrics['fn']:3d}"
        )
        print(
            f"Actual NO        {metrics['fp']:3d}    {metrics['tn']:3d}"
        )

        return rows, metrics

    def save_question_results(self, experiment_name, rows):

        safe_name = experiment_name.lower().replace(" ", "_")

        output_file = Path(
            f"evaluation_{safe_name}_questions.csv"
        )

        fieldnames = [
            "Question_Number",
            "Category",
            "Question",
            "Expected_Answer",
            "Predicted_Answer",
            "Gemini_Response",
        ]

        with open(
            output_file,
            "w",
            newline="",
            encoding="utf-8"
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=fieldnames
            )

            writer.writeheader()
            writer.writerows(rows)

        print(f"\nDetailed results saved to: {output_file}")

    def save_summary(self, summary):

        output_file = Path("evaluation_summary.csv")

        fieldnames = [
            "Experiment",
            "Questions",
            "Accuracy",
            "Macro_Precision",
            "Macro_Recall",
            "Macro_F1",
            "TP",
            "TN",
            "FP",
            "FN",
        ]

        with open(
            output_file,
            "w",
            newline="",
            encoding="utf-8"
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=fieldnames
            )

            writer.writeheader()
            writer.writerows(summary)

        print(f"\nSummary saved to: {output_file}")

    def run(self):

        print("=" * 60)
        print("PCB-QA GEMINI REPRODUCTION EVALUATION")
        print("=" * 60)

        summary = []

        for experiment_name, file_path in self.experiments.items():

            rows, metrics = self.evaluate_experiment(
                experiment_name,
                file_path
            )

            self.save_question_results(
                experiment_name,
                rows
            )

            summary.append({
                "Experiment": experiment_name,
                "Questions": len(rows),
                "Accuracy": f"{metrics['accuracy']:.4f}",
                "Macro_Precision": f"{metrics['precision']:.4f}",
                "Macro_Recall": f"{metrics['recall']:.4f}",
                "Macro_F1": f"{metrics['f1']:.4f}",
                "TP": metrics["tp"],
                "TN": metrics["tn"],
                "FP": metrics["fp"],
                "FN": metrics["fn"],
            })

        print("\n" + "=" * 60)
        print("FINAL SUMMARY")
        print("=" * 60)

        print(
            f"{'Experiment':<20}"
            f"{'Questions':>10}"
            f"{'Accuracy':>12}"
            f"{'Precision':>12}"
            f"{'Recall':>12}"
            f"{'F1':>12}"
        )

        print("-" * 78)

        for row in summary:

            print(
                f"{row['Experiment']:<20}"
                f"{row['Questions']:>10}"
                f"{float(row['Accuracy']):>11.2%}"
                f"{float(row['Macro_Precision']):>12.2%}"
                f"{float(row['Macro_Recall']):>12.2%}"
                f"{float(row['Macro_F1']):>12.2%}"
            )

        self.save_summary(summary)


if __name__ == "__main__":
    evaluator = EvaluateResults()
    evaluator.run()




