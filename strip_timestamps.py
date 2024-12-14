#!/usr/bin/env python3

import sys
import re

# timing & progress indicators
timing_p = r"\d+(\.\d+)?s"
download_speed_p = r"\(\d+ kB/s\)"
remote_repository_progress_p = r"\[=* *\] \d+%"

patterns = [timing_p, download_speed_p, remote_repository_progress_p]


def main():
    if len(sys.argv) != 2:
        print("Usage: ./strip_timestamp <path/to/log.txt>")
        sys.exit(1)

    path = sys.argv[1]
    print(f"Stripping timestamps from: {path}...")

    with open(path, "r") as f:
        lines = f.readlines()

    newlines = []
    for line in lines:
        newline = line.strip()
        # print(f"Oldline:{newline}")
        if line[0] == "#":
            parts = line.split(" ")
            try:
                float(parts[1])
                del [parts[1]]
                newline = " ".join(parts)
            except ValueError:
                pass
        for p in patterns:
            newline = re.sub(p, "", newline)
        # print(f"Newline:{newline}")
        newlines.append(newline)

    path_parts = path.split("/")
    del path_parts[-1]
    newpath = "/".join(path_parts) + "/log_no_time.txt"

    with open(newpath, "w") as f:
        f.writelines(newlines)

    print(f"Result saved in: {newpath}")


if __name__ == "__main__":
    main()
