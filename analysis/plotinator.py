import os
import json
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import pandas as pd
import seaborn as sns

from setup.structure import SUMMARY_ROOT, PLOT_ROOT, extract_parameters

from analysis.analyse import description_from_params

from analysis.tests import COMPARE_TO_TESTNAME

def pretty_print_raw(filepath):
    with open(filepath, "r") as f:
        obj = json.loads(f.read())
    print(json.dumps(obj, indent=4))


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
        len(set(hierarchy)) >= 1
    ), f"Unexpected {"parameters" if fixed_version else "versions"}: {hierarchy} for:\n{index}"
    # Now create hierarchical multiindex for each run
    # if it was a dfstest run, prepent the run nr. with a 't_'
    new_index = []
    for tarfile in index:
        (version, run, dfstest, dfs, ctime, reverse) = extract_parameters(tarfile)
        complete_run = f"t_{run}" if dfstest else run
        if not fixed_version:
            new_index.append((version, complete_run))
        else:
            if not dfs:
                new_index.append(
                    (
                    "no_dfs", complete_run
                    )
                )
            else:
                new_index.append(
                    (
                        f"{'ctime' if ctime else 'alph'}_{'reversed' if reverse else 'sorted'}",
                        complete_run,
                    )
                )
    names = ["version" if not fixed_version else "parameters", "run"]
    return pd.MultiIndex.from_tuples(new_index, names=names)


def nr_of_subplots(root):
    return len(os.listdir(root))


def subfigures(test, fixed_version):
    # root of the files?
    root = os.path.join(SUMMARY_ROOT, test, "fixed_versions" if fixed_version else "fixed_parameters")        
    # Organisation of subplots?
    nr_of_plots = int(nr_of_subplots(root))
    nr_x = int(nr_of_plots/2)
    #nr_x = 2
    #nr_y = 3
    nr_y = int(nr_of_plots/2) + (1 if nr_of_plots%2 == 0 else 0) + 1
    print(f"Creating {nr_x}x{nr_y} subplots...")
    fig, axes = plt.subplots(nrows=nr_x, ncols=nr_y, figsize=(22,7))
    # Create title from filepath
    print(root)
    version_or_params = root.split("/")[-1].replace(".json", "")
    fig.suptitle(f"{test} for {version_or_params.replace("_", " ")}")
    # Create all plots
    all_files = os.listdir(root)
    i = 0
    plot_idx = 1
    # call plotting
    for x in range(nr_x):
        for y in range(nr_y):
            if i < len(all_files):
                print(f"x:{x}, y:{y}")
                #ax = fig.add_subplot(nr_x, nr_y, plot_idx)
                success = correlation_triangle(fixed_version, axes[x, y], os.path.join(root, all_files[i]))
                while not success:
                    i = i + 1
                    success = correlation_triangle(fixed_version, axes[x, y], os.path.join(root, all_files[i]))
                # Set title:
                axes[x,y].set_title(all_files[i].replace(".json", "").replace("_", " "))
                i = i + 1
                plot_idx = plot_idx + 1
                #axes[x, y].tick_params(axis='x', labelrotation=45)
    plt.subplots_adjust(hspace=1.2, wspace=0.7)
    plt.savefig(os.path.join(PLOT_ROOT, f"{test}_{version_or_params}"))


def test():
    # assuming you call this from the root of the repo
    from pathlib import Path
    path = Path("./data/summary/dex_sort/fixed_versions/7.30.2.json").resolve()
    path2 = Path("./data/summary/dex_sort/fixed_versions/7.37.2.json").resolve()

    #fig = plt.figure()
    fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(12,5))
    #ax = fig.add_subplot(1,1,1)
    correlation_triangle(True, axes[0], path)
    correlation_triangle(True, axes[1], path2, cbar_ax=axes[1])
    plt.tight_layout()
    plt.show()


def correlation_triangle(fixed_version, ax, filepath, cbar_ax=None):
    df = generate_pd_frame(filepath, fixed_version)
    if df is not None: # otherwise we skip the file
        mask = np.triu(np.ones_like(df, dtype=bool))
        with plt.xkcd():
            np.fill_diagonal(mask, False)  # maybe?
            colors = ["xkcd:azure", "xkcd:blood red", "xkcd:light grey"]
            cmap = LinearSegmentedColormap.from_list("Custom", colors, len(colors))
            # plt.figure(figsize=(10, 8), dpi=80) 
            # needs to be removed if called from outside
            # else you get a shadow plot
            plot_cbar = cbar_ax is not None
            sns.heatmap(
                df,
                center=1,
                square=True,
                mask=mask,
                linewidths=0.5,
                cmap=cmap,
                vmin=0,
                vmax=2,
                cbar=plot_cbar,
                cbar_kws={"shrink": 0.5},
                ax=ax,
            )
            if plot_cbar:
                colorbar = ax.collections[0].colorbar
                colorbar.set_ticks([0, 1, 2])
            # # I save (len(diff) > 0) => true means inconsitent
                colorbar.set_ticklabels(["match", "inconsistent", "n/a"])
            plt.xticks(rotation=45)
    else:
        print(f"Skipped {filepath}...")
        return False
    return True



def generate_pd_frame(file_path, fixed_version):
    with open(os.path.join(file_path), "r") as f:
        obj = json.loads(f.read())
    if len(obj) == 0: # Not all tests can always be run, e.g., we only have a single 34 run
        return None
    df = pd.DataFrame(data=obj)
    print(f"Working on {file_path}...")
    new_index = create_multiindex(df.index, fixed_version)
    new_column_labels = create_multiindex(df.columns, fixed_version)
    #print(df)
    df = pd.DataFrame(df.to_numpy(), index=new_index, columns=new_column_labels)
    df.sort_index(axis=1, inplace=True)
    df.sort_index(inplace=True)
    #print(df)
    df.replace({False: 0, True: 1}, inplace=True)
    df.fillna(2, inplace=True)
    is_matrix_symmetric(df)
    return df


def visualize():
    for key in COMPARE_TO_TESTNAME.keys():
        test = COMPARE_TO_TESTNAME[key]
        print(test)
        for fixed_version in [True, False]:
            subfigures(test, fixed_version)
    #plt.savefig()
    #plt.tight_layout()
    #plt.show()
