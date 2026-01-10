#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys
import tempfile

def strip_quotes(path):
    """Remove surrounding quotes (single or double) from a path string."""
    path = path.strip()
    if (path.startswith('"') and path.endswith('"')) or \
       (path.startswith("'") and path.endswith("'")):
        return path[1:-1]
    return path

def run(cmd):
    subprocess.run(cmd, check=True)

def filesize_mb(path):
    return os.path.getsize(path) / (1024 * 1024)

def get_gif_info(gif_path):
    """Extract GIF information using ImageMagick identify command."""
    try:
        # Get basic info: dimensions, colors, delay
        result = subprocess.run(
            ["magick", "identify", "-format", "%w %h %k %T\n", gif_path],
            capture_output=True,
            text=True,
            check=True
        )
        
        lines = result.stdout.strip().split('\n')
        if not lines or not lines[0]:
            return None
        
        # Parse first frame for dimensions
        first_line = lines[0].split()
        width = int(first_line[0])
        height = int(first_line[1])
        
        # Count frames
        frame_count = len([line for line in lines if line.strip()])
        
        # Extract colors from all frames to get maximum (GIFs can have varying color counts per frame)
        all_colors = []
        for line in lines:
            if line.strip():
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        all_colors.append(int(parts[2]))
                    except (ValueError, IndexError):
                        pass
        
        # Use max colors across all frames (or first frame's colors if parsing failed)
        if all_colors:
            colors = max(all_colors)
        else:
            colors = int(first_line[2]) if len(first_line) >= 3 else 0
        
        # Get delays (in centiseconds) from all frames
        delay_result = subprocess.run(
            ["magick", "identify", "-format", "%T\n", gif_path],
            capture_output=True,
            text=True,
            check=True
        )
        delays = [int(d) for d in delay_result.stdout.strip().split('\n') if d.strip()]
        
        # Validate that delays count matches frame count
        if len(delays) != frame_count:
            # If mismatch, use frame_count as authoritative and pad/truncate delays
            if len(delays) < frame_count:
                # Pad with last delay value
                last_delay = delays[-1] if delays else 10
                delays.extend([last_delay] * (frame_count - len(delays)))
            else:
                # Truncate to frame_count
                delays = delays[:frame_count]
        
        avg_delay = sum(delays) / len(delays) if delays else 0
        fps = round(100 / avg_delay, 2) if avg_delay > 0 else 0
        
        # Calculate total duration in seconds (delays are in centiseconds)
        total_duration = sum(delays) / 100.0 if delays else 0
        
        return {
            'width': width,
            'height': height,
            'colors': colors,
            'frames': frame_count,
            'fps': fps,
            'avg_delay': avg_delay,
            'duration': total_duration,
            'delays': delays
        }
    except (subprocess.CalledProcessError, ValueError, IndexError) as e:
        return None

def time_range_to_frames(start_time, end_time, delays, total_duration):
    """
    Convert time range (in seconds) to frame range.
    
    Args:
        start_time: Start time in seconds (float)
        end_time: End time in seconds (float, or None to mean end of GIF)
        delays: List of frame delays in centiseconds
        total_duration: Total duration of GIF in seconds
    
    Returns:
        Tuple (start_frame, end_frame) or None if invalid
    """
    if not delays or len(delays) == 0:
        return None
    
    if start_time < 0:
        start_time = 0
    if end_time is None or end_time > total_duration:
        end_time = total_duration
    if start_time >= end_time:
        return None
    
    # Calculate cumulative time for each frame
    cumulative_times = []
    cumulative = 0.0
    for delay in delays:
        cumulative += delay / 100.0
        cumulative_times.append(cumulative)
    
    # Find start frame: first frame that overlaps with start_time
    # cumulative_times[i] is the time at the END of frame i
    # Frame i exists from cumulative_times[i-1] (or 0) to cumulative_times[i]
    start_frame = 0
    prev_time = 0.0
    for i, cum_time in enumerate(cumulative_times):
        # Frame i starts at prev_time and ends at cum_time
        if cum_time > start_time:
            # This frame ends after start_time, so it overlaps
            start_frame = i
            break
        prev_time = cum_time
    
    # Find end frame: last frame that overlaps with end_time
    # We want the last frame where the frame starts <= end_time
    prev_time = 0.0
    end_frame = len(delays) - 1
    for i, cum_time in enumerate(cumulative_times):
        # Frame i starts at prev_time
        if prev_time > end_time:
            # This frame starts after end_time, so previous frame is the last valid one
            end_frame = max(0, i - 1)
            break
        prev_time = cum_time
    
    if start_frame > end_frame:
        return None
    
    return (start_frame, end_frame)

