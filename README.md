1. Set up/switch to your Python 3 virtual environment (e.g., `python3 -m venv .venv && source .venv/bin/activate`).
2. Run `pip install -r requirements.txt` just to confirm the env is ready.
3. CLI: `python simulation.py`.
4. Browser UI (optional): `python app.py` then open http://localhost:5000.

To see all CLI options, run:

```bash
python simulation.py --help
```

The browser UI lives in `app.py` and exposes the same knobs via a form; submit to see the break-even output.
