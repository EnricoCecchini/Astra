# Weather Insights

Weather Insights is a Streamlit app for stargazers. Pick a planet, the Moon or a
constellation and how far you are willing to travel. The app shows which nearby
observing sites will have that target above the horizon in a dark enough sky
during the next 48 hours, and ranks them with a 0–100 suitability score. The score
combines the OpenWeatherMap forecast (cloud, humidity, visibility, wind) with the
target's altitude, twilight darkness and moonlight, which come from Skyfield.

The app has two views:

- **Live Conditions**: current weather at your location (shared from the browser,
  or a city you type in). Below it are a map and ranked cards for every observing
  site in range, each with its viewing window, where to look, the matching forecast
  slot, its score and rating, and a Google Maps directions link.
- **Analytics**: charts built from the weather history this app has logged.
  - Hourly weather-score trend per site.
  - Nighttime ranking of sites.
  - Heatmap of the clearest night hours.
  - Breakdown of each site's latest score.
  - Forecast chart of tonight's observing window for a chosen site and target.

Every successful API call is appended to a CSV under `data/` with its fetch time,
so the analytics run on real accumulated readings.

## Setup

```bash
uv sync
cp variables.env.example variables.env   # then fill in your own OpenWeatherMap key
```

Put your key in `variables.env` as `OPENWEATHER_API_KEY=your_actual_key`. This file
is git-ignored: never commit or share it. The free Current Weather and
5 Day / 3 Hour Forecast APIs use the same key. New keys can take a while to
activate.

The first run downloads the JPL DE421 ephemeris (~17 MB) into `data/skyfield/`.

## Run the app

```bash
uv run streamlit run app.py
```

In the sidebar, click the 📍 icon and allow location access, or type a city name
and press **Use this city**. Then choose a target and a travel distance, and press
**Get Sites**.

## Collect weather history

Analytics is only as good as the history behind it. Run the collector to log
current weather and forecasts for every site in `data/sites.csv` immediately and
then every 5 minutes:

```bash
uv run python scripts/collect_weather.py              # until Ctrl+C
uv run python scripts/collect_weather.py --once       # a single collection
uv run python scripts/collect_weather.py --interval 600
```

Leave it running across several days **and nights**. The ranking and heatmap
views only use nighttime readings. Commit the updated CSVs so the history is
shared.

## Run the tests

```bash
uv run python -m unittest discover -s tests -v
```

The tests are offline: API calls are mocked and every file they write goes to a
temporary directory, so they never change the CSVs in `data/`. Tests that drive the
Streamlit app are skipped until the ephemeris has been downloaded (run the app once).

## Project structure

```
.
├── app.py                      # Streamlit entry point (Live Conditions + Analytics)
├── pyproject.toml
├── variables.env.example       # copy to variables.env (not committed) for your API key
├── data/
│   ├── sites.csv               # curated observing sites
│   ├── historical_weather.csv  # logged current observations
│   ├── forecast_weather.csv    # logged forecast snapshots
│   └── scoring_output.csv      # logged suitability scores
├── scripts/
│   └── collect_weather.py      # periodic weather collector
├── src/weather_app/
│   ├── config.py               # loads the API key from variables.env
│   ├── client.py               # BaseAPIClient, OpenWeatherClient, WeatherReading
│   ├── storage.py              # appends readings to the CSV history
│   ├── models.py               # Site, ScoreResult, AstroSuitabilityScorer
│   ├── astronomy.py            # Skyfield ephemeris, planets, Moon, constellations
│   ├── planner.py              # sites in range and their viewing windows
│   ├── sites.py                # loads data/sites.csv
│   ├── analytics.py            # history loading, metrics and Plotly charts
│   ├── analytics_ui.py         # the Analytics view
│   ├── maps.py                 # map of the user and the sites
│   └── utils.py                # distance, compass and directions helpers
├── tests/
└── PROMPTS.md                  # AI collaboration log
```

## Team

<!-- Names and a one-line summary of who worked on what. -->

## How it works

### Weather client

`BaseAPIClient` is a generic JSON client: it handles the request, timeout and
status codes, with no knowledge of weather. `OpenWeatherClient` adds the endpoints,
the API key and the parsing into `WeatherReading` objects. Every failure raises
`WeatherError` (a subclass of the generic `APIError`) with its own user-facing
message:

- the API key is rejected (401)
- the location or city is not found (404)
- the rate limit is reached (429)
- the service has a server error (5xx)
- the request times out or cannot connect
- the response is malformed

Invalid input raises `ValueError` before any request is made. That covers
out-of-range coordinates, and city names that are empty, too long or not
made of letters.

```python
from weather_app.client import OpenWeatherClient, WeatherError

try:
    client = OpenWeatherClient()
    current = client.current_weather(40.4169, -3.7035)
    madrid = client.current_weather_for_city("Madrid")
    forecast = client.forecast(40.4169, -3.7035)
    print(current.cloud_cover_percent, len(forecast), madrid.missing_scoring_fields)
except (WeatherError, ValueError) as error:
    print(error)
```

Readings carry timezone-aware UTC timestamps. Weather fields are `None` when the
API omits them. Current readings are appended to `data/historical_weather.csv` and
forecast slots to `data/forecast_weather.csv`, each with a `fetched_at` time.

### Scoring

`AstroSuitabilityScorer.score()` turns a forecast slot plus the target's altitude,
darkness and moonlight into a `ScoreResult`. That result holds the component scores,
a weather score, an astronomy score and a combined score, all on a 0–100 scale. It
also has a `rating` (Excellent ≥ 75, Good ≥ 60, Fair ≥ 40, Poor) and is ordered by
combined score, so `sorted(results)` and `max(results)` work.

Each score is appended to `data/scoring_output.csv` with both the scored observing
time (`timestamp`) and when it was calculated (`computed_at`). The app scores each
site, target and forecast slot once per session, so rerunning the page does not
add duplicate rows. The first row of that file is the reference sample the
contract test checks against. Older rows have an empty `computed_at` because it
was not recorded at the time.

The live score uses the forecast slot nearest the start of the viewing window, and
only if it is within 90 minutes, since forecasts come in three-hour steps.
Site forecasts are cached for 30 minutes and current conditions for 10. If one
site's request fails, the others are still shown.

### Collector process (local background instance)

If you start the collector in the background, it writes
`.weather-collector/collector.log` and its process ID to
`.weather-collector/collector.pid` (both git-ignored). To stop it in PowerShell:

```powershell
Stop-Process -Id (Get-Content .weather-collector/collector.pid)
```

Check first that the PID still belongs to the collector. The collector runs only
while the computer is awake and does not restart after a reboot or sign-out. Do not
start a second instance while one is running.
