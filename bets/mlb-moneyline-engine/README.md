# MLB Moneyline Engine

This is the first working data-collection version of the MLB moneyline project.

## Included now

- Live MLB moneylines from The Odds API
- Two-way no-vig probability calculations
- Best returned price for each side
- Probable pitchers when available
- Manual confirmed-lineup entry
- Manual bullpen-availability entry
- Seven signal-family research structure
- Timestamped JSON snapshots
- Data dictionary with 40+ planned fields
- Recommendations disabled until validation

## Critical security step

The API key shown in your screenshot should be rotated before use.

Never upload `.streamlit/secrets.toml` to GitHub.

## Upload to your private GitHub repository

1. Download and extract the ZIP.
2. Open the private repository you created.
3. Click **Add file**.
4. Click **Upload files**.
5. Drag every extracted file and folder into GitHub.
6. Commit the upload.

## Run locally

Install Python 3.11 or newer, then:

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Install:

```bash
pip install -r requirements.txt
```

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and put
your newly rotated key in it.

Start:

```bash
streamlit run app.py
```

## Deploy with Streamlit Community Cloud

1. Connect Streamlit to GitHub.
2. Select this private repository.
3. Main file: `app.py`
4. In Advanced settings → Secrets, enter:

```toml
ODDS_API_KEY = "YOUR_NEW_ROTATED_KEY"
```

5. Deploy.

## Test calculations

```bash
pytest
```

## Important limitation

This is not yet a trained betting model. It is the clean collection and
snapshot layer needed before historical backtesting and probability fitting.
