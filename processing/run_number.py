from pathlib import Path
from typing import Union, Set
import re

def get_next_run_number(next_run_number_path: Path) -> int:
    """Looks at the daq/static/next_run_number.txt which stores the next run number from daq"""
    with open(next_run_number_path, 'r') as file:
        run_number = file.read().strip()
    return int(run_number)

def extract_run_number(file_path: Path, reg_expression: str) -> Union[None, int]:
    """
    From file path it extracts the run number, if no run number is found it returns nothing. 
    Only one capture group is allowed in the regular expression
    """
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found for: {file_path}")

    expression = re.compile(reg_expression)
    match = expression.match(file_path.name)
    if not match:
        return None

    if len(match.groups()) != 1:
        raise ValueError(f"Please provide only one capture group in regular expression, {len(match.groups())} found. Remember in regex capture groups are denoted by parenthesis ()")

    run_num_raw = match.group(1)
    if not run_num_raw.isdigit():
        raise ValueError(f"Your inputted regular expression did not output an integer. Output: {run_num_raw}")

    return int(run_num_raw)

def find_file_by_run_number(source_directory: Path, run_number: int, filename_regex: str):
    """
    Looks through all files in source directory, matching the filename using the filename_regex,
    returns the file with matching run number.
    """
    for file in source_directory.iterdir():
        if not file.is_file():
            continue
        matched_run_number = extract_run_number(file, filename_regex)
        if matched_run_number is None:
            continue

        if run_number == matched_run_number:
            return file

def get_all_run_numbers(directory: Path, reg_expression: str) -> Set[int]:
    """
    Finds all run numbers in a directory based off of a regular expression.
    Supports only one capture group in the regular expression (this should be for the run number!)
    If a non integer string is found, it raises a Value Error.
    """
    run_numbers = set()
    if not directory.is_dir():
        raise NotADirectoryError(f"Directory not found for: {directory}")
    
    for file in directory.iterdir():
        if not file.is_file():
            continue
        run_num = extract_run_number(file, reg_expression)
        if run_num is not None:
            run_numbers.add(run_num)
    return run_numbers