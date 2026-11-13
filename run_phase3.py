import pandas as pd, numpy as np, json, os, zipfile
P='/mnt/data/phase3'; D='/mnt/data/phase2_refined/pressure_features_refined.csv'
d=pd.read_csv(D,parse_dates=['match_date'])
d['season']=d.match_date.dt.year
# score decomposition is based on the historical expected run/wicket values from Phase 2
for kind in ['bat','bowl']:
 if kind=='bat':
  d['run_'+kind]=d.runs-d.exp_bat_runs
  d['wkt_'+kind]=-(d.batter_dismissed.astype(int)-d.exp_bat_wk)
 else:
  d['run_'+kind]=d.exp_bowl_runs-d.runs
  d['wkt_'+kind]=d.bowler_credit.astype(int)-d.exp_bowl_wk
phase=d.phase.map({'powerplay':0.12,'middle':0.22,'death':0.36}).fillna(0).to_numpy()
wkt=np.minimum(d.wickets_before.to_numpy()/7,1)
rec=np.minimum(d.recent_wickets_12_deliveries.fillna(0).to_numpy()/2,1)
models={'baseline':(1,.42,.28),'wickets_emphasis':(.8,.55,.30),'phase_emphasis':(1.3,.32,.20),'balanced_early_collapse':(.9,.48,.37)}
for model,(p,w,r) in models.items(): d['pressure_'+model]=np.minimum(1,p*phase+w*wkt+r*rec)
# one-run minimum for known wides and no-balls; other no-legality type excluded to avoid ambiguity
extra=d.extras_type.isin(['wide','Overstep'])
# Conservative absolute event debit, not a fully context-adjusted extras expectation
extras=d.loc[extra & (d.pressure_baseline>=.55)].groupby('bowler_id').size().rename('recorded_wide_noball_events')

def rankings(kind, pressure='baseline', threshold=.55, wicket_value=7, min_matches=10, extras_penalty=False):
 idcol='striker_id' if kind=='bat' else 'bowler_id'; ncol='striker_name' if kind=='bat' else 'bowler_name'; valid='valid_'+kind
 z=d.loc[d[valid] & d['pressure_'+pressure].ge(threshold),[idcol,ncol,'match_id','comp','season','run_'+kind,'wkt_'+kind]].copy()
 z['value']=z['run_'+kind]+wicket_value*z['wkt_'+kind]
 agg=z.groupby(idcol,sort=False).agg(name=(ncol,'first'),n=('value','size'),matches=('match_id','nunique'),total=('value','sum'),run_resid=('run_'+kind,'sum'),wicket_resid=('wkt_'+kind,'sum')).reset_index()
 alln=d.loc[d[valid]].groupby(idcol).size().rename('all_n');agg=agg.join(alln,on=idcol)
 agg['eligible']=(agg.matches>=min_matches)&(agg.n>=(45 if kind=='bat' else 60))&(agg.all_n>=(100 if kind=='bat' else 120))
 if extras_penalty and kind=='bowl':
  agg=agg.join(extras,on=idcol);agg['recorded_wide_noball_events']=agg.recorded_wide_noball_events.fillna(0)
  agg['total']-=agg.recorded_wide_noball_events
 agg['rating']=6*agg.total/(agg.n+90)
 return agg.loc[agg.eligible].sort_values('rating',ascending=False).reset_index(drop=True),z

