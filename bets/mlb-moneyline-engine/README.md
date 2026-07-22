# MLB Moneyline Engine — Version 2

Version 2 removes almost all daily manual entry.

## Automatic now

- MLB moneylines and no-vig probabilities
- Probable pitchers
- Pitcher season W-L record, ERA, WHIP, starts, innings, strikeouts, and walks
- Official starting lineups after MLB posts them
- Bullpen pitch and inning workload over the previous three days
- Reliever-level workload and consecutive-day use
- Timestamped snapshots
- Optional permanent Supabase storage

## Still manual only for unusual information

- Announced reliever unavailability
- Injuries or soreness
- Pitch-count restrictions
- Late scratches
- Manager comments

## Update the current GitHub repository

Your repository contains a nested `mlb-moneyline-engine` folder.

1. Extract the ZIP.
2. Open the existing `mlb-moneyline-engine` folder inside GitHub.
3. Choose **Add file → Upload files**.
4. Upload the contents of the extracted `mlb-moneyline-engine` folder.
5. Commit the replacements.
6. Render should auto-deploy.

## Permanent Supabase storage

1. In Supabase, open **SQL Editor → New query**.
2. Paste and run `supabase/setup.sql`.
3. In Render Environment, add:

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
```

Never put the service-role key in GitHub or chat.

## Existing Render settings

Root directory:

```text
mlb-moneyline-engine
```

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port $PORT
```

## Limitation

The app still produces no official bet recommendation. The next phase is historical feature construction and walk-forward validation.
