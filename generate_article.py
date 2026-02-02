#!/usr/bin/env python3
"""
Chinese Reader - Daily HSK-level article generator
Generates articles with vocab highlighting and hover translations
"""

import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict

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

def is_chinese_char(char):
    return '\u4e00' <= char <= '\u9fff'

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

SAMPLE_STORIES = [
    {"title": "小明的问题", "content": """小明是一个学生。他十二岁，在中学读书。

小明有一个问题。他不知道自己以后想做什么工作。他的朋友们都知道，但是他不知道。

有一天，小明问他的爸爸："爸爸，你小时候想做什么？"

爸爸说："我小时候想当老师。"

"为什么？"小明问。

"因为我喜欢和人说话，喜欢学习新的东西。"爸爸说。

小明又问妈妈同样的问题。妈妈说她小时候想当医生，因为她想帮助别人。

小明想了很多天。他发现自己喜欢写东西，喜欢看书，也喜欢问问题。

最后，小明对爸爸妈妈说："我以后想当作家！我要写很多书，让很多人看。"

爸爸妈妈听了很高兴。他们说："很好！做你喜欢的事情，你会很快乐。"

从那天起，小明每天都写一些东西。他知道，只要他努力，他的梦想一定会实现。"""},

    {"title": "老人和大海", "content": """在一个小村子里，住着一个老人。他每天都去海边。

老人没有家人，只有一条小船。他每天早上出海，晚上回来。

有一天，一个小孩问老人："你为什么每天都去海上？你不怕吗？"

老人笑了笑说："大海是我的老朋友。我们认识很多年了。"

"大海会说话吗？"小孩问。

"不会说话，但是我能听懂它。"老人说，"海水的声音告诉我很多事情。"

小孩不太明白，但是他很想知道更多。

老人说："你想和我一起去看看吗？"

小孩很高兴，他们一起上了船。

在海上，老人教小孩看天空，听海水，感受风。

"你看，"老人说，"天上的云告诉我们明天会下雨。海水的颜色告诉我们这里有很多鱼。"

小孩第一次感到大海是活的。从那天起，他经常和老人一起出海。

很多年后，小孩长大了。他也成为了一个会听懂大海的人。"""},

    {"title": "两个朋友", "content": """小红和小白是好朋友。她们每天一起上学，一起回家。

小红喜欢说话，小白喜欢听。小红走路很快，小白走路很慢。她们不一样，但是她们是最好的朋友。

有一天，她们吵架了。小红说小白太慢，小白说小红太快。两个人都很生气，决定不做朋友了。

第二天，小红一个人上学。路上她看见一只小鸟，想告诉小白，但是小白不在。她觉得很没意思。

小白也一个人上学。她想问小红一个问题，但是小红不在。她觉得很不开心。

一个星期后，她们在学校门口遇见了。

小红先开口说："对不起，我不应该说你太慢。"

小白也说："对不起，我也不应该生气。"

两个人都笑了。从那天起，她们还是好朋友。

她们明白了一件事：真正的朋友，不需要一样，只需要互相理解。"""},

    {"title": "北京的一天", "content": """今年夏天，我和家人去了北京。这是我第一次去北京。

我们早上六点起床，先去了天安门。那里人很多，大家都在看升旗。

然后我们去了故宫。故宫很大很大，我们走了三个小时。里面有很多老房子，每个房子都有自己的故事。

中午，我们在一家小饭店吃饭。我吃了北京烤鸭，真的很好吃！爸爸说这是北京最有名的菜。

下午，我们去了长城。长城很长，我们只走了一小部分。站在长城上，我能看见很远的地方。我想，古时候的人真的很了不起。

晚上回到酒店，我很累但是很高兴。

妈妈问我："你最喜欢今天的什么？"

我想了想说："我最喜欢长城。因为我知道了，古人为了保护自己的国家，可以做很难的事情。"

这一天，我学到了很多东西。北京，我以后还会再来的！"""},

    {"title": "一本旧书", "content": """我的房间里有很多书。但是有一本书最特别，因为它是我外公的。

外公去年去世了。在他的东西里，我发现了这本旧书。书很旧，有些地方已经看不清楚了。

这本书是一本日记。外公从二十岁开始写，一直写到八十岁。六十年的时间，都在这本书里。

我一页一页地看。我看到外公年轻时候的梦想，他的工作，他的朋友。我看到他遇见外婆的那一天，我看到爸爸出生的那一天。

书里有很多我不知道的故事。原来外公小时候家里很穷，但是他很努力学习。原来外公年轻的时候想当画家，但是后来当了老师。

最让我感动的是最后几页。外公写道："我这一生最幸福的事，就是看着我的孩子和孙子长大。"

看完这本书，我哭了。我决定，我也要开始写日记。也许很多年以后，我的孙子也会看到我的故事。

外公虽然不在了，但是他的故事会一直在。"""},

    {"title": "雨天的故事", "content": """今天下雨了。我坐在窗口，看着外面的雨。

雨不大，但是下了很久。街上的人都打着伞，走得很快。只有一个老人，他没有伞，但是走得很慢。

我很奇怪，为什么他不走快一点？

妈妈看见我在看窗外，问我在想什么。我告诉她关于那个老人的事。

妈妈说："也许他不怕雨，也许他在想事情，也许他只是喜欢慢慢走。每个人都有自己的原因。"

我想了想，觉得妈妈说得对。我们不能知道别人心里想什么。

过了一会儿，雨停了。太阳出来了，天上有一道彩虹。

我跑出去，想更近地看彩虹。在门口，我看见了那个老人。他也在看彩虹，脸上带着微笑。

我突然明白了。也许他就是在等这个——等雨停，等太阳出来，等彩虹。

有时候，慢一点，可以看见更多美好的东西。"""}
]

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
    main()
