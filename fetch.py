import json, re, html, urllib.request, urllib.parse, datetime, email.utils, xml.etree.ElementTree as ET
from pathlib import Path
FEEDS = {'חדשות':'2', 'כלכלה':'6', 'תרבות':'538', 'בריאות':'1208', 'טכנולוגיה':'544', 'רכב':'550', 'אוכל':'975'}
BASE='https://www.ynet.co.il/Integration/StoryRss{}.xml'
OUT=Path(__file__).parent/'site'/'articles.json'

def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', '', s or ''))).strip()

def local(tag): return tag.rsplit('}',1)[-1]

def content(el,name):
    for x in el:
        if local(x.tag)==name:return ''.join(x.itertext()).strip()
    return ''

def image_of(item):
    for x in item.iter():
        name=local(x.tag).lower()
        if name in ('enclosure','thumbnail','content'):
            url=x.attrib.get('url','')
            if url.startswith('http') and (name=='thumbnail' or 'image' in x.attrib.get('type','') or re.search(r'\.(jpg|jpeg|png|webp)',url,re.I)):
                return url
    desc=content(item,'description')
    m=re.search(r'<img[^>]+src=[\'\"]([^\'\"]+)',desc,re.I)
    return html.unescape(m.group(1)) if m else ''

all_items=[]; failures=[]
for category, code in FEEDS.items():
    url=BASE.format(code)
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; personal-news-reader/1.0)','Accept':'application/rss+xml,application/xml,text/xml,*/*'})
        with urllib.request.urlopen(req,timeout=25) as response: raw=response.read()
        root=ET.fromstring(raw)
        entries=[x for x in root.iter() if local(x.tag) in ('item','entry')]
        if not entries: raise ValueError('No feed entries')
        for item in entries:
            title=clean(content(item,'title'))
            link=content(item,'link')
            if not link:
                for x in item:
                    if local(x.tag)=='link': link=x.attrib.get('href',''); break
            link=html.unescape(link)
            if not (title and link.startswith('https://')):
                if link.startswith('http://'): link='https://'+link[7:]
                else: continue
            parsed=urllib.parse.urlparse(link)
            if not (parsed.hostname == 'ynet.co.il' or parsed.hostname.endswith('.ynet.co.il')): continue
            date=content(item,'pubDate') or content(item,'published') or content(item,'updated')
            try: ts=email.utils.parsedate_to_datetime(date).timestamp()
            except Exception:
                try: ts=datetime.datetime.fromisoformat(date.replace('Z','+00:00')).timestamp()
                except Exception: ts=0
            all_items.append({'title':title,'url':link,'section':category,'summary':clean(content(item,'description'))[:220], 'image':image_of(item),'timestamp':int(ts)})
        print(category, len(entries))
    except Exception as exc:
        failures.append(f'{category}: {exc}')
        print('FAILED',category,exc)
old=[]
if OUT.exists():
    try: old=json.loads(OUT.read_text('utf-8')).get('articles',[])
    except Exception: pass
if not all_items and old:
    all_items=old
elif all_items and failures:
    existing={x['url'] for x in all_items}
    failed_sections={x.split(':')[0] for x in failures}
    all_items.extend(x for x in old if x['section'] in failed_sections and x['url'] not in existing)
unique={}
for x in all_items:
    unique.setdefault(x['url'],x)
articles=sorted(unique.values(),key=lambda x:x['timestamp'],reverse=True)[:300]
if not articles: raise SystemExit('No articles; refusing to publish empty data')
payload={'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'count':len(articles),'errors':failures,'articles':articles}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
print('Written',len(articles),'articles')
