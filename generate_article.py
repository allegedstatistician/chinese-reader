#!/usr/bin/env python3
"""
Chinese Reader - Daily HSK-level article generator
Generates articles with vocab highlighting and hover translations
"""

import csv
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

# Load HSK vocabulary
def load_hsk_vocab(level=1):
    """Load HSK vocabulary from CSV files"""
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

def load_all_hsk_up_to(level):
    """Load all HSK vocab up to and including the specified level"""
    all_vocab = {}
    for l in range(1, level + 1):
        all_vocab.update(load_hsk_vocab(l))
    return all_vocab

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

# Load extra vocab for unknown word translations
extra_vocab = {}

def segment_chinese(text):
    """
    Simple Chinese text segmentation
    For production, consider jieba or other segmenters
    This does basic character-by-character with known word matching
    """
    # Try to match longer words first
    words = []
    i = 0
    while i < len(text):
        # Try matching 4, 3, 2, 1 character words
        matched = False
        for length in [4, 3, 2]:
            if i + length <= len(text):
                chunk = text[i:i+length]
                if chunk in hsk_vocab or is_chinese_word(chunk):
                    words.append(chunk)
                    i += length
                    matched = True
                    break
        if not matched:
            words.append(text[i])
            i += 1
    return words

def is_chinese_char(char):
    """Check if character is Chinese"""
    return '\u4e00' <= char <= '\u9fff'

def is_chinese_word(word):
    """Check if string is Chinese characters"""
    return all(is_chinese_char(c) for c in word)

def process_text(text, known_vocab):
    """
    Process Chinese text and identify known/unknown words
    Returns list of (word, is_known, pinyin, english) tuples
    """
    result = []
    i = 0
    
    while i < len(text):
        char = text[i]
        
        # Non-Chinese characters pass through
        if not is_chinese_char(char):
            result.append((char, True, '', ''))
            i += 1
            continue
        
        # Try to match longest known word first
        matched = False
        for length in [4, 3, 2, 1]:
            if i + length <= len(text):
                chunk = text[i:i+length]
                if chunk in known_vocab:
                    info = known_vocab[chunk]
                    result.append((chunk, True, info['pinyin'], info['english']))
                    i += length
                    matched = True
                    break
        
        if not matched:
            # Unknown word - check extra vocab for translation
            # Try multi-char matches in extra vocab
            found_extra = False
            for length in [4, 3, 2]:
                if i + length <= len(text):
                    chunk = text[i:i+length]
                    if chunk in extra_vocab:
                        info = extra_vocab[chunk]
                        result.append((chunk, False, info['pinyin'], info['english']))
                        i += length
                        found_extra = True
                        break
            
            if not found_extra:
                # Single character unknown
                if char in extra_vocab:
                    info = extra_vocab[char]
                    result.append((char, False, info['pinyin'], info['english']))
                else:
                    result.append((char, False, '?', '?'))
                i += 1
    
    return result

