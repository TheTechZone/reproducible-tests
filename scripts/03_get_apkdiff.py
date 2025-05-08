#!/usr/bin/env python3
import argparse
import requests
import stat
from datetime import datetime
from pathlib import Path


def get_apkdiff(version="main"):
    """
    Downloads the apkdiff.py script from the Signal-Android repository,
    adds a shebang and a comment, and saves it to the project root
    with executable permissions.
    """
    url = f"https://github.com/signalapp/Signal-Android/blob/{version}/reproducible-builds/apkdiff/apkdiff.py"
    raw_url = url.replace("blob", "raw")

    # Get path to project root (one level up from this script)
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent
    filename = project_root / "apkdiff.py"

    try:
        response = requests.get(raw_url)
        response.raise_for_status()

        content = response.text
        current_date = datetime.now().strftime("%B %d, %Y")
        modified_content = f"""#!/usr/bin/env python3

# Downloaded on {current_date} from Signal-Android repository (version: {version})
# Original content of apkdiff.py starts here:
{'\n'.join(content.split('\n')[2:])}"""  # We can remove the shebang as we add our own manually. This will not affect the script's execution.

        filename.write_text(modified_content)

        # Make the script executable
        filename.chmod(filename.stat().st_mode | stat.S_IEXEC)

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
