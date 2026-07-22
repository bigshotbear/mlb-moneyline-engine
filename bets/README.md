# MLB Moneyline Engine — Version 3

Version 3 redesigns the home screen around how the tool will actually be used.

## New home screen

### Basic / Eye Test

Every matchup appears as a card with:

- Normal Eastern time instead of UTC/military time
- Both moneylines
- Probable starting pitcher under each team
- Pitcher W-L record and ERA
- MLB batting rank for the season, last 30 days, and last 7 days
- MLB starting-pitching rank for the same three windows
- MLB bullpen rank for the same three windows
- Hot, steady, or cooling trend label

### Indicators

Every game also has an indicator card showing the preliminary team direction
for the data layers currently available.

These directions are not official model hits and do not create a betting
recommendation.

## Detailed Game View

The expensive daily data is loaded for one selected game:

- Official lineups
- Bullpen pitch workload over the previous three days
- Reliever-level workload
- Bookmaker prices
- Optional late-news override
- Timestamped snapshot saving

## Upload this update without creating another nested folder

This ZIP contains the project files directly.

1. Extract the ZIP.
2. In GitHub, open the exact folder Render uses:
   `bets/mlb-moneyline-engine`
3. Click **Add file → Upload files**.
4. Upload the extracted files and folders directly there.
5. `app.py`, `src`, `README.md`, and other existing files should be replaced.
6. Commit the changes.
7. In Render, keep Root Directory:
   `bets/mlb-moneyline-engine`
8. Deploy the latest commit.

## Render settings

Build:

```bash
pip install -r requirements.txt
```

Start:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port $PORT
```
