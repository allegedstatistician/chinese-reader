#!/usr/bin/env python3
"""
Chinese Reader - Daily HSK-level article generator
Generates articles with vocab highlighting and hover translations
"""

import csv
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

def is_chinese_char(char):
    """Check if character is in CJK Unified Ideographs range"""
    return '\u4e00' <= char <= '\u9fff'

def validate_vocab_entry(chinese, pinyin, english, source_file="", line_num=0):
    """
    Validate a vocab entry. Returns (is_valid, errors) tuple.
    Checks:
    - Chinese field contains at least one Chinese character
    - Pinyin is not empty or '?'
    - English is not empty or '?'
    """
    errors = []
    
    # Check Chinese field
    if not chinese or not chinese.strip():
        errors.append("Empty Chinese field")
    elif not any(is_chinese_char(c) for c in chinese):
        errors.append(f"No Chinese characters found in '{chinese}'")
    
    # Check pinyin field
    if not pinyin or not pinyin.strip():
        errors.append("Empty pinyin field")
    elif pinyin.strip() == '?':
        errors.append("Pinyin is '?' (placeholder)")
    
    # Check english field
    if not english or not english.strip():
        errors.append("Empty English field")
    elif english.strip() == '?':
        errors.append("English is '?' (placeholder)")
    
    is_valid = len(errors) == 0
    if errors and source_file:
        errors = [f"{source_file}:{line_num}: {e}" for e in errors]
    
    return is_valid, errors

def validate_vocab_file(csv_path):
    """Validate all entries in a vocab CSV file. Returns (valid_count, error_list)."""
    errors = []
    valid_count = 0
    
    if not csv_path.exists():
        return 0, [f"{csv_path}: File not found"]
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for line_num, row in enumerate(reader, 1):
            if len(row) < 3:
                if row and any(r.strip() for r in row):  # Skip empty lines
                    errors.append(f"{csv_path.name}:{line_num}: Incomplete row (need 3 columns): {row}")
                continue
            
            chinese, pinyin, english = row[0], row[1], row[2]
            is_valid, entry_errors = validate_vocab_entry(
                chinese, pinyin, english, 
                source_file=csv_path.name, line_num=line_num
            )
            
            if is_valid:
                valid_count += 1
            else:
                errors.extend(entry_errors)
    
    return valid_count, errors

def validate_all_vocab(verbose=True):
    """
    Validate all vocab files. Returns True if all valid, False otherwise.
    This is the main validation hook for pre-generation checks.
    """
    base_path = Path(__file__).parent
    vocab_files = [
        base_path / "vocab_main.csv",
        base_path / "extra_vocab.csv",
        base_path / "hsk1.csv",
    ]
    
    all_valid = True
    total_valid = 0
    all_errors = []
    
    for vocab_file in vocab_files:
        if vocab_file.exists():
            valid_count, errors = validate_vocab_file(vocab_file)
            total_valid += valid_count
            if errors:
                all_valid = False
                all_errors.extend(errors)
            if verbose:
                status = "✓" if not errors else "✗"
                print(f"{status} {vocab_file.name}: {valid_count} valid entries, {len(errors)} errors")
    
    if all_errors and verbose:
        print(f"\n❌ VALIDATION ERRORS ({len(all_errors)} total):")
        for err in all_errors[:20]:  # Limit output
            print(f"  {err}")
        if len(all_errors) > 20:
            print(f"  ... and {len(all_errors) - 20} more errors")
    elif verbose:
        print(f"\n✅ All vocab validated: {total_valid} total entries")
    
    return all_valid

def load_main_vocab():
    """Load main vocabulary (frequency-based 300 chars + HSK1 + curated additions)"""
    vocab = {}
    csv_path = Path(__file__).parent / "vocab_main.csv"
    
    if csv_path.exists():
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 3:
                    chinese, pinyin, english = row[0], row[1], row[2]
                    vocab[chinese] = {'pinyin': pinyin, 'english': english}
    return vocab

