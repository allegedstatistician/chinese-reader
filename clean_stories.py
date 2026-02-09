#!/usr/bin/env python3
"""Clean scraped stories: extract only Chinese text, remove English/pinyin/descriptions."""

import json
import re

def is_chinese(char):
    return '\u4e00' <= char <= '\u9fff'

def chinese_ratio(text):
    """What fraction of non-whitespace chars are Chinese?"""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0
    return sum(1 for c in chars if is_chinese(c)) / len(chars)

def clean_story(story):
    """Extract only the Chinese dialogue/narrative lines from a story."""
    lines = story['content'].split('\n')
    chinese_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Skip lines that are mostly English/pinyin
        ratio = chinese_ratio(line)
        if ratio < 0.3:
            continue
        
        # Remove {Play} markers
        line = re.sub(r'\{Play\}', '', line).strip()
        
        # Skip navigation artifacts: "Title (中文)" patterns from site nav
        if re.match(r'^[A-Z].*\(.*[\u4e00-\u9fff].*\)$', line):
            continue
        # Skip lines with 3+ consecutive English words (nav links)
        if re.search(r'[A-Za-z]{2,}\s+[A-Za-z]{2,}\s+[A-Za-z]{2,}', line):
            continue
        # Skip "Chinese" word artifacts
        line = re.sub(r'Chinese', '', line).strip()
        
        if line.startswith('HSK') or 'graded reader' in line.lower():
            continue
        
        if line:
            chinese_lines.append(line)
    
    if len(chinese_lines) < 3:
        return None
    
    # Deduplicate consecutive identical lines
    deduped = [chinese_lines[0]]
    for line in chinese_lines[1:]:
        if line != deduped[-1]:
            deduped.append(line)
    
    # Build clean content
    content = '\n\n'.join(deduped)
    
    # Extract Chinese title if possible
    title = story['title']
    # Try to get the Chinese part from titles like "Thank You (谢谢 你)"
    chinese_match = re.search(r'[（(]([^）)]*[\u4e00-\u9fff]+[^）)]*)[）)]', title)
    if chinese_match:
        title = chinese_match.group(1).strip()
    elif not any(is_chinese(c) for c in title):
        # No Chinese in title, use first line as title
        if deduped:
            title = deduped[0][:20]
    
    return {
        'title': title,
        'content': content
    }


def main():
    with open('/home/ubuntu/clawd/chinese-reader/stories_bulk.json') as f:
        raw = json.load(f)
    
    # Load original sample stories from generate_article.py
    import importlib.util
    spec = importlib.util.spec_from_file_location("gen", "/home/ubuntu/clawd/chinese-reader/generate_article.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    originals = gen.SAMPLE_STORIES
    
    cleaned = []
    skipped = 0
    
    # Clean scraped stories
    for story in raw:
        result = clean_story(story)
        if result and len(result['content']) >= 50:
            cleaned.append(result)
        else:
            skipped += 1
    
    # Add originals (already clean)
    cleaned.extend(originals)
    
    # Final dedup by content start
    seen = set()
    final = []
    for s in cleaned:
        key = re.sub(r'\s+', '', s['content'])[:80]
        if key not in seen:
            seen.add(key)
            final.append(s)
    
    print(f"Cleaned: {len(final)} stories (skipped {skipped} too short)")
    
    # Save
    with open('/home/ubuntu/clawd/chinese-reader/stories_bulk.json', 'w', encoding='utf-8') as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    
    # Show sample
    for s in final[:3]:
        print(f"\n--- {s['title']} ---")
        print(s['content'][:150] + '...')
    
    print(f"\nSaved {len(final)} stories")


if __name__ == '__main__':
    main()
