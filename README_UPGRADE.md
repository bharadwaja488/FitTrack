# FitTrack Dashboard + Local AI Coach

This upgrade adds a local Streamlit dashboard to the original Python/MySQL FitTrack project. It preserves the original console application and existing users and fitness_records tables.

## Features
- Streamlit fitness dashboard and profile selection
- Activity charts for steps and workout duration
- Daily water, sleep, mood and notes log
- Weight history and fitness goals
- BMI, BMR and activity-adjusted calorie estimates
- Optional local Ollama AI Coach with offline fallback

## Setup
1. Keep the original main.py and database.py in the project root.
2. Create and activate a Python virtual environment.
3. Install dependencies: `pip install -r requirements-dashboard.txt`.
4. Copy `.env.example` to `.env` and set your MySQL credentials. Never commit `.env`.
5. Run `streamlit run dashboard.py`.

The first dashboard launch creates three additive MySQL tables: daily_health_logs, weight_history and fitness_goals. It does not alter the original tables.

## Optional local AI
Install Ollama from https://ollama.com/ and pull a model that fits your computer, for example `ollama pull llama3.2:3b`. Keep Ollama running. No paid API key is used. If Ollama is unavailable, built-in offline guidance is used.

## Tests
Run `pytest -q`.

## Notes
- Existing heights are stored in meters and weights in kilograms.
- The first dashboard increment is intended for local/demo use and does not yet implement multi-user web authentication.
- BMI, BMR and calorie values are estimates, not medical diagnoses.
- Local operation does not require paid hosting or a custom domain.