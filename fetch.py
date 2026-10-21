"""Build a filtered-friendly snapshot of Ynet's homepage, using feeds to enrich article metadata."""
import concurrent.futures
import datetime as dt
import email.utils
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.parse as up
import urllib.request as ur
import xml.etree.ElementTree as ET

HOME = 'https://www.ynet.co.il/'
FEEDS = {'חדשות':'2','כלכלה':'6','תרבות':'538','בריאות':'1208','טכנולוגיה':'544','אוכל':'975'}
OUT = Path(__file__).parent/'site'/'articles.json'
NOW = dt.datetime.now(dt.timezone.utc)
BLOCK_SECTION = re.compile(r'/(?:sports?|wheels?|vehicle|vehicles|auto|cars?|motoring|judaism|jewish|yahadut)(?:/|$)', re.I)
HEADERS = {'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36','Accept-Language':'he-IL,he;q=0.9'}


def fetch(url):
    req=ur.Request(url,headers=HEADERS)
    with ur.urlopen(req,timeout=20) as response:
        return response.read().decode('utf-8','replace')


def clean(value):
    return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]*>',' ',value or ''))).strip()


def article_url(href):
    p=up.urlsplit(up.urljoin(HOME,html.unescape(href or '')))
    if p.hostname not in ('ynet.co.il','www.ynet.co.il') or BLOCK_SECTION.search(p.path):
        return ''
    if not (re.search(r'/article/',p.path,re.I) or re.search(r'/articles/\d',p.path,re.I)):
        return ''
    return up.urlunsplit(('https','www.ynet.co.il',p.path,'',''))


def image_url(src):
    if not src or src.startswith('data:'):
        return ''
    url=up.urljoin(HOME,html.unescape(src))
    return url if url.startswith('https://') else ''


def section_from(value):
    value=(value or '').lower()
    patterns=[('ספורט',r'sport|כדורגל|כדורסל'),('רכב',r'vehicle|wheels|\bauto\b|רכב'),('יהדות',r'judaism|jewish|יהדות'),
              ('כלכלה',r'econom|money|business|כלכלה|צרכנות|נדל'),('תרבות',r'culture|entertainment|תרבות|סדרה|מוזיקה'),
              ('בריאות',r'health|wellness|בריאות'),('טכנולוגיה',r'digital|technology|tech|דיגיטל|טכנולוגיה'),
              ('אוכל',r'food|אוכל|מתכונים'),('מדע וסביבה',r'science|environment|מדע|סביבה'),
              ('תיירות',r'travel|vacation|חופש|תיירות'),('דעות',r'opinion|דעות'),('יחסים',r'relationship|יחסים'),
              ('אופנה',r'fashion|אופנה'),('חדשות',r'news|חדשות')]
    for label,pattern in patterns:
        if re.search(pattern,value,re.I):return label
    return ''


class Homepage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active=None; self.heading=0; self.entries=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='a':
            self.finish()
            self.active={'url':article_url(a.get('href','')),'text':[],'heads':[],
                         'title':a.get('title',''),'image':'','section':a.get('data-category','')}
        elif self.active is not None:
            if re.fullmatch(r'h[1-6]',tag):self.heading+=1
            if tag in ('img','source') and not self.active['image']:
                src=a.get('data-src') or a.get('src') or a.get('data-original') or a.get('data-lazy-src')
                if not src and a.get('srcset'):
                    src=a['srcset'].split(',')[0].strip().split(' ')[0]
                self.active['image']=image_url(src)
    def handle_data(self,data):
        if self.active is not None:
            self.active['text'].append(data)
            if self.heading:self.active['heads'].append(data)
    def handle_endtag(self,tag):
        if re.fullmatch(r'h[1-6]',tag):self.heading=max(0,self.heading-1)
        if tag=='a':self.finish()
    def finish(self):
        if self.active is None:return
        a=self.active;self.active=None;self.heading=0
        title=clean(' '.join(a['heads'])) or clean(a['title']) or clean(' '.join(a['text']))
        if not a['url'] or not 12<=len(title)<=210:return
        self.entries.append({'title':title,'url':a['url'],'section':section_from(a['section']) or section_from(a['url']) or 'כללי',
                             'summary':'','image':a['image'],'timestamp':0})