summary=[]
scenario_tables={}
for kind in ['bat','bowl']:
 base,z=rankings(kind,min_matches=10)
 base['rank']=np.arange(1,len(base)+1)
 base.to_csv(f'{P}/{kind}_conservative_baseline.csv',index=False)
 idcol='striker_id' if kind=='bat' else 'bowler_id'
 top_base=set(base[idcol].head(10))
 for pressure in models:
  for th in [.48,.55,.62]:
   for wicket_value in [4,7,10]:
    rr,_=rankings(kind,pressure=pressure,threshold=th,wicket_value=wicket_value,min_matches=10)
    scenario_name=f'{pressure}_t{th}_w{wicket_value}'
    scenario_tables[(kind,scenario_name)]=rr
    summary.append({'role':kind,'scenario':scenario_name,'eligible':len(rr),'top10_overlap_with_baseline':len(top_base&set(rr[idcol].head(10)))})
 # same definition, eligibility alternative
 for minmatch in [5,10,15,20]:
  rr,_=rankings(kind,min_matches=minmatch)
  summary.append({'role':kind,'scenario':f'min_pressure_matches_{minmatch}','eligible':len(rr),'top10_overlap_with_baseline':len(top_base&set(rr[idcol].head(10)))})
 if kind=='bowl':
  rr,_=rankings(kind,min_matches=10,extras_penalty=True)
  rr.to_csv(f'{P}/bowl_extras_penalty_scenario.csv',index=False)
  summary.append({'role':kind,'scenario':'one_run_each_wide_noball_proxy','eligible':len(rr),'top10_overlap_with_baseline':len(top_base&set(rr[idcol].head(10)))})
  scenario_tables[(kind,'extra_debit')]=rr
 # candidate stability across 36 scenarios
 stable=[]
 for (k,s),rr in scenario_tables.items():
  if k!=kind:continue
  for pos,pid in enumerate(rr[idcol].head(10),1): stable.append((pid,s,pos))
 stab=pd.DataFrame(stable,columns=[idcol,'scenario','position'])
 agg=stab.groupby(idcol).agg(top10_scenarios=('scenario','nunique'),median_rank_when_top10=('position','median')).reset_index()
 # all candidates with baseline or scenarios
 candidate=base[[idcol,'name','rank','rating','n','matches']].merge(agg,on=idcol,how='outer')
 name_map=d.groupby(idcol)[('striker_name' if kind=='bat' else 'bowler_name')].first()
 candidate['name']=candidate.name.fillna(candidate[idcol].map(name_map))
 candidate['top10_scenarios']=candidate.top10_scenarios.fillna(0).astype(int)
 candidate['scenario_count']=len([1 for k,s in scenario_tables if k==kind])
 candidate['top10_scenario_share']=candidate.top10_scenarios/candidate.scenario_count
 candidate=candidate.sort_values(['top10_scenarios','rating'],ascending=False)
 candidate.to_csv(f'{P}/{kind}_scenario_stability.csv',index=False)
 # Season and competition splits for baseline top 20 and their leave-one-match-out worst drop
 top20=base[idcol].head(20).tolist();z=z[z[idcol].isin(top20)].copy()
 z.groupby([idcol,'season']).agg(n=('value','size'),matches=('match_id','nunique'),value=('value','sum')).reset_index().to_csv(f'{P}/{kind}_season_splits.csv',index=False)
 z.groupby([idcol,'comp']).agg(n=('value','size'),matches=('match_id','nunique'),value=('value','sum')).reset_index().to_csv(f'{P}/{kind}_competition_splits.csv',index=False)
 mg=z.groupby([idcol,'match_id']).agg(n=('value','size'),value=('value','sum')).reset_index()
 worst=mg.sort_values('value',ascending=False).drop_duplicates(idcol).rename(columns={'n':'best_match_n','value':'best_match_value','match_id':'best_match_id'})
 loo=base[base[idcol].isin(top20)].merge(worst,on=idcol)
 loo['rating_without_best_match']=6*(loo.total-loo.best_match_value)/(loo.n-loo.best_match_n+90)
 loo['rating_drop']=loo.rating-loo.rating_without_best_match
 loo.to_csv(f'{P}/{kind}_best_match_influence.csv',index=False)
 # comparison first half vs second half of period: descriptive, requiring match coverage
 z['period']=np.where(z.match_date if 'match_date' in z else False, '','') if False else 'unused'
 print('\n',kind,'baseline n',len(base),'top10\n',base.head(10)[['name','n','matches','rating']].round(3).to_string(index=False))
 print('stability\n',candidate.head(15)[['name','rank','top10_scenarios','scenario_count','top10_scenario_share']].to_string(index=False))
pd.DataFrame(summary).to_csv(f'{P}/scenario_summary.csv',index=False)
# Pressure coverage comparison
coverage=[]
for model in models:
 for threshold in [.48,.55,.62]:
  for phase_name,g in d.groupby('phase'):
   coverage.append(dict(model=model,threshold=threshold,phase=phase_name,deliveries=len(g),high=int((g['pressure_'+model]>=threshold).sum()),share=float((g['pressure_'+model]>=threshold).mean())))
pd.DataFrame(coverage).to_csv(f'{P}/pressure_definition_coverage.csv',index=False)
# Write machine-readable metadata
with open(f'{P}/analysis_details.json','w') as f:json.dump({'input_rows':len(d),'model_definitions':models,'scenarios_per_role':{'bat':36,'bowl':37},'method':'reuse phase2 prior-date baselines; compare pressure score variants and wicket values; 10-match eligibility in principal comparison','extra_penalty':'minimum one run per wide/no-ball when pressure>=.55, not complete extras accounting'},f,indent=2)
with zipfile.ZipFile('/mnt/data/phase3_sensitivity_package.zip','w',compression=zipfile.ZIP_DEFLATED) as ar:
 for filename in os.listdir(P):
  if filename.endswith(('.csv','.json','.md','.py')):ar.write(f'{P}/{filename}',arcname='phase3/'+filename)
