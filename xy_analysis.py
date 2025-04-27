#!/usr/bin/env python3
import json
# from analysis.aggregation import aggregate_all_runs
from analysis.analyse import run_all_checks
from analysis.checks import (
    compare_dex_hashes,
    compare_first_dex_hash,
    compare_metadata_list
)
# from analysis.plotinator import visualize
# from setup.structure import create_or_clear_summary_directory_for
from analysis.plotinator import visualize

def pretty_print_raw(filepath):
    with open(filepath, "r") as f:
        obj = json.load(f)
    print(json.dumps(obj, indent=4))

###
# Script
###

# redo apkdiff
# aggregate_all_runs(dexsort=False, diffuse=False, apkdiff=True, nav=False, output_meta=False)


# test()
#run_all_checks([compare_dex_hashes, compare_first_dex_hash, compare_metadata_list], with_metadata_list=True)
run_all_checks([compare_dex_hashes, compare_first_dex_hash], with_metadata_list=True)
pretty_print_raw("/home/chrissy/Code/reproducible-tests/data/summary/metadata_list/fixed_versions/7.30.2.json")
visualize()