def compare_gifs(gif1_path, gif2_path):
    """
    Compare two GIF files and display a side-by-side comparison.
    
    Args:
        gif1_path: Path to first GIF file
        gif2_path: Path to second GIF file
    """
    print("\n" + "=" * 70)
    print("📊 GIF Comparison")
    print("=" * 70)
    
    # Validate files exist
    if not os.path.exists(gif1_path):
        print(f"❌ Error: File not found: {gif1_path}")
        return
    if not os.path.exists(gif2_path):
        print(f"❌ Error: File not found: {gif2_path}")
        return
    
    # Get info for both GIFs
    print(f"\n📁 GIF 1: {gif1_path}")
    gif1_info = get_gif_info(gif1_path)
    if not gif1_info:
        print("❌ Error: Could not read GIF 1 information")
        return
    
    print(f"📁 GIF 2: {gif2_path}")
    gif2_info = get_gif_info(gif2_path)
    if not gif2_info:
        print("❌ Error: Could not read GIF 2 information")
        return
    
    # Get file sizes
    size1 = filesize_mb(gif1_path)
    size1_bytes = os.path.getsize(gif1_path)
    size2 = filesize_mb(gif2_path)
    size2_bytes = os.path.getsize(gif2_path)
    
    # Calculate percentage differences
    def calc_percent_diff(val1, val2):
        if val1 == 0:
            return "N/A" if val2 == 0 else "∞"
        return ((val2 - val1) / val1) * 100
    
    def format_diff(val1, val2, unit=""):
        diff = calc_percent_diff(val1, val2)
        if diff == "N/A":
            return "N/A"
        if diff == "∞":
            return "+∞"
        sign = "+" if diff >= 0 else ""
        return f"{sign}{diff:.1f}%"
    
    # Print comparison table
    print("\n" + "-" * 70)
    print(f"{'Property':<20} {'GIF 1':<20} {'GIF 2':<20} {'Difference':<10}")
    print("-" * 70)
    
    # File size
    diff_size = format_diff(size1, size2)
    print(f"{'File Size (MB)':<20} {size1:<20.2f} {size2:<20.2f} {diff_size:<10}")
    print(f"{'File Size (bytes)':<20} {size1_bytes:<20,} {size2_bytes:<20,} {format_diff(size1_bytes, size2_bytes):<10}")
    
    # Dimensions
    dim1 = f"{gif1_info['width']} × {gif1_info['height']}"
    dim2 = f"{gif2_info['width']} × {gif2_info['height']}"
    dim_diff = "Same" if dim1 == dim2 else "Different"
    print(f"{'Dimensions':<20} {dim1:<20} {dim2:<20} {dim_diff:<10}")
    
    # Frame count
    frames1 = gif1_info['frames']
    frames2 = gif2_info['frames']
    frames_diff = frames2 - frames1
    frames_diff_str = f"{frames_diff:+d}" if frames_diff != 0 else "0"
    print(f"{'Frames':<20} {frames1:<20} {frames2:<20} {frames_diff_str:<10}")
    
    # Duration
    dur1 = gif1_info['duration']
    dur2 = gif2_info['duration']
    dur_diff = format_diff(dur1, dur2)
    print(f"{'Duration (sec)':<20} {dur1:<20.2f} {dur2:<20.2f} {dur_diff:<10}")
    
    # FPS
    fps1 = gif1_info['fps']
    fps2 = gif2_info['fps']
    fps_diff = fps2 - fps1
    fps_diff_str = f"{fps_diff:+.2f}" if fps_diff != 0 else "0.00"
    print(f"{'FPS':<20} {fps1:<20.2f} {fps2:<20.2f} {fps_diff_str:<10}")
    
    # Colors
    colors1 = gif1_info['colors']
    colors2 = gif2_info['colors']
    colors_diff = colors2 - colors1
    colors_diff_str = f"{colors_diff:+d}" if colors_diff != 0 else "0"
    print(f"{'Colors (max)':<20} {colors1:<20} {colors2:<20} {colors_diff_str:<10}")
    
    print("-" * 70)
    
    # Summary
    size_saved = size1 - size2
    size_saved_pct = calc_percent_diff(size1, size2)
    if isinstance(size_saved_pct, (int, float)):
        if size_saved_pct > 0:
            print(f"\n✅ GIF 2 is {abs(size_saved_pct):.1f}% smaller ({abs(size_saved):.2f} MB saved)")
        elif size_saved_pct < 0:
            print(f"\n⚠️  GIF 2 is {abs(size_saved_pct):.1f}% larger ({abs(size_saved):.2f} MB more)")
        else:
            print(f"\n📊 Both GIFs have the same file size")
    print()

