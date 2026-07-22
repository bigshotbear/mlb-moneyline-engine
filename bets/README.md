# MLB Moneyline Engine — Version 7

Version 7 replaces equal indicator counting with a 30-indicator weighted
scoring system.

## Main screen

The app now shows:

1. Selected matchup
2. Provisional Matchup Score for both teams
3. Data coverage
4. Number of active edges
5. Top five strongest reasons only

## Thirty raw indicators

The background model tracks:

- 8 starting-pitcher checks
- 9 offense / confirmed-lineup checks
- 6 bullpen checks
- 4 defense / hidden-run checks
- 2 context checks
- 1 no-vig price-edge check

Unavailable indicators remain inside the background catalog and lower the
coverage percentage. They do not create gray clutter.

## Strength scale

Every available indicator receives:

- Direction: away team, home team, or neutral
- Strength: 0 to 100
- Maximum point value
- Weighted point contribution
- Family assignment

## Correlation control

Related indicators are capped by family:

- Starter: 25 points
- Offense: 25 points
- Bullpen: 20 points
- Defense / hidden runs: 10 points
- Context: 10 points
- Market: 10 points

This prevents ERA, WHIP, K/BB, and other related measures from behaving like
fully independent votes.

## Final score

The result is shown as two scores that total 100. It is a relative matchup
score, not a calibrated win probability.

## Full transparency

The main tab shows only the Top 5. The Full Score tab includes family
contributions and an expandable table containing all 30 indicators.
