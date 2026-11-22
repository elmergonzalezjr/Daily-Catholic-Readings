"""Daily Readings, cloud side: a scheduled Claude Code routine writes each day's Gospel retelling and reflection into
feed/YYYY-MM-DD.json in this repository; the TV's Readings app reads it from raw.githubusercontent.com.

    python3 readings.py prepare [YYYY-MM-DD]   today's readings and the writing instructions (or ALREADY DONE / NOT YET)
    python3 readings.py save YYYY-MM-DD FILE   check the JSON and put it in feed/ (keeps 30 days)

"Today" is the date in Belize (UTC-6, no daylight saving). Standard library only.
"""
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
FEED = os.path.join(HERE, "feed")
READINGS_RSS = "https://bible.usccb.org/readings.rss"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
KEEP_DAYS = 30
BELIZE = dt.timezone(dt.timedelta(hours=-6))

EXAMPLE = """{
  "gospelCitation": "Matthew 25:31–46",
  "gospelTitle": "The Final Judgment",
  "retelling": [
    {"verses": "31–33", "text": "Jesus tells His disciples that when the Son of Man comes in glory, accompanied by His angels, He will sit upon His throne. All nations will gather before Him, and He will separate people as a shepherd separates sheep from goats."},
    {"verses": "40", "text": "Jesus explains that whenever they showed kindness and compassion to those most in need, they were serving Him."}
  ],
  "reflectionTitle": "Christ the King: Leadership Through Love and Service",
  "reflection": ["Today's Solemnity reminds us that Jesus Christ is not a King who rules through wealth, status or worldly power. His kingship is revealed through love, justice, mercy and service.", "In the First Reading, God describes Himself as a shepherd who searches for the lost..."],
  "message": "If Christ truly reigns in our hearts, His love should be visible in how we treat others, especially those who cannot offer us anything in return."
}"""


def today():
    return dt.datetime.now(BELIZE).date()


def path_for(day):
    return os.path.join(FEED, day.isoformat() + ".json")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def plain(s):
    s = re.sub(r"<!\[CDATA\[|\]\]>", "", s or "")
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).replace(" ", " ").strip()


def text(s):
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</p>", "\n\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", "", s)).replace(" ", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def readings(day):
    code = day.strftime("%m%d%y") + ".cfm"
    rss = fetch(READINGS_RSS)
    for item in re.findall(r"<item>(.*?)</item>", rss, re.S):
        link = re.search(r"<link>(.*?)</link>", item, re.S)
        if not link or code not in link.group(1):
            continue
        title = plain(re.search(r"<title>(.*?)</title>", item, re.S).group(1))
        desc = re.search(r"<description>(.*?)</description>", item, re.S).group(1).strip()
        if desc.startswith("<![CDATA["):
            desc = re.sub(r"^<!\[CDATA\[|\]\]>$", "", desc)
        else:
            desc = html.unescape(desc)  # the feed escapes the HTML (&lt;h4&gt;...)
        heads = list(re.finditer(r"<h4>(.*?)</h4>", desc, re.S))
        out = []
        for i, h in enumerate(heads):
            head = h.group(1)
            a = head.find("<a")
            label = plain(head[:a] if a > 0 else head)
            cite = plain(head[a:]) if a > 0 else ""
            body = desc[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(desc)]
            out.append((label, cite, text(body.split(" - - -")[0])))
        return title, out
    return None, None


def prepare(day):
    if os.path.exists(path_for(day)):
        print(f"ALREADY DONE: feed/{day.isoformat()}.json exists. Nothing to write today.")
        return 0
    title, rs = readings(day)
    if not rs:
        print(f"NOT YET: the USCCB feed has no readings for {day.isoformat()} yet.")
        return 2
    draft = os.path.join(HERE, "draft-" + day.isoformat() + ".json")
    print(f"Date: {day.strftime('%A, %B')} {day.day}, {day.year}")
    print(f"Celebration: {title}\n\nThe readings of the day (USCCB):")
    for label, cite, body in rs:
        print(f"\n## {label} — {cite}\n{body}")
    print(f"""

===== WHAT TO WRITE =====
You are writing a short daily Catholic devotional for one reader, shown on a TV at home. The reader is a general
manager at work. Use only the readings above. Write in clear, warm, plain English. Capitalize pronouns for God and
Jesus (He, His, Him). Never quote the readings word for word: the retelling must be your own wording, faithful to the
text and to Catholic teaching.

Write ONE JSON object (UTF-8, no other text) to this file:
    {draft}
shaped like this example (which shows the style; today's content will differ):

{EXAMPLE}

1. The Gospel retelling (use the Gospel above; if a shorter form is offered with "Or", use the first, full form).
   gospelCitation uses an en dash between verses. gospelTitle is a short name for the passage. retelling covers every
   verse in order, in groups of one to four verses ("verses" is "31–33" or "40"), each group one or two
   sentences retelling what happens or is said, in your own words.
2. The reflection: reflectionTitle names the day and its theme. reflection is 10 to 16 short paragraphs (one to three
   sentences each), about 350 to 450 words in all. Connect the First Reading, the Second Reading or Psalm, and the
   Gospel; draw out what the Gospel asks of us, including what is surprising or challenging in it; then bring it to
   daily life in families, workplaces and communities, including leading and serving others. message is one sentence:
   the day's message, shown after "Today's message:".

Then check and publish it with:
    python3 readings.py save {day.isoformat()} {os.path.basename(draft)}
""")
    return 0


def check(o):
    for k in ("gospelCitation", "gospelTitle", "reflectionTitle", "message"):
        if not isinstance(o.get(k), str) or not o[k].strip():
            raise ValueError(f"missing {k}")
    r = o.get("retelling")
    if not isinstance(r, list) or not r:
        raise ValueError("retelling must be a non-empty list")
    for g in r:
        if not isinstance(g, dict) or not isinstance(g.get("verses"), str) or not isinstance(g.get("text"), str):
            raise ValueError("each retelling group needs verses and text")
    p = o.get("reflection")
    if not isinstance(p, list) or not p or not all(isinstance(x, str) for x in p):
        raise ValueError("reflection must be a list of paragraphs")


def save(day, src):
    if not os.path.isabs(src):
        src = os.path.join(HERE, src)
    with open(src, encoding="utf-8-sig") as f:
        raw = f.read()
    a, b = raw.find("{"), raw.rfind("}")
    o = json.loads(raw[a:b + 1])
    check(o)
    o["date"] = day.isoformat()
    os.makedirs(FEED, exist_ok=True)
    with open(path_for(day), "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False, indent=1)
    if os.path.basename(src).startswith("draft-"):
        os.remove(src)
    for name in sorted(os.listdir(FEED)):
        m = re.match(r"(\d{4}-\d{2}-\d{2})\.json$", name)
        if m and dt.date.fromisoformat(m.group(1)) < day - dt.timedelta(days=KEEP_DAYS):
            os.remove(os.path.join(FEED, name))
    print(f"SAVED: feed/{day.isoformat()}.json ({len(o['retelling'])} retelling groups, {len(o['reflection'])} paragraphs)")
    return 0


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "prepare":
        return prepare(dt.date.fromisoformat(argv[2]) if len(argv) > 2 else today())
    if cmd == "save":
        return save(dt.date.fromisoformat(argv[2]), argv[3])
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
