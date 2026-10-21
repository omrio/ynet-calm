"""Collect Ynet homepage article headlines, with RSS as a safe fallback."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
import datetime as dt
import email.utils
import html
import json
import re
import xml.etree.ElementTree as ET

HOME = 'https://www.ynet.co.il/'
FEEDS = {'חדשות':'2','כלכלה':'6','תרבות':'538','בריאות':'1208','טכנולוגיה':'544','אוכל':'975'}
OUT = Path(__file__).parent / 'site' / 'articles.json'
NOW = dt.datetime.now(dt.timezone.utc)


def fetch(url):
    req = Request(url, headers={'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36', 'Accept-Language':'he-IL,he;q=0.9'})
    with urlopen(req, timeout=30) as res:
        return res.read()


def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', ' ', s or ''))).strip()


def canonical(href):
    p = urlsplit(urljoin(HOME, html.unescape(href or '')))
    if p.hostname not in ('www.ynet.co.il','ynet.co.il'):
        return ''
    if not (re.search(r'/article/',p.path,re.I) or re.search(r'/articles/\d',p.path,re.I)):
        return ''
    if re.search(r'/(?:sports?|wheels?|vehicle|vehicles|auto|cars?|motoring|judaism|jewish|yahadut)/',p.path,re.I):
        return ''
    return urlunsplit(('https','www.ynet.co.il',p.path,'',''))


class Homepage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.current = None
        self.heading = 0
        self.entries = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a':
            self.finish()
            self.current = {'url':canonical(attrs.get('href','')), 'text':[], 'heading':[], 'title':attrs.get('title',''), 'image':''}
        elif self.current is not None:
            if re.fullmatch(r'h[1-6]',tag):
                self.heading += 1
            if tag == 'img' and not self.current['image']:
                self.current['image'] = attrs.get('src') or attrs.get('data-src') or ''

    def handle_data(self, data):
        if self.current:
            self.current['text'].append(data)
            if self.heading:
                self.current['heading'].append(data)

    def handle_endtag(self, tag):
        if re.fullmatch(r'h[1-6]',tag):
            self.heading = max(0,self.heading-1)
        if tag == 'a':
            self.finish()

    def finish(self):
        if not self.current:
            return
        c = self.current
        self.current = None
        self.heading = 0
        title = clean(' '.join(c['heading'])) or clean(c['title']) or clean(' '.join(c['text']))
        if not c['url'] or not (12 <= len(title) <= 220):
            return
        self.entries.append({'title':title,'url':c['url'],'section':'חדשות','summary':'','image':urljoin(HOME,c['image']) if c['image'] else '', 'timestamp':int(NOW.timestamp())})


def homepage_items():
    parser = Homepage()
    parser.feed(fetch(HOME).decode('utf-8','replace'))
    parser.finish()
    distinct = {}
    for item in parser.entries:
        distinct.setdefault(item['url'],item)
    found = list(distinct.values())
    if len(found) < 15:
        raise ValueError(f'Only {len(found)} headline links extracted from homepage')
    return found


def rss_items():
    results, errors = [], []
    for section, code in FEEDS.items():
        try:
            root = ET.fromstring(fetch('https://www.ynet.co.il/Integration/StoryRss'+code+'.xml'))
            for item in root.iter():
                if item.tag.rsplit('}',1)[-1] != 'item':
                    continue
                values = {child.tag.rsplit('}',1)[-1]:''.join(child.itertext()).strip() for child in item}
                title = clean(values.get('title',''))
                url = canonical(values.get('link',''))
                if not title or not url:
                    continue
                try:
                    timestamp = int(email.utils.parsedate_to_datetime(values.get('pubDate','')).timestamp())
                except Exception:
                    timestamp = 0
                results.append({'title':title,'url':url,'section':section,'summary':clean(values.get('description',''))[:220], 'image':'','timestamp':timestamp})
        except Exception as exc:
            errors.append(f'{section}: {exc}')
    distinct = {}
    for item in results:
        distinct.setdefault(item['url'],item)
    return sorted(distinct.values(),key=lambda x:x['timestamp'],reverse=True), errors


errors=[]
try:
    articles = homepage_items()
    source = 'ynet-homepage'
except Exception as exc:
    errors.append('Homepage: '+str(exc))
    articles, rss_errors = rss_items()
    errors.extend(rss_errors)
    source = 'rss-fallback'

if not articles and OUT.exists():
    articles = json.loads(OUT.read_text('utf-8')).get('articles',[])
    source = 'previous-data'
# Apply exclusions even to preserved data from a previous deployment.
articles = [item for item in articles
            if item.get('section') not in ('רכב', 'יהדות', 'ספורט')
            and canonical(item.get('url', ''))]
if not articles:
    raise SystemExit('No usable articles; aborting deployment')

OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps({'updated_at':NOW.isoformat(),'count':len(articles),'source':source,'errors':errors,'articles':articles[:300]},ensure_ascii=False,indent=2),encoding='utf-8')
print('Published',min(len(articles),300),'articles; source:',source)
if errors: print('Warnings:',*errors,sep='\n')
