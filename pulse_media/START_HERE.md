# Pulse Media Group — Run the Pipeline

## First time only (run these once)

```bash
cd ~/PROJECT-A/pulse_media

pip3 install requests
pip3 install yfinance

python3 database/schema.py
```

## Every time you want to run the pipeline

```bash
cd ~/PROJECT-A/pulse_media

# Fetch news for FinPulse
python3 pipeline/orchestrator.py finpulse

# OR run all 4 pages at once
python3 pipeline/orchestrator.py all
```

## Open the live dashboard

```bash
python3 dashboard/server.py
```
Then open your browser → http://localhost:8888

## Troubleshooting

| Error | Fix |
|-------|-----|
| `pip: command not found` | Use `pip3` instead |
| `python: command not found` | Use `python3` instead |
| `ModuleNotFoundError: requests` | Run `pip3 install requests` |
| `ModuleNotFoundError: yfinance` | Run `pip3 install yfinance` |
