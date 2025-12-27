This repo contains a buy-vs-rent simulator that, month by month, tracks owner outflows (mortgage, maintenance, insurance, closing/selling costs) versus renting, grows the renter’s portfolio with whatever upfront cash (down payment + closing costs) would have gone into the home, and reports when home equity plus any owner investments equals the renter’s portfolio measured in real or nominal dollars. The simulation explicitly assumes the down payment stays invested in equities while you rent instead of growing like home equity. Use either the CLI or optional browser UI to tweak assumptions and watch the break-even outcome.

1. Set up/switch to your Python 3 virtual environment (e.g., `python3 -m venv .venv && source .venv/bin/activate`).
2. Run `pip install -r requirements.txt` just to confirm the env is ready.
3. CLI: `python simulation.py`.
4. Browser UI (optional): `python app.py` then open http://localhost:5000.

To see all CLI options, run:

```bash
python simulation.py --help
```

The browser UI lives in `app.py` and exposes the same knobs via a form; submit to see the break-even output.
