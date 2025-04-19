#!/bin/bash

# Create necessary directories
mkdir -p dist/css
mkdir -p dist/js
mkdir -p dist/images

# Copy all images to dist/images while preserving folder structure
rsync -a src/images/ dist/images/

# Convert images to WebP format while preserving folder structure
find src/images -type f \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" \) -exec sh -c '
  mkdir -p "dist/images/$(dirname "$1" | sed "s|^src/images/||")" &&
  cwebp "$1" -o "dist/images/$(dirname "$1" | sed "s|^src/images/||")/$(basename "${1%.*}.webp")"
' _ {} \;

# Minify CSS files while preserving folder structure
find src/css -type f -name "*.css" -exec sh -c '
  mkdir -p "dist/css/$(dirname "$1" | sed "s|^src/css/||")" &&
  csso "$1" -o "dist/css/$(dirname "$1" | sed "s|^src/css/||")/$(basename "${1%.css}.min.css")"
' _ {} \;

# Minify JS files while preserving folder structure
find src/js -type f -name "*.js" -exec sh -c '
  mkdir -p "dist/js/$(dirname "$1" | sed "s|^src/js/||")" &&
  uglifyjs "$1" -o "dist/js/$(dirname "$1" | sed "s|^src/js/||")/$(basename "${1%.js}.min.js")"
' _ {} \;