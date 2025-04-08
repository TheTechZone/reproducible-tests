#!/usr/bin/env python3

import sys
import os
import subprocess
import argparse

os.environ["LOGURU_LEVEL"] = "ERROR"


# Function to find the Git root using git rev-parse --show-toplevel
def find_git_root():
    try:
        # Run git command to get the root of the repository
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        git_root = result.stdout.strip()
        return git_root
    except subprocess.CalledProcessError:
        print("This script must be run inside a Git repository.")
        sys.exit(1)


# Get the root of the Git repository
git_root = find_git_root()

# Resolve the path to apkdiff file located at the root of the Git repository
apkdiff_path = os.path.join(git_root, "apkdiff.py")

# Try to import apkdiff from the root of the Git repository
try:
    sys.path.insert(0, git_root)  # Add the Git root to the system path
    from apkdiff import ApkDiff
except ImportError:
    print("Please run install.py before using this.")
    sys.exit(1)

from bs4 import BeautifulSoup


def clean_diffoscope_report(infile, outfile):
    # Define the ignore list (this could be keywords, specific file names, etc.)
    ignore_list = [
        "APK Signing Block",
        "zipinfo",
        "apksigner",
        # Add more ignore patterns here as needed
    ]
    ignore_list.extend(ApkDiff.IGNORE_FILES)

    # Function to check if the section should be ignored
    def should_ignore(section):
        text = section.text.lower()
        for pattern in ignore_list:
            if pattern.lower() in text:
                print(f"{pattern} in text!")
                return True
        return False

    # Load the HTML file
    with open(infile, "r", encoding="utf-8") as file:
        soup = BeautifulSoup(file, "lxml")

    if git_root and (title := soup.find("title")) and title.string.startswith(git_root):
        title.string = title.string.removeprefix(git_root).strip("/")

    # Find all sections with the class 'difference' (or any other class you're interested in)
    parent_difference_div = soup.body.find("div", class_="difference")

    # If the parent div exists, proceed to find its children with class 'difference'
    if parent_difference_div:
        # Find all child divs with class 'difference' within this parent div
        difference_sections = parent_difference_div.find_all("div", class_="difference")

        # Iterate over all the 'difference' sections
        for section in difference_sections:
            if should_ignore(section):
                section.decompose()  # Remove the section from the tree

    # Save the modified HTML back to a file
    with open(outfile, "w", encoding="utf-8") as file:
        file.write(str(soup))
    print(f"Report updated and saved as '{outfile}'.")


# Function to run diffoscope and generate the HTML report
def run_diffoscope(path1, path2, output_html, keep_original=False, extra_args=None):
    # Create the base diffoscope command
    command = ["diffoscope", "--html", output_html, path1, path2]

    # Include any additional arguments passed to the script
    if extra_args:
        command.extend(extra_args)

    print(f"diffoscope command:\n\t$ LOGURU_LEVEL=\"ERROR\" {' '.join(command)}")

    # Run diffoscope
    result = subprocess.run(command, capture_output=True)

    if result.returncode == 0:
        print(f"The two files match: {path1} and  {path2}. No output file written.")
    elif result.returncode == 1:
        # If --keep-original is specified, make a copy of the original diffoscope report
        dest = output_html
        if keep_original:
            orig_output_html = f"{os.path.splitext(output_html)[0]}.orig.html"
            os.rename(output_html, orig_output_html)
            print(f"Original diffoscope report saved as '{orig_output_html}'.")
            output_html = orig_output_html

        # Clean the generated HTML report
        clean_diffoscope_report(output_html, dest)
    else:
        print(f"diffoscope failed with an error: {result.stdout} {result.stderr}")


# Main function to parse arguments and execute the script
def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Wrap diffoscope to generate and clean HTML reports."
    )
    parser.add_argument("path1", help="Path to the first file/folder to compare")
    parser.add_argument("path2", help="Path to the second file/folder to compare")
    parser.add_argument(
        "--html", required=True, help="Path to save the generated HTML report"
    )
    parser.add_argument(
        "--keep-original",
        action="store_true",
        help="Keep the original diffoscope report with a .orig suffix",
    )

    # Parse known arguments and forward the unknown ones to diffoscope
    args, unknown_args = parser.parse_known_args()

    # Run diffoscope and process the report
    run_diffoscope(args.path1, args.path2, args.html, args.keep_original, unknown_args)


if __name__ == "__main__":
    main()
