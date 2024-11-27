#!/usr/bin/env python3
import requests
import os
import sys

def create_wrapper_script(jar_path):
    wrapper_content = f'''#!/bin/sh
exec java -jar "{jar_path}" "$@"
'''
    wrapper_path = './bundletool'
    with open(wrapper_path, 'w') as f:
        f.write(wrapper_content)
    os.chmod(wrapper_path, 0o755)
    return wrapper_path

def download_latest_bundletool():
    # GitHub API endpoint for latest release
    api_url = "https://api.github.com/repos/google/bundletool/releases/latest"
    
    try:
        # Get the latest release information
        response = requests.get(api_url)
        response.raise_for_status()
        release_data = response.json()
        
        # Get the JAR asset URL
        jar_asset = next(
            asset for asset in release_data['assets'] 
            if asset['name'].endswith('.jar')
        )
        download_url = jar_asset['browser_download_url']
        jar_name = jar_asset['name']
        
        # Download the JAR file
        print(f"Downloading bundletool from: {download_url}")
        response = requests.get(download_url)
        response.raise_for_status()
        
        # Save the JAR with its original name
        jar_path = os.path.abspath(f'./{jar_name}')
        with open(jar_path, 'wb') as f:
            f.write(response.content)
        
        # Create the wrapper script
        wrapper_path = create_wrapper_script(jar_path)
        
        print(f"Successfully downloaded bundletool JAR to: {jar_path}")
        print(f"Created wrapper script at: {wrapper_path}")
        print(f"Version: {release_data['tag_name']}")
        
    except requests.exceptions.RequestException as e:
        print(f"Error downloading bundletool: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    download_latest_bundletool()
