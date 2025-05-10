#!/usr/bin/env python3
"""
DEX Comparison Tool - Analyzes and compares two Android DEX files.

This tool provides detailed comparison between DEX files, showing differences in:
- Defined classes
- Methods
- Method bytecode
- Fields
- String constants

Output can be formatted as human-readable text or JSON.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Set, Dict, Any

os.environ["LOGURU_LEVEL"] = "ERROR"

try:
    from androguard.misc import AnalyzeDex
    from androguard.core.analysis.analysis import (
        Analysis,
        ClassAnalysis,
        MethodAnalysis,
        FieldAnalysis,
    )
    from androguard.core.dex import DEX, EncodedMethod, ClassDefItem
except ImportError as e:
    print(f"Error: {e}", file=sys.stderr)
    print(
        "Androguard not found. Please install it: pip install androguard",
        file=sys.stderr,
    )
    sys.exit(1)


def get_defined_class_names(dx: Analysis) -> Set[str]:
    """
    Extract names of classes defined within the DEX.

    Args:
        dx: The Androguard Analysis object

    Returns:
        Set of class names defined in the DEX
    """
    names: Set[str] = set()
    if not dx:
        return names

    for cls in dx.get_classes():
        # is_external() checks if the class is defined outside the DEX(s)
        if not cls.is_external():
            vm_class = cls.get_vm_class()
            if isinstance(vm_class, ClassDefItem):  # Ensure it's a defined class
                names.add(vm_class.get_name())
    return names


def get_method_signatures(dx: Analysis) -> Set[str]:
    """
    Extract full signatures (Class->NameDescriptor) of methods.

    Args:
        dx: The Androguard Analysis object

    Returns:
        Set of method signatures
    """
    signatures: Set[str] = set()
    if not dx:
        return signatures

    for method in dx.get_methods():
        # method.full_name provides a unique signature
        signatures.add(method.full_name)
    return signatures


def get_field_signatures(dx: Analysis) -> Set[str]:
    """
    Extract full signatures (Class->Name:Descriptor) of fields.

    Args:
        dx: The Androguard Analysis object

    Returns:
        Set of field signatures
    """
    signatures: Set[str] = set()
    if not dx:
        return signatures

    for field_analysis in dx.get_fields():
        field = field_analysis.get_field()
        # Create a unique representation for the field
        sig = f"{field.get_class_name()}->{field.get_name()}:{field.get_descriptor()}"
        signatures.add(sig)
    return signatures


def get_string_values(dx: Analysis) -> Set[str]:
    """
    Extract unique string values.

    Args:
        dx: The Androguard Analysis object

    Returns:
        Set of unique strings in the DEX
    """
    values: Set[str] = set()
    if not dx:
        return values

    for s in dx.get_strings():
        values.add(s.get_value())
    return values


def compare_bytecode(
    dx1: Analysis, dx2: Analysis, common_method_signatures: Set[str]
) -> Set[str]:
    """
    Compare bytecode of methods present in both DEX files.

    Args:
        dx1: The first Androguard Analysis object
        dx2: The second Androguard Analysis object
        common_method_signatures: Set of method signatures common to both DEX files

    Returns:
        Set of method signatures with different bytecode
    """
    changed_methods: Set[str] = set()
    method_map1 = {m.full_name: m for m in dx1.get_methods()}
    method_map2 = {m.full_name: m for m in dx2.get_methods()}

    for sig in common_method_signatures:
        method1_analysis = method_map1.get(sig)
        method2_analysis = method_map2.get(sig)

        if not method1_analysis or not method2_analysis:
            print(
                f"Warning: Could not find method '{sig}' in both analyses for bytecode comparison.",
                file=sys.stderr,
            )
            continue

        # Get the underlying EncodedMethod objects
        m1 = method1_analysis.get_method()
        m2 = method2_analysis.get_method()

        # Check if methods are concrete (have code)
        if not isinstance(m1, EncodedMethod) or not isinstance(m2, EncodedMethod):
            continue  # Skip abstract/native methods or external

        code1 = m1.get_code()
        code2 = m2.get_code()

        # Handle cases where one or both methods might not have code (e.g., abstract, native)
        raw_code1 = code1.get_raw() if code1 else None
        raw_code2 = code2.get_raw() if code2 else None

        if raw_code1 != raw_code2:
            changed_methods.add(sig)

    return changed_methods


def compare_dex_files(
    file1_path: str,
    file2_path: str,
    compare_bc: bool = False,
    json_output: bool = False,
) -> Dict[str, Any]:
    """
    Load and compare two DEX files.

    Args:
        file1_path: Path to the first DEX file
        file2_path: Path to the second DEX file
        compare_bc: Whether to compare method bytecode
        json_output: Whether to format output as JSON

    Returns:
        Dictionary containing comparison results (for JSON output)
    """
    path1 = Path(file1_path)
    path2 = Path(file2_path)

    # Result dictionary for JSON output
    result: Dict[str, Any] = {
        "file1": str(path1),
        "file2": str(path2),
        "comparison": {},
    }

    if not path1.is_file() or not path2.is_file():
        error_msg = "Error: One or both input files not found."
        print(error_msg, file=sys.stderr)
        result["error"] = error_msg
        return result

    if not json_output:
        print(f"Comparing DEX file 1: {path1.name}")
        print(f"Comparing DEX file 2: {path2.name}")
        print("-" * 30)

    try:
        # AnalyzeDex returns (magic_string, [dvm_list], analysis_obj)
        str1, _, dx1 = AnalyzeDex(file1_path)
        str2, _, dx2 = AnalyzeDex(file2_path)

        result["file1_type"] = str1
        result["file2_type"] = str2

        if not json_output:
            print(f"{str1} vs {str2}")
    except Exception as e:
        error_msg = f"Error analyzing DEX files: {e}"
        print(error_msg, file=sys.stderr)
        result["error"] = error_msg
        return result

    if not dx1 or not dx2:
        error_msg = "Error: Failed to create Analysis objects for one or both files."
        print(error_msg, file=sys.stderr)
        result["error"] = error_msg
        return result

    # --- Compare Classes (Defined within the DEX) ---
    if not json_output:
        print("[+] Comparing Defined Classes...")

    classes1 = get_defined_class_names(dx1)
    classes2 = get_defined_class_names(dx2)
    unique_classes1 = classes1 - classes2
    unique_classes2 = classes2 - classes1
    common_classes = classes1 & classes2

    result["comparison"]["classes"] = {
        "unique_to_file1": list(unique_classes1),
        "unique_to_file2": list(unique_classes2),
        "common_count": len(common_classes),
    }

    if not json_output:
        print(
            f"  Unique to {path1.name} ({len(unique_classes1)}): {list(unique_classes1)[:5]}..."
        )
        print(
            f"  Unique to {path2.name} ({len(unique_classes2)}): {list(unique_classes2)[:5]}..."
        )
        print(f"  Common ({len(common_classes)})")
        print("-" * 30)

    # --- Compare Methods ---
    if not json_output:
        print("[+] Comparing Methods...")

    methods1 = get_method_signatures(dx1)
    methods2 = get_method_signatures(dx2)
    unique_methods1 = methods1 - methods2
    unique_methods2 = methods2 - methods1
    common_methods = methods1 & methods2

    result["comparison"]["methods"] = {
        "unique_to_file1": list(unique_methods1),
        "unique_to_file2": list(unique_methods2),
        "common_count": len(common_methods),
    }

    if not json_output:
        print(
            f"  Unique to {path1.name} ({len(unique_methods1)}): {list(unique_methods1)[:3]}..."
        )
        print(
            f"  Unique to {path2.name} ({len(unique_methods2)}): {list(unique_methods2)[:3]}..."
        )
        print(f"  Common ({len(common_methods)})")

    # --- Compare Bytecode (Optional) ---
    if compare_bc and common_methods:
        if not json_output:
            print("[+] Comparing Bytecode of Common Methods...")

        changed_bc_methods = compare_bytecode(dx1, dx2, common_methods)

        result["comparison"]["bytecode"] = {
            "changed_methods": list(changed_bc_methods),
            "changed_count": len(changed_bc_methods),
        }

        if not json_output:
            print(
                f"  Methods with different bytecode ({len(changed_bc_methods)}): {list(changed_bc_methods)[:3]}..."
            )

    if not json_output:
        print("-" * 30)

    # --- Compare Fields ---
    if not json_output:
        print("[+] Comparing Fields...")

    fields1 = get_field_signatures(dx1)
    fields2 = get_field_signatures(dx2)
    unique_fields1 = fields1 - fields2
    unique_fields2 = fields2 - fields1
    common_fields = fields1 & fields2

    result["comparison"]["fields"] = {
        "unique_to_file1": list(unique_fields1),
        "unique_to_file2": list(unique_fields2),
        "common_count": len(common_fields),
    }

    if not json_output:
        print(
            f"  Unique to {path1.name} ({len(unique_fields1)}): {list(unique_fields1)[:3]}..."
        )
        print(
            f"  Unique to {path2.name} ({len(unique_fields2)}): {list(unique_fields2)[:3]}..."
        )
        print(f"  Common ({len(common_fields)})")
        print("-" * 30)

    # --- Compare Strings ---
    if not json_output:
        print("[+] Comparing Strings...")

    strings1 = get_string_values(dx1)
    strings2 = get_string_values(dx2)
    unique_strings1 = strings1 - strings2
    unique_strings2 = strings2 - strings1
    common_strings = strings1 & strings2

    result["comparison"]["strings"] = {
        "unique_to_file1": list(unique_strings1),
        "unique_to_file2": list(unique_strings2),
        "common_count": len(common_strings),
    }

    # Truncate long strings for display
    if not json_output:
        trunc = lambda s, l=50: (s[:l] + "...") if len(s) > l else s
        print(
            f"  Unique to {path1.name} ({len(unique_strings1)}): {[trunc(s) for s in list(unique_strings1)[:5]]}..."
        )
        print(
            f"  Unique to {path2.name} ({len(unique_strings2)}): {[trunc(s) for s in list(unique_strings2)[:5]]}..."
        )
        print(f"  Common ({len(common_strings)})")
        print("-" * 30)

    return result


def main() -> None:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Compare two DEX files using Androguard.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  dex_compare.py file1.dex file2.dex
  dex_compare.py --bytecode --json file1.dex file2.dex > result.json
  dex_compare.py --json file1.dex file2.dex | jq .
        """,
    )
    parser.add_argument("dexfile1", help="Path to the first DEX file")
    parser.add_argument("dexfile2", help="Path to the second DEX file")
    parser.add_argument(
        "--bytecode",
        "-bc",
        action="store_true",
        help="Compare bytecode of methods common to both DEX files (can be slow)",
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output results in JSON format instead of human-readable text",
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    # Run comparison
    result = compare_dex_files(args.dexfile1, args.dexfile2, args.bytecode, args.json)

    # Output JSON if requested
    if args.json:
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
