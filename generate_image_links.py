#!/usr/bin/env python3
"""
Script to generate markdown file with WebP image links from source images.
This script scans the src/images directory and creates markdown links for all images
that would be converted to WebP format during the build process.
"""

import os
import sys
from pathlib import Path

def find_image_files(directory):
    """Find all image files that would be converted to WebP."""
    image_extensions = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
    svg_extensions = {'.svg'}
    image_files = []
    svg_files = []
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = Path(root) / file
            if file_path.suffix.lower() in image_extensions:
                # Get relative path from src/images
                rel_path = file_path.relative_to(directory)
                image_files.append(rel_path)
            elif file_path.suffix.lower() in svg_extensions:
                # Get relative path from src/images
                rel_path = file_path.relative_to(directory)
                svg_files.append(rel_path)
    
    return sorted(image_files), sorted(svg_files)

def generate_markdown_links(image_files, base_url="https://assets.openterface.com"):
    """Generate markdown links for WebP images."""
    markdown_lines = []
    
    for image_path in image_files:
        # If already WebP, keep as is; otherwise convert to WebP extension
        if image_path.suffix.lower() == '.webp':
            webp_path = image_path
        else:
            webp_path = image_path.with_suffix('.webp')
        
        # Create the full URL
        full_url = f"{base_url}/images/{webp_path}"
        
        # Create a descriptive name for the alt text
        # Remove path separators and file extension, replace with hyphens
        alt_name = str(webp_path).replace('/', '-').replace('\\', '-').replace('.webp', '')
        
        # Generate markdown link
        markdown_link = f"[{alt_name}]({full_url})"
        markdown_lines.append(markdown_link)
    
    return markdown_lines

def generate_svg_markdown_links(svg_files, base_url="https://assets.openterface.com"):
    """Generate markdown links for SVG images."""
    markdown_lines = []
    
    for svg_path in svg_files:
        # Create the full URL (keep .svg extension)
        full_url = f"{base_url}/images/{svg_path}"
        
        # Create a descriptive name for the alt text
        # Remove path separators and file extension, replace with hyphens
        alt_name = str(svg_path).replace('/', '-').replace('\\', '-').replace('.svg', '')
        
        # Generate markdown link
        markdown_link = f"[{alt_name}]({full_url})"
        markdown_lines.append(markdown_link)
    
    return markdown_lines

def main():
    # Get the script directory
    script_dir = Path(__file__).parent
    src_images_dir = script_dir / "src" / "images"
    
    # Check if src/images directory exists
    if not src_images_dir.exists():
        print(f"Error: {src_images_dir} directory not found!")
        print("Please run this script from the project root directory.")
        sys.exit(1)
    
    print(f"Scanning for images in: {src_images_dir}")
    
    # Find all image files
    image_files, svg_files = find_image_files(src_images_dir)
    
    if not image_files and not svg_files:
        print("No image files found!")
        return
    
    print(f"Found {len(image_files)} image files and {len(svg_files)} SVG files")
    
    # Generate markdown links
    webp_markdown_lines = generate_markdown_links(image_files)
    svg_markdown_lines = generate_svg_markdown_links(svg_files)
    
    # Write to output file
    output_file = script_dir / "image_links.md"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Image Links\n\n")
        f.write("Generated from source images in src/images/\n\n")
        
        if webp_markdown_lines:
            f.write("## WebP Image Links\n\n")
            f.write("Copy and paste these links into your markdown files:\n\n")
            for line in webp_markdown_lines:
                f.write(line + "\n\n")
        
        if svg_markdown_lines:
            f.write("## SVG Image Links\n\n")
            f.write("Copy and paste these links into your markdown files:\n\n")
            for line in svg_markdown_lines:
                f.write(line + "\n\n")
    
    print(f"Generated {len(webp_markdown_lines)} WebP image links and {len(svg_markdown_lines)} SVG links")
    print(f"Output saved to: {output_file}")
    
    # Also print a few examples
    if webp_markdown_lines:
        print("\nFirst 3 WebP links:")
        for i, line in enumerate(webp_markdown_lines[:3]):
            print(f"{i+1}. {line}")
    
    if svg_markdown_lines:
        print("\nFirst 3 SVG links:")
        for i, line in enumerate(svg_markdown_lines[:3]):
            print(f"{i+1}. {line}")

if __name__ == "__main__":
    main()