def load_hsk_vocab(level=1):
    """Load HSK vocabulary from CSV files (legacy, kept for compatibility)"""
    vocab = {}
    csv_path = Path(__file__).parent / f"hsk{level}.csv"
    
    if csv_path.exists():
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 3:
                    chinese, pinyin, english = row[0], row[1], row[2]
                    vocab[chinese] = {'pinyin': pinyin, 'english': english}
    return vocab

def load_extra_vocab():
    """Load extra vocabulary for translations of unknown words"""
    vocab = {}
    csv_path = Path(__file__).parent / "extra_vocab.csv"
    
    if csv_path.exists():
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 3:
                    chinese, pinyin, english = row[0], row[1], row[2]
                    vocab[chinese] = {'pinyin': pinyin, 'english': english}
    return vocab

def process_text(text, known_vocab, extra_vocab):
    """
    Process Chinese text - check BOTH vocabs together, prioritizing longer matches.
    This prevents issues like "里面" being split into "里" (HSK1) + "面" (unknown).
    """
    result = []
    i = 0
    
    while i < len(text):
        char = text[i]
        
        if not is_chinese_char(char):
            result.append((char, True, '', ''))
            i += 1
            continue
        
        # Try to find the longest match from EITHER vocab
        best_match = None
        best_length = 0
        best_is_known = False
        
        for length in [4, 3, 2, 1]:
            if i + length <= len(text):
                chunk = text[i:i+length]
                # Check both vocabs, prefer known (HSK) for same length
                if chunk in known_vocab and length > best_length:
                    best_match = chunk
                    best_length = length
                    best_is_known = True
                elif chunk in extra_vocab and length > best_length:
                    best_match = chunk
                    best_length = length
                    best_is_known = False
        
        if best_match:
            if best_is_known:
                info = known_vocab[best_match]
                result.append((best_match, True, info['pinyin'], info['english']))
            else:
                info = extra_vocab[best_match]
                result.append((best_match, False, info['pinyin'], info['english']))
            i += best_length
        else:
            # No match found - log unknown character for review
            unknown_chars.add(char)
            result.append((char, False, '?', '?'))
            i += 1
    
    return result

# Track unknown characters globally for reporting
unknown_chars = set()

def build_sidebar_html(articles, current_date=None):
    """Build sidebar HTML organized by month"""
    # Group by year-month
    by_month = defaultdict(list)
    for art in articles:
        ym = art['date'][:7]  # YYYY-MM
        by_month[ym].append(art)
    
    sidebar_items = []
    for ym in sorted(by_month.keys(), reverse=True):
        month_articles = sorted(by_month[ym], key=lambda x: x['date'], reverse=True)
        dt = datetime.strptime(ym, "%Y-%m")
        month_label = dt.strftime("%B %Y")
        
        article_links = []
        for art in month_articles:
            is_current = art['date'] == current_date
            current_class = ' class="current"' if is_current else ''
            article_links.append(
                f'<li data-date="{art["date"]}"{current_class}>'
                f'<span class="check">○</span>'
                f'<a href="{art["date"]}.html">{art["title"]}</a></li>'
            )
        
        sidebar_items.append(f'''
        <div class="month-group">
            <div class="month-header">{month_label}</div>
            <ul>{"".join(article_links)}</ul>
        </div>''')
    
    return ''.join(sidebar_items)

