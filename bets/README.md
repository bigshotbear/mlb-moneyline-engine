# MLB Moneyline Engine — Version 5

Version 5 matches the requested command-center layout.

## Main layout

- Left sidebar: today's MLB games
- Selected matchup header: both teams, moneylines, pitchers, and records
- Seven green / gray / red lights across the top
- Hover on desktop or tap on mobile to see why a light has that color
- Four adjacent tabs:
  - Scorecard
  - Eye Test
  - Who Wins
  - Game Details

## Scorecard

Shows all seven indicators with:

- HIT
- RISK
- PENDING
- NEUTRAL

Choose either team as the scorecard perspective.

## Eye Test

Shows both clubs side by side with:

- Moneyline
- Starting pitcher
- Pitcher record and ERA
- Batting: season / 30 days / 7 days
- Starting pitching: season / 30 days / 7 days
- Bullpen: season / 30 days / 7 days
- Hot / steady / cooling trends

## Who Wins

Shows:

- Green current lean
- Gray too close
- Red on the team with fewer supporting indicators
- Indicator support counts for both teams

This is intentionally labeled as a preliminary lean, not a trained win probability.

## Upload

Extract the ZIP and upload the files directly into:

`bets/mlb-moneyline-engine`

Then deploy the latest commit in Render.
