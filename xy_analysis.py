#!/usr/bin/env python3
from analysis.aggregation import aggregate_all_runs
from analysis.analyse import run_all_tests
from analysis.tests import (
    compare_dex_hashes,
    compare_first_dex_file_hash,
    compare_metadata_list,
    is_metadata_to_dirorder_consistent,
)
from analysis.plotinator import visualize, pretty_print_raw
from setup.structure import create_or_clear_summary_directory_for


###
# Script
###


# redo apkdiff
# aggregate_all_runs(dexsort=False, diffuse=False, apkdiff=True, nav=False, output_meta=False)


# pretty_print_raw("/home/chrissy/Code/reproducible-tests/data/summary/dex_sort/fixed_versions/7.30.2.json")
visualize()
# test()
# run_all_tests([compare_dex_hashes, compare_first_dex_file_hash], with_metadata_list=False)
