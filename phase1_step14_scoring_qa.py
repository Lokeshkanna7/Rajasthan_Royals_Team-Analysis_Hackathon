"""Phase 1 scoring QA. No inferred totals are labeled exact.
Run: python /mnt/data/phase1_step14_scoring_qa.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path('/mnt/data'); OUT=ROOT/'phase1_outputs';OUT.mkdir(exist_ok=True)
b=pd.read_csv(ROOT/'ball_by_ball.csv',low_memory=False)
m=pd.read_csv(ROOT/'matches.csv',low_memory=False)
c=pd.read_csv(ROOT/'competitions.csv',low_memory=False)
b=b.sort_values(['match_id','innings','innings_ball_num'],kind='stable').reset_index(drop=True)
for col in ['runs','is_wicket','innings','overid','over_ball_num']:
    assert b[col].notna().all(),col
# 'other' acts as an additional nonlegal category judging by within-over reconciliation.
nonlegal={'wide','Overstep','other'}
b['legal_ball_provisional']=(~b.extras_type.isin(nonlegal)).astype('int8')
b['minimum_extra_runs']=(b.extras_type.isin(nonlegal)).astype('int8')+b.extras_2_runs.fillna(0).astype('int16')
# Extra type byes, legbyes, penalty and wide may carry run amounts not represented in the feed.
# An innings is exactly reconstructable up to a given point only if no events of any extra type occurred.
b['any_extra_event']=b.extras_type.notna().astype('int8')
b['bowler_wicket']=((b.is_wicket)&b.dismissal_type.isin(['Caught','Bowled','LBW','Stump','Hit Wicket'])).astype('int8')
b['runout_wicket']=((b.is_wicket)&(b.dismissal_type=='RunOut')).astype('int8')
key=['match_id','innings'];g=b.groupby(key,sort=False)
for col,source in [('legal_balls_before','legal_ball_provisional'),('wickets_before','is_wicket'),('batter_runs_before','runs'),('minimum_extras_before','minimum_extra_runs'),('extra_events_before','any_extra_event')]:
    b[col]=g[source].cumsum()-b[source].astype(int)
b['team_runs_lower_bound_before']=b.batter_runs_before+b.minimum_extras_before
b['team_score_exact_before']=(b.extra_events_before==0)
b['legal_balls_remaining_standard']=np.where(b.innings<=2,120-b.legal_balls_before,np.nan)
# Known metadata only, not target derived from batter runs or final outcome.
meta_cols=['match_id','comp_id','match_date','venue_id','first_inn_revised_overs','second_inn_revised_overs','revised_target','knock_out','result','win_team_id']
b=b.merge(m[meta_cols],on='match_id',validate='many_to_one').merge(c[['comp_id','comp_name','match_format','season']],on='comp_id',validate='many_to_one')
b['primary_scope']=((b.match_format=='T20I')|b.comp_name.str.match(r'^IPL\s+20\d{2}$',case=False,na=False))
b['is_super_over']=b.innings>2
# analyze innings-wide confidence: exact if no extras in entire innings
inn=b.groupby(key,sort=False).agg(deliveries=('runs','size'),legal_balls=('legal_ball_provisional','sum'),batter_runs=('runs','sum'),min_extras=('minimum_extra_runs','sum'),extras_events=('any_extra_event','sum'),wickets=('is_wicket','sum'),bowler_wickets=('bowler_wicket','sum'),runs_on_no_ball=('runs',lambda x: 0)).reset_index().drop(columns='runs_on_no_ball')
inn['minimum_team_total']=inn.batter_runs+inn.min_extras
inn['score_exact_from_feed']=inn.extras_events.eq(0)
inn['is_super_over']=inn.innings.gt(2)
inn['too_many_legal_balls']=inn.legal_balls.gt(np.where(inn.is_super_over,6,120))
inn=inn.merge(m[['match_id','match_date','revised_target','first_inn_revised_overs','second_inn_revised_overs','result','comp_id']],on='match_id',validate='many_to_one')
inn=inn.merge(c[['comp_id','comp_name','match_format']],on='comp_id',validate='many_to_one')
inn['primary_scope']=inn.match_format.eq('T20I')|inn.comp_name.str.match(r'^IPL\s+20\d{2}$',case=False,na=False)
# over QA: the final *observed* over can be partial; others should have six legal balls, except disruptions.
ov=b.groupby(['match_id','innings','overid'],sort=False).agg(observed_deliveries=('runs','size'),legal_balls=('legal_ball_provisional','sum'),other_events=('extras_type',lambda x:x.eq('other').sum()),wide_events=('extras_type',lambda x:x.eq('wide').sum()),noball_events=('extras_type',lambda x:x.eq('Overstep').sum())).reset_index()
mx=ov.groupby(['match_id','innings']).overid.max().rename('final_observed_over').reset_index()
ov=ov.merge(mx,on=['match_id','innings'],validate='many_to_one')
ov['last_observed_over']=ov.overid.eq(ov.final_observed_over)
ov['overlength']=ov.legal_balls.gt(6)
ov['nonfinal_short']=ov.legal_balls.lt(6)&~ov.last_observed_over
# because incomplete innings also occur for rain and other causes, flag rather than correct
bad_over_keys=ov.loc[ov.overlength,['match_id','innings']].drop_duplicates()
bad_matches=set(bad_over_keys.match_id)
b['overlength_match_flag']=b.match_id.isin(bad_matches)
b['nonstandard_target_flag']=b.revised_target.notna()|b.first_inn_revised_overs.notna()|b.second_inn_revised_overs.notna()
b['score_status']=np.where(b.team_score_exact_before,'exact_batter_and_team_runs','lower_bound_only')
# 1st innings needs venue adjusted expected scores; second innings cannot infer a target precisely for most matches.
b['chase_target_available']=b.innings.eq(2)&b.revised_target.notna()
# For each match-innings initial extras before zero, but later in over grows incomplete
keep=['match_id','comp_id','comp_name','match_format','match_date','venue_id','innings','overid','over_ball_num','innings_ball_num','batting_team_id','bowling_team_id','striker_id','striker_name','bowler_id','bowler_name','runs','extras_type','extras_2_runs','is_wicket','dismissal_type','legal_ball_provisional','legal_balls_before','wickets_before','batter_runs_before','minimum_extras_before','team_runs_lower_bound_before','extra_events_before','team_score_exact_before','score_status','is_super_over','nonstandard_target_flag','overlength_match_flag','revised_target','chase_target_available','primary_scope']
b[keep].to_csv(OUT/'delivery_state_qa_v2.csv',index=False)
inn.to_csv(OUT/'innings_scoring_qa_v2.csv',index=False)
ov.to_csv(OUT/'overs_scoring_qa_v2.csv',index=False)
problems=b[(b.is_wicket)&b.dismissal_type.isna()|b.dismissed_player_id.notna()&~b.is_wicket][['match_id','innings','overid','over_ball_num','is_wicket','dismissal_type','dismissed_player_id']]
problems.to_csv(OUT/'wicket_record_anomalies.csv',index=False)
missing=set(m.match_id)-set(b.match_id)
missing_m=m[m.match_id.isin(missing)][['match_id','comp_id','match_date','result']]
missing_m.to_csv(OUT/'matches_without_deliveries.csv',index=False)
summary={
'deliveries':len(b),'matches_with_deliveries':b.match_id.nunique(),'match_records':len(m),'matches_without_deliveries':len(missing),
'primary_scope_matches':b[b.primary_scope].match_id.nunique(),'other_T20_matches':b[~b.primary_scope].match_id.nunique(),
'innings_total':len(inn),'full_innings_with_no_extra_events':int(inn.score_exact_from_feed.sum()),
'balls_with_precise_prior_team_score':int(b.team_score_exact_before.sum()),'balls_with_uncertain_prior_team_score':int((~b.team_score_exact_before).sum()),
'overlength_overs':int(ov.overlength.sum()),'nonfinal_short_overs':int(ov.nonfinal_short.sum()),
'overlength_matches':sorted(bad_matches),'wicket_anomalies':len(problems),
'revised_target_matches':int(m.revised_target.notna().sum()),'chase_delivery_rows_with_revised_target':int(b.chase_target_available.sum()),
'innings_10plus_wickets':int(inn.wickets.ge(10).sum()),'innings_11plus_wickets':int(inn.wickets.gt(10).sum()),
'legal_balls_standard_over120':int(inn[(inn.innings<=2)&(inn.legal_balls>120)].shape[0]),
'extras_cats':b.extras_type.value_counts(dropna=False).to_dict(),
'overs_distribution':ov.legal_balls.value_counts().sort_index().to_dict(),
'outlier_over_rows':ov[ov.overlength].to_dict('records')
}
import json
(OUT/'step14_summary.json').write_text(json.dumps(summary,indent=2,default=str))
print(json.dumps(summary,indent=2,default=str))
