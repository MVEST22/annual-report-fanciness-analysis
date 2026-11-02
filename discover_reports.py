"""Find candidate official annual-report PDFs; keep a human review gate.

Input: report_manifest.csv (company_name,bvd_id,report_url,report_year)
Output: report_candidates.csv with search results and status, without guessing approvals.
Requires: pip install ddgs requests beautifulsoup4
"""
import argparse, csv, re, time
from datetime import date
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS

YEAR=date.today().year
FIELDS=['company_name','bvd_id','candidate_url','source_page','candidate_title','candidate_year','pdf_verified','review_status']
BLOCKED=['linkedin.com','facebook.com','instagram.com','reddit.com','scribd.com']
def extract_year(text):
    years=[int(y) for y in re.findall(r'(?<!\d)20[012]\d(?!\d)',text)]
    years=[y for y in years if y<=YEAR]
    return max(years) if years else ''

def looks_annual(text):
    t=text.lower()
    return ('annual report' in t or 'annual-report' in t or 'årsrapport' in t or 'aarsrapport' in t or 'annualreport' in t) and not any(
      s in t for s in ['interim','quarter','half-year','q1 report','q2 report','q3 report','presentation','remuneration'])

def candidate_links(url):
    """Find PDF links from a public HTML search-result landing page; do not crawl deeper."""
    try:
        r=requests.get(url,timeout=20,headers={'User-Agent':'Mozilla/5.0'})
        r.raise_for_status()
        if 'html' not in r.headers.get('Content-Type','').lower(): return []
        soup=BeautifulSoup(r.text,'html.parser')
        out=[]
        for a in soup.select('a[href]'):
            link=urljoin(url,a['href'])
            label=a.get_text(' ',strip=True)
            if ('.pdf' in urlparse(link).path.lower() or '.pdf' in link.lower()) and looks_annual(label+' '+link):
                out.append((link,label))
        return out[:12]
    except requests.RequestException:
        return []

def verify_pdf(url):
    if not url.startswith('https://'): return False
    try:
        with requests.get(url,timeout=30,stream=True,headers={'User-Agent':'Mozilla/5.0'}) as r:
            if r.status_code != 200: return False
            first=next(r.iter_content(1024),b'')
            return first.startswith(b'%PDF')
    except (requests.RequestException, StopIteration):
        return False

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--manifest',default='report_manifest.csv')
    p.add_argument('--out',default='report_candidates.csv')
    p.add_argument('--limit',type=int,default=0)
    args=p.parse_args()
    with open(args.manifest,newline='',encoding='utf-8-sig') as f:
        rows=list(csv.DictReader(f))
    if args.limit: rows=rows[:args.limit]
    results=[]
    ddgs=DDGS()
    for idx,row in enumerate(rows,1):
        name=row['company_name'].strip()
        print(f'[{idx}/{len(rows)}] {name}',flush=True)
        hits=[]
        for query in [f'{name} annual report {YEAR-1}',
                      f'{name} investor relations annual reports',
                      f'{name} årsrapport {YEAR-1} pdf']:
            try:
                found=list(ddgs.text(query,max_results=8))
                hits.extend(found)
                print(' Search results:',len(found),'query:',query,flush=True)
                if len(hits)>=12: break
            except Exception as exc:
                print(' Search unavailable:',str(exc)[:150],flush=True)
            time.sleep(1)
        print(' Total raw results:',len(hits),flush=True)
        seen=set()
        for hit in hits:
            url=hit.get('href','')
            parsed=urlparse(url)
            if parsed.scheme!='https' or any(b in parsed.netloc for b in BLOCKED):continue
            title=hit.get('title','')
            if not looks_annual(title+' '+url+' '+hit.get('body','')):continue
            options=[(url,title)] if '.pdf' in parsed.path.lower() else (candidate_links(url) or [(url,title)])
            for target,label in options:
                if target in seen:continue
                seen.add(target)
                results.append({'company_name':name,'bvd_id':row['bvd_id'],
                  'candidate_url':target,'source_page':url,'candidate_title':label or title,
                  'candidate_year':extract_year(target+' '+label+' '+title),
                  'pdf_verified':'yes' if '.pdf' in urlparse(target).path.lower() and verify_pdf(target) else 'no',
                  'review_status':'UNREVIEWED — verify company, report year and latest status'})
        time.sleep(1)
    with open(args.out,'w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(results)
    print(f'{len(results)} candidates saved to {args.out}. Manual verification required before scoring.')

if __name__=='__main__': main()
