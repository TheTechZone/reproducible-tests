#!/usr/bin/env python3
# note to future self:
#   - machine readable output
#   - act as a post-processing step for apkdiff
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import defaultdict

os.environ["LOGURU_LEVEL"] = "ERROR"

from androguard.core.axml import (
    ARSCParser,
    ARSCResTablePackage,
    StringBlock,
    ARSCHeader,
    ARSCResTypeSpec,
    ARSCResTableEntry,
    ARSCResType,
)
from tqdm import tqdm


def deep_compare(
    obj1,
    obj2,
    path="",
    max_depth=10,
    current_depth=0,
    exclude_attrs=None,
    include_callable=False,
):
    """
    Generic deep comparison of two Python objects.

    Args:
        obj1: First object to compare
        obj2: Second object to compare
        path: Current attribute path (for nested comparisons)
        max_depth: Maximum recursion depth
        current_depth: Current recursion depth
        exclude_attrs: List of attribute names to exclude from comparison
        include_callable: Whether to include callable attributes in comparison

    Returns:
        A dictionary mapping paths to differences, empty if objects are identical
    """
    if exclude_attrs is None:
        exclude_attrs = set()
    else:
        exclude_attrs = set(exclude_attrs)

    # Add common attributes to exclude
    exclude_attrs.update(["__dict__", "__weakref__", "__module__", "__doc__"])

    differences = {}

    # Check the recursion limit
    if current_depth > max_depth:
        return {f"{path} [max depth reached]": "Recursion limit reached"}

    # Basic identity/equality check
    if obj1 is obj2:  # Same object (identity)
        return {}

    if obj1 == obj2:  # Equal values
        return {}

    # Check for different types
    if type(obj1) != type(obj2):
        return {path: f"Type mismatch: {type(obj1).__name__} vs {type(obj2).__name__}"}

    # Handle None
    if obj1 is None or obj2 is None:
        return {path: f"{obj1} vs {obj2}"}

    # Handle primitive types
    if isinstance(obj1, (int, float, str, bool, bytes, complex)):
        return {path: f"{obj1} vs {obj2}"}

    # Handle sequences (list, tuple)
    if isinstance(obj1, (list, tuple)):
        if len(obj1) != len(obj2):
            differences[f"{path}.length"] = f"{len(obj1)} vs {len(obj2)}"

        # Compare elements
        for i in range(min(len(obj1), len(obj2))):
            item_path = f"{path}[{i}]"
            item_diffs = deep_compare(
                obj1[i],
                obj2[i],
                item_path,
                max_depth,
                current_depth + 1,
                exclude_attrs,
                include_callable,
            )
            differences.update(item_diffs)

        # Report extra elements
        if len(obj1) > len(obj2):
            for i in range(len(obj2), len(obj1)):
                differences[f"{path}[{i}]"] = f"{obj1[i]} vs [missing]"
        elif len(obj2) > len(obj1):
            for i in range(len(obj1), len(obj2)):
                differences[f"{path}[{i}]"] = f"[missing] vs {obj2[i]}"

        return differences

    # Handle dictionaries
    if isinstance(obj1, dict):
        keys1 = set(obj1.keys())
        keys2 = set(obj2.keys())

        # Check for different keys
        if keys1 != keys2:
            only_in_1 = keys1 - keys2
            only_in_2 = keys2 - keys1
            if only_in_1:
                differences[f"{path}.keys_only_in_first"] = sorted(only_in_1)
            if only_in_2:
                differences[f"{path}.keys_only_in_second"] = sorted(only_in_2)

        # Compare common keys
        for key in keys1 & keys2:
            key_path = f"{path}[{repr(key)}]"
            key_diffs = deep_compare(
                obj1[key],
                obj2[key],
                key_path,
                max_depth,
                current_depth + 1,
                exclude_attrs,
                include_callable,
            )
            differences.update(key_diffs)

        return differences

    # Handle sets
    if isinstance(obj1, set):
        only_in_1 = obj1 - obj2
        only_in_2 = obj2 - obj1

        if only_in_1:
            differences[f"{path}.items_only_in_first"] = sorted(only_in_1)
        if only_in_2:
            differences[f"{path}.items_only_in_second"] = sorted(only_in_2)

        return differences

    # Handle custom objects and classes
    try:
        # Try to get all attributes
        attrs1 = dir(obj1)

        # Filter attributes
        filtered_attrs = [
            attr
            for attr in attrs1
            if not attr.startswith("__")
            and attr not in exclude_attrs
            and (include_callable or not callable(getattr(obj1, attr, None)))
        ]

        # Compare each attribute
        for attr in filtered_attrs:
            try:
                # Skip unintended attributes
                if attr in exclude_attrs:
                    continue

                # Get attribute values
                val1 = getattr(obj1, attr)

                # Skip callables unless explicitly included
                if callable(val1) and not include_callable:
                    continue

                # Check if attr exists in obj2
                if not hasattr(obj2, attr):
                    differences[f"{path}.{attr}"] = f"{val1} vs [attribute missing]"
                    continue

                val2 = getattr(obj2, attr)

                # Compare values
                attr_path = f"{path}.{attr}"
                attr_diffs = deep_compare(
                    val1,
                    val2,
                    attr_path,
                    max_depth,
                    current_depth + 1,
                    exclude_attrs,
                    include_callable,
                )
                differences.update(attr_diffs)
            except Exception as e:
                differences[f"{path}.{attr}"] = f"Error comparing: {str(e)}"

    except Exception as e:
        differences[path] = f"Error accessing attributes: {str(e)}"

    return differences


