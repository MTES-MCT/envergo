import csv
from pathlib import Path


def asc_to_csv(asc_file, csv_file):
    # Open the ASC file in read mode
    with open(asc_file, "r") as file:
        # Skip the first 7 lines
        for _ in range(7):
            next(file)

        # Open the CSV file in write mode
        with open(csv_file, "w", newline="") as csv_output:
            writer = csv.writer(csv_output)

            # Convert ASC lines to CSV rows
            for line in file:
                # Split the line by whitespace and remove leading/trailing spaces
                values = [value.strip() for value in line.split()]
                writer.writerow(values)


def run_test():
    ALTI_PARENT_FOLDER = str(Path(__file__).parent.parent)
    asc_file_path = f"{ALTI_PARENT_FOLDER}/output/benchmarks/2023_06_29_16_20_03/decision/44_285000_6705000/5v5_50-70-90-110-130-145-160v59-81-98-113-126-138-149-160_12v12/decision_diff.asc"
    csv_file_path = f"{ALTI_PARENT_FOLDER}/output/benchmarks/2023_06_29_16_20_03/decision/44_285000_6705000/5v5_50-70-90-110-130-145-160v59-81-98-113-126-138-149-160_12v12/decision_diff.csv"
    asc_to_csv(asc_file_path, csv_file_path)
