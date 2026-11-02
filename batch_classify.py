"""Resume-safe classification using manually verified annual-report PDFs.

Only public annual report design is inspected. Profit data never enters scoring.
"""
import argparse, csv, os, re
from pathlib import Path
from classify_reports import score_pdf

ROOT=Path(__file__).resolve().parent
FIELDS=['company_name','bvd_id','report_url','report_year','fanciness','weighted_score',
        'graphic_design','typography','photography_illustrations','charts_visualization',
        'layout_storytelling','pages_reviewed','rationale','status']

def read_csv(path):
    with open(path,newline='',encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def save(rows,out):
    tmp=out.with_name(out.name+'.tmp')
    with open(tmp,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS,extrasaction='ignore')
        w.writeheader();w.writerows(rows)
    os.replace(tmp,out)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--manifest',default='report_manifest.csv')
    p.add_argument('--output',default='batch_scores.csv')
    p.add_argument('--limit',type=int,default=0,help='Maximum companies attempted in this run')
    p.add_argument('--retry-errors',action='store_true')
    args=p.parse_args()
    if args.limit<0:p.error('--limit must be nonnegative')
    manifest=read_csv(args.manifest)
    if not manifest:p.error('Empty manifest')
    if not {'company_name','bvd_id','report_url','report_year'}.issubset(manifest[0]):
        p.error('Manifest missing required columns')
    ids=[r['bvd_id'].strip() for r in manifest]
    if not all(ids) or len(ids)!=len(set(ids)):p.error('Blank/duplicate BvD IDs')
    out=Path(args.output)
    saved={r['bvd_id']:r for r in read_csv(out)} if out.exists() else {}
    attempted=0
    for row in manifest:
        ident=row['bvd_id'].strip()
        previous=saved.get(ident)
        if previous and (previous.get('status')=='scored' or not args.retry_errors):
            print('SKIP',ident,previous.get('status'));continue
        if args.limit and attempted>=args.limit:break
        attempted+=1
        result={k:row.get(k,'') for k in FIELDS}
        file=ROOT/'reports'/(re.sub(r'[^a-zA-Z0-9_-]','_',ident)+'.pdf')
        try:
            if not file.is_file():
                raise FileNotFoundError('No verified local PDF: '+file.name)
            score,weighted,rationale,pages,dimensions=score_pdf(file)
            result.update(fanciness=score,weighted_score=weighted,
                          rationale=rationale,pages_reviewed=pages,status='scored',**dimensions)
            print('SCORED',ident,score,'pages',pages,flush=True)
        except Exception as ex:
            result['status']='error: '+str(ex)[:220]
            print('ERROR',ident,str(ex)[:220],flush=True)
        saved[ident]=result
        save([saved[r['bvd_id']] for r in manifest if r['bvd_id'] in saved],out)
        print('Checkpoint:',out,flush=True)
    print('Attempted:',attempted,'Total scored:',sum(r.get('status')=='scored' for r in saved.values()))

if __name__=='__main__':main()
