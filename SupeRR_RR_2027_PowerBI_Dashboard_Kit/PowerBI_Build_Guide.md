# How to make the native Power BI report (.pbix)

**This package is Power BI-ready data + an immediately working HTML dashboard, NOT a compiled .pbix or a published Power BI URL.** Power BI Desktop is required to author/save a native .pbix and Power BI Service permissions are required to publish a live link.

1. Extract the ZIP in a permanent folder. Open Power BI Desktop > Get data > Text/CSV; import `Players.csv`, `PlayerSeason.csv`, `ChampionsBenchmark.csv`, `ChampionTraits.csv`, `RR_2026_Core_Reference.csv`.
2. Set `Players[PlayerID]` and `PlayerSeason[PlayerID]` to whole-number data; `Season` text (some T20I seasons span years, e.g. 2022/23); rank/pressure opportunities whole number; rating and stability decimal; text fields text. If desired create a sort index using `Category` and `Rank`.
3. Model view: relate `Players[PlayerID]` (one) to `PlayerSeason[PlayerID]` (many), single-direction filter. `ChampionsBenchmark`, `ChampionTraits`, and `RR_2026_Core_Reference` are intentionally disconnected comparison/reference tables. Avoid cross-filtering them into player ratings by mistake.
4. Modeling > New measure: paste each expression from `PowerBI_DAX_Measures.txt` separately. Format stability as percentage.
5. Page 1, **Scout overview**: cards for Shortlisted Players, Pressure Opportunities, Mean Pressure Rating; clustered bar of Players[PlayerName] vs Players[PressureRating], small multiples by Category; slicers on Category and RRRole; player table with PlayerID, PressureMatches, ScenarioShare, RRFit.
6. Page 2, **Player detail**: slicer on PlayerName or PlayerID; cards PressureRating, PressureMatches, RatingWithoutBestMatch; table PlayerSeason[Season, MatchFormat, PressureOpportunities, PressureValue]; multiline table with RRContribution, RRFit, AuctionCaveat. Use a tooltip/report-page drillthrough filtered by PlayerID.
7. Page 3, **Champions**: matrix of Season, Champion and Phase; columns or clustered bars of Champion Batting Runs Per Six, Champion Batter-Runs Conceded Per Six, Champion Credited Wickets Per 100. Keep the three measures in separate visuals to avoid treating unlike units as the same scale.
8. Page 4, **RR squad strategy**: ChampionTraits matrix (ChampionTrait, RRExistingCore, SuggestedCandidates, FitTradeoff); RR core table; caution text about conditional 2027 availability and 4 overseas XI slots.
9. Format in dark navy / pink (#101E30 / #BD314E) with pale background (#F2F5F9), set dates/fields to correct types and validate filters.
10. Save as `SupeRR_RR_2027.pbix`. Only after this can you publish to Power BI Service and obtain a shareable dashboard/report URL.

## Verification checklist
- Player data contains exactly 20 rows, IDs match supplied original ball-by-ball/selection files.
- Power BI visuals label innings scoring as batter-run proxies, not official team runs/economy.
- RR 2026 core is labeled reference, not guaranteed 2027 retained roster.
- A role overlap is NOT an objective win probability and a candidate is NOT declared auction-available.
- Champions are winning franchises from 2022 through 2026; benchmark is their season's games, not solely finals.
- Players can have IPL + T20I source observations even if a proposed role is IPL-focused.
