#!/bin/bash

# Create necessary directories
echo "Creating necessary directories..."
mkdir -p dist/css
mkdir -p dist/js
mkdir -p dist/images

# Copy all images to dist/images while preserving folder structure
echo "Copying images to dist/images..."
rsync -a src/images/ dist/images/
echo "Images copied successfully."

# Generate a list of image files to convert to WebP
echo "Generating list of image files to convert to WebP..."
image_files=$(find src/images -type f \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" \))
echo "Image files to process:"
echo "$image_files"

# Convert images to WebP format
echo "Converting images to WebP format..."
for file in $image_files; do
  target_dir="dist/images/$(dirname "$file" | sed "s|^src/images/||")"
  if [[ "$target_dir" == "dist/images/" ]]; then
    target_dir="dist/images"
  fi
  mkdir -p "$target_dir"
  echo "Processing image: $file -> $target_dir/$(basename "${file%.*}.webp")"
  cwebp "$file" -o "$target_dir/$(basename "${file%.*}.webp")"
done

# Generate a list of CSS files to minify
echo "Generating list of CSS files to minify..."
css_files=$(find src/css -type f -name "*.css")
echo "CSS files to process:"
echo "$css_files"

# Minify CSS files
echo "Minifying CSS files..."
for file in $css_files; do
  target_dir="dist/css/$(dirname "$file" | sed "s|^src/css/||")"
  if [[ "$target_dir" == "dist/css/" ]]; then
    target_dir="dist/css"
  fi
  mkdir -p "$target_dir"
  echo "Processing CSS: $file -> $target_dir/$(basename "${file%.css}.min.css")"
  csso "$file" -o "$target_dir/$(basename "${file%.css}.min.css")"
done

# Generate a list of JS files to minify
echo "Generating list of JS files to minify..."
js_files=$(find src/js -type f -name "*.js")
echo "JS files to process:"
echo "$js_files"

# Minify JS files
echo "Minifying JS files..."
for file in $js_files; do
  target_dir="dist/js/$(dirname "$file" | sed "s|^src/js/||")"
  if [[ "$target_dir" == "dist/js/" ]]; then
    target_dir="dist/js"
  fi
  mkdir -p "$target_dir"
  echo "Processing JS: $file -> $target_dir/$(basename "${file%.js}.min.js")"
  uglifyjs "$file" -o "$target_dir/$(basename "${file%.js}.min.js")"
done

echo "Build process completed."