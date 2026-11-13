import pandas as pd, numpy as np, os, json, zipfile
O='/mnt/data/phase2_refined';os.makedirs(O,exist_ok=True)
raw=pd.read_csv('/mnt/data/ball_by_ball.csv',low_memory=False)
feat=pd.read_csv('/mnt/data/phase2_outputs/pressure_delivery_features.csv',low_memory=False)
# one-to-one delivery join on the complete event key
keys=['match_id','innings','innings_ball_num']
assert not raw.duplicated(keys).any() and not feat.duplicated(keys).any()
cols=keys+['is_wicket','dismissal_type','dismissed_player_id','pace_or_spin']
d=feat.merge(raw[cols],on=keys,how='left',validate='one_to_one')
assert len(d)==len(feat)
d=d.loc[d.pressure_state_valid].copy()
d['match_date']=pd.to_datetime(d.match_date)
d['bowler_credit']=d.dismissal_type.isin(['Caught','Bowled','LBW','Stump','Hit Wicket'])
d['batter_dismissed']=d.dismissed_player_id.eq(d.striker_id) & d.dismissal_type.notna()
d['legal']=d.legal.astype(bool)
d['ball_faced']=~d.extras_type.eq('wide') # potentially 'other' nonlegal, yes faced if recorded as nonwide
# score only deliveries with strictly known batting runs, matching their denominators
# bowling legal deliveries only; wides/no-balls excluded as extras amounts unavailable
d['score_batting']=d.ball_faced
d['score_bowling']=d.legal
# define pressure before ball using only prior wicket stats, phase and legal counts
phase={'powerplay':0.12,'middle':0.22,'death':0.36}
d['pressure_v2']= (d.phase.map(phase) + .42*np.minimum(d.wickets_before.clip(lower=0)/7,1)+ .28*np.minimum(d.recent_wickets_12_deliveries.clip(lower=0)/2,1)).clip(0,1)
d['wband']=pd.cut(d.wickets_before,[-1,2,5,20],labels=['0-2','3-5','6+']).astype(str)
d['comp']=d.competition_group
# feature rate for each row with prior DATE ONLY history (context and comp-phase fallback)
# separate denominators and wicket definitions for batting/bowling, do not score non-opportunities
# no same-date leakage; warmup 10 prior matches in respective competition required
for task,flag,outcome,wk in [('bat','score_batting','runs','batter_dismissed'),('bowl','score_bowling','runs','bowler_credit')]:
    e=d.loc[d[flag],['match_date','comp','phase','innings','wband',outcome,wk]].copy()
    e['n']=1;e['run_sum']=e[outcome];e['wk_sum']=e[wk].astype(float)
    base=['comp','phase']
    detail=['comp','phase','innings','wband']
    def history(groupcols,prefix):
        z=e.groupby(groupcols+['match_date'],observed=True)[['n','run_sum','wk_sum']].sum().reset_index().sort_values('match_date')
        for x in ['n','run_sum','wk_sum']:
            z[prefix+x]=z.groupby(groupcols,observed=True)[x].cumsum()-z[x]
        return z[groupcols+['match_date']+[prefix+x for x in ['n','run_sum','wk_sum']]]
    h1=history(base,'base_');h2=history(detail,'detail_')
    d=d.merge(h1,on=base+['match_date'],how='left',validate='many_to_one')
    d=d.merge(h2,on=detail+['match_date'],how='left',validate='many_to_one')
    b_n=d['base_n'].fillna(0); b_run=d.base_run_sum.fillna(0); b_wk=d.base_wk_sum.fillna(0)
    t_n=d.detail_n.fillna(0);t_run=d.detail_run_sum.fillna(0);t_wk=d.detail_wk_sum.fillna(0)
    # prior base phase conditioned on comp, shrink to broad cricket default
    prior_run=(b_run+200*1.2)/(b_n+200)
    prior_wk=(b_wk+200*.045)/(b_n+200)
    d['exp_'+task+'_runs']=(t_run+120*prior_run)/(t_n+120)
    d['exp_'+task+'_wk']=(t_wk+120*prior_wk)/(t_n+120)
    d['history_'+task]=b_n
    d.drop(columns=[f'{q}_{c}' for q in ['base','detail'] for c in ['n','run_sum','wk_sum']],inplace=True)
