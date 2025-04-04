import os
import json
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from setup.structure import(
    SUMMARY_ROOT,
    extract_parameters
)

from analysis.analyse import(
    description_from_params
)


def create_multiindex(index, hierarchy="version"):
    """
    hierarchy := "version"|"params"
    """
    # For now, we assume that witchever is not set by hierarchy will be constant
    # Sanity check this
    nothierarchy = []
    for tarfile in index:
        (version, _ , _, dfs, ctime, reverse) = extract_parameters(tarfile)
        if hierarchy == "version":
            nothierarchy.append((dfs, ctime, reverse))
        else:
            nothierarchy.append(version)
    assert(len(set(nothierarchy)) == 1), f"Unexpected {"parameters" if hierarchy == "version" else "versions"}: {set(nothierarchy)}"
    # Now create hierarchical multiindex for each run
    # if it was a dfstest run, prepent the run nr. with a 't_'
    new_index = []
    for tarfile in index:
        (version, run, dfstest, dfs, ctime, reverse) = extract_parameters(tarfile)
        complete_run = f"t_{run}" if dfstest else run
        if hierarchy == "version":
            new_index.append((version, complete_run))
        else:
            new_index.append((f"{'ctime' if ctime else 'alph'}_{'reversed' if reverse else 'sorted'}", complete_run))
    names = ["version" if version else "parameters", "run"]
    return pd.MultiIndex.from_tuples(new_index, names=names)


def visualize():
    with open(os.path.join(SUMMARY_ROOT, "dex_sort", "fixed_parameters","ctime_reverse_sorted.json"), 'r') as f:
        obj = json.loads(f.read())
    print(json.dumps(obj, indent=4))
    # turn this into a dataframe which will later be copied into a new one with meaningful indices
    df = pd.DataFrame(data=obj)
    new_index = create_multiindex(df.index)
    new_column_labels = create_multiindex(df.columns)
    df = pd.DataFrame(df.to_numpy(), index=new_index, columns=new_column_labels)
    df.sort_index(axis=1, inplace=True)
    df.sort_index(inplace=True)
    #print(df)
    df.replace({False:0, True:1}, inplace=True)
    #print(df)
    df.fillna(3, inplace=True)
    #print(df)
    #df = df.reindex(sorted(df.rows), axis=0)
    #print(df)
    #mask = np.triu(np.ones_like(df, dtype=bool))
    sns.heatmap(df, center=0, square=True, linewidths=.5, cbar_kws={"shrink": .5})
    #plt.savefig()
    plt.tight_layout()
    plt.show()