def get_common_styles():
    return '''
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
            background: #fafafa;
            color: #333;
            display: flex;
            min-height: 100vh;
        }
        
        /* Sidebar */
        .sidebar {
            width: 280px;
            background: #fff;
            border-right: 1px solid #e0e0e0;
            padding: 20px;
            overflow-y: auto;
            position: fixed;
            height: 100vh;
        }
        .sidebar h2 {
            font-size: 18px;
            margin-bottom: 5px;
            color: #4CAF50;
        }
        .sidebar .stats {
            font-size: 12px;
            color: #666;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid #eee;
        }
        .month-group { margin-bottom: 20px; }
        .month-header {
            font-size: 13px;
            font-weight: bold;
            color: #666;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .sidebar ul { list-style: none; }
        .sidebar li {
            display: flex;
            align-items: center;
            padding: 6px 8px;
            border-radius: 4px;
            margin-bottom: 2px;
            transition: background 0.2s;
        }
        .sidebar li:hover { background: #f5f5f5; }
        .sidebar li.current { background: #e8f5e9; }
        .sidebar li.read { opacity: 0.6; }
        .sidebar li.read .check { color: #4CAF50; }
        .sidebar .check {
            font-size: 14px;
            margin-right: 8px;
            color: #ccc;
            flex-shrink: 0;
        }
        .sidebar a {
            color: #333;
            text-decoration: none;
            font-size: 14px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .sidebar a:hover { color: #4CAF50; }
        
        /* Main content */
        .main {
            margin-left: 280px;
            flex: 1;
            padding: 40px;
            max-width: 900px;
        }
        h1 {
            font-size: 32px;
            margin-bottom: 10px;
        }
        .date {
            color: #666;
            font-size: 14px;
            margin-bottom: 30px;
        }
        .content {
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            line-height: 2.2;
            font-size: 24px;
        }
        .known { cursor: help; }
        .unknown {
            background: #fff3cd;
            border-bottom: 2px solid #ffc107;
            cursor: help;
            padding: 0 2px;
            border-radius: 2px;
        }
        
        /* Tooltip */
        .tooltip {
            position: fixed;
            background: #333;
            color: white;
            padding: 10px 15px;
            border-radius: 6px;
            font-size: 16px;
            z-index: 1000;
            pointer-events: none;
            max-width: 300px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .tooltip .pinyin { color: #4CAF50; font-weight: bold; }
        .tooltip .english { color: #aaa; font-style: italic; }
        
        /* Read button */
        .actions { margin-top: 30px; }
        .read-btn {
            display: inline-block;
            padding: 10px 20px;
            font-size: 14px;
            cursor: pointer;
            border: none;
            border-radius: 6px;
            transition: all 0.2s;
        }
        .read-btn.unread {
            background: #4CAF50;
            color: white;
        }
        .read-btn.unread:hover { background: #45a049; }
        .read-btn.done {
            background: #e8f5e9;
            color: #4CAF50;
            border: 2px solid #4CAF50;
        }
        
        /* Legend */
        .legend {
            margin-top: 30px;
            padding: 15px;
            background: #f5f5f5;
            border-radius: 6px;
            font-size: 13px;
            color: #666;
        }
        .legend-unknown {
            background: #fff3cd;
            border-bottom: 2px solid #ffc107;
            padding: 0 4px;
        }
        
        /* Mobile */
        @media (max-width: 768px) {
            .sidebar {
                position: relative;
                width: 100%;
                height: auto;
                border-right: none;
                border-bottom: 1px solid #e0e0e0;
            }
            .main {
                margin-left: 0;
                padding: 20px;
            }
            body { flex-direction: column; }
        }
    '''

def get_common_js():
    return '''
        function getReadArticles() {
            return JSON.parse(localStorage.getItem('chineseReaderRead') || '[]');
        }
        function saveReadArticles(articles) {
            localStorage.setItem('chineseReaderRead', JSON.stringify(articles));
        }
        function updateSidebar() {
            const read = getReadArticles();
            let readCount = 0;
            document.querySelectorAll('.sidebar li').forEach(li => {
                const date = li.dataset.date;
                const check = li.querySelector('.check');
                if (read.includes(date)) {
                    li.classList.add('read');
                    check.textContent = '✓';
                    readCount++;
                } else {
                    li.classList.remove('read');
                    check.textContent = '○';
                }
            });
            const stats = document.querySelector('.sidebar .stats');
            const total = document.querySelectorAll('.sidebar li').length;
            if (stats) stats.textContent = `${readCount} / ${total} articles read`;
        }
    '''

