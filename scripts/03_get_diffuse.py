#!/usr/bin/env python3
import zipfile
import requests
import argparse
import shutil
from pathlib import Path


def get_latest_release_tag():
    """
    Fetches the latest release tag from the diffuse GitHub repo.
    """
    url = "https://api.github.com/repos/JakeWharton/diffuse/releases/latest"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()["tag_name"]
    else:
        print(f"Error fetching latest release: {response.status_code}")
        return None


def download_release(tag, download_dir: Path):
    """
    Downloads the zip release for the given tag into download_dir.
    """
    url = f"https://github.com/JakeWharton/diffuse/releases/download/{tag}/diffuse-{tag}.zip"
    zip_filename = download_dir / f"diffuse-{tag}-bin.zip"
    response = requests.get(url, stream=True)

    if response.status_code == 200:
        with zip_filename.open("wb") as zip_file:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    zip_file.write(chunk)
        print(f"Downloaded {zip_filename}")
        return zip_filename
    else:
        print(f"Error downloading release with tag {tag}: {response.status_code}")
        return None


def unzip_file(zip_filename: Path, tools_path: Path):
    """
    Extracts the zip file and moves contents into tools/diffuse.
    """
    extract_path = tools_path / "temp_extract"
    extract_path.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_filename, "r") as zip_ref:
            zip_ref.extractall(extract_path)

        extracted_folders = [f for f in extract_path.iterdir() if f.is_dir()]
        if len(extracted_folders) != 1:
            raise ValueError("Expected exactly one folder in the archive")

        source_folder = extracted_folders[0]
        target_folder = tools_path / "diffuse"

        if target_folder.exists():
            shutil.rmtree(target_folder)

        shutil.move(str(source_folder), str(target_folder))
        print(f"Successfully moved files to {target_folder}")

        shutil.rmtree(extract_path)
        return True

    except Exception as e:
        print(f"Error during extraction: {e}")
        if extract_path.exists():
            shutil.rmtree(extract_path)
        return False


def main(tag=None):
    # Resolve project root as one level above this script's directory
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent
    tools_path = project_root / "tools"

    tools_path.mkdir(parents=True, exist_ok=True)

    if tag is None:
        tag = get_latest_release_tag()
        if tag is None:
            return

    zip_filename = download_release(tag, tools_path)
    if zip_filename and unzip_file(zip_filename, tools_path):
        try:
            zip_filename.unlink()
            print(f"Deleted temporary zip file: {zip_filename}")
        except OSError as e:
            print(f"Failed to delete zip file: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download diffuse release.")
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="The tag to download the release from (default: latest)",
    )
    args = parser.parse_args()

    main(args.version)
