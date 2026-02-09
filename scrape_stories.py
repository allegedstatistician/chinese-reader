#!/usr/bin/env python3
"""
Scrape HSK 1-2 graded reader stories from chinesegradedreader.com.
Run once to build stories_bulk.py.
"""

import re
import json
import time
import sys
import urllib.request
from html.parser import HTMLParser

class SimpleHTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip = False
        self.skip_tags = {'script', 'style', 'noscript'}
    
    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.skip = True
        if tag in ('br', 'p', 'div', 'h1', 'h2', 'h3', 'h4', 'li'):
            self.text_parts.append('\n')
    
    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            self.skip = False
        if tag in ('p', 'div', 'h1', 'h2', 'h3', 'h4', 'li'):
            self.text_parts.append('\n')
    
    def handle_data(self, data):
        if not self.skip:
            self.text_parts.append(data)
    
    def get_text(self):
        return ''.join(self.text_parts)


def fetch(url, retries=2):
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; educational-scraper/1.0)'
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
            else:
                print(f"  Failed: {url} - {e}", flush=True)
                return None


def html_to_text(html):
    extractor = SimpleHTMLTextExtractor()
    extractor.feed(html)
    return extractor.get_text()


def is_chinese(char):
    return '\u4e00' <= char <= '\u9fff'


def extract_chinese_lines(text):
    lines = []
    seen = set()
    for line in text.split('\n'):
        line = line.strip()
        line = re.sub(r'\{Play\}', '', line).strip()
        chinese_count = sum(1 for c in line if is_chinese(c))
        if chinese_count >= 3:
            normalized = re.sub(r'\s+', '', line)
            if normalized not in seen:
                seen.add(normalized)
                lines.append(line)
    return lines


def main():
    stories = []
    
    # Get story links from HSK 1 and HSK 2 index pages
    story_urls = []
    for level_url in [
        'https://chinesegradedreader.com/free-hsk-1-graded-reader-stories/',
        'https://chinesegradedreader.com/free-hsk-2-graded-reader-stories/',
    ]:
        print(f"Fetching index: {level_url}", flush=True)
        html = fetch(level_url)
        if not html:
            continue
        links = re.findall(r'href="(https://chinesegradedreader\.com/free-hsk-[12]-graded-reader-stories/[^/"]+/)"', html)
        story_urls.extend(links)
    
    story_urls = list(dict.fromkeys(story_urls))  # dedupe preserving order
    print(f"Found {len(story_urls)} story URLs", flush=True)
    
    for url in story_urls:
        slug = url.split('/')[-2]
        print(f"  Fetching: {slug}", flush=True)
        html = fetch(url)
        if not html:
            continue
        
        # Extract title - try Chinese title from <h1>
        title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else slug
        
        text = html_to_text(html)
        chinese_lines = extract_chinese_lines(text)
        
        if len(chinese_lines) >= 3:
            content = '\n\n'.join(chinese_lines)
            stories.append({'title': title, 'content': content, 'source': 'chinesegradedreader.com'})
            print(f"    ✓ {len(chinese_lines)} lines", flush=True)
        
        time.sleep(0.5)  # Faster but still polite
    
    # Deduplicate by content similarity
    seen_content = set()
    unique = []
    for s in stories:
        key = re.sub(r'\s+', '', s['content'])[:100]
        if key not in seen_content:
            seen_content.add(key)
            unique.append(s)
    
    print(f"\nTotal: {len(unique)} unique stories", flush=True)
    
    # Save as JSON (simpler than Python source)
    outpath = '/home/ubuntu/clawd/chinese-reader/stories_bulk.json'
    with open(outpath, 'w', encoding='utf-8') as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    
    print(f"Saved to {outpath}", flush=True)


if __name__ == '__main__':
    main()