def generate_article_html(title, processed_text, date_str, date_key, sidebar_html):
    """Generate HTML with sidebar and hover tooltips"""
    
    html_content = []
    for word, is_known, pinyin, english in processed_text:
        if not is_chinese_char(word[0]) if word else True:
            if word == '\n':
                html_content.append('<br>')
            else:
                html_content.append(word)
        elif is_known:
            html_content.append(
                f'<span class="known" data-pinyin="{pinyin}" data-english="{english}">{word}</span>'
            )
        else:
            html_content.append(
                f'<span class="unknown" data-pinyin="{pinyin}" data-english="{english}">{word}</span>'
            )
    
    body_html = ''.join(html_content)
    
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Chinese Reader</title>
    <style>{get_common_styles()}</style>
</head>
<body>
    <nav class="sidebar">
        <h2>📚 Chinese Reader</h2>
        <div class="stats">Loading...</div>
        {sidebar_html}
    </nav>
    
    <main class="main">
        <h1>{title}</h1>
        <div class="date">{date_str} · Level 1 · 300 chars</div>
        
        <div class="content">{body_html}</div>
        
        <div class="actions">
            <button id="readBtn" class="read-btn unread" onclick="toggleRead()">
                ✓ Mark as Read
            </button>
        </div>
        
        <div class="legend">
            <span class="legend-unknown">Highlighted</span> = Beyond HSK 1 (hover for pinyin + translation)
        </div>
    </main>
    
    <div id="tooltip" class="tooltip" style="display: none;"></div>
    
    <script>
        const DATE_KEY = '{date_key}';
        const tooltip = document.getElementById('tooltip');
        const readBtn = document.getElementById('readBtn');
        
        {get_common_js()}
        
        function isRead() {{
            return getReadArticles().includes(DATE_KEY);
        }}
        
        function updateButton() {{
            if (isRead()) {{
                readBtn.textContent = '✓ Read';
                readBtn.className = 'read-btn done';
            }} else {{
                readBtn.textContent = '✓ Mark as Read';
                readBtn.className = 'read-btn unread';
            }}
        }}
        
        function toggleRead() {{
            const articles = getReadArticles();
            if (isRead()) {{
                const idx = articles.indexOf(DATE_KEY);
                articles.splice(idx, 1);
            }} else {{
                articles.push(DATE_KEY);
            }}
            saveReadArticles(articles);
            updateButton();
            updateSidebar();
        }}
        
        updateButton();
        updateSidebar();
        
        document.querySelectorAll('.known, .unknown').forEach(el => {{
            el.addEventListener('mouseenter', (e) => {{
                const pinyin = e.target.dataset.pinyin;
                const english = e.target.dataset.english;
                if (pinyin && english) {{
                    tooltip.innerHTML = `<span class="pinyin">${{pinyin}}</span><br><span class="english">${{english}}</span>`;
                    tooltip.style.display = 'block';
                }}
            }});
            el.addEventListener('mousemove', (e) => {{
                tooltip.style.left = (e.clientX + 15) + 'px';
                tooltip.style.top = (e.clientY + 15) + 'px';
            }});
            el.addEventListener('mouseleave', () => {{
                tooltip.style.display = 'none';
            }});
        }});
    </script>
</body>
</html>'''

def generate_index_html(sidebar_html, latest_article):
    """Generate index that redirects to latest or shows welcome"""
    
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chinese Reader</title>
    <meta http-equiv="refresh" content="0; url={latest_article}.html">
    <style>{get_common_styles()}</style>
</head>
<body>
    <nav class="sidebar">
        <h2>📚 Chinese Reader</h2>
        <div class="stats">Loading...</div>
        {sidebar_html}
    </nav>
    <main class="main">
        <h1>Welcome</h1>
        <p>Redirecting to the latest article...</p>
        <p><a href="{latest_article}.html">Click here if not redirected</a></p>
    </main>
    <script>
        {get_common_js()}
        updateSidebar();
    </script>
</body>
</html>'''