def split_gif(input_gif, split_points, gif_info, output_dir, input_name, input_ext, width=None, fps=None, colors=None):
    """
    Split a GIF at specified time points, creating multiple output files.
    
    Args:
        input_gif: Path to input GIF file
        split_points: List of time points (in seconds) to split at
        gif_info: GIF information dictionary
        output_dir: Directory to save output files
        input_name: Base name for output files (without extension)
        input_ext: File extension (e.g., '.gif')
        width: Optional target width for optimization
        fps: Optional target FPS for optimization
        colors: Optional number of colors for optimization
    
    Returns:
        List of output file paths
    """
    if not split_points:
        return []
    
    # Sort and validate split points
    split_points = sorted([float(p) for p in split_points])
    total_duration = gif_info['duration']
    delays = gif_info.get('delays', [])
    
    # Filter out invalid points and add boundaries
    valid_points = [0.0]
    for point in split_points:
        if 0 < point < total_duration:
            valid_points.append(point)
    valid_points.append(total_duration)
    
    # Remove duplicates
    valid_points = sorted(list(set(valid_points)))
    
    if len(valid_points) < 2:
        print("⚠️  Warning: No valid split points. Keeping original GIF.")
        return []
    
    output_files = []
    print(f"\n✂️  Splitting GIF into {len(valid_points) - 1} segments...")
    
    for i in range(len(valid_points) - 1):
        start_time = valid_points[i]
        end_time = valid_points[i + 1]
        
        # Convert time range to frame range
        frame_range = time_range_to_frames(start_time, end_time, delays, total_duration)
        if not frame_range:
            print(f"⚠️  Warning: Could not extract segment {i+1} ({start_time:.2f}-{end_time:.2f}s). Skipping.")
            continue
        
        start_frame, end_frame = frame_range
        
        # Generate output filename
        output_filename = f"{input_name}_part{i+1}{input_ext}"
        output_path = os.path.join(output_dir, output_filename)
        
        # Extract frames using ImageMagick
        extract_cmd = ["magick", f"{input_gif}[{start_frame}-{end_frame}]"]
        
        # Extract frames first to a temp file
        temp_fd, temp_file = tempfile.mkstemp(suffix='.gif', prefix='gif_split_')
        os.close(temp_fd)
        
        try:
            # Extract frames
            extract_cmd.append(temp_file)
            run(extract_cmd)
            
            # Build optimization command
            opt_cmd = ["magick", temp_file]
            
            # Add resize if specified
            if width:
                opt_cmd += ["-resize", f"{width}x"]
            
            # Add FPS adjustment if specified
            if fps:
                delay = int(100 / fps)
                opt_cmd += ["-delay", str(delay)]
            
            # Add color reduction if specified
            if colors:
                opt_cmd += ["-colors", str(colors)]
            
            # Add optimization and output
            opt_cmd += ["-layers", "Optimize", output_path]
            
            # Run optimization
            run(opt_cmd)
            
            # Clean up temp file
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except Exception as e:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            print(f"⚠️  Warning: Failed to process segment {i+1}: {e}")
            continue
        
        output_files.append(output_path)
        segment_duration = end_time - start_time
        print(f"   ✓ Created segment {i+1}: {output_filename} ({start_time:.2f}-{end_time:.2f}s, {segment_duration:.2f}s)")
    
    return output_files

