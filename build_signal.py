#!/usr/bin/env python3
import os
import subprocess
import sys
import shutil
import argparse
import contextlib
from pathlib import Path


class SignalBuilder:

    def __init__(self, args):
        self.script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        self.reproducible_apks_dir = self.script_dir / 'reproducible-signal'
        self.device_apks_dir = self.reproducible_apks_dir / 'apks-from-device'
        self.built_apks_dir = self.reproducible_apks_dir / 'apks-i-built'
        # Will be overwritten if dfs is defined
        self.signal_repo_dir = self.script_dir / 'Signal-Android'
        self.dfs = args.dfs  # None, "chaos", "sort", ""sort_reversed"
        self.dfs_root_dir = None
        self.clean = args.clean

    def run_command(self, cmd, cwd=None, check=True, shell=False):
        """Run a command and stream output in real-time."""
        try:
            # Print the command being run
            print(f"\n$ {' '.join(cmd)}")

            process = subprocess.Popen(
                cmd,
                cwd=str(cwd) if cwd else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True,
                shell=shell,  # for the dutchies
            )

            # Stream output in real-time
            output = []
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    print(line.rstrip())
                    output.append(line)

            # Get the return code
            return_code = process.wait()

            if check and return_code != 0:
                print(f"\nCommand failed with exit code {return_code}")
                sys.exit(return_code)

            return subprocess.CompletedProcess(
                cmd, return_code,
                stdout=''.join(output),
                stderr=''
            )

        except Exception as e:
            print(f"\nError running command: {' '.join(cmd)}")
            print(f"Error: {str(e)}")
            sys.exit(1)

    def setup_directories(self):
        """Create necessary directories."""
        print("Setting up directories...")
        os.makedirs(self.device_apks_dir, exist_ok=True)
        os.makedirs(self.built_apks_dir, exist_ok=True)

    def create_overlay_filesystem(self, dfs):
        """Create the directory for the overlay and run disorderfs with the appropriate args"""
        print("Creating overlay filesystem...")
        dfs_root_dir = self.script_dir / dfs
        with contextlib.suppress(FileNotFoundError):
            os.rmdir(dfs_root_dir)
        os.makedirs(dfs_root_dir, exist_ok=True)
        command = ["sudo", "-S", "disorderfs", "--multi-user=yes"]
        if dfs == "chaos":
            command.append("--sort-dirents=no")
        else:
            command.append("--sort-dirents=yes")
            command.append(f"--reverse-dirents={'yes' if dfs == 'sort_reversed' else 'no'}")
        command.append(str(self.signal_repo_dir))
        command.append(str(dfs_root_dir))
        self.run_command(command, self.script_dir)
        pid = self.get_disorderfs_pid(dfs_root_dir)
        print("Increasing the number of filehandlers that the overlay process may open...")
        command = ["sudo", "-S", "prlimit", "-n=16000", f"--pid={pid}"]
        self.run_command(command, self.script_dir)
        print("Redirecting the Signal repo dir to point to the overlay...")
        self.dfs_root_dir = dfs_root_dir
        self.signal_repo_dir = dfs_root_dir / "Signal-Android"

    def get_disorderfs_pid(self, dfs_root_dir):
        # Find the disorderfs process ID
        completedProcess = self.run_command(["ps", "-aux", "|", "grep", str(dfs_root_dir), "|", "awk", "'{print $2}'"],
                                            shell=True)
        return completedProcess.stdout.strip()

    def clone_signal(self, version):
        """Clone Signal repository at specific version."""
        if not version.startswith('v'):
            version = f'v{version}'

        print(f"Cloning Signal Android repository version {version}...")
        if self.signal_repo_dir.exists():
            shutil.rmtree(self.signal_repo_dir)

        self.run_command([
            'git', 'clone', '--depth', '1',
            '--branch', version,
            'https://github.com/signalapp/Signal-Android.git'
        ])

    def build_docker_image(self):
        """Build the Signal Android Docker image."""
        print("Building Docker image...")
        self.run_command(
            ['docker', 'build', '-t', 'signal-android', '.'],
            cwd=self.signal_repo_dir / 'reproducible-builds'
        )

    def build_signal(self):
        """Build Signal using Docker."""
        print("Building Signal...")
        uid = os.getuid()
        gid = os.getgid()

        self.run_command([
            'docker', 'run', '--rm',
            '-v', f"{self.signal_repo_dir}:/project",
            '-w', '/project',
            '--user', f"{uid}:{gid}",
            'signal-android',
            './gradlew', 'bundlePlayProdRelease'
        ])

    def copy_bundle(self):
        """Copy the built bundle to our directory."""
        bundle_path = self.signal_repo_dir / 'app/build/outputs/bundle/playProdRelease/Signal-Android-play-prod-release.aab'
        target_path = self.built_apks_dir / 'bundle.aab'

        print("Copying bundle file...")
        shutil.copy2(bundle_path, target_path)

    def check_adb_devices(self):
        """Check if any ADB devices are connected."""
        print("Checking for connected Android devices...")
        result = self.run_command(['adb', 'devices'], check=False)

        # Parse the output to count connected devices
        lines = result.stdout.strip().split('\n')
        # Remove the first line (header) and any empty lines
        device_lines = [line for line in lines[1:] if line.strip()]

        if not device_lines:
            print("Error: No Android devices connected. Please connect a device and try again.")
            sys.exit(1)

        print(f"Found {len(device_lines)} connected device(s):")
        for line in device_lines:
            print(f"  {line}")

    def generate_apks(self):
        """Generate device-specific APKs using bundletool."""
        print("Generating APKs for connected device...")
        bundletool_path = self.script_dir / 'bundletool'
        if not bundletool_path.exists():
            print("Error: bundletool not found. Please run download_bundletool.py first.")
            sys.exit(1)

        self.run_command([
            str(bundletool_path),
            'build-apks',
            '--bundle=bundle.aab',
            '--output-format=DIRECTORY',
            '--output=apks',
            '--connected-device'
        ], cwd=self.built_apks_dir)

    def cleanup(self):
        """Clean up unnecessary files."""
        print("Cleaning up...")
        apks_dir = self.built_apks_dir / 'apks'
        if apks_dir.exists():
            # Move APK files to parent directory
            splits_dir = apks_dir / 'splits'
            if splits_dir.exists():
                for apk in splits_dir.glob('*.apk'):
                    shutil.move(str(apk), str(self.built_apks_dir / apk.name))

            # Remove the apks directory
            shutil.rmtree(apks_dir)

        # Remove the bundle file
        bundle_file = self.built_apks_dir / 'bundle.aab'
        if bundle_file.exists():
            os.remove(bundle_file)

        # Kill disorderfs
        if self.dfs_root_dir:
            pid = self.get_disorderfs_pid(self.dfs_root_dir)
            self.run_command(["sudo", "-S", "kill", pid], check=False)

    def pull_device_apks(self):
        """Pull Signal APKs from the connected device."""
        print("\nPulling APKs from device...")

        # Get paths of all Signal APKs on device
        result = self.run_command(
            ['adb', 'shell', 'pm', 'path', 'org.thoughtcrime.securesms'],
            check=False
        )

        if not result.stdout.strip():
            print("Error: Signal not found on device. Please make sure Signal is installed.")
            sys.exit(1)

        # Extract paths and pull each APK
        paths = [line.replace('package:', '').strip()
                 for line in result.stdout.splitlines()
                 if line.strip()]

        print(f"Found {len(paths)} APK(s) on device:")
        for path in paths:
            # Extract the APK name from the path
            apk_name = os.path.basename(path)
            if 'split_config.' in apk_name:
                # Convert split_config.arm64-v8a.apk to base-arm64-v8a.apk format
                config_type = apk_name.replace('split_config.', '')
                target_name = f'base-{config_type}'
            else:
                # Convert base.apk to base-master.apk
                target_name = 'base-master.apk'

            target_path = self.device_apks_dir / target_name
            print(f"  Pulling {apk_name} -> {target_name}")

            self.run_command([
                'adb', 'pull',
                path,
                str(target_path)
            ])

    def print_apk_summary(self):
        """Print a summary of the APKs in both directories."""
        print("\nAPK Summary:")
        print("-" * 50)

        print("\nAPKs from device:")
        for apk in sorted(self.device_apks_dir.glob('*.apk')):
            size = os.path.getsize(apk)
            print(f"  {apk.name} ({size:,} bytes)")

        print("\nBuilt APKs:")
        for apk in sorted(self.built_apks_dir.glob('*.apk')):
            size = os.path.getsize(apk)
            print(f"  {apk.name} ({size:,} bytes)")

    def setup_apkdiff(self):
        """Copy apkdiff.py from Signal repo and make it executable."""
        print("\nSetting up apkdiff.py...")
        apkdiff_src = self.signal_repo_dir / 'reproducible-builds/apkdiff/apkdiff.py'
        apkdiff_dest = self.reproducible_apks_dir / 'apkdiff.py'

        if not apkdiff_src.exists():
            print("Error: apkdiff.py not found in Signal repository.")
            print("Please make sure Signal-Android is cloned and contains the reproducible-builds directory.")
            sys.exit(1)

        shutil.copy2(apkdiff_src, apkdiff_dest)
        os.chmod(apkdiff_dest, 0o755)
        return apkdiff_dest

    def compare_apks(self):
        """Compare APKs using apkdiff.py."""
        print("\nComparing APKs...")

        # First check if we have matching sets of APKs
        built_apks = sorted(self.built_apks_dir.glob('*.apk'))
        device_apks = sorted(self.device_apks_dir.glob('*.apk'))

        if not built_apks or not device_apks:
            print("Error: No APKs found to compare.")
            sys.exit(1)

        if len(built_apks) != len(device_apks):
            print(f"Warning: Number of APKs doesn't match! "
                  f"Built: {len(built_apks)}, Device: {len(device_apks)}")

        # Copy apkdiff.py from Signal repo
        apkdiff_path = self.setup_apkdiff()

        print("\nRunning APK comparisons:")
        print("-" * 50)
        all_match = True

        # Compare APKs with matching names
        for built_apk in built_apks:
            device_apk = self.device_apks_dir / built_apk.name
            if not device_apk.exists():
                print(f"\nWarning: No matching device APK for {built_apk.name}")
                all_match = False
                continue

            print(f"\nComparing {built_apk.name}:")
            result = self.run_command(
                [str(apkdiff_path), str(built_apk), str(device_apk)],
                check=False
            )
            if result.returncode != 0:
                all_match = False

        if all_match:
            print("\nSuccess! All APKs match! 🎉")
            print("Your device is running the exact same code that is in the Signal Android repository.")
        else:
            print("\nWarning: Some APKs don't match. 🚨")
            print("This could mean the installed version doesn't match the version you built,")
            print("or that the build wasn't fully reproducible.")

    def build(self, version):
        """Run the complete build process."""
        try:
            self.setup_directories()
            self.clone_signal(version)
            if self.dfs:
                self.create_overlay_filesystem(self.dfs)
            self.build_docker_image()
            # print("Finished building docker image, quittin early!")
            # exit(0)
            self.build_signal()
            self.copy_bundle()
            if version:
                self.check_adb_devices()
            self.generate_apks()
            if self.clean:
                self.cleanup()
            if version:
                self.pull_device_apks()
                self.print_apk_summary()
                self.compare_apks()

            print("\nBuild completed successfully!")
            print(f"APKs are located in:")
            print(f"  Device APKs: {self.device_apks_dir}")
            print(f"  Built APKs:  {self.built_apks_dir}")

        except Exception as e:
            print(f"Error during build process: {e}")
            sys.exit(1)


