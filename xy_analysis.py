#!/usr/bin/env python3
from analysis.analyse import (
    assemble_consistent_tarfile_list, 
    check_for_same_version,
    compare_metadata_list,
    is_metadata_to_dirorder_consistent,
    check_for_same_params,
    get_all_tarfiles,
    get_all_versions
)


tarfiles = assemble_consistent_tarfile_list(is_metadata_to_dirorder_consistent)
#print(tarfiles)
versions = get_all_versions()
for v in versions:
    check_for_same_version(v, tarfiles, compare_metadata_list)
    print()
#check_for_same_version("v7.28.4", tarfiles, compare_metadata_list)
all_files = get_all_tarfiles()
check_for_same_params(all_files, compare_metadata_list, dfs=False)
print()
# Enumerate the 4 parameter combinations
check_for_same_params(all_files, compare_metadata_list, dfs=True, alph=True, ctime=False, reverse=False)
print()
check_for_same_params(all_files, compare_metadata_list, dfs=True, alph=True, ctime=False, reverse=True)
print()
check_for_same_params(all_files, compare_metadata_list, dfs=True, alph=False, ctime=True, reverse=False)
print()
check_for_same_params(all_files, compare_metadata_list, dfs=True, alph=False, ctime=True, reverse=True)