This repo contains a buy-vs-rent simulation that steps through owning costs (mortgage, maintenance, insurance, etc.) versus renting, growing both portfolios, and reporting the month/year when homeownership catches up to renting based on the parameters you supply (real or nominal dollars). Use either the CLI or optional browser UI to tweak assumptions and watch the break-even outcome.

1. Set up/switch to your Python 3 virtual environment (e.g., `python3 -m venv .venv && source .venv/bin/activate`).
2. Run `pip install -r requirements.txt` just to confirm the env is ready.
3. CLI: `python simulation.py`.
4. Browser UI (optional): `python app.py` then open http://localhost:5000.

To see all CLI options, run:

```bash
python simulation.py --help
```

The browser UI lives in `app.py` and exposes the same knobs via a form; submit to see the break-even output.
