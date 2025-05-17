import os
import hashlib
import time
from itertools import combinations
from tqdm import tqdm
from pathlib import Path


def compute_sha256(file_path, block_size=65536):
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(block_size):
            sha256.update(chunk)
    return sha256.hexdigest()


def get_files_with_info(folder):
    file_info = {}
    for root, _, files in os.walk(folder):
        for name in files:
            full_path = os.path.join(root, name)
            rel_path = os.path.relpath(full_path, folder)
            ctime = os.path.getctime(full_path)
            sha256 = compute_sha256(full_path)
            file_info[rel_path] = {
                "full_path": full_path,
                "ctime": ctime,
                "sha256": sha256,
            }
    return file_info


def compare_folders(folder1, folder2):
    files1 = get_files_with_info(folder1)
    files2 = get_files_with_info(folder2)

    all_files = set(files1.keys()).union(files2.keys())

    only_in_1 = []
    only_in_2 = []
    modified = []

    for f in all_files:
        in_1 = f in files1
        in_2 = f in files2

        if in_1 and not in_2:
            only_in_1.append((f, files1[f]["ctime"], files1[f]["sha256"], None))
        elif in_2 and not in_1:
            only_in_2.append((f, files2[f]["ctime"], files2[f]["sha256"], None))
        else:
            # Compare SHA256 hashes
            if files1[f]["sha256"] != files2[f]["sha256"]:
                latest_ctime = max(files1[f]["ctime"], files2[f]["ctime"])
                modified.append(
                    (f, latest_ctime, files1[f]["sha256"], files2[f]["sha256"])
                )

    # Sort all by creation time
    only_in_1.sort(key=lambda x: x[1])
    only_in_2.sort(key=lambda x: x[1])
    modified.sort(key=lambda x: x[1])

    return {
        "only_in_folder1": only_in_1,
        "only_in_folder2": only_in_2,
        "modified": modified,
    }


def format_results(results):
    def format_list(title, items):
        print(f"\n{title}:")
        for f, ctime, sha, maybe_sha2 in items:
            shadata = sha[:8]
            if maybe_sha2:
                shadata += f" vs {maybe_sha2[:8]}"
            print(f"{f} ({shadata}) - Created: {time.ctime(ctime)}")

    format_list("Only in Folder 1", results["only_in_folder1"])
    format_list("Only in Folder 2", results["only_in_folder2"])
    format_list("Modified Files", results["modified"])


# Example usage
# folder1 = './results/signal_7_41_3__dfs-sort__run_1/build'
# folder2 = './results/signal_7_41_3__dfs-sort__run_2/build'

folders = combinations(
    [(f"./results/signal_7_41_3__dfs-sort__run_{i}/build", i) for i in range(1, 10)], 2
)

for (folder_1, idx1), (folder_2, idx2) in tqdm(folders):
    print(f"Comparing {folder_1} and {folder_2}")
    results = compare_folders(folder_1, folder_2)
    # todo: wrote result to ./results/diff_{idx1}_{idx2}.txt

    output_path = Path(f"./results/diff_{idx1}_{idx2}.txt").resolve()
    with output_path.open("w") as f:
        f.write(f"diff between {folder_1} and {folder_2}")

        def write_list(title, items):
            f.write(f"\n{title}:\n")
            for file_name, ctime, sha, maybe_sha2 in items:
                shadata = sha[:8]
                if maybe_sha2:
                    shadata += f" vs {maybe_sha2[:8]}"
                f.write(f"{file_name} ({shadata}) - Created: {time.ctime(ctime)}\n")

        write_list("Only in Folder 1", results["only_in_folder1"])
        write_list("Only in Folder 2", results["only_in_folder2"])
        write_list("Modified Files", results["modified"])

    print(f"✓ Diff written to {output_path}")