def _load_stories():
    """Load stories from stories_bulk.json"""
    stories_path = Path(__file__).parent / "stories_bulk.json"
    if stories_path.exists():
        with open(stories_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    # Fallback: minimal default
    return [{"title": "你好", "content": "你好！我是学生。我喜欢学习中文。"}]

SAMPLE_STORIES = _load_stories()

def get_story_for_date(date):
    day_of_year = date.timetuple().tm_yday
    return SAMPLE_STORIES[day_of_year % len(SAMPLE_STORIES)]

# Load main vocabulary (417 characters: top 300 frequency + HSK1 + curated)
main_vocab = load_main_vocab()
extra_vocab = load_extra_vocab()

# Legacy alias for compatibility
hsk_vocab = main_vocab

def main():
    """Generate today's article and rebuild all pages with updated sidebar"""
    global unknown_chars
    unknown_chars = set()  # Reset for this run
    
    today = datetime.now()
    date_str = today.strftime("%B %d, %Y")
    date_key = today.strftime("%Y-%m-%d")
    
    output_dir = Path(__file__).parent / "docs"
    output_dir.mkdir(exist_ok=True)
    
    # Get today's story
    story = get_story_for_date(today)
    processed = process_text(story['content'], hsk_vocab, extra_vocab)
    
    # Build article list from existing HTML files + today
    articles = []
    for html_file in output_dir.glob("????-??-??.html"):
        date = html_file.stem
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()
            title_match = re.search(r'<h1>(.+?)</h1>', content)
            title = title_match.group(1) if title_match else date
        articles.append({'date': date, 'title': title})
    
    # Add today if not already there
    if not any(a['date'] == date_key for a in articles):
        articles.append({'date': date_key, 'title': story['title']})
    else:
        # Update title for today
        for a in articles:
            if a['date'] == date_key:
                a['title'] = story['title']
    
    # Build sidebar
    sidebar_html = build_sidebar_html(articles, date_key)
    
    # Generate today's article
    html = generate_article_html(story['title'], processed, date_str, date_key, sidebar_html)
    with open(output_dir / f"{date_key}.html", 'w', encoding='utf-8') as f:
        f.write(html)
    
    # Regenerate all other articles with updated sidebar
    for art in articles:
        if art['date'] == date_key:
            continue
        
        html_path = output_dir / f"{art['date']}.html"
        if html_path.exists():
            # Read existing content and extract the article body
            with open(html_path, 'r', encoding='utf-8') as f:
                old_html = f.read()
            
            # Extract title, date display, and content
            title = art['title']
            dt = datetime.strptime(art['date'], "%Y-%m-%d")
            art_date_str = dt.strftime("%B %d, %Y")
            
            content_match = re.search(r'<div class="content">(.+?)</div>\s*<div class="actions">', old_html, re.DOTALL)
            if content_match:
                body_html = content_match.group(1).strip()
                
                # Build sidebar for this article
                art_sidebar = build_sidebar_html(articles, art['date'])
                
                new_html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Chinese Reader</title>
    <style>{get_common_styles()}</style>
</head>
<body>
    <nav class="sidebar">
        <h2>📚 Chinese Reader</h2>
        <div class="stats">Loading...</div>
        {art_sidebar}
    </nav>
    
    <main class="main">
        <h1>{title}</h1>
        <div class="date">{art_date_str} · Level 1 · 300 chars</div>
        
        <div class="content">{body_html}</div>
        
        <div class="actions">
            <button id="readBtn" class="read-btn unread" onclick="toggleRead()">
                ✓ Mark as Read
            </button>
        </div>
        
        <div class="legend">
            <span class="legend-unknown">Highlighted</span> = Beyond HSK 1 (hover for pinyin + translation)
        </div>
    </main>
    
    <div id="tooltip" class="tooltip" style="display: none;"></div>
    
    <script>
        const DATE_KEY = '{art["date"]}';
        const tooltip = document.getElementById('tooltip');
        const readBtn = document.getElementById('readBtn');
        
        {get_common_js()}
        
        function isRead() {{
            return getReadArticles().includes(DATE_KEY);
        }}
        
        function updateButton() {{
            if (isRead()) {{
                readBtn.textContent = '✓ Read';
                readBtn.className = 'read-btn done';
            }} else {{
                readBtn.textContent = '✓ Mark as Read';
                readBtn.className = 'read-btn unread';
            }}
        }}
        
        function toggleRead() {{
            const articles = getReadArticles();
            if (isRead()) {{
                const idx = articles.indexOf(DATE_KEY);
                articles.splice(idx, 1);
            }} else {{
                articles.push(DATE_KEY);
            }}
            saveReadArticles(articles);
            updateButton();
            updateSidebar();
        }}
        
        updateButton();
        updateSidebar();
        
        document.querySelectorAll('.known, .unknown').forEach(el => {{
            el.addEventListener('mouseenter', (e) => {{
                const pinyin = e.target.dataset.pinyin;
                const english = e.target.dataset.english;
                if (pinyin && english) {{
                    tooltip.innerHTML = `<span class="pinyin">${{pinyin}}</span><br><span class="english">${{english}}</span>`;
                    tooltip.style.display = 'block';
                }}
            }});
            el.addEventListener('mousemove', (e) => {{
                tooltip.style.left = (e.clientX + 15) + 'px';
                tooltip.style.top = (e.clientY + 15) + 'px';
            }});
            el.addEventListener('mouseleave', () => {{
                tooltip.style.display = 'none';
            }});
        }});
    </script>
</body>
</html>'''
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(new_html)
    
    # Generate index (redirects to latest)
    latest = max(articles, key=lambda x: x['date'])
    index_html = generate_index_html(build_sidebar_html(articles), latest['date'])
    with open(output_dir / "index.html", 'w', encoding='utf-8') as f:
        f.write(index_html)
    
    total_chars = sum(1 for w, _, _, _ in processed if w and is_chinese_char(w[0]))
    known_chars = sum(1 for w, known, _, _ in processed if w and known and is_chinese_char(w[0]))
    
    print(f"Generated: {story['title']}")
    print(f"Stats: {known_chars}/{total_chars} characters in main vocab")
    print(f"Articles: {len(articles)}")
    
    # Report any unknown characters that need to be added to vocab
    if unknown_chars:
        print(f"\n⚠️  UNKNOWN CHARACTERS FOUND: {', '.join(sorted(unknown_chars))}")
        print("Add these to extra_vocab.csv to fix '?' tooltips")
    
    return date_key

if __name__ == "__main__":
    # CLI argument handling
    if len(sys.argv) > 1:
        if sys.argv[1] in ('--validate', '-v', 'validate'):
            # Run validation only
            success = validate_all_vocab(verbose=True)
            sys.exit(0 if success else 1)
        elif sys.argv[1] in ('--help', '-h', 'help'):
            print("Usage: python generate_article.py [command]")
            print("")
            print("Commands:")
            print("  (none)      Generate today's article")
            print("  validate    Validate all vocab files only (no generation)")
            print("  --help      Show this help message")
            sys.exit(0)
        else:
            print(f"Unknown argument: {sys.argv[1]}")
            print("Use --help for usage information")
            sys.exit(1)
    
    # Default: validate first, then generate
    print("=== Pre-generation vocab validation ===")
    if not validate_all_vocab(verbose=True):
        print("\n❌ Vocab validation failed! Fix errors before generating.")
        print("Run 'python generate_article.py validate' to check vocab files")
        sys.exit(1)
    print("")
    
    main()
