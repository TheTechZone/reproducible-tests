from setup.shell import execute
from setup.pm import get_package_manager
from plumbum import local
import os

git = local["git"]
make = local["make"]
rm = local["rm"]

# Idempotence
execute(rm["-r", "disorderfs"], retcodes=(0,1))

# Clone disorderfs
execute(git["clone", "https://salsa.debian.org/reproducible-builds/disorderfs.git"])

# Install libraries of fuse needed by disorderfs
pm = get_package_manager()
pm.install_libfuse()
pm.install("pkgconf")

# Make disorderfs
os.chdir("./disorderfs")

execute(make["install"], as_sudo=True)