class Metadata(HTMLParser):
    def __init__(self):
        super().__init__(); self.meta={}
    def handle_starttag(self,tag,attrs):
        if tag!='meta':return
        a=dict(attrs)
        name=(a.get('property') or a.get('name') or '').lower()
        if name and a.get('content'):
            self.meta.setdefault(name,a['content'])


def article_metadata(url):
    try:
        p=Metadata();p.feed(fetch(url)[:160000]);m=p.meta
        section=section_from(m.get('article:section','')) or section_from(m.get('og:section',''))
        published=m.get('article:published_time') or m.get('datepublished') or ''
        try:stamp=int(dt.datetime.fromisoformat(published.replace('Z','+00:00')).timestamp())
        except (ValueError,TypeError):stamp=0
        return url,{'image':image_url(m.get('og:image') or m.get('twitter:image') or ''),
                    'section':section, 'timestamp':stamp,'summary':clean(m.get('og:description',''))[:220]}
    except Exception as ex:
        return url,{}


def rss_items():
    items={}; errors=[]
    for section,code in FEEDS.items():
        try:
            root=ET.fromstring(fetch('https://www.ynet.co.il/Integration/StoryRss'+code+'.xml'))
            for item in root.iter():
                if item.tag.rsplit('}',1)[-1]!='item':continue
                def child(name):
                    x=next((c for c in item if c.tag.rsplit('}',1)[-1]==name),None)
                    return ''.join(x.itertext()).strip() if x is not None else ''
                url=article_url(child('link'));title=clean(child('title'))
                if not url or not title:continue
                try:stamp=int(email.utils.parsedate_to_datetime(child('pubDate')).timestamp())
                except Exception:stamp=0
                img=''
                for e in item.iter():
                    if e.tag.rsplit('}',1)[-1] in ('thumbnail','enclosure','content'):
                        candidate=e.attrib.get('url','')
                        if candidate and (e.tag.rsplit('}',1)[-1]=='thumbnail' or 'image' in e.attrib.get('type','') or re.search(r'\.(?:png|jpe?g|webp)',candidate,re.I)):
                            img=image_url(candidate);break
                if not img:
                    d=child('description');found=re.search(r'<img\b[^>]*\bsrc=[\'\"]([^\'\"]+)',d,re.I)
                    if found:img=image_url(found.group(1))
                items[url]={'title':title,'url':url,'section':section,'summary':clean(child('description'))[:220],'image':img,'timestamp':stamp}
        except Exception as ex:errors.append(f'{section}: {ex}')
    return items,errors


def build():
    rss,feed_errors=rss_items()
    errors=list(feed_errors)
    try:
        parser=Homepage();parser.feed(fetch(HOME));parser.finish()
        unique={}
        for a in parser.entries:unique.setdefault(a['url'],a)
        articles=list(unique.values())
        if len(articles)<15:raise ValueError(f'Only {len(articles)} homepage links')
        source='ynet-homepage'
        for a in articles:
            f=rss.get(a['url'])
            if f:
                for k in ('image','summary','timestamp'):
                    if not a[k] and f[k]:a[k]=f[k]
                if a['section']=='כללי':a['section']=f['section']
        # Pages use numeric article IDs; the RSS typically covers recent articles only.
        # Get missing image and section directly from each article. Bound concurrency.
        missing=[a for a in articles if not a['image'] or a['section']=='כללי' or not a['timestamp']]
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            for url,meta in pool.map(article_metadata,(a['url'] for a in missing)):
                a=unique[url]
                for k in ('image','summary','timestamp'):
                    if not a[k] and meta.get(k):a[k]=meta[k]
                if meta.get('section') and a['section']=='כללי':a['section']=meta['section']
        print('Homepage links:',len(articles),'enrichment requests:',len(missing))
    except Exception as ex:
        errors.append(f'Homepage: {ex}')
        articles=sorted(rss.values(),key=lambda a:a['timestamp'],reverse=True)[:150]
        source='rss-fallback'
    articles=[a for a in articles if a['section'] not in ('ספורט','רכב','יהדות') and not BLOCK_SECTION.search(up.urlsplit(a['url']).path)]
    if not articles and OUT.exists():
        articles=json.loads(OUT.read_text('utf-8')).get('articles',[])
        source='previous-data'
    if not articles:raise SystemExit('No articles; retaining previous deployment')
    payload={'updated_at':NOW.isoformat(),'source':source,'count':len(articles),'errors':errors,'articles':articles[:300]}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Published',len(articles),'articles, source:',source,'errors:',errors)

if __name__=='__main__':build()
