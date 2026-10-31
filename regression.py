"""Estimate profit (million DKK) on annual-report fanciness using local OLS."""
import argparse
from pathlib import Path
import pandas as pd
import statsmodels.api as sm

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',required=True,help='Local CSV: bvd_id,profit_m_dkk,fanciness')
    args=p.parse_args()
    df=pd.read_csv(args.input)
    required={'bvd_id','profit_m_dkk','fanciness'}
    if not required.issubset(df): raise ValueError('Missing columns: '+str(required-set(df.columns)))
    df=df.copy()
    df['profit_m_dkk']=pd.to_numeric(df['profit_m_dkk'],errors='coerce')
    df['fanciness']=pd.to_numeric(df['fanciness'],errors='coerce')
    df=df.dropna(subset=['bvd_id','profit_m_dkk','fanciness'])
    if df['bvd_id'].duplicated().any(): raise ValueError('Duplicate BvD company IDs')
    if not df['fanciness'].between(1,5).all(): raise ValueError('Fanciness must be between 1 and 5')
    if len(df)<3 or df.fanciness.nunique()<2: raise ValueError('Need at least 3 firms and two different fanciness scores')
    model=sm.OLS(df['profit_m_dkk'],sm.add_constant(df['fanciness'])).fit()
    out=Path('results');out.mkdir(exist_ok=True)
    report=model.summary().as_text()
    (out/'regression_output.txt').write_text(report,encoding='utf-8')
    b=float(model.params['fanciness']);pv=float(model.pvalues['fanciness'])
    print(report)
    print(f'\\nReport: coefficient = {b:.6f} million DKK per point; p-value = {pv:.6g}; N = {len(df)}')
    print('Interpretation is associative, not causal. Output: results/regression_output.txt')
if __name__=='__main__':main()
