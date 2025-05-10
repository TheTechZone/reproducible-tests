#!/bin/bash

# Path to the base directory where the folders are located
base_dir="../data/build/classes/"

# Output JSON file where the results will be stored
output_json_file="comparisons_summary.json"

# Initialize an empty array for the comparison results
comparisons=()

# Get all subfolders in the base directory
subfolders=($(find "$base_dir" -mindepth 1 -maxdepth 1 -type d))

# Loop through all pairs of subfolders
for i in "${!subfolders[@]}"; do
    for j in $(seq $((i + 1)) $((${#subfolders[@]} - 1))); do
        folder1="${subfolders[$i]}"
        folder2="${subfolders[$j]}"

        echo "{$folder1} vs {$folder2}"
        # Generate an output file name for the comparison
        output_filename="comparison_$(basename "$folder1")_$(basename "$folder2").json"

        # Run the comparison script (replace script.py with your actual script)
        python3 dex_folder_compare.py "$folder1" "$folder2" -o "dex_sim/$output_filename" -bc

        # Save the comparison result into an array
        comparisons+=("{\"folder1\": \"$folder1\", \"folder2\": \"$folder2\", \"output_file\": \"$output_filename\"}\n")
    done
done

# Write the results to the output JSON file
echo "[${comparisons[*]}]" | sed 's/}{/},\n{/g' > "$output_json_file"

echo "Comparisons complete. Results saved in $output_json_file"
