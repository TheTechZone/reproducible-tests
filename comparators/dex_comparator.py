#!/usr/bin/env python3
import os
import sys
import argparse
from pathlib import Path

os.environ["LOGURU_LEVEL"] = "ERROR"
try:
    from androguard.misc import AnalyzeDex
    from androguard.core.analysis.analysis import Analysis
    from androguard.core.dex import (
        DEX,
        EncodedMethod,
        ClassDefItem,
    )

    # from androguard.util import confirm_api_level  # For potential future use
except ImportError as e:
    print(e)
    print("Error: Androguard not found.")
    print("Please install it: pip3 install androguard")
    sys.exit(1)


def get_defined_class_names(dx: Analysis) -> set[str]:
    """Extracts names of classes defined within the DEX."""
    names = set()
    if not dx:
        return names
    for cls in dx.get_classes():
        # is_external() checks if the class is defined outside the DEX(s)
        if not cls.is_external():
            vm_class = cls.get_vm_class()
            if isinstance(vm_class, ClassDefItem):  # Ensure it's a defined class
                names.add(vm_class.get_name())
    return names


def get_method_signatures(dx: Analysis) -> set[str]:
    """Extracts full signatures (Class->NameDescriptor) of methods."""
    signatures = set()
    if not dx:
        return signatures
    for method in dx.get_methods():
        # method.full_name provides a unique signature
        signatures.add(method.full_name)
    return signatures


def get_field_signatures(dx: Analysis) -> set[str]:
    """Extracts full signatures (Class->Name:Descriptor) of fields."""
    signatures = set()
    if not dx:
        return signatures
    for field_analysis in dx.get_fields():
        field = field_analysis.get_field()
        # Create a unique representation for the field
        sig = f"{field.get_class_name()}->{field.get_name()}:{field.get_descriptor()}"
        signatures.add(sig)
    return signatures


def get_string_values(dx: Analysis) -> set[str]:
    """Extracts unique string values."""
    values = set()
    if not dx:
        return values
    for s in dx.get_strings():
        values.add(s.get_value())
    return values


def compare_bytecode(dx1: Analysis, dx2: Analysis, common_method_signatures: set[str]):
    """Compares bytecode of methods present in both DEX files."""
    changed_methods = set()
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


def compare_dex_files(file1_path: str, file2_path: str, compare_bc: bool):
    """Loads and compares two DEX files."""
    path1 = Path(file1_path)
    path2 = Path(file2_path)

    if not path1.is_file() or not path2.is_file():
        print("Error: One or both input files not found.", file=sys.stderr)
        return

    print(f"Comparing DEX file 1: {path1.name}")
    print(f"Comparing DEX file 2: {path2.name}")
    print("-" * 30)

    try:
        # AnalyzeDex returns ([dvm_list], analysis_obj)
        str1, _, dx1 = AnalyzeDex(file1_path)
        str2, _, dx2 = AnalyzeDex(file2_path)
        print(f"{str1} vs {str2}")
    except Exception as e:
        print(f"Error analyzing DEX files: {e}", file=sys.stderr)
        return

    if not dx1 or not dx2:
        print(
            "Error: Failed to create Analysis objects for one or both files.",
            file=sys.stderr,
        )
        return

    # --- Compare Classes (Defined within the DEX) ---
    print("[+] Comparing Defined Classes...")
    classes1 = get_defined_class_names(dx1)
    classes2 = get_defined_class_names(dx2)
    unique_classes1 = classes1 - classes2
    unique_classes2 = classes2 - classes1
    common_classes = classes1 & classes2
    print(
        f"  Unique to {path1.name} ({len(unique_classes1)}): {list(unique_classes1)[:5]}..."
    )  # Show the first few
    print(
        f"  Unique to {path2.name} ({len(unique_classes2)}): {list(unique_classes2)[:5]}..."
    )
    print(f"  Common ({len(common_classes)})")
    print("-" * 30)

    # --- Compare Methods ---
    print("[+] Comparing Methods...")
    methods1 = get_method_signatures(dx1)
    methods2 = get_method_signatures(dx2)
    unique_methods1 = methods1 - methods2
    unique_methods2 = methods2 - methods1
    common_methods = methods1 & methods2
    print(
        f"  Unique to {path1.name} ({len(unique_methods1)}): {list(unique_methods1)[:3]}..."
    )  # Show the first few
    print(
        f"  Unique to {path2.name} ({len(unique_methods2)}): {list(unique_methods2)[:3]}..."
    )
    print(f"  Common ({len(common_methods)})")

    # --- Compare Bytecode (Optional) ---
    if compare_bc and common_methods:
        print("[+] Comparing Bytecode of Common Methods...")
        changed_bc_methods = compare_bytecode(dx1, dx2, common_methods)
        print(
            f"  Methods with different bytecode ({len(changed_bc_methods)}): {list(changed_bc_methods)[:3]}..."
        )
    print("-" * 30)

    # --- Compare Fields ---
    print("[+] Comparing Fields...")
    fields1 = get_field_signatures(dx1)
    fields2 = get_field_signatures(dx2)
    unique_fields1 = fields1 - fields2
    unique_fields2 = fields2 - fields1
    common_fields = fields1 & fields2
    print(
        f"  Unique to {path1.name} ({len(unique_fields1)}): {list(unique_fields1)[:3]}..."
    )  # Show the first few
    print(
        f"  Unique to {path2.name} ({len(unique_fields2)}): {list(unique_fields2)[:3]}..."
    )
    print(f"  Common ({len(common_fields)})")
    print("-" * 30)

    # --- Compare Strings ---
    print("[+] Comparing Strings...")
    strings1 = get_string_values(dx1)
    strings2 = get_string_values(dx2)
    unique_strings1 = strings1 - strings2
    unique_strings2 = strings2 - strings1
    common_strings = strings1 & strings2
    # Truncate long strings for display
    trunc = lambda s, l=50: (s[:l] + "...") if len(s) > l else s
    print(
        f"  Unique to {path1.name} ({len(unique_strings1)}): {[trunc(s) for s in list(unique_strings1)[:5]]}..."
    )
    print(
        f"  Unique to {path2.name} ({len(unique_strings2)}): {[trunc(s) for s in list(unique_strings2)[:5]]}..."
    )
    print(f"  Common ({len(common_strings)})")
    print("-" * 30)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compare two DEX files using Androguard."
    )
    parser.add_argument("dexfile1", help="Path to the first DEX file.")
    parser.add_argument("dexfile2", help="Path to the second DEX file.")
    parser.add_argument(
        "--bytecode",
        "-bc",
        action="store_true",
        help="Compare bytecode of methods common to both DEX files (can be slow).",
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    compare_dex_files(args.dexfile1, args.dexfile2, args.bytecode)