def format_differences(diffs, indent=0):
    """Format differences in a human-readable form"""
    output = []
    indent_str = " " * indent

    for path, diff in sorted(diffs.items()):
        if isinstance(diff, dict):
            output.append(f"{indent_str}{path}:")
            output.append(format_differences(diff, indent + 2))
        elif isinstance(diff, list):
            output.append(f"{indent_str}{path}: [{', '.join(map(str, diff))}]")
        else:
            output.append(f"{indent_str}{path}: {diff}")

    return "\n".join(output)


class ARSCComparer:
    """Class to compare ARSC files with enhanced functionality"""

    def __init__(self, target_file, source_file, output_file=None, verbose=False):
        self.target_file = target_file
        self.source_file = source_file
        self.output_file = output_file
        self.verbose = verbose
        self.allowed_diff_paths = [".res1"]
        self.res1_diffs = []
        self.other_diffs = defaultdict(list)

    def log(self, message, level=0):
        """Log messages with proper indentation"""
        indent = "  " * level
        print(f"{indent}{message}")

    def redirect_output(self):
        """Redirect output to file if specified"""
        if self.output_file:
            return open(self.output_file, "w")
        return sys.stdout

    def compare(self):
        """Compare two ARSC files and report differences"""
        if not os.path.exists(self.target_file):
            print(f"Error: Target file not found - {self.target_file}")
            return False

        if not os.path.exists(self.source_file):
            print(f"Error: Source file not found - {self.source_file}")
            return False

        # Redirect output if needed
        original_stdout = sys.stdout
        output_handle = self.redirect_output()
        sys.stdout = output_handle

        success = True

        try:
            # Parse both ARSC files
            arsc1 = ARSCParser(open(self.target_file, "rb").read())
            arsc2 = ARSCParser(open(self.source_file, "rb").read())

            self.log("Comparing ARSC files:")
            self.log(
                f"Target: {self.target_file} ({os.path.getsize(self.target_file)} bytes)"
            )
            self.log(
                f"Source: {self.source_file} ({os.path.getsize(self.source_file)} bytes)"
            )
            self.log("-" * 80)

            # Compare package info
            self.log("\n=== Package Information ===")
            all_package_names = sorted(
                set(arsc1.packages.keys()) | set(arsc2.packages.keys())
            )

            if len(all_package_names) == 0:
                self.log("Warning: No packages found in the ARSC files")
                success = False

            # Track types for debugging
            package_counts = 0
            type_counts = defaultdict(int)

            for package_name in all_package_names:
                self.log(f"Package Name: {package_name}", 1)

                # Check if package exists in both files
                if package_name not in arsc1.packages:
                    self.log(f"Package only in source file: {package_name}", 2)
                    success = False
                    continue

                if package_name not in arsc2.packages:
                    self.log(f"Package only in target file: {package_name}", 2)
                    success = False
                    continue

                packages1 = arsc1.packages[package_name]
                packages2 = arsc2.packages[package_name]

                # Check package length
                if len(packages1) != len(packages2):
                    self.log(
                        f"Package length mismatch: {len(packages1)} vs {len(packages2)}",
                        2,
                    )
                    success = False
                    continue

                package_counts += 1

                # Compare each package element
                for i in tqdm(range(len(packages1))):
                    pkg1 = packages1[i]
                    pkg2 = packages2[i]

                    type_name = type(pkg1).__name__
                    type_counts[type_name] += 1

                    if type(pkg1) != type(pkg2):
                        self.log(
                            f"Element type mismatch at index {i}: {type(pkg1).__name__} vs {type(pkg2).__name__}",
                            2,
                        )
                        success = False
                        continue

                    # Different comparison strategies based on type
                    if isinstance(pkg1, ARSCResTablePackage):
                        if self.verbose:
                            self.log(f"Package ID: {pkg1.id} [{pkg1.get_name()}]", 2)
                        diffs = deep_compare(pkg1, pkg2)
                        if diffs:
                            self.log(
                                f"Differences in ARSCResTablePackage at index {i}:", 2
                            )
                            self.log(format_differences(diffs), 3)
                            self.other_diffs["ARSCResTablePackage"].append((i, diffs))
                            success = False

                    elif isinstance(pkg1, StringBlock):
                        if self.verbose:
                            self.log(f"StringPool: (#{pkg1.stringCount} strings)", 2)
                        diffs = deep_compare(pkg1, pkg2)
                        if diffs:
                            self.log(f"Differences in StringBlock at index {i}:", 2)
                            self.log(format_differences(diffs), 3)
                            self.other_diffs["StringBlock"].append((i, diffs))
                            success = False

                    elif isinstance(pkg1, ARSCHeader):
                        diffs = deep_compare(pkg1, pkg2)
                        if diffs:
                            self.log(f"Differences in ARSCHeader at index {i}:", 2)
                            self.log(format_differences(diffs), 3)
                            self.other_diffs["ARSCHeader"].append((i, diffs))
                            success = False

                    elif isinstance(pkg1, ARSCResTypeSpec):
                        diffs = deep_compare(pkg1, pkg2)

                        # Handle allowed differences
                        if diffs and all(
                            any(
                                path.endswith(allowed)
                                for allowed in self.allowed_diff_paths
                            )
                            for path in diffs.keys()
                        ):
                            if self.verbose:
                                self.log(
                                    f"Allowed differences in ARSCResTypeSpec at index {i}:",
                                    2,
                                )
                                self.log(format_differences(diffs), 3)

                            # Store differences for potential patching
                            self.res1_diffs.append((i, pkg1, pkg2, diffs))
                        elif diffs:
                            self.log(
                                f"Disallowed differences in ARSCResTypeSpec at index {i}:",
                                2,
                            )
                            self.log(format_differences(diffs), 3)
                            self.other_diffs["ARSCResTypeSpec"].append((i, diffs))
                            success = False

                    elif isinstance(pkg1, ARSCResTableEntry):
                        # Use string representation for comparison
                        if pkg1.__repr__() != pkg2.__repr__():
                            self.log(
                                f"Differences in ARSCResTableEntry at index {i}", 2
                            )
                            self.log(f"Target: {pkg1.__repr__()}", 3)
                            self.log(f"Source: {pkg2.__repr__()}", 3)
                            self.other_diffs["ARSCResTableEntry"].append(
                                (
                                    i,
                                    {
                                        "representation": f"{pkg1.__repr__()} vs {pkg2.__repr__()}"
                                    },
                                )
                            )
                            success = False

                    elif isinstance(pkg1, list):
                        if pkg1 != pkg2:
                            self.log(f"List difference at index {i}", 2)
                            self.other_diffs["list"].append(
                                (i, {"diff": "Lists differ"})
                            )
                            success = False

                    elif isinstance(pkg1, ARSCResType):
                        diffs = deep_compare(pkg1, pkg2)
                        if diffs:
                            self.log(f"Differences in ARSCResType at index {i}:", 2)
                            self.log(format_differences(diffs), 3)
                            self.other_diffs["ARSCResType"].append((i, diffs))
                            success = False
                    else:
                        # Other types
                        self.log(
                            f"Unhandled type: {type(pkg1).__name__} at index {i}", 2
                        )
                        try:
                            diffs = deep_compare(pkg1, pkg2)
                            if diffs:
                                self.log(format_differences(diffs), 3)
                                self.other_diffs[type(pkg1).__name__].append((i, diffs))
                                success = False
                        except:
                            self.log(
                                f"Could not compare objects of type {type(pkg1).__name__}",
                                3,
                            )
                            success = False

            # Summary
            self.log("\n=== Comparison Summary ===")
            self.log(f"Total packages compared: {package_counts}")
            self.log("Object types encountered:")
            for type_name, count in type_counts.items():
                self.log(f"  {type_name}: {count}", 1)

            self.log(f"\nAllowed differences (.res1): {len(self.res1_diffs)}")
            self.log(
                f"Other differences: {sum(len(diffs) for diffs in self.other_diffs.values())}"
            )

            for type_name, diffs in self.other_diffs.items():
                if diffs:
                    self.log(f"  {type_name}: {len(diffs)}", 1)

            if success:
                self.log(
                    f"\nFiles match, {'with only the allowed' if len(self.res1_diffs) > 0 else 'with no'} differences."
                )
            else:
                self.log(
                    "\nFiles have differences beyond the allowed .res1 differences."
                )

        except Exception as e:
            self.log(f"Error during comparison: {str(e)}")
            import traceback

            self.log(traceback.format_exc())
            success = False

        # Restore stdout if it was redirected
        if self.output_file:
            output_handle.close()
            sys.stdout = original_stdout
            print(f"Comparison results saved to {self.output_file}")

        return success

    def patch_apk(self, source_apk, output_apk):
        """
        Patch the source APK by transferring the .res1 values from target to source

        Args:
            source_apk: Path to the source APK file
            output_apk: Path to save the patched APK

        Returns:
            bool: True if patching was successful
        """
        if not os.path.exists(source_apk):
            print(f"Error: Source APK not found - {source_apk}")
            return False

        self.log(
            f"Copying ARSC file from target to {source_apk} -> {output_apk}", level=1
        )
        self.log("BEWARE that this is EXPERIMENTAL!")
        self.log("Currently disabled")
        self.exit(-1)
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        try:
            # Extract the APK
            with zipfile.ZipFile(source_apk, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            # Copy the target ARSC file
            target_arsc_path = os.path.join(temp_dir, "resources.arsc")
            shutil.copy(self.target_file, target_arsc_path)

            # Create the modified APK
            temp_apk_path = os.path.join(temp_dir, "modified.apk")
            with zipfile.ZipFile(temp_apk_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zipf.write(file_path, arcname)

            # Align the APK
            print("Aligning APK...")
            align_cmd = f"zipalign -p 4 {temp_apk_path} {output_apk}"
            print(f"Executing: {align_cmd}")
            subprocess.run(align_cmd, shell=True, check=True)

            # Sign the APK
            print("Signing APK...")
            sign_cmd = f"apksigner sign --ks ~/.android/debug.keystore {output_apk}"
            print(f"Executing: {sign_cmd}")
            subprocess.run(sign_cmd, shell=True, check=True)

            # Verify the signing
            print("Verifying APK signature...")
            verify_cmd = f"apksigner verify {output_apk}"
            print(f"Executing: {verify_cmd}")
            subprocess.run(verify_cmd, shell=True, check=True)

            print(f"Modified APK created at {output_apk}")
            return True

        except Exception as e:
            print(f"Error during process: {str(e)}")
            import traceback

            print(traceback.format_exc())
            return False

        finally:
            # Clean up the temporary directory
            shutil.rmtree(temp_dir)


def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(
        description="Compare and patch Android ARSC resource files"
    )

    parser.add_argument("source_arsc", help="Source ARSC file (compiled by yourself)")
    parser.add_argument("target_arsc", help="Target ARSC file (usually from PlayStore)")
    parser.add_argument(
        "-o", "--output", help="Output file for comparison results", default=None
    )
    parser.add_argument(
        "-v", "--verbose", help="Enable verbose output", action="store_true"
    )

    # Add patching options
    parser.add_argument(
        "--patch",
        help="Patch the source APK with target ARSC values",
        action="store_true",
    )
    parser.add_argument("--source-apk", help="Source APK file to patch")
    parser.add_argument("--output-apk", help="Output path for patched APK")

    args = parser.parse_args()

    # Create the comparer
    comparer = ARSCComparer(
        args.target_arsc, args.source_arsc, args.output, args.verbose
    )

    # Perform comparison
    success = comparer.compare()

    # Perform patching if requested
    if args.patch:
        if not args.source_apk:
            print("Error: Source APK (--source-apk) is required for patching")
            return 1

        if not args.output_apk:
            print("Error: Output APK path (--output-apk) is required for patching")
            return 1

        if not success and not args.verbose:
            print("Warning: Files have differences beyond allowed .res1 differences.")
            print("Use --verbose for more details.")

        patch_success = comparer.patch_apk(args.source_apk, args.output_apk)
        if not patch_success:
            return 1

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
