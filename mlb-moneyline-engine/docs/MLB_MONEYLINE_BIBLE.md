# MLB Moneyline Engine — Research Bible

## Mission

Build a moneyline-only research tool that starts from the sportsbook's no-vig
market probability, measures new and asymmetric matchup information, and outputs
a calibrated win probability only after historical validation.

## Non-negotiable rules

1. AI agreement is a working hypothesis, not validation.
2. Do not fabricate correlations, coefficients, win rates, VIFs, thresholds, or confidence bands.
3. Related statistics belong in signal families so they do not receive duplicate votes.
4. Opening no-vig market probability is the prior, not a predictive pillar.
5. Current price is a separate decision gate.
6. Reverse line movement is context, not an analytical vote.
7. CLV matters, but validation also includes calibration, Brier score, log loss,
   out-of-sample EV/ROI, sample size, and uncertainty.
8. Historical features must be frozen at the true pregame timestamp.
9. An 11-1 record is supporting context, not an automatic trigger.
10. Many raw inputs may be used without treating them as independent signals.

## Seven provisional signal families

1. Starting-pitcher projection
2. Starter-versus-confirmed-lineup matchup
3. Confirmed-lineup strength and lineup shock
4. High-leverage bullpen asymmetry
5. Catching, baserunning, and hidden runs
6. Batted-ball and defensive interaction
7. Situational and roster context

## Outside the seven

- Opening no-vig probability: market baseline
- Current no-vig probability: comparison point
- Expected value: decision output
- Reverse line movement: market context
- Closing line value: evaluation
- Final result: target
- Unit size: undefined until validation

## Current build

The application collects live MLB moneylines, calculates no-vig market
probabilities, loads probable pitchers when available, accepts manually verified
lineups and bullpen status, and saves timestamped snapshots.

It intentionally produces no official betting recommendation.
