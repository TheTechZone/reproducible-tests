#!/usr/bin/env python3
"""
agp2bundletool.py - Find the bundletool version pinned to a specific AGP version

This tool helps Android developers find the bundletool version pinned to a specific
Android Gradle Plugin (AGP) version by analyzing the AGP's POM file from Google's
Maven repository.

Usage:
    python agp2bundletool.py 8.9.0
    python agp2bundletool.py 8.3.0 -v
"""

import argparse
import sys
import requests
import xml.etree.ElementTree as ET


def eprint(*args, **kwargs):
    """Print to stderr."""
    print(*args, file=sys.stderr, **kwargs)


group_id = "com.android.tools.build"
artifact_id = "gradle"
google_maven_base_url = "https://maven.google.com/"


def check_agp_version_exists(agp_version):
    """
    Check if the specified AGP version exists in the Maven repository.

    Args:
        agp_version: The version string of the Android Gradle Plugin

    Returns:
        bool: True if the version exists, False otherwise
    """
    # Construct the POM URL
    pom_url = f"{google_maven_base_url}{group_id.replace('.', '/')}/{artifact_id}/{agp_version}/{artifact_id}-{agp_version}.pom"

    try:
        response = requests.get(pom_url)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def get_bundletool_version(agp_version, verbose=False):
    """
    Fetches the POM file for a given AGP version from the Google repository
    and extracts the pinned bundletool version programmatically.

    Args:
        agp_version: The version string of the Android Gradle Plugin (e.g., "8.9.0").
        verbose: Whether to print verbose output.

    Returns:
        The bundletool version string, or None if not found or an error occurs.
    """
    if not check_agp_version_exists(agp_version):
        eprint(
            f"Error: AGP version {agp_version} does not exist or cannot be accessed."
        )
        return None

    # Construct the POM URL
    pom_url = f"{google_maven_base_url}{group_id.replace('.', '/')}/{artifact_id}/{agp_version}/{artifact_id}-{agp_version}.pom"

    if verbose:
        print(f"Fetching POM from: {pom_url}")

    try:
        response = requests.get(pom_url)
        response.raise_for_status()

        # Parse the XML content
        namespace = {"mvn": "http://maven.apache.org/POM/4.0.0"}
        root = ET.fromstring(response.content)

        # Find the <dependencies> element
        dependencies = root.find("mvn:dependencies", namespace)
        if dependencies is None:
            eprint("Error: <dependencies> element not found in POM.")
            return None

        # Iterate through dependency elements to find bundletool
        for dependency in dependencies.findall("mvn:dependency", namespace):
            gid_elem = dependency.find("mvn:groupId", namespace)
            aid_elem = dependency.find("mvn:artifactId", namespace)
            version_elem = dependency.find("mvn:version", namespace)

            if (
                gid_elem is not None
                and gid_elem.text == "com.android.tools.build"
                and aid_elem is not None
                and aid_elem.text == "bundletool"
                and version_elem is not None
            ):
                if verbose:
                    print(
                        f"Found bundletool version {version_elem.text} for AGP {agp_version}"
                    )
                return version_elem.text  # Found the version!

        eprint(f"Bundletool dependency not found for AGP version {agp_version}")
        return None

    except requests.exceptions.RequestException as e:
        eprint(f"Error fetching POM: {e}")
        return None
    except ET.ParseError as e:
        eprint(f"Error parsing POM XML: {e}")
        return None
    except Exception as e:
        eprint(f"An unexpected error occurred: {e}")
        return None


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Find the bundletool version pinned to an Android Gradle Plugin (AGP) version."
    )

    # Add positional argument for AGP version
    parser.add_argument("agp_version", help="AGP version to check (e.g., 8.9.0)")

    # Optional verbose flag
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show verbose output"
    )

    args = parser.parse_args()

    # Check the specified AGP version with verbose flag
    bundletool_v = get_bundletool_version(args.agp_version, args.verbose)
    if bundletool_v:
        # Print the result to stdout
        print(bundletool_v)
        return 0
    else:
        return 1  # Exit with error code


if __name__ == "__main__":
    sys.exit(main())
