#!/usr/bin/env python3
import shutil
import subprocess
import sys
import os
from pathlib import Path


class DependencyChecker:
    def __init__(self):
        self.results = {}
        self.all_passed = True

    def check_command(self, command, args=None):
        """Check if a command exists and is executable."""
        try:
            if args is None:
                args = ["--version"]

            result = subprocess.run([command] + args, capture_output=True, text=True)
            version = result.stdout if result.stdout else result.stderr
            return True, version.strip()
        except FileNotFoundError:
            return False, None

    def check_symlink(self, command):
        """Check if a command is a symlink and get its target."""
        try:
            which_result = shutil.which(command)
            if which_result:
                target = os.path.realpath(which_result)
                return True, target
            return False, None
        except Exception:
            return False, None

    def print_result(
        self, name, installed, version=None, is_link=False, link_target=None
    ):
        """Print the result of a dependency check."""
        status = "✓" if installed else "✗"
        color_start = (
            "\033[32m" if installed else "\033[31m"
        )  # Green for success, Red for failure
        color_end = "\033[0m"

        result = f"{color_start}{status}{color_end} {name}: "
        if installed:
            if version:
                result += f"Found ({version})"
            else:
                result += "Found"
            if is_link and link_target:
                result += f"\n  → Links to: {link_target}"
        else:
            result += "Not found"
            self.all_passed = False

        print(result)
        self.results[name] = installed

    def check_python(self):
        version = sys.version.split()[0]
        is_python3 = version.startswith("3")
        self.print_result("Python 3.x", is_python3, version)

    def check_git(self):
        installed, version = self.check_command("git")
        self.print_result("Git", installed, version)

    def check_docker(self):
        installed, version = self.check_command("docker")
        self.print_result("Docker", installed, version)

    def check_adb(self):
        installed, version = self.check_command("adb", ["version"])
        is_link, link_target = self.check_symlink("adb")
        self.print_result("ADB", installed, version, is_link, link_target)

    def check_gcc(self):
        installed = self.check_command("gcc")
        self.print_result("gcc", installed)

    def check_make(self):
        installed, version = self.check_command("make")
        self.print_result("make", installed)

    def check_bundletool(self):
        """Check if bundletool is available and properly linked."""
        # First check if the wrapper script exists in the current directory
        wrapper_path = "./bundletool"
        jar_found = False
        jar_path = None

        if os.path.isfile(wrapper_path) and os.access(wrapper_path, os.X_OK):
            # Read the wrapper script to find the JAR path
            with open(wrapper_path, "r") as f:
                content = f.read()
                import re

                jar_match = re.search(r'java -jar "(.*?)"', content)
                if jar_match:
                    jar_path = jar_match.group(1)
                    if os.path.isfile(jar_path):
                        jar_found = True

        if jar_found:
            # Try to get version using java -jar
            try:
                result = subprocess.run(
                    ["java", "-jar", jar_path, "version"],
                    capture_output=True,
                    text=True,
                )
                version = result.stdout.strip() if result.stdout else None
                self.print_result("Bundletool", True, version, True, jar_path)
                return
            except Exception:
                pass

        # If we get here, either the wrapper doesn't exist or the JAR wasn't found
        self.print_result("Bundletool", False)

    def run_all_checks(self):
        """Run all dependency checks."""
        print("Checking dependencies...")
        print("-" * 50)

        self.check_python()
        self.check_git()
        self.check_docker()
        self.check_adb()
        self.check_bundletool()
        self.check_gcc()
        self.check_make()

        print("-" * 50)
        if self.all_passed:
            print("All dependencies are satisfied! ✓")
        else:
            print("Some dependencies are missing. ✗")
            sys.exit(1)


if __name__ == "__main__":
    checker = DependencyChecker()
    checker.run_all_checks()
