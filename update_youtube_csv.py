#!/usr/bin/env python3
"""
YouTube CSV Metadata Updater

This script updates src/data/youtube.csv with YouTube video metadata.
It fetches metadata for videos and updates the CSV file, preserving user edits
and supporting maintenance workflows.

Usage:
    python update_youtube_csv.py [--dry-run] [--verbose] [--offline] [--force] [--skip-existing]
"""

import os
import re
import sys
import csv
import time
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import requests
from datetime import datetime

# Supported language codes for detection
SUPPORTED_LANGUAGES = ['en', 'zh', 'ja', 'ko', 'fr', 'de', 'it', 'es', 'pt', 'ro']


class LanguageDetector:
    """Detects language using LM Studio API."""
    
    def __init__(self, api_url: str = "http://127.0.0.1:1234/v1/chat/completions", verbose: bool = False):
        self.api_url = api_url
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })
        # Disable proxy for localhost connections
        self.session.trust_env = False
        self.session.proxies = {'http': None, 'https': None}
        self.model_name = None
        self._get_available_model()
    
    def _get_available_model(self):
        """Get the first available model from LM Studio."""
        try:
            models_url = self.api_url.replace('/v1/chat/completions', '/v1/models')
            response = self.session.get(models_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and len(data['data']) > 0:
                    for model in data['data']:
                        model_id = model.get('id', '')
                        if 'chat' in model_id.lower() or 'gpt' in model_id.lower() or 'llama' in model_id.lower():
                            self.model_name = model_id
                            break
                    else:
                        self.model_name = data['data'][0].get('id', 'local-model')
        except Exception:
            self.model_name = 'local-model'
    
    def _extract_language_code(self, text: str) -> Optional[str]:
        """Extract language code from LLM response."""
        text = text.strip().upper()
        for lang_code in SUPPORTED_LANGUAGES:
            if lang_code.upper() in text or f'"{lang_code}"' in text or f"'{lang_code}'" in text:
                return lang_code
        pattern = r'\b(en|zh|ja|ko|fr|de|it|es|pt|ro)\b'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).lower()
        return None
    
    def detect_language(self, title: str, description: str) -> Optional[str]:
        """Detect language from title and description using LLM."""
        text_to_analyze = f"Title: {title}\n\nDescription: {description[:500]}"
        prompt = f"""Analyze the following YouTube video title and description, and determine the primary language.

Supported language codes:
- en (English)
- zh (Chinese)
- ja (Japanese)
- ko (Korean)
- fr (French)
- de (German)
- it (Italian)
- es (Spanish)
- pt (Portuguese)
- ro (Romanian)

Text to analyze:
{text_to_analyze}

Respond with ONLY the language code (e.g., "en", "zh", "ja"). Do not include any explanation or additional text."""

        try:
            payload = {
                "model": self.model_name or "local-model",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 50
            }
            response = self.session.post(self.api_url, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if 'choices' in data and len(data['choices']) > 0:
                    content = data['choices'][0].get('message', {}).get('content', '').strip()
                    if content:
                        return self._extract_language_code(content)
            return None
        except Exception:
            return None


class YouTubeMetadataFetcher:
    """Fetches YouTube video metadata using web scraping."""
    
    def __init__(self, offline_mode: bool = False, proxy: str = None):
        self.offline_mode = offline_mode
        if not offline_mode:
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            
            # Set up proxy if provided
            if proxy:
                proxies = {
                    'http': proxy,
                    'https': proxy
                }
                self.session.proxies.update(proxies)
                
        self.cache = {}
        
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([^&\n?#]+)',
            r'youtube\.com/watch\?.*v=([^&\n?#]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def normalize_youtube_url(self, url: str) -> Optional[str]:
        """Normalize YouTube URL to standard format: https://www.youtube.com/watch?v=<video_id>"""
        video_id = self.extract_video_id(url)
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
        return None
    
    def fetch_video_metadata(self, video_id: str) -> Dict[str, str]:
        """Fetch video metadata from YouTube."""
        if video_id in self.cache:
            return self.cache[video_id]
            
        if self.offline_mode:
            empty_metadata = {
                'title': '',
                'author_name': '',
                'thumbnail_url': '',
                'video_thumbnail_url': '',
                'date': '',
                'views': '',
                'description': ''
            }
            self.cache[video_id] = empty_metadata
            return empty_metadata
            
        try:
            # Try to get video info from oEmbed API first (no API key needed)
            oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            response = self.session.get(oembed_url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                # oEmbed returns video thumbnail, save it before we overwrite with channel avatar
                video_thumbnail = data.get('thumbnail_url', '')
                
                metadata = {
                    'title': data.get('title', ''),
                    'author_name': data.get('author_name', ''),
                    'thumbnail_url': '',  # Will be set to channel avatar in _fetch_additional_metadata
                    'video_thumbnail_url': video_thumbnail,  # Video thumbnail from oEmbed
                    'date': '',  # oEmbed doesn't provide date
                    'views': '',  # oEmbed doesn't provide views
                    'description': ''
                }
                
                # Try to get additional info from the video page
                self._fetch_additional_metadata(video_id, metadata)
                
                self.cache[video_id] = metadata
                return metadata
                
        except Exception as e:
            print(f"Warning: Could not fetch metadata for video {video_id}: {e}")
            
        # Return empty metadata if fetch fails
        empty_metadata = {
            'title': '',
            'author_name': '',
            'thumbnail_url': '',
            'video_thumbnail_url': '',
            'date': '',
            'views': '',
            'description': ''
        }
        self.cache[video_id] = empty_metadata
        return empty_metadata
    
    def _fetch_additional_metadata(self, video_id: str, metadata: Dict[str, str]):
        """Try to fetch additional metadata from the video page."""
        try:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            response = self.session.get(video_url, timeout=15)
            
            if response.status_code == 200:
                content = response.text
                
                # Extract views using regex - store as actual number
                views_match = re.search(r'"viewCount":"(\d+)"', content)
                if views_match:
                    views = int(views_match.group(1))
                    metadata['views'] = str(views)  # Store as number, not formatted
                
                # Extract publish date
                date_match = re.search(r'"publishDate":"(\d{4}-\d{2}-\d{2})"', content)
                if not date_match:
                    # Try alternative date patterns
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', content)
                    if date_match:
                        date_str = date_match.group(1).split('T')[0]  # Extract just the date part
                    else:
                        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', content)
                        if date_match:
                            date_str = date_match.group(1)
                        else:
                            date_str = None
                else:
                    date_str = date_match.group(1)
                
                if date_str:
                    try:
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        metadata['date'] = date_obj.strftime('%Y-%m-%d')  # Keep ISO format for CSV
                    except ValueError:
                        metadata['date'] = date_str
                
                # Extract channel avatar/icon (keep in thumbnail_url)
                avatar_match = re.search(r'"channelThumbnail":\s*\{\s*"thumbnails":\s*\[.*?"url":\s*"([^"]+)"', content, re.DOTALL)
                if avatar_match:
                    metadata['thumbnail_url'] = avatar_match.group(1)
                
                # Extract video thumbnail/cover image if not already set from oEmbed
                if not metadata.get('video_thumbnail_url'):
                    # Try multiple patterns for video thumbnail
                    video_thumb_patterns = [
                        r'"thumbnail":\s*\{\s*"thumbnails":\s*\[.*?"url":\s*"([^"]+)"',  # Standard thumbnail
                        r'"videoDetails":\s*\{[^}]*"thumbnail":\s*\{\s*"thumbnails":\s*\[.*?"url":\s*"([^"]+)"',  # Video details thumbnail
                        r'"maxresdefault":\s*"([^"]+)"',  # Max resolution thumbnail
                        r'"hqdefault":\s*"([^"]+)"',  # High quality thumbnail
                    ]
                    
                    video_thumbnail = None
                    for pattern in video_thumb_patterns:
                        thumb_match = re.search(pattern, content, re.DOTALL)
                        if thumb_match:
                            video_thumbnail = thumb_match.group(1)
                            break
                    
                    # If not found in page, construct from video ID
                    if not video_thumbnail:
                        video_thumbnail = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
                    
                    metadata['video_thumbnail_url'] = video_thumbnail
                
                # Try to extract description - handle escaped quotes properly
                # Pattern: "shortDescription":"...content..." where content can contain escaped quotes
                # We need to match the full JSON string value, handling escaped quotes
                desc_patterns = [
                    # Try to find shortDescription in JSON structure
                    r'"shortDescription":"((?:[^"\\]|\\.)*)"',
                    # Alternative: look for description in videoPrimaryInfoRenderer
                    r'"description":\s*\{\s*"simpleText":\s*"((?:[^"\\]|\\.)*)"',
                    # Another alternative pattern
                    r'"description":\s*"((?:[^"\\]|\\.)*)"',
                ]
                
                description = ''
                for pattern in desc_patterns:
                    desc_match = re.search(pattern, content, re.DOTALL)
                    if desc_match:
                        description = desc_match.group(1)
                        # Unescape JSON sequences
                        description = description.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
                        # Replace newlines with spaces for CSV (or keep them - CSV can handle them)
                        description = description.replace('\n', ' ').replace('\r', ' ')
                        # Remove extra whitespace
                        description = ' '.join(description.split())
                        if description:
                            break
                
                if description:
                    metadata['description'] = description
                        
        except Exception as e:
            # Silently fail for additional metadata
            pass


class YouTubeCSVUpdater:
    """Updates YouTube CSV file with metadata."""
    
    CSV_COLUMNS = ['youtube_url', 'title', 'author_name', 'thumbnail_url', 'video_thumbnail_url', 'date', 'views', 'description', 'fetch_date', 'z_index', 'language', 'product', 'action_status']
    
    def __init__(self, csv_path: Path, dry_run: bool = False, verbose: bool = False, 
                 offline: bool = False, proxy: str = None, force: bool = False, 
                 skip_existing: bool = False, api_url: str = "http://127.0.0.1:1234/v1/chat/completions"):
        self.csv_path = csv_path
        self.dry_run = dry_run
        self.verbose = verbose
        self.offline = offline
        self.force = force
        self.skip_existing = skip_existing
        self.metadata_fetcher = YouTubeMetadataFetcher(offline_mode=offline, proxy=proxy)
        self.api_url = api_url
        # Initialize language detector if not offline (will be None if API is not available)
        self.language_detector = None
        if not offline:
            try:
                self.language_detector = LanguageDetector(api_url=api_url, verbose=verbose)
                # Test if API is available
                if self.language_detector.model_name is None:
                    self.language_detector = None
            except Exception:
                self.language_detector = None
        
    def normalize_views(self, views_str: str) -> str:
        """Convert formatted view count (e.g., '4.0K', '26.5K', '1.62M') to actual number."""
        if not views_str or not views_str.strip():
            return ''
        
        views_str = views_str.strip().upper()
        
        # If it's already a number, return as is
        if views_str.isdigit():
            return views_str
        
        # Handle K (thousands) and M (millions)
        try:
            if views_str.endswith('K'):
                number = float(views_str[:-1])
                return str(int(number * 1000))
            elif views_str.endswith('M'):
                number = float(views_str[:-1])
                return str(int(number * 1000000))
            elif views_str.endswith('B'):
                number = float(views_str[:-1])
                return str(int(number * 1000000000))
            else:
                # Try to parse as number
                return str(int(float(views_str)))
        except (ValueError, AttributeError):
            # If parsing fails, return original
            return views_str
    
    def read_csv(self) -> List[Dict[str, str]]:
        """Read CSV file and return list of rows."""
        rows = []
        
        if not self.csv_path.exists():
            print(f"Error: CSV file not found: {self.csv_path}")
            return rows
            
        try:
            with open(self.csv_path, 'r', encoding='utf-8-sig') as f:  # utf-8-sig handles BOM
                reader = csv.DictReader(f)
                for row in reader:
                    # Normalize keys (remove BOM if present)
                    normalized_row = {}
                    for key, value in row.items():
                        normalized_key = key.lstrip('\ufeff')  # Remove BOM from key
                        normalized_row[normalized_key] = value
                    
                    # Normalize views column if present
                    if 'views' in normalized_row:
                        normalized_row['views'] = self.normalize_views(normalized_row['views'])
                    
                    # Skip rows where youtube_url is empty or is the header
                    url = normalized_row.get('youtube_url', '').strip()
                    if url and url != 'youtube_url':  # Skip header row if somehow included
                        rows.append(normalized_row)
        except Exception as e:
            print(f"Error reading CSV file: {e}")
            
        return rows
    
    def get_existing_values(self, column: str) -> List[str]:
        """Get unique, non-empty values from a specific column in the CSV."""
        rows = self.read_csv()
        values = set()
        for row in rows:
            value = row.get(column, '').strip()
            if value:
                values.add(value)
        return sorted(list(values))
    
    def write_csv(self, rows: List[Dict[str, str]]):
        """Write rows to CSV file."""
        if self.dry_run:
            print(f"[DRY RUN] Would write {len(rows)} rows to {self.csv_path}")
            return
            
        try:
            # Create backup
            backup_path = self.csv_path.with_suffix('.csv.backup')
            if self.csv_path.exists():
                import shutil
                shutil.copy2(self.csv_path, backup_path)
                if self.verbose:
                    print(f"Created backup: {backup_path}")
            
            # Write CSV (using utf-8-sig to maintain BOM if it existed)
            # Note: Python's csv module automatically handles long descriptions by escaping
            # quotes and special characters, so full descriptions can be stored safely
            
            # Determine all columns: start with standard columns, then add any extra columns from rows
            all_columns = list(self.CSV_COLUMNS)
            for row in rows:
                for key in row.keys():
                    if key not in all_columns:
                        all_columns.append(key)  # Preserve any extra columns (e.g., language, product)
            
            with open(self.csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=all_columns)
                writer.writeheader()
                writer.writerows(rows)
                
            print(f"Updated CSV file: {self.csv_path}")
            
        except Exception as e:
            print(f"Error writing CSV file: {e}")
            raise
    
    def needs_update(self, row: Dict[str, str]) -> bool:
        """Check if a row needs metadata update."""
        url = row.get('youtube_url', '').strip()
        if not url:
            return False
            
        # If force mode, always update
        if self.force:
            return True
            
        # If skip_existing mode, skip rows that have any metadata
        if self.skip_existing:
            has_metadata = any([
                row.get('title', '').strip(),
                row.get('author_name', '').strip(),
                row.get('thumbnail_url', '').strip(),
                row.get('date', '').strip(),
                row.get('views', '').strip()
            ])
            return not has_metadata
            
        # Default: update if missing critical fields (title or author_name)
        missing_critical = not row.get('title', '').strip() or not row.get('author_name', '').strip()
        return missing_critical
    
    def update_row(self, row: Dict[str, str], row_num: int = 0, total_rows: int = 0) -> Tuple[Dict[str, str], bool]:
        """Update a single row with fetched metadata. Returns (updated_row, success)."""
        url = row.get('youtube_url', '').strip()
        if not url:
            return row, False
            
        video_id = self.metadata_fetcher.extract_video_id(url)
        if not video_id:
            print(f"  [{row_num}/{total_rows}] ⚠️  Warning: Could not extract video ID from {url}")
            return row, False
            
        # Show progress
        progress_pct = int((row_num / total_rows) * 100) if total_rows > 0 else 0
        print(f"  [{row_num}/{total_rows}] ({progress_pct}%) Fetching metadata for video {video_id}...", end='', flush=True)
            
        metadata = self.metadata_fetcher.fetch_video_metadata(video_id)
        
        # Check if we got meaningful metadata
        has_title = bool(metadata.get('title', '').strip())
        has_author = bool(metadata.get('author_name', '').strip())
        success = has_title or has_author
        
        # Update row with fetched metadata
        # Only update empty fields unless force mode
        if self.force:
            # Force mode: overwrite all fields
            row['title'] = metadata.get('title', '')
            row['author_name'] = metadata.get('author_name', '')
            row['thumbnail_url'] = metadata.get('thumbnail_url', '')
            row['video_thumbnail_url'] = metadata.get('video_thumbnail_url', '')
            row['date'] = metadata.get('date', '')
            row['views'] = metadata.get('views', '')
            row['description'] = metadata.get('description', '')
        else:
            # Normal mode: only fill empty fields, preserve user edits
            if not row.get('title', '').strip():
                row['title'] = metadata.get('title', '')
            if not row.get('author_name', '').strip():
                row['author_name'] = metadata.get('author_name', '')
            if not row.get('thumbnail_url', '').strip():
                row['thumbnail_url'] = metadata.get('thumbnail_url', '')
            if not row.get('video_thumbnail_url', '').strip():
                row['video_thumbnail_url'] = metadata.get('video_thumbnail_url', '')
            if not row.get('date', '').strip():
                row['date'] = metadata.get('date', '')
            if not row.get('views', '').strip():
                row['views'] = metadata.get('views', '')
            if not row.get('description', '').strip():
                row['description'] = metadata.get('description', '')
        
        # Update fetch_date if we fetched new data
        if metadata.get('title') or metadata.get('author_name'):
            row['fetch_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Show result
        if success:
            title_preview = metadata.get('title', '')[:50] + '...' if len(metadata.get('title', '')) > 50 else metadata.get('title', '')
            desc_len = len(metadata.get('description', ''))
            desc_info = f" (desc: {desc_len} chars)" if desc_len > 0 else ""
            print(f" ✓ {title_preview}{desc_info}")
        else:
            print(f" ✗ Failed to fetch metadata")
        
        return row, success
    
    def update_csv(self):
        """Update CSV file with metadata."""
        print("=" * 60)
        print("YouTube CSV Metadata Updater")
        print("=" * 60)
        
        rows = self.read_csv()
        
        if not rows:
            print("❌ No rows found in CSV file.")
            return
            
        total_rows = len(rows)
        print(f"\n📊 Found {total_rows} rows in CSV file.")
        
        # Count rows that need updating
        rows_to_update = [i for i, row in enumerate(rows) if self.needs_update(row)]
        rows_to_skip = total_rows - len(rows_to_update)
        
        if rows_to_skip > 0:
            print(f"⏭️  {rows_to_skip} rows will be skipped (already have metadata)")
        
        if not rows_to_update:
            print("\n✅ All rows already have metadata. No updates needed.")
            return
        
        print(f"🔄 {len(rows_to_update)} rows will be processed.\n")
        
        updated_count = 0
        skipped_count = 0
        success_count = 0
        failed_count = 0
        
        for idx, i in enumerate(rows_to_update, 1):
            row = rows[i]
            url = row.get('youtube_url', '').strip()
            
            if not url:
                skipped_count += 1
                print(f"  [{idx}/{len(rows_to_update)}] ⚠️  Skipping row {i+1} (no URL)")
                continue
                
            if not self.needs_update(row):
                skipped_count += 1
                if self.verbose:
                    print(f"  [{idx}/{len(rows_to_update)}] ⏭️  Skipping row {i+1} (already has metadata)")
                continue
            
            updated_row, success = self.update_row(row, idx, len(rows_to_update))
            rows[i] = updated_row
            updated_count += 1
            
            if success:
                success_count += 1
            else:
                failed_count += 1
            
            # Add small delay to avoid rate limiting
            if not self.offline:
                time.sleep(0.5)
        
        # Final summary
        print("\n" + "=" * 60)
        print("📈 Summary")
        print("=" * 60)
        print(f"  ✅ Successfully updated: {success_count} rows")
        if failed_count > 0:
            print(f"  ❌ Failed to fetch: {failed_count} rows")
        print(f"  ⏭️  Skipped: {skipped_count} rows")
        print(f"  📝 Total processed: {updated_count} rows")
        print("=" * 60)
        
        if updated_count > 0:
            self.write_csv(rows)
            print(f"\n💾 CSV file updated: {self.csv_path}")
        else:
            print("\n✅ No updates needed.")
    
    def check_duplicates(self):
        """Check for duplicate YouTube URLs in the CSV and report them."""
        print("=" * 60)
        print("Checking for Duplicate YouTube URLs")
        print("=" * 60)
        
        rows = self.read_csv()
        
        if not rows:
            print("❌ No rows found in CSV file.")
            return
        
        # Group rows by normalized URL
        url_groups = {}
        for idx, row in enumerate(rows, start=1):
            url = row.get('youtube_url', '').strip()
            if not url:
                continue
            
            # Normalize URL for comparison
            normalized_url = self.metadata_fetcher.normalize_youtube_url(url)
            if not normalized_url:
                # If normalization fails, use original URL
                normalized_url = url
            
            if normalized_url not in url_groups:
                url_groups[normalized_url] = []
            
            url_groups[normalized_url].append({
                'row_num': idx,
                'url': url,
                'normalized_url': normalized_url,
                'title': row.get('title', '').strip(),
                'author': row.get('author_name', '').strip(),
                'product': row.get('product', '').strip(),
                'language': row.get('language', '').strip(),
                'z_index': row.get('z_index', '').strip()
            })
        
        # Find duplicates
        duplicates = {url: entries for url, entries in url_groups.items() if len(entries) > 1}
        
        if not duplicates:
            print(f"\n✅ No duplicates found in {len(rows)} rows.")
            return
        
        # Report duplicates
        print(f"\n⚠️  Found {len(duplicates)} duplicate video(s) across {sum(len(entries) for entries in duplicates.values())} rows:\n")
        
        for normalized_url, entries in sorted(duplicates.items()):
            print(f"Video: {normalized_url}")
            if entries[0]['title']:
                print(f"  Title: {entries[0]['title']}")
            if entries[0]['author']:
                print(f"  Author: {entries[0]['author']}")
            print(f"  Found in {len(entries)} row(s):")
            
            for entry in entries:
                details = []
                if entry['title']:
                    details.append(f"title: '{entry['title'][:50]}...'" if len(entry['title']) > 50 else f"title: '{entry['title']}'")
                if entry['product']:
                    details.append(f"product: {entry['product']}")
                if entry['language']:
                    details.append(f"language: {entry['language']}")
                if entry['z_index']:
                    details.append(f"z_index: {entry['z_index']}")
                
                detail_str = f" ({', '.join(details)})" if details else ""
                print(f"    - Row {entry['row_num']}: {entry['url']}{detail_str}")
            
            print()
        
        print("=" * 60)
        print(f"Summary: {len(duplicates)} duplicate video(s) found")
        print("=" * 60)
    
    def detect_language_for_row(self, row: Dict[str, str]) -> Optional[str]:
        """Detect language for a specific row using local LLM API. Returns None if API is not available."""
        if not self.language_detector:
            return None
        
        title = row.get('title', '').strip()
        description = row.get('description', '').strip()
        
        if not title and not description:
            return None
        
        try:
            language_code = self.language_detector.detect_language(title, description)
            return language_code
        except Exception:
            # Silently fail if API is not available
            return None
    
    def delete_row(self, row_num: int):
        """Delete a row from the CSV by row number."""
        print("=" * 60)
        print("Delete Row from CSV")
        print("=" * 60)
        
        # Validate row number
        if row_num == 1:
            print("❌ Cannot delete row 1 (CSV header).")
            return False
        
        rows = self.read_csv()
        
        if not rows:
            print("❌ No rows found in CSV file.")
            return False
        
        # Row numbers are 1-indexed (1 = header, 2 = first data row)
        # In our rows list, index 0 = first data row (row 2 in CSV)
        data_row_index = row_num - 2
        
        if data_row_index < 0 or data_row_index >= len(rows):
            print(f"❌ Invalid row number: {row_num}")
            print(f"   Valid row numbers: 2-{len(rows) + 1}")
            return False
        
        # Get row info for confirmation
        row_to_delete = rows[data_row_index]
        url = row_to_delete.get('youtube_url', '').strip()
        title = row_to_delete.get('title', '').strip()
        
        print(f"\nRow {row_num} to delete:")
        if url:
            print(f"  URL: {url}")
        if title:
            print(f"  Title: {title[:80]}..." if len(title) > 80 else f"  Title: {title}")
        if not url and not title:
            print(f"  (Empty row)")
        
        if self.dry_run:
            print("\n[DRY RUN] Would delete this row.")
            return True
        
        # Confirm deletion
        response = input(f"\nAre you sure you want to delete row {row_num}? (yes/no): ").strip().lower()
        if response != 'yes':
            print("Cancelled.")
            return False
        
        # Delete the row
        rows.pop(data_row_index)
        
        # Write back to CSV
        self.write_csv(rows)
        print(f"\n✅ Successfully deleted row {row_num}.")
        return True
    
    def add_new_url_simple(self, url: str):
        """Add a new YouTube URL to the CSV without interactive prompts."""
        # Normalize URL
        normalized_url = self.metadata_fetcher.normalize_youtube_url(url)
        if not normalized_url:
            print(f"❌ Invalid YouTube URL: {url}")
            return False
        
        video_id = self.metadata_fetcher.extract_video_id(normalized_url)
        
        # Check if URL already exists (normalize existing URLs for comparison)
        existing_rows = self.read_csv()
        for row in existing_rows:
            existing_url = row.get('youtube_url', '').strip()
            normalized_existing = self.metadata_fetcher.normalize_youtube_url(existing_url)
            if normalized_existing == normalized_url or existing_url == normalized_url:
                print(f"⚠️  URL already exists in CSV: {normalized_url}")
                return False
        
        # Fetch metadata
        if not self.offline:
            print(f"📥 Fetching metadata for video {video_id}...")
        metadata = self.metadata_fetcher.fetch_video_metadata(video_id)
        
        # Create new row
        new_row = {}
        for col in self.CSV_COLUMNS:
            new_row[col] = ''
        
        # Set URL (normalized)
        new_row['youtube_url'] = normalized_url
        new_row['action_status'] = '0'  # Default to 0
        
        # Set metadata
        new_row['title'] = metadata.get('title', '')
        new_row['author_name'] = metadata.get('author_name', '')
        new_row['thumbnail_url'] = metadata.get('thumbnail_url', '')
        new_row['video_thumbnail_url'] = metadata.get('video_thumbnail_url', '')
        new_row['date'] = metadata.get('date', '')
        new_row['views'] = metadata.get('views', '')
        new_row['description'] = metadata.get('description', '')
        if metadata.get('title') or metadata.get('author_name'):
            new_row['fetch_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Try to detect language if not already set and API is available
        if not new_row.get('language', '').strip() and self.language_detector:
            if self.verbose:
                print("🔍 Detecting language...")
            detected_language = self.detect_language_for_row(new_row)
            if detected_language:
                new_row['language'] = detected_language
                if self.verbose:
                    print(f"  ✓ Detected language: {detected_language}")
            elif self.verbose:
                print("  ⚠️  Could not detect language (API may not be available)")
        
        # Read existing rows and append new one
        existing_rows.append(new_row)
        
        # Write to CSV
        if self.dry_run:
            print(f"\n[DRY RUN] Would add URL: {normalized_url}")
        else:
            self.write_csv(existing_rows)
            print(f"\n✅ Successfully added URL to CSV: {normalized_url}")
            if new_row.get('language'):
                print(f"  Language: {new_row['language']}")
        
        return True
    
    def add_new_url_interactive(self, provided_url: Optional[str] = None):
        """Interactively add a new YouTube URL to the CSV."""
        print("=" * 60)
        print("Add New YouTube URL")
        print("=" * 60)
        
        # Use provided URL or prompt for it
        if provided_url:
            url = provided_url.strip()
            print(f"\nUsing provided URL: {url}")
        else:
            # Prompt for YouTube URL
            while True:
                url = input("\nEnter YouTube URL: ").strip()
                if not url:
                    print("❌ URL cannot be empty. Please try again.")
                    continue
                break
        
        # Normalize URL
        normalized_url = self.metadata_fetcher.normalize_youtube_url(url)
        if not normalized_url:
            print("❌ Invalid YouTube URL. Please enter a valid YouTube URL.")
            return
        
        video_id = self.metadata_fetcher.extract_video_id(normalized_url)
        
        # Check if URL already exists (normalize existing URLs for comparison)
        existing_rows = self.read_csv()
        url_exists = False
        for row in existing_rows:
            existing_url = row.get('youtube_url', '').strip()
            normalized_existing = self.metadata_fetcher.normalize_youtube_url(existing_url)
            if normalized_existing == normalized_url or existing_url == normalized_url:
                url_exists = True
                break
        
        if url_exists:
            print(f"⚠️  This URL already exists in the CSV.")
            if not provided_url:  # Only ask for confirmation if URL was entered interactively
                response = input("Do you want to continue anyway? (y/n): ").strip().lower()
                if response != 'y':
                    print("Cancelled.")
                    return
            else:
                print("Skipping duplicate URL.")
                return
        
        # Prompt for z_index (optional - allow empty)
        # Get max z_index from existing rows
        existing_rows = self.read_csv()
        max_z_index = None
        for row in existing_rows:
            z_val = row.get('z_index', '').strip()
            if z_val:
                try:
                    z_num = int(z_val)
                    if max_z_index is None or z_num > max_z_index:
                        max_z_index = z_num
                except ValueError:
                    pass
        
        prompt_text = "\nEnter z_index (numeric, press Enter to skip): "
        if max_z_index is not None:
            prompt_text = f"\nEnter z_index (numeric, press Enter to skip, current max: {max_z_index}): "
        
        z_index_input = input(prompt_text).strip()
        z_index = ''
        if z_index_input:
            try:
                z_index = str(int(z_index_input))
            except ValueError:
                print("⚠️  Invalid z_index format, leaving blank.")
        
        # Prompt for product (optional)
        existing_products = self.get_existing_values('product')
        product = ''
        if existing_products:
            print("\nProduct options:")
            for idx, prod in enumerate(existing_products, 1):
                print(f"  {idx}. {prod}")
            print(f"  {len(existing_products) + 1}. Enter custom value")
            print(f"  {len(existing_products) + 2}. Skip (leave blank)")
            
            while True:
                product_choice = input(f"\nSelect product (1-{len(existing_products) + 2}, or press Enter to skip): ").strip()
                if not product_choice:
                    break
                try:
                    choice_num = int(product_choice)
                    if 1 <= choice_num <= len(existing_products):
                        product = existing_products[choice_num - 1]
                        break
                    elif choice_num == len(existing_products) + 1:
                        custom_product = input("Enter custom product value (or press Enter to skip): ").strip()
                        if custom_product:
                            product = custom_product
                        break
                    elif choice_num == len(existing_products) + 2:
                        break
                    else:
                        print(f"❌ Invalid choice. Please enter a number between 1 and {len(existing_products) + 2}.")
                except ValueError:
                    print("❌ Invalid input. Please enter a number.")
        
        # Prompt for language (optional)
        existing_languages = self.get_existing_values('language')
        language = ''
        auto_detect_language = False
        
        if existing_languages:
            print("\nLanguage options:")
            for idx, lang in enumerate(existing_languages, 1):
                print(f"  {idx}. {lang}")
            print(f"  {len(existing_languages) + 1}. Enter custom value")
            if self.language_detector:
                print(f"  {len(existing_languages) + 2}. Auto-detect using LLM")
                print(f"  {len(existing_languages) + 3}. Skip (leave blank)")
                max_option = len(existing_languages) + 3
            else:
                print(f"  {len(existing_languages) + 2}. Skip (leave blank)")
                max_option = len(existing_languages) + 2
            
            while True:
                language_choice = input(f"\nSelect language (1-{max_option}, or press Enter to skip): ").strip()
                if not language_choice:
                    break
                try:
                    choice_num = int(language_choice)
                    if 1 <= choice_num <= len(existing_languages):
                        language = existing_languages[choice_num - 1]
                        break
                    elif choice_num == len(existing_languages) + 1:
                        custom_language = input("Enter custom language value (or press Enter to skip): ").strip()
                        if custom_language:
                            language = custom_language
                        break
                    elif choice_num == len(existing_languages) + 2 and self.language_detector:
                        auto_detect_language = True
                        break
                    elif (choice_num == len(existing_languages) + 2 and not self.language_detector) or \
                         (choice_num == len(existing_languages) + 3 and self.language_detector):
                        break
                    else:
                        print(f"❌ Invalid choice. Please enter a number between 1 and {max_option}.")
                except ValueError:
                    print("❌ Invalid input. Please enter a number.")
        
        # Fetch metadata
        print(f"\n📥 Fetching metadata for video {video_id}...")
        metadata = self.metadata_fetcher.fetch_video_metadata(video_id)
        
        # Create new row
        new_row = {}
        for col in self.CSV_COLUMNS:
            new_row[col] = ''
        
        # Set user-provided values (use normalized URL)
        new_row['youtube_url'] = normalized_url
        new_row['z_index'] = z_index
        new_row['product'] = product
        new_row['action_status'] = '0'  # Default to 0
        
        # Set metadata
        new_row['title'] = metadata.get('title', '')
        new_row['author_name'] = metadata.get('author_name', '')
        new_row['thumbnail_url'] = metadata.get('thumbnail_url', '')
        new_row['video_thumbnail_url'] = metadata.get('video_thumbnail_url', '')
        new_row['date'] = metadata.get('date', '')
        new_row['views'] = metadata.get('views', '')
        new_row['description'] = metadata.get('description', '')
        if metadata.get('title') or metadata.get('author_name'):
            new_row['fetch_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Auto-detect language if user selected that option
        if auto_detect_language and self.language_detector:
            print("\n🔍 Detecting language using LLM...")
            detected_language = self.detect_language_for_row(new_row)
            if detected_language:
                language = detected_language
                print(f"  ✓ Detected language: {detected_language}")
            else:
                print("  ⚠️  Could not detect language (API may not be available)")
        
        # Set language (either user-selected or auto-detected)
        new_row['language'] = language
        
        # Read existing rows and append new one
        existing_rows = self.read_csv()
        existing_rows.append(new_row)
        
        # Write to CSV
        if self.dry_run:
            print("\n[DRY RUN] Would add the following row:")
            print(f"  URL: {normalized_url}")
            print(f"  Title: {new_row['title']}")
            print(f"  Author: {new_row['author_name']}")
            print(f"  z_index: {z_index if z_index else '(blank)'}")
            print(f"  Product: {product if product else '(blank)'}")
            print(f"  Language: {language if language else '(blank)'}")
        else:
            self.write_csv(existing_rows)
            print("\n✅ Successfully added new URL to CSV!")
            print(f"  URL: {normalized_url}")
            if new_row['title']:
                print(f"  Title: {new_row['title']}")
            if new_row['author_name']:
                print(f"  Author: {new_row['author_name']}")
            if language:
                print(f"  Language: {language}")


def main():
    parser = argparse.ArgumentParser(
        description='Update src/data/youtube.csv with YouTube video metadata',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update only rows with missing metadata
  python update_youtube_csv.py
  
  # Force update all rows (useful for updating view counts that change over time)
  python update_youtube_csv.py --force
  
  # Force update with VPN
  python update_youtube_csv.py --force --vpn
  
  # Skip rows that already have metadata
  python update_youtube_csv.py --skip-existing
  
  # Dry run to see what would be updated
  python update_youtube_csv.py --dry-run --verbose
  
  # Use VPN proxy
  python update_youtube_csv.py --vpn
  
  # Interactively add a new YouTube URL
  python update_youtube_csv.py --add-url
  
  # Add a new YouTube URL with URL provided (skips URL prompt)
  python update_youtube_csv.py --add-url "https://www.youtube.com/watch?v=VIDEO_ID"
  
  # Add a new YouTube URL without prompts (just the URL)
  python update_youtube_csv.py --add-url-simple "https://www.youtube.com/watch?v=VIDEO_ID"
  
  # Check for duplicate YouTube URLs in the CSV
  python update_youtube_csv.py --check-duplicates
  
  # Delete a row by row number (row 1 is header, cannot be deleted)
  python update_youtube_csv.py --delete-row 5
        """
    )
    parser.add_argument('--csv-path', 
                       help='Path to CSV file (default: src/data/youtube.csv)',
                       type=Path)
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be done without making changes')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Enable verbose output')
    parser.add_argument('--offline', action='store_true', 
                       help='Run in offline mode (no network requests)')
    parser.add_argument('--proxy', 
                       help='HTTP/HTTPS proxy URL (e.g., http://127.0.0.1:1087)')
    parser.add_argument('--vpn', action='store_true',
                       help='Use VPN proxy at http://0.0.0.0:1087')
    parser.add_argument('--force', action='store_true',
                       help='Force update all rows (including those with existing metadata). Useful for updating view counts that change over time.')
    parser.add_argument('--skip-existing', action='store_true',
                       help='Skip rows that already have any metadata')
    parser.add_argument('--add-url', nargs='?', const=None, metavar='URL',
                       help='Interactively add a new YouTube URL to the CSV. If URL is provided, it will be used directly.')
    parser.add_argument('--add-url-simple',
                       help='Add a new YouTube URL to the CSV without interactive prompts (just the URL)',
                       metavar='URL')
    parser.add_argument('--check-duplicates', action='store_true',
                       help='Check for duplicate YouTube URLs in the CSV and report them')
    parser.add_argument('--delete-row', type=int,
                       help='Delete a row from the CSV by row number (row 1 is header, cannot be deleted)',
                       metavar='ROW_NUM')
    parser.add_argument('--api-url',
                       default='http://127.0.0.1:1234/v1/chat/completions',
                       help='LM Studio API URL for language detection (default: http://127.0.0.1:1234/v1/chat/completions)')
    
    args = parser.parse_args()
    
    # Determine CSV path
    if args.csv_path:
        csv_path = Path(args.csv_path)
    else:
        # Default to src/data/youtube.csv (relative to script directory)
        script_dir = Path(__file__).parent
        csv_path = script_dir / "src" / "data" / "youtube.csv"
    
    # Determine proxy settings (priority: --proxy > --vpn > environment variables)
    proxy = args.proxy
    if not proxy and args.vpn:
        proxy = 'http://0.0.0.0:1087'
    if not proxy:
        proxy = os.environ.get('http_proxy') or os.environ.get('https_proxy')
    
    if proxy and not args.offline:
        print(f"Using proxy: {proxy}")
    
    # Validate arguments
    if args.force and args.skip_existing:
        print("Error: --force and --skip-existing cannot be used together")
        sys.exit(1)
    
    if (args.add_url is not None) or args.add_url_simple:
        if args.force:
            print("Error: --add-url/--add-url-simple cannot be used with --force")
            sys.exit(1)
        if args.skip_existing:
            print("Error: --add-url/--add-url-simple cannot be used with --skip-existing")
            sys.exit(1)
    
    if args.check_duplicates and (args.force or args.skip_existing or (args.add_url is not None) or args.add_url_simple):
        print("Error: --check-duplicates cannot be used with other operation flags")
        sys.exit(1)
    
    if args.delete_row and (args.force or args.skip_existing or (args.add_url is not None) or args.add_url_simple or args.check_duplicates):
        print("Error: --delete-row cannot be used with other operation flags")
        sys.exit(1)
    
    updater = YouTubeCSVUpdater(
        csv_path=csv_path,
        dry_run=args.dry_run,
        verbose=args.verbose,
        offline=args.offline,
        proxy=proxy,
        force=args.force,
        skip_existing=args.skip_existing,
        api_url=args.api_url
    )
    
    if args.delete_row:
        updater.delete_row(args.delete_row)
    elif args.check_duplicates:
        updater.check_duplicates()
    elif args.add_url_simple:
        updater.add_new_url_simple(args.add_url_simple)
    elif args.add_url is not None:
        updater.add_new_url_interactive(provided_url=args.add_url)
    else:
        updater.update_csv()


if __name__ == "__main__":
    main()

