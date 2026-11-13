"""Reproducible descriptive EDA from validated fields, without inventing team runs."""
from pathlib import Path
import pandas as pd, numpy as np
P=Path('/mnt/data');O=P/'phase1_outputs';O.mkdir(exist_ok=True)
b=pd.read_csv(P/'ball_by_ball.csv',low_memory=False)
m=pd.read_csv(P/'matches.csv');c=pd.read_csv(P/'competitions.csv')
b=b.merge(m[['match_id','comp_id','venue_id','match_date','revised_target']],on='match_id',validate='many_to_one').merge(c[['comp_id','comp_name','match_format']],on='comp_id',validate='many_to_one')
b=b[(b.match_format.eq('T20I')|b.comp_name.str.match(r'^IPL\s+20\d{2}$',case=False,na=False))&b.innings.le(2)].copy()
b['phase']=np.select([b.overid.le(6),b.overid.le(15)],['Powerplay (1-6)','Middle (7-15)'],default='Death (16-20)')
b['legal']=(~b.extras_type.isin(['wide','Overstep','other'])).astype('int8')
b['bowler_wicket']=(b.is_wicket & b.dismissal_type.isin(['Caught','Bowled','LBW','Stump','Hit Wicket'])).astype(int)
b['boundary']=b.is_four|b.is_six
phase=b.groupby(['match_format','phase'],observed=True).agg(deliveries=('runs','size'),legal_balls=('legal','sum'),batter_runs=('runs','sum'),bowler_wickets=('bowler_wicket','sum'),boundaries=('boundary','sum'),matches=('match_id','nunique')).reset_index()
phase['batter_runs_per_six_legal_balls']=phase.batter_runs/phase.legal_balls*6
phase['bowler_wickets_per_120_legal_balls']=phase.bowler_wickets/phase.legal_balls*120
phase.to_csv(O/'phase_batter_runs_summary.csv',index=False)
style=b.groupby(['match_format','phase','pace_or_spin'],dropna=False,observed=True).agg(deliveries=('runs','size'),legal_balls=('legal','sum'),batter_runs=('runs','sum'),bowler_wickets=('bowler_wicket','sum'),matches=('match_id','nunique')).reset_index()
style['batter_runs_per_six_legal_balls']=style.batter_runs/style.legal_balls*6
style.to_csv(O/'bowling_style_phase_summary.csv',index=False)
# No exact innings totals; only scoring proxy and wickets.
venue=b.groupby(['venue_id','match_format'],dropna=False).agg(deliveries=('runs','size'),legal_balls=('legal','sum'),batter_runs=('runs','sum'),team_wicket_events=('is_wicket','sum'),matches=('match_id','nunique')).reset_index()
venue['batter_runs_per_six_legal_balls']=venue.batter_runs/venue.legal_balls*6
venue['venue_sample_flag']=np.where(venue.matches>=10,'10+ matches',np.where(venue.matches>=5,'5-9 matches','<5 matches'))
venue.to_csv(O/'venue_coverage_scoring_proxy.csv',index=False)
# Historical sample assessment, not the actual eligibility threshold
bat=b.groupby(['striker_id','striker_name','match_format']).agg(deliveries_faced=('legal','sum'),recorded_deliveries=('runs','size'),batter_runs=('runs','sum'),matches=('match_id','nunique')).reset_index()
# official balls faced include no-balls, but not wides: use this for eligibility
b['balls_faced']=(b.extras_type!='wide').astype('int8')
bat=b.groupby(['striker_id','striker_name','match_format']).agg(balls_faced=('balls_faced','sum'),batter_runs=('runs','sum'),matches=('match_id','nunique')).reset_index()
bol=b.groupby(['bowler_id','bowler_name','match_format']).agg(legal_balls=('legal','sum'),bowler_wickets=('bowler_wicket','sum'),matches=('match_id','nunique')).reset_index()
bat.to_csv(O/'batter_sample_sizes.csv',index=False);bol.to_csv(O/'bowler_sample_sizes.csv',index=False)
print('primary regular matches',b.match_id.nunique(),'deliveries',len(b),'venues',b.venue_id.nunique())
print('phase:',phase[['match_format','phase','legal_balls','batter_runs_per_six_legal_balls','bowler_wickets']].to_string(index=False))
print('venue sample groups:',venue.venue_sample_flag.value_counts().to_dict())
print('batters with >=100 balls',bat.groupby('striker_id').balls_faced.sum().ge(100).sum(),'all batters',bat.striker_id.nunique())
print('bowlers >=120 legal deliveries',bol.groupby('bowler_id').legal_balls.sum().ge(120).sum(),'all bowlers',bol.bowler_id.nunique())
