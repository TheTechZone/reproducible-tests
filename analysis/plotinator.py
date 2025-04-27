from pathlib import Path
from typing import Optional, Union
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm
from matplotlib.cm import ScalarMappable
import numpy as np
import pandas as pd
import seaborn as sns

from setup.structure import SUMMARY_ROOT, PLOT_ROOT, parameters_from_tar_filename

from analysis.checks import COMPARE_TO_CHECK_NAME


def assert_symmetry(df: pd.DataFrame) -> None:
    """
    matrices should be symmetrical, validate this before turning the plot into a triangle

    Raises:
           AssertionError: If any check fails
    """
    array = df.to_numpy()
    for x, y in np.ndindex(array.shape):
        assert (
            array[x, y] == array[y, x]
        ), f"Symmetry broken for {x} <=> {y} was: {array[x, y]} and {array[y, x]}\n{df}"


def create_multiindex(index: pd.Index, fixed_version: bool) -> pd.MultiIndex:
    """
    Create a MultiIndex based on either fixed versions or parameters.

    hierarchy := "version"|"params"
    """
    hierarchy: list[str | tuple] = []

    # Extract version/parameter info for each tarfile
    for tarfile in index:
        (version, _, _, dfs, ctime, reverse) = parameters_from_tar_filename(tarfile)
        if fixed_version:
            hierarchy.append((version))
        else:
            hierarchy.append((dfs, ctime, reverse))

    # Ensure at least one unique hierarchy entry exists
    assert (
        len(set(hierarchy)) >= 1
    ), f"Unexpected {'parameters' if not fixed_version else 'versions'}: {hierarchy} for:\n{index}"

    new_index = []

    # Construct the new index based on the fixed_version flag
    for tarfile in index:
        (version, run, dfstest, dfs, ctime, reverse) = parameters_from_tar_filename(
            tarfile
        )
        complete_run = f"t_{run}" if dfstest else run

        if fixed_version:
            index_tuple = (
                (
                    "no_dfs"
                    if not dfs
                    else f"{'ctime' if ctime else 'alph'}_{'reversed' if reverse else 'sorted'}"
                ),
                complete_run,
            )
        else:
            index_tuple = (version, complete_run)

        new_index.append(index_tuple)

    names = ["version" if not fixed_version else "parameters", "run"]

    return pd.MultiIndex.from_tuples(new_index, names=names)


def nr_of_subplots(root: Path) -> int:
    return len(list(root.iterdir()))