# Check for help flag
if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h', 'help']:
    print("\n🎞️ GIF Size Optimizer")
    print("\nUsage:")
    print("  python optimize_gif.py [path-to-gif]")
    print("  python optimize_gif.py <gif1> <gif2>          # Compare two GIFs")
    print("  python optimize_gif.py --compare <gif1> <gif2> # Compare two GIFs")
    print("\nExamples:")
    print("  python optimize_gif.py")
    print("  python optimize_gif.py /path/to/image.gif")
    print("  python optimize_gif.py 'path with spaces/image.gif'")
    print("  python optimize_gif.py original.gif optimized.gif")
    print("  python optimize_gif.py --compare file1.gif file2.gif")
    print("\nIf no path is provided, the script will prompt for it interactively.")
    print("If two paths are provided, the script will compare the two GIFs.\n")
    sys.exit(0)

print("\n🎞️ GIF Size Optimizer\n")

# Check for ImageMagick installation
if not shutil.which("magick"):
    print("❌ Error: ImageMagick not found. Please install ImageMagick first.")
    print("   On macOS: brew install imagemagick")
    print("   On Ubuntu/Debian: sudo apt-get install imagemagick")
    sys.exit(1)

# Check for comparison mode
if len(sys.argv) >= 3:
    # Check if --compare flag is used
    if sys.argv[1] == '--compare':
        if len(sys.argv) != 4:
            print("❌ Error: --compare requires exactly two GIF file paths")
            print("   Usage: python optimize_gif.py --compare <gif1> <gif2>")
            sys.exit(1)
        gif1 = strip_quotes(sys.argv[2].strip())
        gif2 = strip_quotes(sys.argv[3].strip())
        gif1 = os.path.abspath(gif1)
        gif2 = os.path.abspath(gif2)
        compare_gifs(gif1, gif2)
        sys.exit(0)
    elif len(sys.argv) == 3:
        # Two file paths provided - assume comparison mode
        gif1 = strip_quotes(sys.argv[1].strip())
        gif2 = strip_quotes(sys.argv[2].strip())
        gif1 = os.path.abspath(gif1)
        gif2 = os.path.abspath(gif2)
        compare_gifs(gif1, gif2)
        sys.exit(0)

# Get input GIF path from command line argument or prompt
if len(sys.argv) > 1:
    input_gif = sys.argv[1].strip()
    input_gif = strip_quotes(input_gif)
    print(f"📁 Using GIF path from argument: {input_gif}\n")
else:
    input_gif = input("👉 Path to input GIF: ").strip()
    input_gif = strip_quotes(input_gif)

input_gif = os.path.abspath(input_gif)

if not os.path.exists(input_gif):
    print(f"❌ Error: File not found: {input_gif}")
    sys.exit(1)

# Validate that input is a GIF file
if not input_gif.lower().endswith('.gif'):
    print(f"❌ Error: Input file is not a GIF file: {input_gif}")
    print("   Please provide a file with .gif extension")
    sys.exit(1)

# Display current GIF information
print("\n📊 Current GIF Information:")
print("─" * 50)
orig_size = filesize_mb(input_gif)
print(f"📦 File size: {orig_size:.2f} MB ({os.path.getsize(input_gif):,} bytes)")

gif_info = get_gif_info(input_gif)
if gif_info:
    frame_count = gif_info['frames']
    print(f"📐 Dimensions: {gif_info['width']} × {gif_info['height']} px")
    print(f"🎬 Frames: {frame_count} (indices 0-{frame_count - 1})")
    print(f"⏱️  Current FPS: {gif_info['fps']:.2f}")
    print(f"⏳ Duration: {gif_info['duration']:.2f} seconds")
    print(f"🎨 Colors: {gif_info['colors']}")
