#!/usr/bin/env python3
import os
import zipfile
import requests
import argparse
import shutil


# Function to get the latest release tag from GitHub
def get_latest_release_tag():
    url = "https://api.github.com/repos/JakeWharton/diffuse/releases/latest"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data["tag_name"]
    else:
        print(f"Error fetching latest release: {response.status_code}")
        return None


# Function to download the release zip file
def download_release(tag):
    url = f"https://github.com/JakeWharton/diffuse/releases/download/{tag}/diffuse-{tag}.zip"
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        zip_filename = f"diffuse-{tag}-bin.zip"
        with open(zip_filename, "wb") as zip_file:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    zip_file.write(chunk)
        print(f"Downloaded {zip_filename}")
        return zip_filename
    else:
        print(f"Error downloading release with tag {tag}: {response.status_code}")
        return None


# Function to unzip the downloaded file
def unzip_file(zip_filename, base_folder="tools"):
    # Extract the archive normally
    extract_path = os.path.join(base_folder, "temp_extract")
    os.makedirs(extract_path, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_filename, "r") as zip_ref:
            zip_ref.extractall(extract_path)

        # Find the extracted folder containing the files
        extracted_folders = [
            d
            for d in os.listdir(extract_path)
            if os.path.isdir(os.path.join(extract_path, d))
        ]

        if len(extracted_folders) != 1:
            raise ValueError("Expected exactly one folder in the archive")

        source_folder = os.path.join(extract_path, extracted_folders[0])
        target_folder = os.path.join(base_folder, "diffuse")

        # Remove existing target folder if it exists
        if os.path.exists(target_folder):
            shutil.rmtree(target_folder)

        # Rename/move the extracted folder
        shutil.move(source_folder, target_folder)
        print(f"Successfully moved files to {target_folder}")

        # Clean up temporary extraction directory
        shutil.rmtree(extract_path)

        return True

    except Exception as e:
        print(f"Error during extraction: {e}")
        # Clean up temporary extraction directory if it exists
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)
        return False


# Main function to handle the process
def main(tag=None):
    if tag is None:
        # Get the latest release tag if not specified
        tag = get_latest_release_tag()
        if tag is None:
            return

    # Download the release
    zip_filename = download_release(tag)
    if zip_filename:
        # Unzip the file
        if unzip_file(zip_filename):
            # Delete the zip file after successful extraction
            try:
                os.remove(zip_filename)
                print(f"Deleted temporary zip file: {zip_filename}")
            except OSError as e:
                print(f"Failed to delete zip file: {e}")


# Run the script
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download diffuse.")
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="The tag to download the release from (default: latest)",
    )
    args = parser.parse_args()

    main(args.version)  # No tag specified, uses the latest tag by default
