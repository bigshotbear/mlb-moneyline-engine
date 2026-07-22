# MLB Moneyline Engine — Version 8

Version 8 adds the two final workflow pages requested.

## Best Bets

- Scores the entire current MLB slate
- Sorts games strongest to weakest
- Shows Top 5 or Full Slate
- Writes the selection as:
  `Boston Red Sox moneyline over Baltimore Orioles because...`
- Displays raw score, coverage-adjusted score, data coverage, price, and label
- Pulls incomplete raw scores toward 50 so low-coverage matchups do not look
  overwhelmingly strong

## Parlays

Creates provisional combinations only when enough games clear adjustable:

- Minimum adjusted score
- Minimum coverage

Possible cards:

- Top 2-Leg
- Top 3-Leg
- Value 2-Leg

It shows combined odds and identifies the weakest leg. It will display no
parlay when too few games pass.

## Live Center

The live screen uses MLB's live game feed and refreshes every 20 seconds:

- Score
- Inning and half-inning
- Outs
- Balls and strikes
- Base runners
- Current batter
- Current pitcher
- Latest play
- Official lineup detection
- Live-feed connected status

The live screen no longer waits for all 30 pregame indicators before showing
usable information.

## Live odds

Live odds are refreshed manually to protect the free Odds API monthly credits.
MLB live game state keeps auto-refreshing without consuming those credits.

## Live watch rules

The screen includes transparent, unvalidated watch labels:

- Better-Price Watch
- Live Entry Watch
- Do Not Chase
- Late Comeback Risk
- Monitor

These are rule-based research prompts, not trained live win probabilities.