# score on eligible historical warmup (50 previous comp-phase opportunities)
d['valid_bat']=d.score_batting & d.history_bat.ge(50)
d['valid_bowl']=d.score_bowling & d.history_bowl.ge(50)
# apply phase-balanced pressure threshold, capping contribution of a few matches later
WICKET_VALUE=7.0
d['bat_value']= np.where(d.valid_bat,(d.runs-d.exp_bat_runs)-WICKET_VALUE*(d.batter_dismissed.astype(float)-d.exp_bat_wk),0.)
d['bowl_value']=np.where(d.valid_bowl,(d.exp_bowl_runs-d.runs)+WICKET_VALUE*(d.bowler_credit.astype(float)-d.exp_bowl_wk),0.)
# team runs from wide/no-ball and bye are missing, explicit limit
threshold=.55
d['high_pressure_v2']=d.pressure_v2>=threshold
# export delivery table; limit columns to directly needed
outcols=keys+['match_date','comp','phase','striker_id','striker_name','bowler_id','bowler_name','runs','extras_type','legal','wickets_before','recent_wickets_12_deliveries','pressure_v2','high_pressure_v2','exp_bat_runs','exp_bat_wk','exp_bowl_runs','exp_bowl_wk','batter_dismissed','bowler_credit','valid_bat','valid_bowl','bat_value','bowl_value']
d[outcols].to_csv(O+'/pressure_features_refined.csv',index=False)

def rank(kind,thresh=.55, subset=None):
    player='striker_id' if kind=='bat' else 'bowler_id'; name='striker_name' if kind=='bat' else 'bowler_name';valid='valid_bat' if kind=='bat' else 'valid_bowl';val='bat_value' if kind=='bat' else 'bowl_value';other='batter_dismissed' if kind=='bat' else 'bowler_credit'
    z=d if subset is None else d.loc[subset]
    z=z.loc[z[valid]].copy();z['pressure_flag']=z.pressure_v2.ge(thresh)
    high=z[z.pressure_flag].groupby(player).agg(player_name=(name,'first'),high_n=(val,'size'),high_matches=('match_id','nunique'),high_value=(val,'sum'),high_wickets=(other,'sum'),high_runs=('runs','sum')).reset_index()
    alln=z.groupby(player).agg(total_n=(val,'size'),total_matches=('match_id','nunique')).reset_index()
    result=high.merge(alln,on=player)
    result['rating_per_6_shrunk']=6*result.high_value/(result.high_n+90)
    eligible=(result.high_n.ge(45 if kind=='bat' else 60)&result.high_matches.ge(5)&result.total_n.ge(100 if kind=='bat' else 120))
    result['eligible']=eligible
    return result.sort_values('rating_per_6_shrunk',ascending=False).reset_index(drop=True)

stats={}
for kind in ['bat','bowl']:
    r=rank(kind);r.to_csv(O+f'/{kind}_rankings_exploratory.csv',index=False)
    print('\n',kind,'eligible',r.eligible.sum());print(r[r.eligible].head(12)[['player_name','high_n','high_matches','high_value','high_wickets','rating_per_6_shrunk']].to_string(index=False))
    stats[kind+'_eligible']=int(r.eligible.sum())
    # rank overlap scenario different weights threshold values and separate comps
    top=set(r[r.eligible].head(10).iloc[:,0]);sen=[]
    for t in [.48,.52,.55,.60,.65]:
        rt=rank(kind,t);top2=set(rt[rt.eligible].head(10).iloc[:,0]);sen.append(dict(threshold=t,eligible=int(rt.eligible.sum()),top10_overlap=len(top&top2)))
    pd.DataFrame(sen).to_csv(O+f'/{kind}_threshold_sensitivity.csv',index=False)
    print('threshold sensitivity',sen)
