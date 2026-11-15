# Weather Insights

<!-- Replace this with a real description of what your app does once it exists. -->

## Setup

```bash
uv sync
cp variables.env.example variables.env   # then fill in your own OpenWeatherMap key
```

## Run the app

```bash
uv run streamlit run app.py
```

## Run the tests

```bash
uv run --with pytest pytest
```

## Project structure

```
.
├── pyproject.toml
├── variables.env               # not committed — your API key
├── src/
│   └── weather_app/
│       ├── client.py           # API client classes
│       ├── models.py           # data classes (snapshots, locations...)
│       ├── storage.py          # logging/loading fetched history
│       └── analytics.py        # analytical views
├── app.py                      # Streamlit entry point
├── tests/
└── PROMPTS.md                  # AI collaboration log
```

## Team

<!-- Names and a one-line summary of who worked on what. -->

## Weather integration

Create an OpenWeather account and put your key in the ignored `variables.env`
file as `OPENWEATHER_API_KEY=your_actual_key`. Do not commit or share your key.
The free Current Weather and 5 Day / 3 Hour Forecast APIs use the same key.
New keys may take time to activate. The app requests metric units.

`OpenWeatherClient.current_weather(lat, lon)` returns a current `WeatherReading`;
`forecast(lat, lon)` returns forecast readings with timezone-aware UTC timestamps.
Optional fields can be `None`. Invalid inputs raise `ValueError`; service and
response errors raise `WeatherError` with a user-facing message. For example:

```python
from weather_app.client import OpenWeatherClient, WeatherError

try:
    client = OpenWeatherClient()
    current = client.current_weather(40.4169, -3.7035)
    forecast = client.forecast(40.4169, -3.7035)
    print(current.cloud_cover_percent, len(forecast))
except (WeatherError, ValueError) as error:
    print(error)
```

The planner shows the forecast slot nearest the beginning of the first viewing
window, only if it is within 90 minutes. It is a three-hour forecast, not a
five-minute measurement. Successful site forecasts are cached for 30 minutes.
The combined suitability score remains unavailable until all astronomy scoring
inputs are implemented. Failed site requests do not block other sites. Weather
history and analytics are not implemented yet.

The standard-library client tests can also be run without installing pytest:

```bash
uv run python -m unittest discover -s tests -v
```

### Handoff: weather data contract

- `OpenWeatherClient.current_weather(latitude, longitude)` returns one
  `WeatherReading` with `kind="current"`; `forecast(latitude, longitude)`
  returns a list with `kind="forecast"`.
- A reading contains the requested `latitude` and `longitude`, a timezone-aware
  UTC `timestamp`, `temperature_c`, `cloud_cover_percent`, `humidity_percent`,
  `visibility_m`, `wind_speed_mps`, and `description`. Weather fields may be
  `None` if absent in the response.
- `forecast_for_time(readings, when)` selects the closest forecast within 90
  minutes of the timezone-aware time supplied, or returns `None`.
- The existing `AstroSuitabilityScorer.score()` expects cloud cover, relative
  humidity, visibility, wind, target altitude, darkness suitability, and
  target-dependent moonlight suitability. It does not currently consume a
  `WeatherReading` directly; the caller must pass the individual fields.
- `data/scoring_output.csv` is a sample **scoring result**, not the weather
  client's input or output contract. The app does not use its sample score now.
- Offline tests include a mock forecast passed through the scorer and checked
  against every score in `data/scoring_output.csv`. The app does not yet make
  that scoring connection itself. Live requests to both current conditions and the five-day forecast
  succeeded after key activation. A real-browser app check is still pending. The combined score,
  historical weather storage, and analytics are not yet integrated.
- API keys are local secrets: each contributor must create `variables.env`
  from `variables.env.example` and supply their own key, never commit it.

### Periodic weather collection

Run `.venv\Scripts\python.exe scripts/collect_weather.py` to collect current
weather and forecasts for every site in `data/sites.csv` immediately and every
300 seconds afterward. Use `--once` for a single collection or `--interval 600`
for a different interval. Current readings append to `data/historical_weather.csv`
and forecast slots to `data/forecast_weather.csv`; fetch times distinguish repeated
forecast snapshots. Failed requests are logged and other sites still run.

The local background instance writes `.weather-collector/collector.log` and its
process ID to `.weather-collector/collector.pid`. Stop that instance in PowerShell
with `Stop-Process -Id (Get-Content .weather-collector/collector.pid)` after checking
the PID still belongs to the collector. It runs while the computer is awake and
does not automatically restart after reboot or sign-out. Starting the command
above in a terminal creates a foreground instance; stop it with Ctrl+C. Avoid
starting a second instance while the background collector is active.
