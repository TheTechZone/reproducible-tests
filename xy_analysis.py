#!/usr/bin/env python3
from analysis.analyse import (
    assemble_consistent_tarfile_list, 
    check_for_same_version,
    compare_metadata_list,
    is_metadata_to_dirorder_consistent,
    check_for_same_params,
    get_all_tarfiles
)


#tarfiles = assemble_consistent_tarfile_list(is_metadata_to_dirorder_consistent)
#print(tarfiles)
#check_for_same_version("v7.28.4", tarfiles, compare_metadata_list)
all_files = get_all_tarfiles()
check_for_same_params(all_files, compare_metadata_list, dfs=False)