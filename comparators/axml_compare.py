#!/usr/bin/env python3

import os
import sys
import subprocess
import traceback
import difflib
from termcolor import colored
from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum
import copy

os.environ["LOGURU_LEVEL"] = "ERROR"
from androguard.core.axml import AXMLPrinter
import xml.etree.ElementTree as ET


class ChangeType(Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass
class XMLDifference:
    """Represents a semantic difference between XML elements"""

    change_type: ChangeType
    xpath: str  # XPath to the element
    element_type: str  # 'element', 'attribute', 'text'
    name: str  # Element or attribute name
    old_value: Any = None  # Previous value (for attributes or text)
    new_value: Any = None  # New value (for attributes or text)
    details: dict[str, Any] = field(default_factory=dict)  # Additional information


class AndroidXMLSemanticDiffComparator:
    def __init__(self, file1, file2):
        """
        Initialize comparator with two binary XML files

        :param file1: Path to the first binary XML file
        :param file2: Path to the second binary XML file
        """
        self.file1 = file1
        self.file2 = file2
        self.differences = []  # Will store XMLDifference objects
        self.file1_type = None
        self.file2_type = None
        # For text-based diff
        self.file1_lines = []
        self.file2_lines = []

        # Android namespace
        self.android_ns = "{http://schemas.android.com/apk/res/android}"

    def parse_binary_xml(
        self, file_path
    ) -> tuple[Optional[bytes], bool, Optional[ET.Element]]:
        """
        Parse binary XML file using Androguard

        :param file_path: Path to binary XML file
        :return: Parsed XML string, boolean indicating if it's a manifest, and ElementTree
        """
        try:
            # Read the binary file
            with open(file_path, "rb") as f:
                raw_data = f.read()

            # Parse using AXMLPrinter
            printer = AXMLPrinter(raw_data)
            xml_string = printer.get_xml()

            # Check if it's a manifest
            is_manifest = b"manifest" in xml_string.lower()

            # Parse into ElementTree
            root = ET.fromstring(xml_string)

            return xml_string, is_manifest, root

        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            traceback.print_exc()
            return None, False, None

    def get_element_signature(self, elem):
        """
        Generate a unique signature for an element based on its tag and key attributes
        """
        # For Android XML, we consider 'android:name' as the primary identifier
        name_attr = f"{self.android_ns}name"
        if name_attr in elem.attrib:
            return f"{elem.tag}[@{name_attr}='{elem.attrib[name_attr]}']"

        # For other elements, check common identifier attributes
        id_attrs = [f"{self.android_ns}id", "id", "name", "key", "class"]
        for attr in id_attrs:
            if attr in elem.attrib:
                return f"{elem.tag}[@{attr}='{elem.attrib[attr]}']"

        # If no identifier is found, use just the tag
        return elem.tag

    def get_element_path(self, elem, parent_map):
        """
        Generate a path for an element based on its position in the tree
        """
        path = []
        current = elem

        while current is not None:
            parent = parent_map.get(current)
            if parent is None:
                # Root element
                path.insert(0, current.tag)
                break

            # Find position among siblings with the same tag
            siblings = [child for child in parent if child.tag == current.tag]
            if len(siblings) > 1:
                pos = siblings.index(current) + 1
                path.insert(0, f"{current.tag}[{pos}]")
            else:
                path.insert(0, current.tag)

            current = parent

        return "/" + "/".join(path)

    def build_parent_map(self, root):
        """Build a map of child->parent relationships"""
        parent_map = {}
        for parent in root.findall(".//*"):
            for child in parent:
                parent_map[child] = parent
        return parent_map

    def build_element_map(self, root, parent_map):
        """
        Build a map of elements indexed by their signature and path
        """
        element_map = {}

        # First, index by unique signatures
        for elem in root.findall(".//*"):
            signature = self.get_element_signature(elem)
            path = self.get_element_path(elem, parent_map)

            key = (signature, path)
            if key in element_map:
                # If there's a collision, make the path more specific
                count = 1
                while (signature, f"{path}[{count}]") in element_map:
                    count += 1
                element_map[(signature, f"{path}[{count}]")] = elem
            else:
                element_map[key] = elem

        return element_map

    def compare_attributes(self, elem1, elem2, path):
        """Compare attributes of two elements"""
        differences = []

        # Get sets of attribute names
        attrs1 = set(elem1.attrib.keys())
        attrs2 = set(elem2.attrib.keys())

        # Find attributes that were added
        for attr in attrs2 - attrs1:
            differences.append(
                XMLDifference(
                    change_type=ChangeType.ADDED,
                    xpath=path,
                    element_type="attribute",
                    name=attr,
                    new_value=elem2.attrib[attr],
                )
            )

        # Find attributes that were removed
        for attr in attrs1 - attrs2:
            differences.append(
                XMLDifference(
                    change_type=ChangeType.REMOVED,
                    xpath=path,
                    element_type="attribute",
                    name=attr,
                    old_value=elem1.attrib[attr],
                )
            )

        # Compare values of common attributes
        for attr in attrs1 & attrs2:
            if elem1.attrib[attr] != elem2.attrib[attr]:
                differences.append(
                    XMLDifference(
                        change_type=ChangeType.MODIFIED,
                        xpath=path,
                        element_type="attribute",
                        name=attr,
                        old_value=elem1.attrib[attr],
                        new_value=elem2.attrib[attr],
                    )
                )

        return differences

    def compare_xml_trees(self, root1, root2):
        """
        Compare two XML trees and identify semantic differences
        """
        differences = []

        # Build parent maps for both trees
        parent_map1 = self.build_parent_map(root1)
        parent_map2 = self.build_parent_map(root2)

        # Generate signature-to-element maps for both trees
        elements1 = self.build_element_map(root1, parent_map1)
        elements2 = self.build_element_map(root2, parent_map2)

        # Compare root elements separately
        root_diffs = self.compare_attributes(root1, root2, f"/{root1.tag}")
        differences.extend(root_diffs)

        # Find elements that exist in both trees
        common_signatures = set(elements1.keys()) & set(elements2.keys())

        # Compare common elements
        for sig in common_signatures:
            elem1 = elements1[sig]
            elem2 = elements2[sig]
            path = self.get_element_path(elem1, parent_map1)

            # Compare attributes
            attr_diffs = self.compare_attributes(elem1, elem2, path)
            differences.extend(attr_diffs)

            # Compare text content if relevant
            if elem1.text and elem2.text:
                text1 = elem1.text.strip()
                text2 = elem2.text.strip()
                if text1 and text2 and text1 != text2:
                    differences.append(
                        XMLDifference(
                            change_type=ChangeType.MODIFIED,
                            xpath=path,
                            element_type="text",
                            name="text",
                            old_value=text1,
                            new_value=text2,
                        )
                    )

        # Find elements that were removed (in tree1 but not in tree2)
        for sig, elem in elements1.items():
            if sig not in elements2:
                path = self.get_element_path(elem, parent_map1)

                # Check if this is truly a removed element or just a moved element
                # For this simple approach, we'll just check the signature without path
                signature = sig[
                    0
                ]  # The first part is the element signature without path
                possible_moved = False

                for other_sig in elements2:
                    if other_sig[0] == signature:
                        possible_moved = True
                        break

                if not possible_moved:
                    differences.append(
                        XMLDifference(
                            change_type=ChangeType.REMOVED,
                            xpath=path,
                            element_type="element",
                            name=elem.tag,
                            details={"attributes": copy.deepcopy(elem.attrib)},
                        )
                    )

                    # removed for now since it might be too verbose
                    # for attr, value in elem.attrib.items():
                    #     differences.append(
                    #         XMLDifference(
                    #             change_type=ChangeType.REMOVED,
                    #             xpath=path,
                    #             element_type="attribute",
                    #             name=attr,
                    #             new_value=value,
                    #         )
                    #     )

        # Find elements that were added (in tree2 but not in tree1)
        for sig, elem in elements2.items():
            if sig not in elements1:
                path = self.get_element_path(elem, parent_map2)

                # Check if this is truly a new element or just a moved element
                signature = sig[
                    0
                ]  # The first part is the element signature without path
                possible_moved = False

                for other_sig in elements1:
                    if other_sig[0] == signature:
                        possible_moved = True
                        break

                if not possible_moved:
                    differences.append(
                        XMLDifference(
                            change_type=ChangeType.ADDED,
                            xpath=path,
                            element_type="element",
                            name=elem.tag,
                            details={"attributes": copy.deepcopy(elem.attrib)},
                        )
                    )

                    # Also add information about the attributes of this new element
                    for attr, value in elem.attrib.items():
                        differences.append(
                            XMLDifference(
                                change_type=ChangeType.ADDED,
                                xpath=path,
                                element_type="attribute",
                                name=attr,
                                new_value=value,
                            )
                        )

        return differences

    def generate_colored_diff(self):
        """
        Generate a diff-style output of the XML files with color coding
        """
        repo_dir = (
            subprocess.Popen(
                ["git", "rev-parse", "--show-toplevel"], stdout=subprocess.PIPE
            )
            .communicate()[0]
            .rstrip()
            .decode("utf-8")
        )
        # Use difflib to create a unified diff
        diff = list(
            difflib.unified_diff(
                self.file1_lines,
                self.file2_lines,
                fromfile=os.path.relpath(self.file1, start=repo_dir),
                tofile=os.path.relpath(self.file2, start=repo_dir),
                lineterm="",
            )
        )

        # Color-code the diff
        colored_diff = []
        for line in diff:
            if line.startswith("---"):
                colored_diff.append(colored(line, "red"))
            elif line.startswith("+++"):
                colored_diff.append(colored(line, "green"))
            elif line.startswith("-"):
                colored_diff.append(colored(line, "red"))
            elif line.startswith("+"):
                colored_diff.append(colored(line, "green"))
            elif line.startswith("@@"):
                colored_diff.append(colored(line, "cyan"))
            else:
                colored_diff.append(line)

        return colored_diff

    def compare(self):
        """
        Main comparison method that performs both text and semantic diff
        """
        try:
            # Parse both XML files
            xml_str1, is_manifest1, root1 = self.parse_binary_xml(self.file1)
            xml_str2, is_manifest2, root2 = self.parse_binary_xml(self.file2)

            if is_manifest1 != is_manifest2:
                print(
                    "Attempting to compore two different types of xml files. Exiting early."
                )
                sys.exit(-1)
            if not (root1 is not None and root2 is not None):
                print("Failed to parse one or both XML files.")
                return False
            assert xml_str1 is not None and xml_str2 is not None

            # Store file types
            self.file1_type = "Android Manifest" if is_manifest1 else "Resource XML"
            self.file2_type = "Android Manifest" if is_manifest2 else "Resource XML"

            # Print file types
            print(f"{self.file1}: {self.file1_type}")
            print(f"{self.file2}: {self.file2_type}")

            # Split XML strings into lines for text-based diffing
            self.file1_lines = [line.decode() for line in xml_str1.splitlines()]
            self.file2_lines = [line.decode() for line in xml_str2.splitlines()]

            # Generate and print text diff
            diff_output = self.generate_colored_diff()

            if len(diff_output) > 0:
                print("\nText-Based XML Differences:")
                for line in diff_output:
                    print(line)
            else:
                print("\nXML files are identical (text comparison).")

            # Perform semantic comparison using the new approach
            self.differences = self.compare_xml_trees(root1, root2)

            if self.differences:
                print("\nSemantic XML Differences:")
                for diff in self.differences:
                    if diff.change_type == ChangeType.ADDED:
                        if diff.element_type == "element":
                            print(colored(f"+ Element added: {diff.xpath}", "green"))
                        elif diff.element_type == "attribute":
                            print(
                                colored(
                                    f'\t+ Attribute added: {diff.xpath}/@{diff.name}="{diff.new_value}"',
                                    "green",
                                )
                            )
                        elif diff.element_type == "text":
                            print(
                                colored(
                                    f'+ Text content added: {diff.xpath} = "{diff.new_value}"',
                                    "green",
                                )
                            )

                    elif diff.change_type == ChangeType.REMOVED:
                        if diff.element_type == "element":
                            print(colored(f"- Element removed: {diff.xpath}", "red"))
                        elif diff.element_type == "attribute":
                            print(
                                colored(
                                    f'- Attribute removed: {diff.xpath}/@{diff.name}="{diff.old_value}"',
                                    "red",
                                )
                            )
                        elif diff.element_type == "text":
                            print(
                                colored(
                                    f'- Text content removed: {diff.xpath} = "{diff.old_value}"',
                                    "red",
                                )
                            )

                    elif diff.change_type == ChangeType.MODIFIED:
                        if diff.element_type == "attribute":
                            print(
                                colored(
                                    f"~ Attribute modified: {diff.xpath}/@{diff.name}",
                                    "yellow",
                                )
                            )
                            print(f'  - Old value: "{diff.old_value}"')
                            print(f'  + New value: "{diff.new_value}"')
                        elif diff.element_type == "text":
                            print(
                                colored(
                                    f"~ Text content modified: {diff.xpath}", "yellow"
                                )
                            )
                            print(f'  - Old value: "{diff.old_value}"')
                            print(f'  + New value: "{diff.new_value}"')

                print(f"\nSummary: Found {len(self.differences)} semantic differences")
                print(self.get_stats())
                return True
            else:
                print("\nXML files are semantically identical.")
                return False

        except Exception as e:
            print(f"Comparison failed: {e}")
            traceback.print_exc()
            return False

    def get_differences(self):
        """
        Return the semantic differences
        """
        return self.differences

    def get_stats(self):
        """
        Get statistics about the semantic differences
        """
        stats = {
            "added_elements": sum(
                1
                for d in self.differences
                if d.change_type == ChangeType.ADDED and d.element_type == "element"
            ),
            "removed_elements": sum(
                1
                for d in self.differences
                if d.change_type == ChangeType.REMOVED and d.element_type == "element"
            ),
            "added_attributes": sum(
                1
                for d in self.differences
                if d.change_type == ChangeType.ADDED and d.element_type == "attribute"
            ),
            "removed_attributes": sum(
                1
                for d in self.differences
                if d.change_type == ChangeType.REMOVED and d.element_type == "attribute"
            ),
            "modified_attributes": sum(
                1
                for d in self.differences
                if d.change_type == ChangeType.MODIFIED
                and d.element_type == "attribute"
            ),
            "text_changes": sum(
                1 for d in self.differences if d.element_type == "text"
            ),
            "total": len(self.differences),
            "file1_type": self.file1_type,
            "file2_type": self.file2_type,
        }
        return stats

    def filter_differences(self, **kwargs):
        """
        Filter differences based on criteria

        :param kwargs: Criteria to filter by (element_type, change_type, path_contains, etc.)
        :return: Filtered list of differences
        """
        result = self.differences

        if "element_type" in kwargs:
            result = [d for d in result if d.element_type == kwargs["element_type"]]

        if "change_type" in kwargs:
            change_type = kwargs["change_type"]
            if isinstance(change_type, str):
                change_type = ChangeType(change_type)
            result = [d for d in result if d.change_type == change_type]

        if "path_contains" in kwargs:
            result = [d for d in result if kwargs["path_contains"] in d.xpath]

        if "name_contains" in kwargs:
            result = [d for d in result if kwargs["name_contains"] in d.name]

        return result


ALLOWED_PLAYSTORE_VENDING_TYPES = {
    "com.android.vending.derived.apk.id",
    "com.android.stamp.source",
    "com.android.stamp.type",
}


def main():
    # Check arguments
    if len(sys.argv) != 3:
        print("Usage: python3 android_xml_semantic_diff.py <file1.xml> <file2.xml>")
        sys.exit(1)

    # Get file paths
    file1 = sys.argv[1]
    file2 = sys.argv[2]

    # Validate file existence
    if not (os.path.exists(file1) and os.path.exists(file2)):
        print("Error: One or both files do not exist.")
        sys.exit(1)

    # Run comparison
    comparator = AndroidXMLSemanticDiffComparator(file1, file2)
    has_differences = comparator.compare()

    if has_differences:
        print("The two files differ")

        if comparator.file1_type == "Android Manifest":
            print("checking if those differences are related to PlayStore delivery")
            added = comparator.filter_differences(
                change_type=ChangeType.ADDED, element_type="element"
            )
            removed = comparator.filter_differences(
                change_type=ChangeType.REMOVED, element_type="element"
            )
            modified = comparator.filter_differences(change_type=ChangeType.MODIFIED)

            if (added and removed) or modified:
                print("not good :C")
                return
            if added:
                print(f"{comparator.file1} must be from playstore")
                # for addition in added:
                #     print(addition.details)
                attrs_diffs = {
                    d.details["attributes"][
                        "{http://schemas.android.com/apk/res/android}name"
                    ]: d.details["attributes"][
                        "{http://schemas.android.com/apk/res/android}value"
                    ]
                    for d in added
                }
            else:
                print(f"{comparator.file2} must be from playstore")
                # for removal in removed:
                #     print(removal)

                attrs_diffs = {
                    d.details["attributes"][
                        "{http://schemas.android.com/apk/res/android}name"
                    ]: d.details["attributes"][
                        "{http://schemas.android.com/apk/res/android}value"
                    ]
                    for d in removed
                }

            all_valid = set(attrs_diffs.keys()).issubset(
                ALLOWED_PLAYSTORE_VENDING_TYPES
            )

            if not all_valid:
                invalid_keys = set(attrs_diffs.keys()) - ALLOWED_PLAYSTORE_VENDING_TYPES
                print(f"Invalid keys found: {invalid_keys}")
            else:
                print("All keys are valid")

        else:
            print("differences were not expected :(")
        # comparator.filter_differences(element_type="element", change_type=ChangeType.ADDED)
    # # Example of programmatic access to differences
    # if has_differences:
    #     print("\nProgrammatic access examples:")

    #     # Example 1: Find all permission-related changes
    #     permission_changes = comparator.filter_differences(path_contains="permission")
    #     if permission_changes:
    #         print("\nPermission changes:")
    #         for change in permission_changes:
    #             print(f"  - {change.change_type.value}: {change.xpath}")

    #     # Example 2: Find all added elements
    #     added_elements = comparator.filter_differences(
    #         element_type="element", change_type=ChangeType.ADDED
    #     )

    #     if added_elements:
    #         print("\nAdded elements with attributes:")
    #         for elem in added_elements:
    #             print(f"  Element: {elem.xpath}")
    #             if "attributes" in elem.details:
    #                 for attr, value in elem.details["attributes"].items():
    #                     print(f"    - {attr}: {value}")

    #     # Example 3: Find all modified attributes
    #     modified_attrs = comparator.filter_differences(
    #         element_type="attribute", change_type=ChangeType.MODIFIED
    #     )

    #     if modified_attrs:
    #         print("\nModified attributes:")
    #         for attr in modified_attrs:
    #             print(
    #                 f"  {attr.xpath}/@{attr.name}: {attr.old_value} -> {attr.new_value}"
    #             )


if __name__ == "__main__":
    main()