def subfigures(test: str, fixed_version: bool) -> None:
    # root of the files?
    root = (
        SUMMARY_ROOT
        / test
        / ("fixed_versions" if fixed_version else "fixed_parameters")
    )

    # Organisation of subplots?
    nr_of_plots = nr_of_subplots(root)
    nr_x = int(nr_of_plots / 2)
    nr_y = int(nr_of_plots / 2) + (1 if nr_of_plots % 2 == 0 else 0) + 1
    print(f"Creating {nr_x}x{nr_y} subplots...")
    fig, axes = plt.subplots(nrows=nr_x, ncols=nr_y, figsize=(22, 7))
    # Create title from filepath
    print(root)
    version_or_params = root.name.replace(".json", "")
    fig.suptitle(f"{test} for {version_or_params.replace("_", " ")}")
    # Create all plots
    all_files = list(root.iterdir())
    # print(all_files)
    # return
    i = 0
    plot_idx = 1

    successful_plots = []
    # call plotting
    for x in range(nr_x):
        for y in range(nr_y):
            if i < len(all_files):
                print(f"x:{x}, y:{y}")
                file_path = all_files[i]
                success = correlation_triangle(fixed_version, axes[x, y], file_path)
                while not success:
                    i = i + 1
                    if i < len(all_files):
                        file_path = all_files[i]
                        success = correlation_triangle(fixed_version, axes[x, y], file_path)
                    else:
                        # we are out of data
                        # No more files to plot, hide the remaining axes
                        axes[x, y].set_visible(False)
                        break
                # Set title:
                title = file_path.stem.replace("_", " ")
                axes[x, y].set_title(title)
                # Record the successful plot
                successful_plots.append(
                    {
                        "ax": axes[x, y],
                        "title": title,
                        "position": (x, y),
                    }
                )
                i = i + 1
                plot_idx = plot_idx + 1
            else:
                # No more files to plot, hide the remaining axes
                axes[x, y].set_visible(False)

    cbar_shrink = 0.5
    total_plots = len(successful_plots)
    if total_plots > 0:
        # Calculate optimal grid dimensions
        optimal_cols = int(np.ceil(np.sqrt(total_plots)))
        optimal_rows = int(np.ceil(total_plots / optimal_cols))

        # Only rearrange if the current layout is not optimal
        if nr_x != optimal_rows or nr_y != optimal_cols:
            print(f"Rebalancing layout to {optimal_rows}x{optimal_cols}")
            cbar_shrink = 0.4
            # Hide all current axes
            for x in range(nr_x):
                for y in range(nr_y):
                    axes[x, y].set_visible(False)

            # Create a new figure with optimal dimensions
            new_fig, new_axes = plt.subplots(
                nrows=optimal_rows,
                ncols=optimal_cols,
                figsize=(optimal_cols * 12.75, optimal_rows * 4.25),
            )

            # Make sure new_axes is a 2D array
            if optimal_rows == 1 and optimal_cols == 1:
                new_axes = np.array([[new_axes]])
            elif optimal_rows == 1:
                new_axes = new_axes.reshape(1, -1)
            elif optimal_cols == 1:
                new_axes = new_axes.reshape(-1, 1)

            # Copy content from the old figure to the new figure
            for idx, plot in enumerate(successful_plots):
                new_x = idx // optimal_cols
                new_y = idx % optimal_cols

                # Get the old plot's content and transfer it
                # This is a simplified approach - in reality, you may need to
                # re-run correlation_triangle with the new axes
                # old_ax = plot["ax"]
                new_ax = new_axes[new_x, new_y]

                # Transfer the title
                new_ax.set_title(plot["title"])

                # Re-run correlation_triangle with the new axis
                # old_pos = plot['position']
                # file_name = plot["title"].replace(" ", "_") + ".json"
                filename = plot["title"].replace(" ", "_") + ".json"
                correlation_triangle(fixed_version, new_ax, root / filename)

            # Set the title on the new figure
            new_fig.suptitle(f"{test} for {version_or_params.replace('_', ' ')}")
            plt.close(fig)

            fig = new_fig
            axes = new_axes
            # return

    plt.tight_layout()

    colors = ["xkcd:blood red", "xkcd:azure", "xkcd:light grey"]
    cmap = LinearSegmentedColormap.from_list("Custom", colors, len(colors))
    bounds = [0, 1, 2, 3]
    norm = BoundaryNorm(bounds, 4)

    cbar = fig.colorbar(
        ScalarMappable(norm=norm, cmap=cmap),
        ax=axes,
        orientation="vertical",
        ticks=[0.5, 1.5, 2.5],
        shrink=cbar_shrink,
    )
    cbar.set_ticklabels(["inconsistent", "match", "n/a"])

    plt.savefig(PLOT_ROOT / f"{test}_{version_or_params}", dpi=300)


def correlation_triangle(fixed_version: bool, ax, filepath: Path) -> bool:
    df = generate_pd_frame(filepath, fixed_version)
    if df is not None:  # otherwise, we skip the file
        print(df)
        mask = np.triu(np.ones_like(df, dtype=bool), k=1)
        with plt.xkcd():
            np.fill_diagonal(mask, False)
            colors = ["xkcd:blood red", "xkcd:azure", "xkcd:light grey"]
            cmap = LinearSegmentedColormap.from_list("Custom", colors, len(colors))
            sns.heatmap(
                df,
                center=1,
                square=True,
                mask=mask,
                linewidths=0.5,
                cmap=cmap,
                vmin=0,
                vmax=2,
                cbar=False,
                ax=ax,
            )

            plt.setp(
                ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor"
            )
            plt.setp(
                ax.get_yticklabels(), rotation=0, ha="right", rotation_mode="anchor"
            )  # to fix some inconsistency with the rotation angles
    else:
        print(f"Skipped {filepath}")
        return False
    return True


def generate_pd_frame(
    file_path: Union[str, Path], fixed_version: bool
) -> Optional[pd.DataFrame]:
    # Read the JSON file directly into a DataFrame
    file_path = Path(file_path)

    try:
        df = pd.read_json(file_path)
    except ValueError as e:
        print(f"Error reading {file_path}: {e}")
        return None
    print(df)
    # Return early if the data is empty
    if df.empty:
        # Not all tests can always be run, e.g., we only have a single 34 run
        return None
    df.fillna(2, inplace=True)

    print(f"Working on {file_path}...")
    new_index = create_multiindex(df.index, fixed_version)
    new_column_labels = create_multiindex(df.columns, fixed_version)
    df = pd.DataFrame(df.to_numpy(), index=new_index, columns=new_column_labels)
    df.sort_index(axis=1, inplace=True)
    df.sort_index(inplace=True)
    assert_symmetry(df)
    return df


def visualize() -> None:
    for key in COMPARE_TO_CHECK_NAME.keys():
        test = COMPARE_TO_CHECK_NAME[key]
        print(test)
        for fixed_version in [True, False]:
            subfigures(test, fixed_version)