def generate_html(title, processed_text, date_str):
    """Generate HTML with hover tooltips"""
    
    html_content = []
    for word, is_known, pinyin, english in processed_text:
        if not is_chinese_char(word[0]) if word else True:
            # Non-Chinese, pass through
            if word == '\n':
                html_content.append('<br>')
            else:
                html_content.append(word)
        elif is_known:
            # Known HSK word - subtle styling, still has tooltip
            html_content.append(
                f'<span class="known" data-pinyin="{pinyin}" data-english="{english}">{word}</span>'
            )
        else:
            # Unknown word - highlighted
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
    <style>
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 2;
            font-size: 22px;
            background: #fafafa;
            color: #333;
        }}
        h1 {{
            font-size: 28px;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }}
        .date {{
            color: #666;
            font-size: 14px;
            margin-bottom: 20px;
        }}
        .content {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .known {{
            cursor: help;
        }}
        .unknown {{
            background: #fff3cd;
            border-bottom: 2px solid #ffc107;
            cursor: help;
            padding: 0 2px;
            border-radius: 2px;
        }}
        .tooltip {{
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
        }}
        .tooltip .pinyin {{
            color: #4CAF50;
            font-weight: bold;
        }}
        .tooltip .english {{
            color: #aaa;
            font-style: italic;
        }}
        .legend {{
            margin-top: 30px;
            padding: 15px;
            background: #f5f5f5;
            border-radius: 6px;
            font-size: 14px;
        }}
        .legend-item {{
            display: inline-block;
            margin-right: 20px;
        }}
        .legend-known {{
            color: #333;
        }}
        .legend-unknown {{
            background: #fff3cd;
            border-bottom: 2px solid #ffc107;
            padding: 0 4px;
        }}
        .stats {{
            margin-top: 20px;
            font-size: 14px;
            color: #666;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div class="date">{date_str} | HSK Level 1</div>
    
    <div class="content">
        {body_html}
    </div>
    
    <div class="legend">
        <span class="legend-item"><span class="legend-unknown">黄色高亮</span> = 超出HSK 1词汇 (hover查看释义)</span>
        <span class="legend-item"><span class="legend-known">普通文字</span> = HSK 1词汇</span>
    </div>
    
    <div id="tooltip" class="tooltip" style="display: none;"></div>
    
    <script>
        const tooltip = document.getElementById('tooltip');
        
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

# Sample stories for HSK 1 level
SAMPLE_STORIES = [
    {
        "title": "我的一天",
        "content": """今天是星期一。我早上六点起床。

我先喝茶，然后吃饭。我吃米饭和菜。

八点我去学校。我坐出租车去。

在学校，我学习中文。老师很好。我们看书，写字。

中午十二点，我和朋友吃饭。我们去饭店。我喜欢吃中国菜。

下午我在学校读书。五点我回家。

晚上我看电视。我喜欢看电影。

十点我睡觉。今天很好！"""
    },
    {
        "title": "我的家",
        "content": """我家有五个人：爸爸、妈妈、哥哥、妹妹和我。

爸爸四十五岁。他工作很忙。他喜欢喝茶。

妈妈四十三岁。她做饭很好吃。她喜欢买东西。

哥哥二十岁。他是大学生。他喜欢打电话。

妹妹十五岁。她是中学生。她喜欢看书。

我们家有一只狗。狗的名字叫小白。它很可爱。

星期天，我们一起吃饭，看电视。我爱我的家。"""
    },
    {
        "title": "去商店",
        "content": """今天是星期六。我和妈妈去商店买东西。

商店很大。里面有很多人。

我想买一本书。那本书很好看。

妈妈想买水果。苹果三块钱一斤。妈妈买了五斤。

我们也买了一些茶。爸爸很喜欢喝茶。

在商店，我看见一只小猫。它很可爱！

我们买了很多东西。我们很高兴。

下午我们回家。妈妈做饭，我看书。今天很好！"""
    }
]

def get_story_for_date(date):
    """Get a story based on the date (cycles through available stories)"""
    day_of_year = date.timetuple().tm_yday
    return SAMPLE_STORIES[day_of_year % len(SAMPLE_STORIES)]

# Initialize vocab
hsk_vocab = load_hsk_vocab(1)
extra_vocab = load_extra_vocab()

def main():
    """Generate today's article"""
    today = datetime.now()
    date_str = today.strftime("%Y年%m月%d日")
    
    # Get today's story
    story = get_story_for_date(today)
    
    # Process the text
    processed = process_text(story['content'], hsk_vocab)
    
    # Count stats
    total_chars = sum(1 for w, _, _, _ in processed if w and is_chinese_char(w[0]))
    known_chars = sum(1 for w, known, _, _ in processed if w and known and is_chinese_char(w[0]))
    
    # Generate HTML
    html = generate_html(story['title'], processed, date_str)
    
    # Save to file
    output_dir = Path(__file__).parent / "docs"
    output_dir.mkdir(exist_ok=True)
    
    # Save as index.html (always latest)
    with open(output_dir / "index.html", 'w', encoding='utf-8') as f:
        f.write(html)
    
    # Also save dated version
    dated_filename = today.strftime("%Y-%m-%d") + ".html"
    with open(output_dir / dated_filename, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"Generated: {story['title']}")
    print(f"Stats: {known_chars}/{total_chars} characters are HSK 1 vocab")
    print(f"Saved to: {output_dir / 'index.html'}")
    
    return output_dir / "index.html"

if __name__ == "__main__":
    main()