else:
    print("⚠️  Could not read detailed GIF information")
    gif_info = None
print("─" * 50)

# Generate output filename automatically: same directory, with suffix
input_dir = os.path.dirname(input_gif)
input_basename = os.path.basename(input_gif)
input_name, input_ext = os.path.splitext(input_basename)
output_basename = f"{input_name}_optimized{input_ext}"
output_gif = os.path.join(input_dir, output_basename)

print(f"\n📁 Output will be saved to: {output_gif}")

# ---- Interactive options ----
# Trimming selection: frame-based or time-based
frame_range = None
split_points = None  # For split mode (time-based or frame-based)
if gif_info:
    trim_method = input("\n✂️  Trim by time or frames? (t/f, Enter to skip trimming): ").strip().lower()
    
    if trim_method in ['f', 'frames']:
        # Frame-based trimming or splitting
        frame_range_input = input("   Frame range to keep (e.g., 10-50 for trim, 10 or 10,50 for split, Enter to keep all): ").strip()
        if frame_range_input:
            frame_range_input = frame_range_input.strip()
            try:
                if '-' in frame_range_input:
                    # Format: "start-end" → TRIM mode (keep only this range)
                    parts = frame_range_input.split('-')
                    if len(parts) != 2:
                        print("⚠️  Warning: Invalid frame range format. Use 'start-end' for trim, or comma-separated for split. Keeping all frames.")
                    else:
                        start = int(parts[0].strip())
                        end = int(parts[1].strip())
                        if start < 0 or end >= gif_info['frames'] or start > end:
                            print(f"⚠️  Warning: Frame range {start}-{end} is invalid (valid range: 0-{gif_info['frames'] - 1}). Keeping all frames.")
                        else:
                            frame_range = (start, end)
                            # Calculate approximate time range
                            if gif_info.get('delays'):
                                selected_delays = gif_info['delays'][start:end+1]
                                time_range = sum(selected_delays) / 100.0
                                print(f"   ✓ Will keep frames {start}-{end} (~{time_range:.2f} seconds)")
                elif ',' in frame_range_input:
                    # Format: "10, 50" → SPLIT mode (split at these frames)
                    split_frames_str = [p.strip() for p in frame_range_input.split(',')]
                    try:
                        split_frames = [int(p) for p in split_frames_str if p]
                        # Convert frame numbers to time points for consistency
                        if gif_info.get('delays'):
                            cumulative = 0.0
                            frame_times = []
                            for delay in gif_info['delays']:
                                cumulative += delay / 100.0
                                frame_times.append(cumulative)
                            
                            split_points = []
                            for frame_num in split_frames:
                                if 0 <= frame_num < len(frame_times):
                                    split_points.append(frame_times[frame_num])
                                else:
                                    print(f"⚠️  Warning: Frame {frame_num} is out of range. Skipping.")
                            
                            if split_points:
                                frame_range = None  # Signal split mode
                                print(f"   ✓ Will split at frames: {', '.join([str(f) for f in split_frames])} ({', '.join([f'{t:.2f}s' for t in split_points])})")
                            else:
                                print("⚠️  Warning: No valid split frames. Keeping all frames.")
                        else:
                            print("⚠️  Warning: Cannot convert frames to time. Keeping all frames.")
                    except ValueError:
                        print("⚠️  Warning: Invalid split frames format. Use numbers like '10, 50'. Keeping all frames.")
                else:
                    # Format: "10" → SPLIT mode (split at this frame)
                    split_frame = int(frame_range_input.strip())
                    if split_frame < 0 or split_frame >= gif_info['frames']:
                        print(f"⚠️  Warning: Split frame {split_frame} is invalid (valid range: 0-{gif_info['frames'] - 1}). Keeping all frames.")
                    else:
                        # Convert frame number to time point
                        if gif_info.get('delays'):
                            cumulative = 0.0
                            for i, delay in enumerate(gif_info['delays']):
                                if i == split_frame:
                                    split_points = [cumulative]
                                    frame_range = None  # Signal split mode
                                    print(f"   ✓ Will split at frame {split_frame} (~{cumulative:.2f}s)")
                                    break
                                cumulative += delay / 100.0
                        else:
                            print("⚠️  Warning: Cannot convert frame to time. Keeping all frames.")
            except ValueError:
                print("⚠️  Warning: Invalid frame format. Use numbers like '10-50' for trim, or '10' or '10,50' for split. Keeping all frames.")
    
    elif trim_method in ['t', 'time']:
        # Time-based trimming or splitting
        time_range_input = input("   Time range to keep in seconds (e.g., 2.5-5.0 for trim, 2.5 or 2.5,5.5 for split, Enter to keep all): ").strip()
        if time_range_input:
            time_range_input = time_range_input.strip()
            try:
                if '-' in time_range_input:
                    # Format: "start-end" → TRIM mode (keep only this range)
                    parts = time_range_input.split('-')
                    if len(parts) != 2:
                        print("⚠️  Warning: Invalid time range format. Use 'start-end' for trim, or comma-separated for split. Keeping all frames.")
                    else:
                        start_time = float(parts[0].strip())
                        end_time = float(parts[1].strip())
                        if start_time < 0 or end_time > gif_info['duration'] or start_time >= end_time:
                            print(f"⚠️  Warning: Time range {start_time}-{end_time} is invalid (valid range: 0-{gif_info['duration']:.2f} seconds). Keeping all frames.")
                        else:
                            # Convert time range to frame range
                            frame_range = time_range_to_frames(
                                start_time, 
                                end_time, 
                                gif_info.get('delays', []), 
                                gif_info['duration']
                            )
                            if frame_range:
                                start_frame, end_frame = frame_range
                                print(f"   ✓ Will keep frames {start_frame}-{end_frame} (time: {start_time:.2f}-{end_time:.2f} seconds)")
                            else:
                                print("⚠️  Warning: Could not convert time range to frames. Keeping all frames.")
                elif ',' in time_range_input:
                    # Format: "2.5, 5.5" → SPLIT mode (split at these points)
                    split_points_str = [p.strip() for p in time_range_input.split(',')]
                    try:
                        split_points = [float(p) for p in split_points_str if p]
                        frame_range = None  # Signal split mode
                        print(f"   ✓ Will split at: {', '.join([f'{p:.2f}s' for p in split_points])}")
                    except ValueError:
                        print("⚠️  Warning: Invalid split points format. Use numbers like '2.5, 5.5'. Keeping all frames.")
                        split_points = None
                else:
                    # Format: "2.5" → SPLIT mode (split at this point)
                    split_point = float(time_range_input.strip())
                    if split_point < 0 or split_point >= gif_info['duration']:
                        print(f"⚠️  Warning: Split point {split_point} is invalid (valid range: 0-{gif_info['duration']:.2f} seconds). Keeping all frames.")
                    else:
                        split_points = [split_point]
                        frame_range = None  # Signal split mode
                        print(f"   ✓ Will split at: {split_point:.2f}s")
            except ValueError:
                print("⚠️  Warning: Invalid time format. Use numbers like '2.5-5.0' for trim, or '2.5' or '2.5,5.5' for split. Keeping all frames.")
                split_points = None
    
    elif trim_method == '':
        # User chose to skip trimming
        pass
    else:
        print("⚠️  Warning: Invalid choice. Use 'f' for frames, 't' for time, or Enter to skip. Keeping all frames.")
