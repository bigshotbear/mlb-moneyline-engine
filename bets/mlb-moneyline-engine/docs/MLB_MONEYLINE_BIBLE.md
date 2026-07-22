# MLB Moneyline Engine — Research Bible

## Version 2 automation

- Official MLB lineup detection after lineups are posted
- Probable-pitcher IDs and current season records
- Current ERA, WHIP, starts, innings, strikeouts, and walks
- Team bullpen workload over the previous three days
- Reliever-level workload and consecutive-day use
- Optional permanent Supabase storage
- Manual entry reduced to unusual late-news overrides

## Seven provisional signal families

1. Starting-pitcher projection
2. Starter-versus-confirmed-lineup matchup
3. Confirmed-lineup strength and lineup shock
4. High-leverage bullpen asymmetry
5. Catching, baserunning, and hidden runs
6. Batted-ball and defensive interaction
7. Situational and roster context

## Rules

- No fabricated thresholds, coefficients, win rates, or confidence bands.
- An 11-1 pitcher record is supporting evidence, not a standalone trigger.
- Bullpen workload does not automatically prove a reliever is unavailable.
- No recommendations until calibration, CLV, Brier/log loss, and out-of-sample profitability are evaluated.
