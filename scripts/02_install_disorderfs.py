#!/usr/bin/env python3
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parents[1]
disorderfs_dir = str((Path(__file__).parent / "../disorderfs").resolve())
sys.path.insert(0, str(root_dir))
from src.setup import execute
from src.setup import get_package_manager
from plumbum import local
import os

git = local["git"]
make = local["make"]
rm = local["rm"]

# Idempotence
execute(rm["-r", "disorderfs"], retcodes=(0, 1))

# Clone disorderfs
execute(git["clone", "https://github.com/Cerenia/disorderfs.git", disorderfs_dir])

# Install libraries of fuse needed by disorderfs
pm = get_package_manager()
pm.install_libfuse()
pm.install("pkgconf")

# Make disorderfs
os.chdir(disorderfs_dir)
execute(make)
execute(make["install"], as_sudo=True)
