#!/usr/bin/env bash
set -euo pipefail

INPUT_DIR="themk_exports"
OUTPUT_ROOT="vault_batches"
SCRIPT="scripts/mediawiki_to_md.py"

mkdir -p "$OUTPUT_ROOT"

for xml_file in "$INPUT_DIR"/themk_batch_*.xml; do
    [ -e "$xml_file" ] || continue

    base_name="$(basename "$xml_file" .xml)"
    output_dir="$OUTPUT_ROOT/$base_name"

    echo "Processing $xml_file -> $output_dir"
    python "$SCRIPT" "$xml_file" "$output_dir"
done

echo "All XML files processed."