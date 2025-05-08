#!/usr/bin/env python3
import requests
import sys
import argparse
from pathlib import Path


def create_wrapper_script(jar_path: Path, script_dir: Path) -> Path:
    wrapper_path = (
        script_dir.parent / "bundletool"
    )  # n.b. this would have to change if the script is moved
    wrapper_content = f"""#!/bin/sh
exec java -jar "{jar_path}" "$@"
"""
    wrapper_path.write_text(wrapper_content)
    wrapper_path.chmod(0o755)
    return wrapper_path


def download_bundletool(version: str = None):
    script_dir = Path(__file__).resolve().parent

    try:
        api_url = (
            f"https://api.github.com/repos/google/bundletool/releases/tags/{version}"
            if version
            else "https://api.github.com/repos/google/bundletool/releases/latest"
        )

        response = requests.get(api_url)
        response.raise_for_status()
        release_data = response.json()

        jar_asset = next(
            asset for asset in release_data["assets"] if asset["name"].endswith(".jar")
        )
        download_url = jar_asset["browser_download_url"]
        jar_name = jar_asset["name"]

        print(f"Downloading bundletool from: {download_url}")
        response = requests.get(download_url)
        response.raise_for_status()

        jar_path = script_dir.parent / jar_name
        jar_path.write_bytes(response.content)

        wrapper_path = create_wrapper_script(jar_path, script_dir)

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
    parser = argparse.ArgumentParser(
        description="Download bundletool from GitHub releases"
    )
    parser.add_argument(
        "--version", help="GitHub release tag to download (default: latest)"
    )
    args = parser.parse_args()
    download_bundletool(args.version)


if __name__ == "__main__":
    main()
