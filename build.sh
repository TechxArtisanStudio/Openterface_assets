#!/bin/bash

# Build script: process src/ into dist/ (images, firmware, site browser, etc.)

set -e

echo "Creating necessary directories..."
mkdir -p dist/css dist/js dist/images dist/data
mkdir -p dist/firmware dist/scripts
mkdir -p dist/openterface/firmware dist/openterface/scripts
mkdir -p dist/minikvm

if [ -f src/CNAME ]; then
    cp src/CNAME dist/CNAME
    echo "CNAME file copied."
fi

copy_dir() {
    local src="$1"
    local dest="$2"
    local label="$3"
    if [ -d "$src" ] && [ "$(ls -A "$src" 2>/dev/null)" ]; then
        echo "Copying $label..."
        rsync -a "$src" "$dest"
        echo "$label copied successfully."
    else
        echo "No $label found, skipping..."
    fi
}

copy_dir src/images/ dist/images/ "images"
copy_dir src/data/ dist/data/ "data"
copy_dir src/firmware/ dist/firmware/ "firmware"
copy_dir src/scripts/ dist/scripts/ "scripts"
copy_dir src/openterface/firmware/ dist/openterface/firmware/ "openterface firmware"
copy_dir src/openterface/scripts/ dist/openterface/scripts/ "openterface scripts"
copy_dir src/minikvm/ dist/minikvm/ "minikvm"

echo "Generating list of image files to convert to WebP..."
image_files=$(find src/images -type f \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" \) 2>/dev/null || true)

if [ -n "$image_files" ]; then
    echo "Image files to process:"
    echo "$image_files"

    echo "Converting images to WebP format..."
    for file in $image_files; do
        rel_path=$(echo "$file" | sed "s|^src/images/||")
        rel_dir=$(dirname "$rel_path")

        if [ "$rel_dir" = "." ]; then
            target_dir="dist/images"
        else
            target_dir="dist/images/$rel_dir"
        fi

        mkdir -p "$target_dir"
        base_name=$(basename "${file%.*}")
        output_file="$target_dir/$base_name.webp"

        echo "Processing image: $file -> $output_file"
        rm -f "$output_file"

        if cwebp "$file" -o "$output_file" 2>&1; then
            echo "  ✓ Successfully created: $output_file"
        else
            echo "  ✗ Failed to convert: $file"
            exit 1
        fi
    done
    echo "WebP conversion completed."
else
    echo "No images found for WebP conversion, skipping..."
fi

css_files=$(find src/css -type f -name "*.css" 2>/dev/null || true)
if [ -n "$css_files" ]; then
    echo "CSS files to process:"
    echo "$css_files"
    echo "Minifying CSS files..."
    for file in $css_files; do
        echo "Input CSS file: $file"
        target_dir="dist/css/$(dirname "$file" | sed "s|^src\/css||")"
        mkdir -p "$target_dir"
        output_file="$target_dir$(basename "${file%.css}.min.css")"
        echo "Output CSS file: $output_file"
        csso "$file" -o "$output_file"
    done
    echo "CSS minification completed."
else
    echo "No CSS files found, skipping minification..."
fi

js_files=$(find src/js -type f -name "*.js" 2>/dev/null || true)
if [ -n "$js_files" ]; then
    echo "JS files to process:"
    echo "$js_files"
    echo "Minifying JS files..."
    for file in $js_files; do
        echo "Input JS file: $file"
        target_dir="dist/js/$(dirname "$file" | sed "s|^src\/js||")"
        mkdir -p "$target_dir"
        output_file="$target_dir$(basename "${file%.js}.min.js")"
        echo "Output JS file: $output_file"
        uglifyjs "$file" -o "$output_file"
    done
    echo "JS minification completed."
else
    echo "No JS files found, skipping minification..."
fi

if [ -d src/site ] && [ "$(ls -A src/site 2>/dev/null)" ]; then
    echo "Copying site files to dist/..."
    rsync -a src/site/ dist/
    echo "Site files copied successfully."
fi

echo "Build process completed."
