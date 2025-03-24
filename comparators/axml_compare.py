# #!/usr/bin/env python3
# import os
# import sys
#
# os.environ["LOGURU_LEVEL"] = "ERROR"
#
# from androguard.core.axml import AXMLParser
# from androguard.core.axml import AXMLPrinter
#
#
# def parse_binary_xml(file_path):
#     """
#     Parse a binary XML file and return its contents and type.
#
#     :param file_path: Path to the binary XML file
#     :return: Tuple of (parsed_xml, is_manifest, error)
#     """
#     try:
#         with open(file_path, "rb") as f:
#             xml_data = f.read()
#
#         # Use AXMLParser to parse the binary XML
#         parser = AXMLParser(xml_data)
#         printer = AXMLPrinter(xml_data)
#
#         # Try to get the parsed XML string
#         parsed_xml = printer.get_xml_obj()
#
#         # Check if this is an Android Manifest file
#         is_manifest = "manifest" in parsed_xml.tag.lower()
#
#         return parsed_xml, is_manifest, None
#
#     except Exception as e:
#         return None, False, str(e)
#
#
# def compare_binary_xmls(file1, file2):
#     """
#     Compare two binary XML files.
#
#     :param file1: Path to the first binary XML file
#     :param file2: Path to the second binary XML file
#     """
#     # Parse first file
#     xml1, is_manifest1, err1 = parse_binary_xml(file1)
#     if err1:
#         print(f"Error parsing {file1}: {err1}")
#         return
#
#     # Parse second file
#     xml2, is_manifest2, err2 = parse_binary_xml(file2)
#     if err2:
#         print(f"Error parsing {file2}: {err2}")
#         return
#
#     # Print file types
#     print(f"{file1}: {'Android Manifest' if is_manifest1 else 'Resource XML'}")
#     print(f"{file2}: {'Android Manifest' if is_manifest2 else 'Resource XML'}")
#
#     # Compare basic attributes if both files are parsed successfully
#     if xml1 is not None and xml2 is not None:
#         # Compare tags
#         if xml1.tag != xml2.tag:
#             print("Tags differ:")
#             print(f"{file1} tag: {xml1.tag}")
#             print(f"{file2} tag: {xml2.tag}")
#
#         # Compare attributes
#         attrs1 = xml1.attrib
#         attrs2 = xml2.attrib
#
#         # Find different attributes
#         diff_attrs = set(attrs1.keys()) ^ set(attrs2.keys())
#         if diff_attrs:
#             print("Different attributes:")
#             for attr in diff_attrs:
#                 if attr in attrs1:
#                     print(f"{file1} has attribute {attr}: {attrs1[attr]}")
#                 if attr in attrs2:
#                     print(f"{file2} has attribute {attr}: {attrs2[attr]}")
#
#         # Compare attribute values
#         common_attrs = set(attrs1.keys()) & set(attrs2.keys())
#         diff_values = {attr for attr in common_attrs if attrs1[attr] != attrs2[attr]}
#
#         if diff_values:
#             print("Attributes with different values:")
#             for attr in diff_values:
#                 print(f"{attr}:")
#                 print(f"{file1} value: {attrs1[attr]}")
#                 print(f"{file2} value: {attrs2[attr]}")
#
#         if not (diff_attrs or diff_values):
#             print("XML files are identical.")
#
#
# def main():
#     # Check if correct number of arguments is provided
#     if len(sys.argv) != 3:
#         print("Usage: python3 compare_binary_xmls.py <file1.xml> <file2.xml>")
#         sys.exit(1)
#
#     # Get file paths from command line arguments
#     file1 = sys.argv[1]
#     file2 = sys.argv[2]
#
#     # Validate file existence
#     if not (os.path.exists(file1) and os.path.exists(file2)):
#         print("Error: One or both files do not exist.")
#         sys.exit(1)
#
#     # Compare the XML files
#     compare_binary_xmls(file1, file2)
#
#
# if __name__ == "__main__":
#     main()

# !/usr/bin/env python3

import os
import sys
import traceback

os.environ["LOGURU_LEVEL"] = "ERROR"

from androguard.core.axml import AXMLParser
from androguard.core.axml import AXMLPrinter
import xml.etree.ElementTree as ET


