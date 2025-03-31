#!/usr/bin/env python3
from analysis.analyse import (
    assemble_consistent_tarfile_list, 
    compare_for_same_version,
    compare_metadata_list
)


tarfiles = assemble_consistent_tarfile_list()
print(tarfiles)
compare_for_same_version("v7.28.4", tarfiles, compare_metadata_list)