# YouTube CSV Updater

A script to manage YouTube video metadata in a CSV file.

**Default CSV location:** `src/data/youtube.csv`

Assets deploy (`build.sh` / GitHub Actions) only **copies** this CSV to the CDN. It does **not** run this updater. Refresh metadata locally, commit, then deploy.

## Metadata columns

| Column | How it's filled |
|--------|-----------------|
| `title`, `author_name`, `video_thumbnail_url` | YouTube oEmbed |
| `thumbnail_url` (channel avatar), `date`, `description`, `views` | Watch-page HTML scrape |
| `like_count`, `comment_count` | Watch-page HTML scrape for likes; Innertube `next` for comments when HTML omits them |
| `format` | Manual (`long` / `short`); blank → infer from URL on marketing sites |
| `z_index`, `language`, `product`, `action_status` | Manual / optional LLM language detect |

## Basic Usage

### Update existing entries with missing metadata

Fills missing title/author **and** missing `like_count` / `comment_count`:

```bash
python scripts/update_youtube_csv.py
```

### Force update all entries (views + likes + comments)

```bash
python scripts/update_youtube_csv.py --force
```

## Adding New URLs

### Interactive mode (prompts for z_index, product, language)
```bash
python scripts/update_youtube_csv.py --add-url
```
- Press Enter to skip any field (leaves it blank)
- Shows existing options for product and language

### Simple mode (just add the URL, no prompts)
```bash
python scripts/update_youtube_csv.py --add-url-simple "https://www.youtube.com/watch?v=VIDEO_ID"
```

**Note:** URLs are automatically normalized to `https://www.youtube.com/watch?v=<video_id>` format, ignoring extra parameters.

## Checking for Duplicates

```bash
python scripts/update_youtube_csv.py --check-duplicates
```

Shows all duplicate YouTube videos found in the CSV with row numbers and details.

## Deleting Rows

```bash
python scripts/update_youtube_csv.py --delete-row 5
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
python scripts/update_youtube_csv.py --check-duplicates

# Add URL interactively
python scripts/update_youtube_csv.py --add-url

# Add URL without prompts
python scripts/update_youtube_csv.py --add-url-simple "https://youtu.be/VIDEO_ID"

# Delete row 5
python scripts/update_youtube_csv.py --delete-row 5

# Refresh views + likes + comments
python scripts/update_youtube_csv.py --force

# Update with VPN
python scripts/update_youtube_csv.py --force --vpn
```

## Marketing sites

After updating the CSV, marketing repos load it via `npm run sync:videos` (local path or CDN). Optional secondary enrich: set `YOUTUBE_API_KEY` so website sync can refresh statistics via YouTube Data API. See `web-dev-tool/analytics/youtube-workflow.md`.