class AndroidXMLComparator:
    def __init__(self, file1, file2):
        """
        Initialize comparator with two binary XML files

        :param file1: Path to the first binary XML file
        :param file2: Path to the second binary XML file
        """
        self.file1 = file1
        self.file2 = file2
        self.differences = []

    def parse_binary_xml(self, file_path):
        """
        Parse binary XML file using Androguard

        :param file_path: Path to binary XML file
        :return: Parsed XML string and boolean indicating if it's a manifest
        """
        try:
            # Read binary file
            with open(file_path, 'rb') as f:
                raw_data = f.read()

            # Parse using AXMLPrinter
            printer = AXMLPrinter(raw_data)
            xml_string = printer.get_xml()

            # Check if it's a manifest
            is_manifest = b'manifest' in xml_string.lower()

            return xml_string, is_manifest

        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            traceback.print_exc()
            return None, False

    def compare_xml_trees(self, xml1, xml2):
        """
        Recursively compare two XML trees

        :param xml1: First XML ElementTree
        :param xml2: Second XML ElementTree
        """

        def _compare_elements(elem1, elem2, path=''):
            """
            Recursive element comparison helper

            :param elem1: First XML element
            :param elem2: Second XML element
            :param path: Current path in XML tree
            """
            # Compare tags
            if elem1.tag != elem2.tag:
                self.differences.append(
                    f"Different tags at {path}: "
                    f"{elem1.tag} vs {elem2.tag}"
                )

            # Compare attributes
            attrs1 = elem1.attrib
            attrs2 = elem2.attrib

            # Check for different attributes
            attrs1_keys = set(attrs1.keys())
            attrs2_keys = set(attrs2.keys())

            # Detect added/removed attributes
            added_attrs = attrs2_keys - attrs1_keys
            removed_attrs = attrs1_keys - attrs2_keys

            for attr in added_attrs:
                self.differences.append(
                    f"Added attribute at {path}: {attr}='{attrs2[attr]}'"
                )

            for attr in removed_attrs:
                self.differences.append(
                    f"Removed attribute at {path}: {attr}='{attrs1[attr]}'"
                )

            # Compare common attribute values
            common_attrs = attrs1_keys & attrs2_keys
            for attr in common_attrs:
                if attrs1[attr] != attrs2[attr]:
                    self.differences.append(
                        f"Different attribute value at {path}/{attr}: "
                        f"'{attrs1[attr]}' vs '{attrs2[attr]}'"
                    )

            # Compare text content (if any)
            if (elem1.text or '').strip() != (elem2.text or '').strip():
                self.differences.append(
                    f"Different text content at {path}: "
                    f"'{elem1.text}' vs '{elem2.text}'"
                )

            # Recursively compare child elements
            children1 = list(elem1)
            children2 = list(elem2)

            # Check number of children
            if len(children1) != len(children2):
                self.differences.append(
                    f"Different number of children at {path}: "
                    f"{len(children1)} vs {len(children2)}"
                )

            # Recursively compare existing children
            for i, (child1, child2) in enumerate(zip(children1, children2)):
                child_path = f"{path}/{child1.tag}[{i}]"
                _compare_elements(child1, child2, child_path)

        # Perform the comparison
        _compare_elements(xml1, xml2)

    def compare(self):
        """
        Main comparison method
        """
        try:
            # Parse both XML files
            xml_str1, is_manifest1 = self.parse_binary_xml(self.file1)
            xml_str2, is_manifest2 = self.parse_binary_xml(self.file2)

            if not (xml_str1 and xml_str2):
                print("Failed to parse one or both XML files.")
                return

            # Print file types
            print(f"{self.file1}: {'Android Manifest' if is_manifest1 else 'Resource XML'}")
            print(f"{self.file2}: {'Android Manifest' if is_manifest2 else 'Resource XML'}")

            # Parse XML strings to ElementTree
            tree1 = ET.fromstring(xml_str1)
            tree2 = ET.fromstring(xml_str2)

            # Perform deep comparison
            self.compare_xml_trees(tree1, tree2)

            # Print results
            if self.differences:
                print("\nDifferences found:")
                for diff in self.differences:
                    print(diff)
            else:
                print("\nXML files are identical.")

        except Exception as e:
            print(f"Comparison failed: {e}")
            traceback.print_exc()


def main():
    # Check arguments
    if len(sys.argv) != 3:
        print("Usage: python3 android_xml_comparator.py <file1.xml> <file2.xml>")
        sys.exit(1)

    # Get file paths
    file1 = sys.argv[1]
    file2 = sys.argv[2]

    # Validate file existence
    if not (os.path.exists(file1) and os.path.exists(file2)):
        print("Error: One or both files do not exist.")
        sys.exit(1)

    # Run comparison
    comparator = AndroidXMLComparator(file1, file2)
    comparator.compare()


if __name__ == "__main__":
    main()