#!/usr/bin/env python3
import argparse
import os
import requests
import stat
from datetime import datetime


def get_apkdiff(version="main"):
    """
    Downloads the apkdiff.py script from the Signal-Android repository,
    adds a shebang and a comment, and saves it to the current directory
    with executable permissions.
    """
    url = f"https://github.com/signalapp/Signal-Android/blob/{version}/reproducible-builds/apkdiff/apkdiff.py"
    raw_url = url.replace("blob", "raw")
    filename = "apkdiff.py"

    try:
        response = requests.get(raw_url)
        response.raise_for_status()

        content = response.text
        current_date = datetime.now().strftime("%B %d, %Y")
        modified_content = f"""#!/usr/bin/env python3

# Downloaded on {current_date} from Signal-Android repository (version: {version})
# Original content of apkdiff.py starts here:
{content}"""

        with open(filename, "w") as f:
            f.write(modified_content)

        # Make the script executable
        st = os.stat(filename)
        os.chmod(filename, st.st_mode | stat.S_IEXEC)

        print(
            f"Downloaded {filename} from {url}, version: {version} and set executable permissions."
        )

    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")
    except OSError as e:
        print(f"Error setting executable permissions for {filename}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download apkdiff.py from Signal-Android repository."
    )
    parser.add_argument(
        "--version",
        type=str,
        default="main",
        help="The tag or branch to download from (default: main)",
    )
    args = parser.parse_args()

    get_apkdiff(args.version)