else:
    print("\n⚠️  Cannot determine trimming options - GIF info not available. Keeping all frames.")

width = input("\n🔧 Target width in px (Enter to keep original): ").strip()
fps = input("⏱️ Target FPS (recommended 8–12, Enter to skip): ").strip()
colors = input("🎨 Number of colors (32/64/128, Enter to keep): ").strip()

# Parse optimization parameters
width_value = None
if width:
    try:
        width_value = int(width)
        if width_value <= 0:
            print("⚠️  Warning: Width must be positive. Skipping resize.")
            width_value = None
    except ValueError:
        print("⚠️  Warning: Invalid width value. Skipping resize.")

fps_value = None
if fps:
    try:
        fps_value = int(fps)
        if fps_value <= 0:
            print("⚠️  Warning: FPS must be positive. Skipping FPS adjustment.")
            fps_value = None
    except ValueError:
        print("⚠️  Warning: Invalid FPS value. Skipping FPS adjustment.")

colors_value = None
if colors:
    try:
        colors_value = int(colors)
        if colors_value <= 0:
            print("⚠️  Warning: Number of colors must be positive. Skipping color reduction.")
            colors_value = None
    except ValueError:
        print("⚠️  Warning: Invalid colors value. Skipping color reduction.")

# Check if we're in split mode
if split_points and gif_info:
    # Split mode: create multiple output files
    print("\n⚙️ Processing split segments...\n")
    output_files = split_gif(
        input_gif,
        split_points,
        gif_info,
        input_dir,
        input_name,
        input_ext,
        width_value,
        fps_value,
        colors_value
    )
    
    if output_files:
        print("\n✅ Done!\n")
        print(f"📁 Created {len(output_files)} segment(s):")
        total_size = 0
        for i, output_file in enumerate(output_files, 1):
            size = filesize_mb(output_file)
            total_size += size
            print(f"   {i}. {os.path.basename(output_file)} ({size:.2f} MB)")
        print(f"\n📦 Total size: {total_size:.2f} MB")
        saved = orig_size - total_size
        percent = (saved / orig_size) * 100 if orig_size else 0
        print(f"💾 Saved: {saved:.2f} MB ({percent:.1f}%) compared to original\n")
    else:
        print("⚠️  No segments were created.\n")
    sys.exit(0)

