#!/usr/bin/env python3
"""
DEX Set Comparison - Analyzes and compares DEX files across multiple folders.

- Takes two or more folders containing DEX files as input
- Analyzes all DEX files in each folder
- For each DEX in a folder, finds the most similar DEX file in each other folder
- Outputs a detailed comparison report in JSON format, including similarity scores

Output includes:
- Similarity scores between DEX files
- Detailed differences in classes, methods, fields, and strings
- Pairwise comparisons between folders
"""

import argparse
import itertools
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

from dex_compare import (
    get_defined_class_names,
    get_method_signatures,
    get_field_signatures,
    get_string_values,
    compare_bytecode,
)

# Set logging level to ERROR to suppress unnecessary messages
# todo: check upstream
os.environ["LOGURU_LEVEL"] = "ERROR"

try:
    from androguard.misc import AnalyzeDex
    from androguard.core.analysis.analysis import Analysis
except ImportError as e:
    print(f"Error: {e}", file=sys.stderr)
    print(
        "Androguard not found. Please install it: pip install androguard",
        file=sys.stderr,
    )
    sys.exit(1)


class DexData:
    """
    Class to hold analysis data for a DEX file
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file_name = Path(file_path).name
        self.magic_string = ""
        self.dx = None
        self.classes = set()
        self.methods = set()
        self.fields = set()
        self.strings = set()
        self.analyzed = False

    def analyze(self) -> bool:
        """Analyze the DEX file and extract its components"""
        try:
            self.magic_string, _, self.dx = AnalyzeDex(self.file_path)
            if not self.dx:
                print(f"Warning: Failed to analyze {self.file_path}", file=sys.stderr)
                return False

            self.classes = get_defined_class_names(self.dx)
            self.methods = get_method_signatures(self.dx)
            self.fields = get_field_signatures(self.dx)
            self.strings = get_string_values(self.dx)
            self.analyzed = True
            return True
        except Exception as e:
            print(f"Error analyzing {self.file_path}: {e}", file=sys.stderr)
            return False


def calculate_similarity_score(
    dex1: DexData, dex2: DexData, with_bytecode: bool = False
) -> Dict[str, Any]:
    """
    Calculate similarity scores between two DEX files.

    Args:
        dex1: First DexData object
        dex2: Second DexData object
        with_bytecode: Whether to include bytecode comparison in similarity

    Returns:
        Dictionary with similarity data and scores
    """
    if not dex1.analyzed or not dex2.analyzed:
        return {"error": "One or both DEX files could not be analyzed"}

    # Common components
    common_classes = dex1.classes & dex2.classes
    common_methods = dex1.methods & dex2.methods
    common_fields = dex1.fields & dex2.fields
    common_strings = dex1.strings & dex2.strings

    # Unique components
    unique_classes1 = dex1.classes - dex2.classes
    unique_classes2 = dex2.classes - dex1.classes
    unique_methods1 = dex1.methods - dex2.methods
    unique_methods2 = dex2.methods - dex1.methods
    unique_fields1 = dex1.fields - dex2.fields
    unique_fields2 = dex2.fields - dex1.fields
    unique_strings1 = dex1.strings - dex2.strings
    unique_strings2 = dex2.strings - dex1.strings

    # Calculate similarity percentages
    total_classes = len(dex1.classes) + len(dex2.classes) - len(common_classes)
    total_methods = len(dex1.methods) + len(dex2.methods) - len(common_methods)
    total_fields = len(dex1.fields) + len(dex2.fields) - len(common_fields)
    total_strings = len(dex1.strings) + len(dex2.strings) - len(common_strings)

    # Avoid division by zero
    class_similarity = (
        (len(common_classes) / total_classes) * 100 if total_classes > 0 else 100
    )
    method_similarity = (
        (len(common_methods) / total_methods) * 100 if total_methods > 0 else 100
    )
    field_similarity = (
        (len(common_fields) / total_fields) * 100 if total_fields > 0 else 100
    )
    string_similarity = (
        (len(common_strings) / total_strings) * 100 if total_strings > 0 else 100
    )

    # Calculate bytecode similarity if requested
    bytecode_similarity = None
    changed_bc_methods = set()
    if with_bytecode and dex1.dx and dex2.dx and common_methods:
        changed_bc_methods = compare_bytecode(dex1.dx, dex2.dx, common_methods)
        unchanged_methods = len(common_methods) - len(changed_bc_methods)
        bytecode_similarity = (
            (unchanged_methods / len(common_methods)) * 100 if common_methods else 100
        )

    # Calculate overall similarity (weighted average)
    weights = {"classes": 0.35, "methods": 0.35, "fields": 0.15, "strings": 0.15}

    # Adjust weights if bytecode comparison is included
    if bytecode_similarity is not None:
        weights = {
            "classes": 0.25,
            "methods": 0.25,
            "bytecode": 0.25,
            "fields": 0.125,
            "strings": 0.125,
        }

    overall_similarity = (
        weights["classes"] * class_similarity
        + weights["methods"] * method_similarity
        + weights["fields"] * field_similarity
        + weights["strings"] * string_similarity
    )

    if bytecode_similarity is not None:
        overall_similarity += weights["bytecode"] * bytecode_similarity

    # Create result dictionary
    result = {
        "similarity": {
            "overall": round(overall_similarity, 2),
            "classes": round(class_similarity, 2),
            "methods": round(method_similarity, 2),
            "fields": round(field_similarity, 2),
            "strings": round(string_similarity, 2),
        },
        "comparison": {
            "classes": {
                "unique_to_file1": list(unique_classes1),
                "unique_to_file2": list(unique_classes2),
                "common_count": len(common_classes),
            },
            "methods": {
                "unique_to_file1": list(unique_methods1),
                "unique_to_file2": list(unique_methods2),
                "common_count": len(common_methods),
            },
            "fields": {
                "unique_to_file1": list(unique_fields1),
                "unique_to_file2": list(unique_fields2),
                "common_count": len(common_fields),
            },
            "strings": {
                "unique_to_file1": list(unique_strings1),
                "unique_to_file2": list(unique_strings2),
                "common_count": len(common_strings),
            },
        },
    }

    if bytecode_similarity is not None:
        result["similarity"]["bytecode"] = round(bytecode_similarity, 2)
        result["comparison"]["bytecode"] = {
            "changed_methods": list(changed_bc_methods),
            "changed_count": len(changed_bc_methods),
        }

    return result


def find_dex_files(folder_path: str) -> List[str]:
    """
    Find all DEX files in a folder.

    Args:
        folder_path: Path to search for DEX files

    Returns:
        List of paths to DEX files
    """
    dex_files = []
    folder = Path(folder_path)

    if not folder.is_dir():
        print(f"Error: {folder_path} is not a directory", file=sys.stderr)
        return dex_files

    # Find all files with .dex extension
    for file_path in folder.glob("**/*.dex"):
        dex_files.append(str(file_path))

    # Also consider APK files as they may contain DEX
    for file_path in folder.glob("**/*.apk"):
        dex_files.append(str(file_path))

    return dex_files


def process_dex_file(file_path: str) -> Tuple[str, Optional[DexData]]:
    """
    Process a single DEX file for parallel execution.

    Args:
        file_path: Path to the DEX file

    Returns:
        Tuple of (file_path, DexData object or None if analysis failed)
    """
    dex_data = DexData(file_path)
    if dex_data.analyze():
        return file_path, dex_data
    return file_path, None


def analyze_folders(
    folders: List[str], parallel: bool = True
) -> Dict[str, Dict[str, DexData]]:
    """
    Analyze all DEX files in the provided folders.

    Args:
        folders: List of folder paths
        parallel: Whether to use parallel processing

    Returns:
        Dictionary mapping folder names to dictionaries of file paths to DexData objects
    """
    folder_dex_data = {}
    total_files = 0

    # Find all DEX files in all folders
    for folder in folders:
        folder_name = Path(folder).name
        dex_files = find_dex_files(folder)
        folder_dex_data[folder_name] = {}
        total_files += len(dex_files)

        if not dex_files:
            print(f"Warning: No DEX files found in {folder}", file=sys.stderr)
            continue

        print(f"Found {len(dex_files)} DEX files in {folder}")

        if parallel and len(dex_files) > 1:
            # Use parallel processing for many files
            with ProcessPoolExecutor() as executor:
                futures = [
                    executor.submit(process_dex_file, file_path)
                    for file_path in dex_files
                ]
                for i, future in enumerate(as_completed(futures), 1):
                    file_path, dex_data = future.result()
                    if dex_data:
                        file_name = Path(file_path).name
                        folder_dex_data[folder_name][file_name] = dex_data
                    print(f"Processed {i}/{len(dex_files)} files in {folder}", end="\r")
                print()
        else:
            # Sequential processing
            for i, file_path in enumerate(dex_files, 1):
                dex_data = DexData(file_path)
                if dex_data.analyze():
                    file_name = Path(file_path).name
                    folder_dex_data[folder_name][file_name] = dex_data
                print(f"Processed {i}/{len(dex_files)} files in {folder}", end="\r")
            print()

    print(f"Finished analyzing {total_files} DEX files across {len(folders)} folders")
    return folder_dex_data


def compare_folders(
    folder_dex_data: Dict[str, Dict[str, DexData]], with_bytecode: bool = False
) -> Dict[str, Any]:
    """
    Perform pairwise comparison between folders.

    Args:
        folder_dex_data: Mapping of folder names to file data
        with_bytecode: Whether to compare method bytecode

    Returns:
        Dictionary with comparison results
    """
    result = {"folder_comparisons": {}}

    folder_names = list(folder_dex_data.keys())

    # For each pair of folders
    for folder1, folder2 in itertools.combinations(folder_names, 2):
        print(f"Comparing folder '{folder1}' with '{folder2}'...")

        folder_pair = f"{folder1}_vs_{folder2}"
        result["folder_comparisons"][folder_pair] = {"dex_comparisons": []}

        dex_files1 = folder_dex_data[folder1]
        dex_files2 = folder_dex_data[folder2]

        # For each DEX file in folder1, find the most similar in folder2
        for file1_name, dex1 in dex_files1.items():
            best_match = None
            best_similarity = -1
            best_comparison = None

            for file2_name, dex2 in dex_files2.items():
                comparison = calculate_similarity_score(dex1, dex2, with_bytecode)

                if "error" not in comparison:
                    similarity = comparison["similarity"]["overall"]

                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match = file2_name
                        best_comparison = comparison

            if best_match:
                result["folder_comparisons"][folder_pair]["dex_comparisons"].append(
                    {
                        "file1": file1_name,
                        "file2": best_match,
                        "similarity": best_comparison["similarity"],
                        "comparison": best_comparison["comparison"],
                    }
                )

                print(
                    f"  '{file1_name}' best matches '{best_match}' with similarity {best_similarity:.2f}%"
                )

        # Sort by similarity (descending)
        result["folder_comparisons"][folder_pair]["dex_comparisons"].sort(
            key=lambda x: x["similarity"]["overall"], reverse=True
        )

    return result


def main() -> None:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Compare DEX files across multiple folders using Androguard.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  dexset_compare.py folder1 folder2
  dexset_compare.py --bytecode folder1 folder2 folder3
  dexset_compare.py --bytecode --output result.json folder1 folder2
        """,
    )
    parser.add_argument(
        "folders", nargs="+", help="Folders containing DEX files to compare"
    )
    parser.add_argument(
        "--bytecode",
        "-bc",
        action="store_true",
        help="Compare bytecode of methods (can be slow for many files)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Write results to the specified JSON file instead of stdout",
    )
    parser.add_argument(
        "--sequential",
        "-s",
        action="store_true",
        help="Use sequential processing instead of parallel processing",
    )

    args = parser.parse_args()
    args.sequential = True

    if len(args.folders) < 2:
        print(
            "Error: At least two folders must be specified for comparison",
            file=sys.stderr,
        )
        parser.print_help(sys.stderr)
        sys.exit(1)

    # Check that all folders exist
    for folder in args.folders:
        if not Path(folder).is_dir():
            print(f"Error: '{folder}' is not a directory", file=sys.stderr)
            sys.exit(1)

    # Analyze all DEX files in all folders
    folder_dex_data = analyze_folders(args.folders, not args.sequential)

    # Check if any DEX files were found
    total_dex_files = sum(len(files) for files in folder_dex_data.values())
    if total_dex_files == 0:
        print(
            "Error: No DEX files found in any of the specified folders", file=sys.stderr
        )
        sys.exit(1)

    # Compare folders pairwise
    result = compare_folders(folder_dex_data, args.bytecode)

    # Add metadata
    result["metadata"] = {
        "folders": args.folders,
        "folder_counts": {
            folder: len(files) for folder, files in folder_dex_data.items()
        },
        "with_bytecode": args.bytecode,
    }

    # Output the result
    json_result = json.dumps(result, indent=2, default=str)
    if args.output:
        with open(args.output, "w") as f:
            f.write(json_result)
        print(f"Results written to {args.output}")
    else:
        print(json_result)


if __name__ == "__main__":
    main()
