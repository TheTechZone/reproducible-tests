import os
import json
import matplotlib
import numpy as np
import pandas as pd
import seaborn as sns

from setup.structure import(
    SUMMARY_ROOT
)

def visualize():
    with open(os.path.join(SUMMARY_ROOT, "dex_sort", "fixed_parameters","ctime_reverse_sorted.json"), 'r') as f:
        obj = json.loads(f.read())

    print(json.dumps(obj, indent=4))

    #mask = np.triu(np.ones_like(corr, dtype=bool))