# Build ImageMagick command
# If frame range is specified, we need to extract frames first
working_gif = input_gif
temp_gif = None

if frame_range:
    # Create a temporary file for the trimmed GIF
    temp_fd, temp_gif = tempfile.mkstemp(suffix='.gif', prefix='gif_trim_')
    os.close(temp_fd)
    
    # Extract frame range using ImageMagick syntax: input.gif[start-end]
    start, end = frame_range
    extract_cmd = ["magick", f"{input_gif}[{start}-{end}]", temp_gif]
    print(f"\n✂️  Extracting frames {start}-{end}...")
    try:
        run(extract_cmd)
        working_gif = temp_gif
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: Failed to extract frames with exit code {e.returncode}")
        if temp_gif and os.path.exists(temp_gif):
            os.remove(temp_gif)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: Failed to extract frames: {e}")
        if temp_gif and os.path.exists(temp_gif):
            os.remove(temp_gif)
        sys.exit(1)

cmd = ["magick", working_gif]

if width_value:
    cmd += ["-resize", f"{width_value}x"]

if fps_value:
    delay = int(100 / fps_value)  # GIF delay = 100 / fps
    cmd += ["-delay", str(delay)]

if colors_value:
    cmd += ["-colors", str(colors_value)]

cmd += ["-layers", "Optimize", output_gif]

print("\n⚙️ Running optimization...\n")
try:
    run(cmd)
except subprocess.CalledProcessError as e:
    print(f"❌ Error: ImageMagick optimization failed with exit code {e.returncode}")
    print("   Please check that ImageMagick is properly installed and the input file is valid.")
    # Clean up temp file if it exists
    if temp_gif and os.path.exists(temp_gif):
        os.remove(temp_gif)
    sys.exit(1)
except FileNotFoundError:
    print("❌ Error: ImageMagick 'magick' command not found in PATH")
    # Clean up temp file if it exists
    if temp_gif and os.path.exists(temp_gif):
        os.remove(temp_gif)
    sys.exit(1)
finally:
    # Clean up temporary file if it was created
    if temp_gif and os.path.exists(temp_gif):
        try:
            os.remove(temp_gif)
        except:
            pass

new_size = filesize_mb(output_gif)
saved = orig_size - new_size
percent = (saved / orig_size) * 100 if orig_size else 0

print("✅ Done!\n")
print(f"📦 New size: {new_size:.2f} MB")
print(f"💾 Saved: {saved:.2f} MB ({percent:.1f}%)")
print(f"📁 Output: {output_gif}\n")
