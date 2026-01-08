# YouTube CSV Updater

A script to manage YouTube video metadata in a CSV file.

**Default CSV location:** `src/data/youtube.csv`

## Basic Usage

### Update existing entries with missing metadata
```bash
python update_youtube_csv.py
```

### Force update all entries (useful for updating view counts)
```bash
python update_youtube_csv.py --force
```

## Adding New URLs

### Interactive mode (prompts for z_index, product, language)
```bash
python update_youtube_csv.py --add-url
```
- Press Enter to skip any field (leaves it blank)
- Shows existing options for product and language

### Simple mode (just add the URL, no prompts)
```bash
python update_youtube_csv.py --add-url-simple "https://www.youtube.com/watch?v=VIDEO_ID"
```

**Note:** URLs are automatically normalized to `https://www.youtube.com/watch?v=<video_id>` format, ignoring extra parameters.

## Checking for Duplicates

```bash
python update_youtube_csv.py --check-duplicates
```

Shows all duplicate YouTube videos found in the CSV with row numbers and details.

## Deleting Rows

```bash
python update_youtube_csv.py --delete-row 5
```

Deletes a row by row number. Row 1 is the CSV header and cannot be deleted. The script will show the row details and ask for confirmation before deleting.

## Other Options

- `--dry-run` - Preview changes without saving
- `--verbose` - Show detailed output
- `--offline` - Run without network requests
- `--vpn` - Use VPN proxy
- `--csv-path PATH` - Specify custom CSV file path

## Examples

```bash
# Check for duplicates
python update_youtube_csv.py --check-duplicates

# Add URL interactively
python update_youtube_csv.py --add-url

# Add URL without prompts
python update_youtube_csv.py --add-url-simple "https://youtu.be/VIDEO_ID"

# Delete row 5
python update_youtube_csv.py --delete-row 5

# Update with VPN
python update_youtube_csv.py --force --vpn
```
