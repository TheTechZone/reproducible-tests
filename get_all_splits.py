#!/usr/bin/env python3
"""
This script generates and analyzes APK splits from an Android App Bundle (AAB) file.

The script will generate APK splits using bundletool and provide information about
each generated APK including its size and SHA-256 hash.

Usage:
    python get_all_splits.py [-k] <aab_file> <output_dir>

Arguments:
    aab_file    Path to the AAB file
    output_dir  Output directory for the APK splits

Options:
    -k, --keep  Keep output files (do not clean up)
"""
import os
import subprocess
import sys
import zipfile
import hashlib
from pathlib import Path
import shutil
import argparse


class APKSplitGenerator:
    def __init__(self, keep_output=False):
        self.script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        self.output_dir = None
        self.aab_file = None
        self.bundletool_script = self.script_dir / "bundletool"
        # self.bundletool_jar = self.script_dir / "bundletool-all-1.17.2.jar"
        self.keep_output = keep_output

    def run_command(self, cmd, cwd=None, check=True):
        """Run a command and stream output in real-time."""
        try:
            print(f"\n$ {' '.join(cmd)}")

            process = subprocess.Popen(
                cmd,
                cwd=str(cwd) if cwd else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            output = []
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    print(line.rstrip())
                    output.append(line)

            return_code = process.wait()

            if check and return_code != 0:
                print(f"\nCommand failed with exit code {return_code}")
                sys.exit(return_code)

            return subprocess.CompletedProcess(
                cmd, return_code, stdout="".join(output), stderr=""
            )
        except subprocess.CalledProcessError as e:
            print(f"Command failed: {e}")
            sys.exit(1)

    def check_bundletool_installed(self):
        """Check if bundletool script and jar exist"""
        if not self.bundletool_script.exists():
            print(f"Error: bundletool script not found at {self.bundletool_script}")
            sys.exit(1)
        # if not self.bundletool_jar.exists():
        #     print(f"Error: bundletool jar not found at {self.bundletool_jar}")
        # sys.exit(1)
        # Make sure the script is executable
        self.bundletool_script.chmod(0o755)

    def generate_apk_splits(self, aab_file, output_dir):
        """Generate APK splits using bundletool"""
        self.aab_file = Path(aab_file)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        print(f"Generating APK splits from {self.aab_file}...")
        output_apks = self.output_dir / "output.apks"

        self.run_command(
            [
                str(self.bundletool_script),
                "build-apks",
                "--bundle",
                str(self.aab_file),
                "--output",
                str(output_apks),
            ]
        )

        print(f"APK splits generated at {output_apks}")
        return output_apks

    def extract_apks(self, apks_file):
        """Extract APKs from the .apks file"""
        apks_file = Path(apks_file)
        print(f"Extracting APKs from {apks_file} to {self.output_dir}...")
        with zipfile.ZipFile(apks_file, "r") as zip_ref:
            zip_ref.extractall(self.output_dir)
        print(f"APKs extracted to {self.output_dir}")

    def calculate_sha256(self, file_path):
        """Calculate the SHA-256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def get_apk_info(self, apk_path):
        """Get detailed information about an APK using bundletool's get-manifest command"""
        try:
            result = self.run_command(
                [
                    str(self.bundletool_script),
                    "dump",
                    "manifest",
                    "--apk",
                    str(apk_path),
                ]
            )
            return result.stdout
        except Exception as e:
            print(f"Failed to get manifest for {apk_path}: {e}")
            return None

    def list_apks(self):
        """List all APK files with their SHA-256 hashes and manifest information"""
        print("\nAnalyzing APK splits:")
        for root, _, files in os.walk(self.output_dir):
            for file in files:
                if file.endswith(".apk"):
                    file_path = os.path.join(root, file)
                    sha256 = self.calculate_sha256(file_path)
                    manifest_info = self.get_apk_info(file_path)

                    print(f"\n{file}:")
                    print(f"  Size: {os.path.getsize(file_path):,} bytes")
                    print(f"  SHA-256: {sha256}")
                    if manifest_info:
                        print("  Manifest Info:")
                        print(f"{manifest_info}")

    def get_device_spec_info(self, apks_file):
        """Get information about which devices each APK targets"""
        try:
            print("\nAnalyzing device targeting information...")
            result = self.run_command([str(self.bundletool_script), "get-device-spec"])
            device_spec = "device-spec.json"

            # Now use the device spec to get targeting information
            result = self.run_command(
                [
                    str(self.bundletool_script),
                    "get-size-total",
                    "--apks",
                    str(apks_file),
                    "--device-spec",
                    device_spec,
                ]
            )

            if os.path.exists(device_spec):
                os.remove(device_spec)

            return result.stdout
        except Exception as e:
            print(f"Failed to get device targeting info: {e}")
            return None

    def clean_up(self):
        """Clean up the temporary files"""
        if self.keep_output:
            print("\nKeeping output files as requested")
            return

        if self.output_dir and self.output_dir.exists():
            print(f"\nCleaning up {self.output_dir}...")
            shutil.rmtree(self.output_dir)
            print("Cleanup complete.")

    def process(self, aab_file, output_dir):
        """Main processing function"""
        self.check_bundletool_installed()
        output_apks = self.generate_apk_splits(aab_file, output_dir)
        self.extract_apks(output_apks)
        self.list_apks()

        # Get device targeting information
        device_info = self.get_device_spec_info(output_apks)
        if device_info:
            print("\nDevice Targeting Information:")
            print(device_info)

        if not self.keep_output:
            self.clean_up()


def main():
    parser = argparse.ArgumentParser(
        description="Generate and analyze APK splits from an AAB file"
    )
    parser.add_argument("aab_file", help="Path to the AAB file")
    parser.add_argument("output_dir", help="Output directory for the APK splits")
    parser.add_argument(
        "-k", "--keep", action="store_true", help="Keep output files (do not clean up)"
    )

    args = parser.parse_args()

    if not os.path.exists(args.aab_file):
        print(f"Error: AAB file '{args.aab_file}' does not exist.")
        sys.exit(1)

    generator = APKSplitGenerator(keep_output=args.keep)
    generator.process(args.aab_file, args.output_dir)


if __name__ == "__main__":
    main()
