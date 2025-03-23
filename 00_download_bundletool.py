#!/usr/bin/env python3
import requests
import os
import sys
import argparse

def create_wrapper_script(jar_path):
    wrapper_content = f"""#!/bin/sh
exec java -jar "{jar_path}" "$@"
"""
    wrapper_path = "./bundletool"
    with open(wrapper_path, "w") as f:
        f.write(wrapper_content)
    os.chmod(wrapper_path, 0o755)
    return wrapper_path

def download_bundletool(version=None):
    """Download bundletool for specified version or latest if none provided."""
    try:
        # Construct API URL based on version parameter
        api_url = (
            f"https://api.github.com/repos/google/bundletool/releases/tags/{version}"
            if version
            else "https://api.github.com/repos/google/bundletool/releases/latest"
        )

        # Fetch release data
        response = requests.get(api_url)
        response.raise_for_status()
        release_data = response.json()

        # Extract JAR asset details
        jar_asset = next(
            asset for asset in release_data["assets"] if asset["name"].endswith(".jar")
        )
        download_url = jar_asset["browser_download_url"]
        jar_name = jar_asset["name"]

        # Download and save the JAR
        print(f"Downloading bundletool from: {download_url}")
        response = requests.get(download_url)
        response.raise_for_status()

        jar_path = os.path.abspath(f"./{jar_name}")
        with open(jar_path, "wb") as f:
            f.write(response.content)

        # Create wrapper script
        wrapper_path = create_wrapper_script(jar_path)

        # Print success messages
        print(f"Successfully downloaded bundletool JAR to: {jar_path}")
        print(f"Created wrapper script at: {wrapper_path}")
        print(f"Version: {release_data['tag_name']}")

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Error: Release tag '{version}' does not exist", file=sys.stderr)
            sys.exit(1)
        print(f"HTTP Error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Error downloading bundletool: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Download bundletool from GitHub releases')
    parser.add_argument('--version', help='GitHub release tag to download (default: latest)')
    args = parser.parse_args()
    download_bundletool(args.version)

if __name__ == "__main__":
    main()
