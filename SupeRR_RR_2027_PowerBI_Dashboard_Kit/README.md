# SupeRR Selector | RR 2027 — Power BI-ready dashboard package

## Deliverables
- `RR_2027_Interactive_Dashboard.html`: **working offline interactive dashboard**, with player explorer, IDs, pressure stats, RR fit, and historical IPL champions chart; open it in any browser. **This is not a native Power BI `.pbix` file.**
- `Players.csv`: 20 ranked players; unique key `Category + PlayerID`, performance and qualitative fit fields.
- `PlayerSeason.csv`: pressure-match observations by season/competition; relation `Players[PlayerID] (1) -> PlayerSeason[PlayerID] (many)`.
- `ChampionsBenchmark.csv`: champion-year phase aggregates. The champion seasons are 2022 Gujarat Titans; 2023 Chennai Super Kings; 2024 Kolkata Knight Riders; 2025 and 2026 Royal Challengers Bengaluru.
- `ChampionTraits.csv`: qualitative role similarities, with caveats and limits.
- `RR_2026_Core_Reference.csv`: select verified 2026 RR incumbent roles; **not** a final 2027 retained squad.
- `PowerBI_DAX_Measures.txt`: measures to copy to Power BI.
- `PowerBI_Build_Guide.md`: instructions, relationships and recommended visuals.

## Source/provenance
- Numerics: organizer-provided CSVs and Phase 2/4 modeling outputs from this project.
- RR 2026 squad: https://www.rajasthanroyals.com/latest-news/ipl-2026-rr-players-retention-list ; https://www.cricbuzz.com/cricket-series/ipl-2026/auction/teams/64
- Champions: https://www.iplt20.com/ (past winners); https://www.iplt20.com/news/article/tata-ipl-2026-final-rcb-v-gt-match-report

## Limitations and risk
- The data has incomplete numeric extras. Batting runs, inferred team totals and bowling economy must not be represented as verified official scorecard totals. The supplied bowling proxy counts batter runs conceded, not all runs conceded.
- Historical 'champion patterns' are descriptive **champion-team season phase aggregates** and qualitative archetypes. Without a non-champion comparison they do not prove champions have statistically unique traits, nor that acquiring any player will lead to winning.
- The model is a heuristic pressure proxy based on phase, wickets lost and recent wickets, not win probability or required run rate.
- Pressure ratings are not raw strike rates/economies, and rating weights are not statistically calibrated.
- Pakistan players were excluded from the proposed shortlist per user direction; this is a user-specific filter, not an organizer eligibility rule.
- Auction release, price, remaining purse and 2027 registration/retention unknown as of 13 Nov 2026.
- Player data was measured across IPL and T20I; no claim that overall ranks equal IPL-only rankings.
