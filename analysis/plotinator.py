import os
import json
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import pandas as pd
import seaborn as sns

from setup.structure import SUMMARY_ROOT, extract_parameters

from analysis.analyse import description_from_params


# matrices should be symmetrical, sanity check this before turning the plot into a triangle
def is_matrix_symmetric(dataframe):
    array = dataframe.to_numpy()
    for x, y in np.ndindex(array.shape):
        assert array[x, y] == array[y, x], f"Symmetry broken for {x} <=> {y} was: {array[x, y]} and {array[y, x]}\n{dataframe}"


def create_multiindex(index, fixed_version):
    """
    hierarchy := "version"|"params"
    """
    # Sanity check if the version/parameters are really fixed
    hierarchy = []
    for tarfile in index:
        #print(tarfile)
        (version, _, _, dfs, ctime, reverse) = extract_parameters(tarfile)
        if not fixed_version:
            hierarchy.append((dfs, ctime, reverse))
        else:
            hierarchy.append(version)
    assert (
        len(set(hierarchy)) == 1
    ), f"Unexpected {"parameters" if fixed_version else "versions"}: {set(hierarchy)} for:\n{index}"
    # Now create hierarchical multiindex for each run
    # if it was a dfstest run, prepent the run nr. with a 't_'
    new_index = []
    for tarfile in index:
        (version, run, dfstest, dfs, ctime, reverse) = extract_parameters(tarfile)
        complete_run = f"t_{run}" if dfstest else run
        if fixed_version:
            new_index.append((version, complete_run))
        else:
            new_index.append(
                (
                    f"{'ctime' if ctime else 'alph'}_{'reversed' if reverse else 'sorted'}",
                    complete_run,
                )
            )
    names = ["version" if version else "parameters", "run"]
    return pd.MultiIndex.from_tuples(new_index, names=names)


def nr_of_subplots(root):
    return len(os.listdir(root))


def subfigures(test, fixed_title, fixed_version):
    # root of the files?
    root = os.path.join(SUMMARY_ROOT, test)        
    # Organisation of subplots?
    nr_of_plots = nr_of_subplots(root)
    nr_x = int(nr_of_plots/2)
    nr_y = int(nr_of_plots/2) + ( 1 if nr_of_plots%2 == 0 else 0)
    fig, ax = plt.subplots(nr_x, nr_y)
    # title?
    fig.suptitle(f"{test} for {fixed_title}")
    # Create all plots
    plots = correlation_triangles(root, fixed_version)
    i = 0
    # call plotting
    for x in range(nr_x):
        for y in range(nr_y):
            ax[x, y] = plots[i]
            i = i + 1
    plt.show()



def correlation_triangles(root, fixed_version):
    # returns an array of ax populated by the triangles
    root = os.path.join(root, "fixed_versions" if fixed_version else "fixed_parameters")
    plots = []
    for summary_file in os.listdir(root):
        df = generate_pd_frame(os.path.join(root, summary_file), fixed_version)
        mask = np.triu(np.ones_like(df, dtype=bool))
        plt.xkcd()
        np.fill_diagonal(mask, False)  # maybe?
        colors = ["xkcd:azure", "xkcd:blood red", "xkcd:light grey"]
        cmap = LinearSegmentedColormap.from_list("Custom", colors, len(colors))
        plt.figure(figsize=(10, 8), dpi=80)
        ax = sns.heatmap(
            df,
            center=1,
            square=True,
            mask=mask,
            linewidths=0.5,
            cbar_kws={"shrink": 0.5},
            cmap=cmap,
            vmin=np.amin(df),
            vmax=np.amax(df),
        )
        colorbar = ax.collections[0].colorbar
        colorbar.set_ticks([0, 1, 2])
        colorbar.set_ticklabels(["match", "inconsistent", "n/a"])
        plt.xticks(rotation=45)
        plots.add(ax)



def generate_pd_frame(file_path, fixed_version):
    with open(os.path.join(file_path), "r") as f:
        obj = json.loads(f.read())
    df = pd.DataFrame(data=obj)
    print(f"Working on {file_path}...")
    new_index = create_multiindex(df.index, fixed_version)
    new_column_labels = create_multiindex(df.columns, fixed_version)
    df = pd.DataFrame(df.to_numpy(), index=new_index, columns=new_column_labels)
    df.sort_index(axis=1, inplace=True)
    df.sort_index(inplace=True)
    df.replace({False: 0, True: 1}, inplace=True)
    df.fillna(2, inplace=True)
    is_matrix_symmetric(df)
    return df


def visualize():
    subfigures("dex_sort", "blah", True)
    # plt.savefig()
    plt.tight_layout()
    plt.show()
