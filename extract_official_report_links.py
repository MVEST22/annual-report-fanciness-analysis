"""Collect annual-report link candidates from known company investor-relations pages.

This does not guess company domains, bypass access restrictions, or auto-approve reports.
Input: report_manifest.csv including optional 'official_source_page'.
Output: official_page_candidates.csv; choose matching original designed PDFs manually.
"""
import argparse, csv, re, time
from urllib.parse import urlparse, urljoin, unquote
from pathlib import Path
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parent
FIELDS=['company_name','bvd_id','source_page','candidate_url','link_text',
        'candidate_year','pdf_hint','status']
HEADERS={'User-Agent':'Mozilla/5.0 (compatible; university research report review)'}
KEYWORDS=('annual report','annual-report','annualreport','annual reports',
          'aarsrapport','årsrapport','annual reporting','financial reports',
          'reports and presentations','financial statements','annual financial')
EXCLUDE=('interim','quarterly','quarter','half year','half-year','remuneration',
         'sustainability report','esg report','q1','q2','q3','q4')
def cleaned(text):
    return re.sub(r'\s+',' ',unquote(text)).strip().lower()

def year(text):
    x=re.findall(r'(?<!\d)(20[012]\d)(?!\d)',text)
    return max(x) if x else ''

def pdf_hint(url):
    u=url.lower()
    return 'yes' if '.pdf' in urlparse(u).path or '.pdf?' in u else 'unknown'

def crawl(source,session,depth=1):
    base=urlparse(source)
    if base.scheme!='https' or not base.hostname:
        return [],'source_not_https'
    queue=[(source,0)];seen=set();found=[];errors=[]
    while queue and len(seen)<12:
        url,d=queue.pop(0)
        if url in seen:continue
        seen.add(url)
        try:
            r=session.get(url,timeout=(12,25),headers=HEADERS)
            r.raise_for_status()
            if 'html' not in r.headers.get('Content-Type','').lower():
                errors.append('non_html_landing');continue
            soup=BeautifulSoup(r.text,'html.parser')
            for a in soup.find_all('a',href=True):
                href=urljoin(url,a['href'])
                parsed=urlparse(href)
                if parsed.scheme!='https' or not parsed.netloc:continue
                label=a.get_text(' ',strip=True)
                context=cleaned(label+' '+href)
                if any(w in context for w in EXCLUDE):continue
                relevant=any(w in context for w in KEYWORDS)
                is_pdf=pdf_hint(href)=='yes'
                if relevant and is_pdf:
                    found.append((url,href,label,'pdf_link'))
                elif relevant and d<depth and parsed.hostname==base.hostname and href not in seen:
                    queue.append((href,d+1))
                elif relevant and d==depth:
                    found.append((url,href,label,'landing_page_only'))
        except requests.RequestException as exc:
            errors.append(str(exc)[:100])
        time.sleep(0.3)
    return found,'; '.join(errors)[:200]

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--manifest',default=str(ROOT/'report_manifest.csv'))
    p.add_argument('--out',default=str(ROOT/'official_page_candidates.csv'))
    p.add_argument('--limit',type=int,default=0)
    p.add_argument('--depth',type=int,default=1,choices=[0,1,2])
    args=p.parse_args()
    with open(args.manifest,newline='',encoding='utf-8-sig') as f:
        entries=list(csv.DictReader(f))
    if not entries or not {'company_name','bvd_id'}.issubset(entries[0]):
        p.error('Missing company_name/bvd_id in manifest')
    if args.limit:entries=entries[:args.limit]
    results=[]
    with requests.Session() as session:
        for i,company in enumerate(entries,1):
            source=(company.get('official_source_page') or '').strip()
            if not source:
                print(f'[{i}/{len(entries)}] {company["company_name"]}: missing official source',flush=True)
                continue
            links,err=crawl(source,session,args.depth)
            if not links:
                results.append({'company_name':company['company_name'],'bvd_id':company['bvd_id'],
                 'source_page':source,'candidate_url':'','link_text':'','candidate_year':'',
                 'pdf_hint':'','status':'no_candidates: '+err})
            for page,url,title,status in links:
                results.append({'company_name':company['company_name'],'bvd_id':company['bvd_id'],
                 'source_page':page,'candidate_url':url,'link_text':title,'candidate_year':year(title+' '+url),
                 'pdf_hint':pdf_hint(url),'status':'UNREVIEWED_'+status})
            print(f'[{i}/{len(entries)}] {company["company_name"]}: {len(links)} candidates',flush=True)
    with open(args.out,'w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(results)
    print('Candidate rows:',len(results),'Written:',args.out)
    print('Check company/year/actual PDF and official source before copying into report_url.')
if __name__=='__main__': main()
