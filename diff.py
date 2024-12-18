from typing import Dict, List, Any
from dexparser import DEXParser

class DEXDeepComparator:
    def __init__(self, dex_file1: bytes, dex_file2: bytes):
        """
        Initialize the comparator with two DEX files

        :param dex_file1: Bytes of first DEX file
        :param dex_file2: Bytes of the second DEX file
        """
        # Parse APK/DEX files
        apk1 = DEXParser(fileobj=dex_file1)
        apk2 = DEXParser(fileobj=dex_file2)

        # Store parsed DEX files
        self.dex_files1 = apk1
        self.dex_files2 = apk2

        print(self._dex_to_version(self.dex_files1))
        print(self.dex_files1.header['endian_tag'])
        print(self._dex_to_version(self.dex_files2))
        # Comparison results
        self.comparison_results = {}

    def _dex_to_version(self, dex: DEXParser) -> int:
        """
        Extract the version of a DEX file

        :param dex: DEXParser instance
        :return: Version string
        """
        magic = dex.header['magic']
        return int(magic.removeprefix(b"dex\n")[:3])

    def _extract_class_details(self, dex: DEXParser) -> Dict[str, Dict[str, Any]]:
        """
        Extract comprehensive details about classes in a DEX file

        :param dex: DEXParser instance
        :return: Dictionary of class details
        """
        # Get type IDs and strings for resolving class names
        typeids = dex.get_typeids()
        strings = dex.get_strings()

        # Detailed class information
        class_details = {}

        # Iterate through class definitions
        for class_def in dex.get_classdef_data():
            # Resolve class name
            type_id = typeids[class_def["class_idx"]]
            class_name = strings[type_id].decode("utf-8")

            # Extract class data
            try:
                class_data = dex.get_class_data(class_def["class_data_off"])
            except Exception:
                class_data = None

            # Get superclass name
            superclass_name = (
                strings[typeids[class_def["superclass_idx"]]].decode("utf-8")
                if class_def["superclass_idx"] < len(typeids)
                else "Unknown"
            )

            # Collect detailed information
            class_details[class_name] = {
                "id": class_def["class_idx"],
                "access": class_def.get("access", []),
                "superclass": superclass_name,
                "static_fields_count": (
                    len(class_data.get("static_fields", [])) if class_data else 0
                ),
                "instance_fields_count": (
                    len(class_data.get("instance_fields", [])) if class_data else 0
                ),
                "direct_methods_count": (
                    len(class_data.get("direct_methods", [])) if class_data else 0
                ),
                "virtual_methods_count": (
                    len(class_data.get("virtual_methods", [])) if class_data else 0
                ),
            }

        return class_details

    def _extract_method_details(
        self, dex: DEXParser
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract comprehensive details about methods in a DEX file

        :param dex: DEXParser instance
        :return: Dictionary of method details
        """
        typeids = dex.get_typeids()
        strings = dex.get_strings()
        method_details = {}

        # Get method information
        method_ids = dex.get_methods()
        protoids = dex.get_protoids()

        for method_id in method_ids:
            # Resolve class name
            class_type_id = typeids[method_id["class_idx"]]
            class_name = strings[class_type_id].decode("utf-8")

            # Resolve method name
            method_name = strings[method_id["name_idx"]]

            # Resolve prototype details
            proto = protoids[method_id["proto_idx"]]
            shorty_signature = strings[proto["shorty_idx"]]
            return_type = strings[typeids[proto["return_type_idx"]]]

            # Add method details
            if class_name not in method_details:
                method_details[class_name] = []

            method_details[class_name].append(
                {
                    "id": method_id["class_idx"],
                    "name": method_name.decode("utf-8"),
                    "signature": shorty_signature.decode("utf-8"),
                    "return_type": return_type.decode("utf-8"),
                }
            )

        return method_details

    def compare_dex_files(self) -> Dict[str, Any]:
        """
        Perform a comprehensive comparison between DEX files

        :return: Detailed comparison results
        """
        # Compare each DEX file
        comparison = {
            "classes": self._compare_classes(
                self._extract_class_details(self.dex_files1),
                self._extract_class_details(self.dex_files2),
            ),
            "methods": self._compare_methods(
                self._extract_method_details(self.dex_files1),
                self._extract_method_details(self.dex_files2),
            ),
        }
        return comparison

    def _compare_classes(
        self, classes1: Dict[str, Any], classes2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compare class details between two DEX files

        :param classes1: First set of class details
        :param classes2: Second set of class details
        :return: Detailed class comparison
        """
        class_comparison = {
            "unique_to_dex1": list(set(classes1.keys()) - set(classes2.keys())),
            "unique_to_dex2": list(set(classes2.keys()) - set(classes1.keys())),
            "common_classes_with_differences": {},
        }

        # Compare common classes
        for class_name in set(classes1.keys()) & set(classes2.keys()):
            class1_details = classes1[class_name]
            class2_details = classes2[class_name]

            differences = {}
            for key, value1 in class1_details.items():
                value2 = class2_details.get(key)
                if value1 != value2:
                    differences[key] = {"dex1": value1, "dex2": value2}

            if differences:
                class_comparison["common_classes_with_differences"][
                    class_name
                ] = differences

        return class_comparison

    def _compare_methods(
        self, methods1: Dict[str, List[Dict]], methods2: Dict[str, List[Dict]]
    ) -> Dict[str, Any]:
        """
        Compare method details between two DEX files

        :param methods1: First set of method details
        :param methods2: Second set of method details
        :return: Detailed method comparison
        """
        method_comparison = {
            "unique_classes_to_dex1": list(set(methods1.keys()) - set(methods2.keys())),
            "unique_classes_to_dex2": list(set(methods2.keys()) - set(methods1.keys())),
            "common_classes_with_method_differences": {},
        }

        # Compare common classes with methods
        for class_name in set(methods1.keys()) & set(methods2.keys()):
            class_method_comparison = {
                "unique_methods_to_dex1": [],
                "unique_methods_to_dex2": [],
                "method_signature_differences": [],
            }

            # Find method differences
            def method_key(m):
                return m["name"], m["signature"], m["return_type"]

            methods1_set = {method_key(m) for m in methods1[class_name]}
            methods2_set = {method_key(m) for m in methods2[class_name]}

            class_method_comparison["unique_methods_to_dex1"] = [
                m for m in methods1[class_name] if method_key(m) not in methods2_set
            ]
            class_method_comparison["unique_methods_to_dex2"] = [
                m for m in methods2[class_name] if method_key(m) not in methods1_set
            ]

            # Find methods with the same name but different signature/return type
            methods1_by_name = {}
            methods2_by_name = {}
            for m in methods1[class_name]:
                methods1_by_name.setdefault(m["name"], []).append(m)
            for m in methods2[class_name]:
                methods2_by_name.setdefault(m["name"], []).append(m)

            # Compare methods with the same name
            for name in set(methods1_by_name.keys()) & set(methods2_by_name.keys()):
                # Create sets of (signature, return_type) for each DEX
                dex1_signatures = {
                    (m["signature"], m["return_type"]) for m in methods1_by_name[name]
                }
                dex2_signatures = {
                    (m["signature"], m["return_type"]) for m in methods2_by_name[name]
                }

                # Find truly unique signatures (ones that don't appear in either DEX)
                unique_signatures = dex1_signatures ^ dex2_signatures

                # Only report differences for unique signatures
                for method1 in methods1_by_name[name]:
                    sig1 = (method1["signature"], method1["return_type"])
                    if sig1 in unique_signatures:
                        for method2 in methods2_by_name[name]:
                            sig2 = (method2["signature"], method2["return_type"])
                            if sig2 in unique_signatures:
                                class_method_comparison[
                                    "method_signature_differences"
                                ].append(
                                    {
                                        "method_name": name,
                                        "dex1": method1,
                                        "dex2": method2,
                                    }
                                )

            # Only add if there are differences
            if any(class_method_comparison.values()):
                method_comparison["common_classes_with_method_differences"][
                    class_name
                ] = class_method_comparison

        return method_comparison


def main(file1: str, file2: str):
    """
    Main function to compare two DEX/APK files

    :param file1: Path to first DEX/APK file
    :param file2: Path to the second DEX/APK file
    """
    import json

    try:
        # Read files
        with open(file1, "rb") as f1, open(file2, "rb") as f2:
            # Create comparator
            comparator = DEXDeepComparator(f1.read(), f2.read())

            # Compare files
            comparison_results = comparator.compare_dex_files()

            # Print results
            print(json.dumps(comparison_results, indent=2))

    except Exception as e:
        print(f"Error comparing files: {e}")
        import traceback

        traceback.print_exc()


# if __name__ == '__main__':
#     if len(sys.argv) != 3:
#         print("Usage: python dex_deep_comparison.py <file1.apk/dex> <file2.apk/dex>")
#         sys.exit(1)

#     main(sys.argv[1], sys.argv[2])
if __name__ == "__main__":
    main(
        "apkdiff-results/base-master.apk_playstore_vs_fedora40/first/classes2.dex",
        "apkdiff-results/base-master.apk_playstore_vs_fedora40/second/classes2.dex",
    )
