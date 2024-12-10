import os
import sys
import subprocess


def apk_filepath(bundle_filepath, apk_name):
    partial = bundle_filepath.split("/")
    del(partial[-1])
    return os.path.join(*partial, "apks", "splits", apk_name)


def run_apkdiff(path1, path2):
    # for this quick and dirty test we simply used the copied apkdiff instead of fetching it every time
    result = run_command(
        [f'python {str(os.path.join(os.getcwd(), "apkdiff.py"))}', path1, path2],
        check=False
    )
    return result.returncode == 0


def run_command(cmd, cwd=None, check=True):
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
            universal_newlines=True
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





DIRECTORY_OF_INTEREST = "local_builds_mudkip"

INCLUDE_ALL_RUNS = ["no_disorderfs", "disorderfs_no_sort"]
APKS_OF_INTEREST = ["base-master.apk"]

unique_bundle_filepaths = []

for path, _, files in os.walk(os.getcwd()):
    if DIRECTORY_OF_INTEREST in path:
        for f in files:
            if f.endswith(".aab"):
                filepath = os.path.join(path, f)
                if any(dir in path for dir in INCLUDE_ALL_RUNS):
                    unique_bundle_filepaths.append(filepath)
                elif "01" in path:
                    unique_bundle_filepaths.append(filepath)


results = []
for apk in APKS_OF_INTEREST:
    for i in range(0, len(unique_bundle_filepaths)):
        for j in range(0, len(unique_bundle_filepaths)):
            if i != j:
                results.append(run_apkdiff(apk_filepath(unique_bundle_filepaths[i], apk), apk_filepath(unique_bundle_filepaths[j], apk)))

print(results)