# uncertainty: cluster bootstrap 200 replicates among pressure matches, rank frequency among initially eligible top20 and overall eligible
rng=np.random.default_rng(831)
for kind in ['bat','bowl']:
    pid='striker_id' if kind=='bat' else 'bowler_id'; val='bat_value' if kind=='bat' else 'bowl_value';valid='valid_bat' if kind=='bat' else 'valid_bowl'
    base=rank(kind); allowed=base.loc[base.eligible,pid].to_numpy();z=d.loc[d[valid] & d.high_pressure_v2 & d[pid].isin(allowed),['match_id',pid,val]]
    matchids=z.match_id.unique(); pidix={p:i for i,p in enumerate(allowed)};midix={m:i for i,m in enumerate(matchids)}
    a=np.zeros((len(matchids),len(allowed)),dtype=float); n=np.zeros_like(a)
    for (m,p),g in z.groupby(['match_id',pid]):
        i=midix[m];j=pidix[p];a[i,j]=g[val].sum();n[i,j]=len(g)
    frequency=np.zeros(len(allowed));means=np.zeros((200,len(allowed)))
    for rep in range(200):
        weights=rng.multinomial(len(matchids),np.full(len(matchids),1/len(matchids)))
        av=weights@a;nv=weights@n;ratings=6*av/(nv+90)
        means[rep]=ratings;frequency[np.argsort(-ratings)[:10]]+=1
    summary=pd.DataFrame({pid:allowed,'bootstrap_top10_frequency':frequency/200,'ci_05':np.quantile(means,.05,axis=0),'ci_95':np.quantile(means,.95,axis=0)})
    base=base.merge(summary,on=pid,how='left');base.to_csv(O+f'/{kind}_ranking_with_uncertainty.csv',index=False)
    print('\nbootstrap',kind);print(base[base.eligible].head(10)[['player_name','rating_per_6_shrunk','bootstrap_top10_frequency','ci_05','ci_95']].round(3).to_string(index=False))
    stats[kind+'_top10_mean_frequency']=round(float(base[base.eligible].head(10).bootstrap_top10_frequency.mean()),3)
# pressure distribution by phase; early collapse coverage
p=d.groupby(['phase','comp']).agg(deliveries=('match_id','size'),high_pressure=('high_pressure_v2','sum')).reset_index();p['share']=p.high_pressure/p.deliveries;p.to_csv(O+'/pressure_coverage.csv',index=False)
print('\ncoverage\n',p.to_string(index=False))
print('Early powerplay high',int((d.phase.eq('powerplay')&d.high_pressure_v2).sum()))
# Split competition top results descriptive, no fixed rating due to few samples
for kind in ['bat','bowl']:
    full=rank(kind); top=set(full[full.eligible].head(10).iloc[:,0]);pcol='striker_id' if kind=='bat' else 'bowler_id'; vv='bat_value' if kind=='bat' else 'bowl_value'; f='valid_bat' if kind=='bat' else 'valid_bowl';x=d.loc[d.high_pressure_v2 & d[f] & d[pcol].isin(top)].groupby([pcol,'comp']).agg(n=(vv,'size'),sum_value=(vv,'sum')).reset_index();x['raw_value_per_6']=6*x.sum_value/x.n;x.to_csv(O+f'/{kind}_competition_splits.csv',index=False)
with open(O+'/run_statistics.json','w') as f: json.dump({'input_deliveries':len(d),'pressure_deliveries':int(d.high_pressure_v2.sum()),'pressure_share':round(float(d.high_pressure_v2.mean()),4),'weight_wicket':WICKET_VALUE,'threshold':threshold,**stats},f,indent=2)
with zipfile.ZipFile('/mnt/data/phase2_refined_package.zip','w',zipfile.ZIP_DEFLATED) as z:
 for f in os.listdir(O):z.write(O+'/'+f,'phase2_refined/'+f)
 z.write('/mnt/data/phase2_refine.py','phase2_refine.py')