def get_installed_version():
    try:
        result = subprocess.run(['adb', 'shell', 'dumpsys', 'package', 'org.thoughtcrime.securesms'],
                                capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            if 'versionName=' in line:
                return line.split('=')[1].strip()
    except subprocess.CalledProcessError:
        return None


def main(args):
    if args.version is None:
        version = get_installed_version()
    else:
        version = args.version
    if not version:
        print("No version provided and couldn't detect installed version.")
        print("Example: ./build_signal.py 7.7.0")
        sys.exit(1)
    else:
        print(f"Building {'installed' if not args.version else ''} Signal version: {version}")

    builder = SignalBuilder(args)
    builder.build(version)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", action="store", default=None, help="Provide the version you want to "
                                                                        "reproducably build. If this is not provided, the"
                                                                        "program attempts to pull an APK from a phone"
                                                                        "connected via. adb.")
    parser.add_argument("--dfs", choices=["chaos", "sort", "sort_reversed"], default=None,
                        help="Choose if and how to use"
                             "disorderfs as the underlay filesystem for the build.\n"
                             "chaos: introduce nondeterminism\n"
                             "sort: deterministically sort directory entries\n"
                             "sort_reversed: deterministically sort directory entries in reverse\n")
    parser.add_argument("--clean", action="store_true", default=False,
                        help="Clean up after building APKs. False by default.")
    args = parser.parse_args()
    main(args)
