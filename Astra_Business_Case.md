# AstroWeather — Conversation Notes and Project Design

*Prepared 14 November 2026. This is a structured record of the discussion, not a verbatim chat transcript. Examples and scores are illustrative unless otherwise noted.*

## 1. Starting point: the assignment

The group capstone asks for an object-oriented Python application powered by OpenWeatherMap, delivered through Streamlit and developed collaboratively on GitHub. The supplied `README.md` specifies:

- A reusable generic JSON API client and an OpenWeather-specific subclass, deliberate encapsulation, a meaningful special method beyond `__init__`, and at least one `@property`.
- API keys from environment variables using `python-dotenv`, input validation, specific error messages, and graceful handling when some locations fail.
- Each successful current-weather fetch saved with timestamps to CSV or SQLite; at least three analytical views covering at least two of historical trends, cross-location comparisons, and computed metrics.
- At least two Streamlit views, two clearly labeled charts, and meaningful interactions.
- A packaged `src/` project, `pyproject.toml`, setup README, `PROMPTS.md`, AI co-author trailers where appropriate, and authentic Git contributions from every teammate.
- Submission of a runnable repository with accumulated, real weather records and no committed API secrets.

## 2. First round of app concepts

We considered eight weather-centered products:

| Idea | Basic value proposition |
| --- | --- |
| WeatherFit | Find favorable outdoor exercise windows. |
| SmartCommute | Choose a commuting mode according to weather. |
| SkyCast | Recommend photography conditions. |
| WeatherWise | Personalize clothing suggestions through feedback. |
| EventCast | Assess outdoor-event weather risks. |
| BreatheEasy | Combine outdoor comfort and air quality. |
| SolarSense | Estimate solar generation using weather. |
| WeatherMood | Examine associations between weather and self-reported mood. |

The conversation emphasized that a useful decision-making product is preferable to an interface that merely repeats API values.

## 3. More ideas aligned to the assignment

The second brainstorm focused on comparison, historical logging, and derived metrics:

- **ClimateMatch:** Match weather preferences to cities.
- **WeatherTwin:** Identify cities with similar weather using standardized vector distances.
- **WeatherBattle:** Compare and rank cities head to head.
- **UrbanHeat:** Explore differences between urban locations, without claiming to measure heat-island effects without suitable controls.
- **WeatherStability:** Compare observed variability and consistency of weather.
- **WeatherEscape:** Find nearby destinations with better weather.
- **WeatherRisk:** Screen for potentially adverse conditions using clearly labeled non-official scores.
- **TravelWindow:** Find favorable days for sightseeing and potentially assess forecast errors.
- **WeatherEconomics:** Assess weather suitability for business operations.
- **ForecastLab:** Compare saved forecasts with subsequent observations.

## 4. Ideas using another straightforward API

Potential combinations included:

| Idea | Extra source(s) | Main use |
| --- | --- | --- |
| TripWise | REST Countries; geocoding | Destination filtering and comparisons |
| RunSmart | OpenStreetMap; routing | Running route recommendations |
| AirAware | OpenAQ | Weather and pollution comparisons |
| SolarPlanner | Solar radiation and energy data | Electricity-use planning |
| **AstroWeather** | Astronomical calculations; geography | Find favorable opportunities to observe celestial objects |
| BikeWise | Routing; OpenStreetMap | Cycling conditions and headwind analysis |
| CityPulse | Air quality; geographic amenities | Environmental city comparisons |
| BeachFinder | Marine weather; OpenStreetMap | Beach suitability ranking |
| EcoTravel | Routing; emissions factors | Destination trade-offs |
| GeoWeather | Elevation; country metadata | Geographic/weather relationships |

The user selected **AstroWeather**.

## 5. AstroWeather: agreed product direction

### Core user question

> **When and where should I go to observe a celestial body I care about, considering expected weather and how far I am willing to travel?**

### User inputs

1. Celestial body or target (initially the Moon and major planets).
2. Starting city or geographic location.
3. Maximum distance willing to travel.
4. Minimum acceptable stargazing suitability score (such as 75/100).
5. Observation date range, initially limited to the free five-day forecast horizon.

An additional future input could specify naked-eye versus telescope observation.

### Expected output

A ranked set of observation opportunities with date/time, suggested location, distance, total score, and a breakdown of weather and celestial visibility. A user selects an opportunity for details, such as cloud cover, wind, humidity, object altitude, darkness, and Moon illumination.

**Important:** The dates and scores used in the discussion were illustrative, not computed real-world forecasts.

## 6. Proposed data sources

| Source | Role | Notes |
| --- | --- | --- |
| [OpenWeatherMap](https://openweathermap.org/api) | Current observations; five-day, three-hour forecasts | Current observations create the historical dataset; forecasts drive future recommendations. |
| [Skyfield](https://rhodesmill.org/skyfield/) Python library | Celestial positions, altitudes, Sun/Moon geometry | Local computation avoids a separate astronomy API for the initial objects. |
| Geographic coordinates and a curated observing-site list | Candidate sites and straight-line distance | Initial MVP can avoid route-planning complexity. |
| Optional OpenStreetMap/Overpass or routing service | Site discovery and road distance | Later phase; available site data does not automatically guarantee darkness or accessibility. |
| Optional documented light-pollution data | Night-sky quality | Particularly important for faint deep-sky targets; not equivalent to cloud cover. |

The free OpenWeather offering includes current weather and a five-day, three-hour forecast according to its published API pages. Historical records must be accumulated independently for this assignment.

## 7. Scoring design discussed

### Weather suitability

Normalize components to 0–100 and initially consider:

\[
S_W = 0.50C + 0.20H + 0.15V + 0.15W
\]

Where `C` is cloud suitability, `H` humidity suitability, `V` visibility suitability, and `W` wind suitability. For example, `C = 100 − cloud_cover_percent` is a simple starting transformation.

### Astronomical suitability

An illustrative formulation:

\[
S_A = 0.50A + 0.30D + 0.20M
\]

Where `A` is celestial-object altitude suitability, `D` darkness suitability, and `M` target-dependent moonlight suitability. A simple altitude heuristic considered was `A = min(100, altitude_degrees / 60 × 100)` for nonnegative altitudes.

### Combined score

\[
S = 0.60S_W + 0.40S_A
\]

These weights and transformations are **proposed heuristics**, not validated scientific models. They should be justified, tested, and possibly customized per target.

**Hard eligibility rules** should precede ranking: the object must be sufficiently above the horizon; solar altitude must permit the relevant observation; travel radius must be respected; and forecast data must cover the candidate time. An impossible observation must not receive a high score merely because the weather is clear.

Moonlight affects faint galaxies very differently from bright planets, and observing the Moon itself calls for different scoring.

## 8. Exact implementation of the data-and-analytics requirement

### 8.1 Collect and log actual weather

Persist every successful current-weather response in SQLite (or CSV). Proposed fields:

| Field | Meaning |
| --- | --- |
| `observation_id` | Unique row ID |
| `location_id`, `latitude`, `longitude` | Observed place |
| `observed_at_utc` | Timestamp reported for the weather observation |
| `fetched_at_utc` | When the app retrieved it |
| `temperature_c` | Temperature in °C |
| `humidity_pct` | Relative humidity in % |
| `cloud_cover_pct` | Cloud coverage in % |
| `visibility_m` | Visibility in meters, where provided |
| `wind_speed_m_s` | Wind speed in m/s |

Do **not** conflate forecasts with actual observations. If forecasts are logged, store them separately with issuance and target times.

Recommended collection: track a manageable set of sites around Madrid; fetch at regular intervals, including night hours; also log successful user-triggered requests. Scheduled scripts or GitHub Actions are more dependable than using an interactive Streamlit session as a scheduler. Avoid treating repeated retrievals of the same underlying observation as independent measurements.

### 8.2 Analytics view 1: Stargazing History

**Category: trend over time**

- Plot timestamp versus cloud coverage (%) for a user-selected location.
- Plot the derived meteorological score `S_W` over time.
- Filter to locally nighttime observations when describing opportunities for stargazing.
- Allow selection of date range and location.

User question: **How have viewing conditions evolved at this site?**

### 8.3 Analytics view 2: Location Rankings

**Category: cross-location comparison**

- Rank candidate sites by current meteorological suitability.
- Compare historical mean suitability over matched observation periods:

\[
\bar S_i = \frac{1}{n_i}\sum_{t=1}^{n_i} S_{i,t}
\]

- Show the fraction of recorded nighttime observations above a selected threshold:

\[
F_i = \frac{\#\{t:S_{i,t}\geq 75\}}{n_i}\times 100\%
\]

- Show a labeled bar chart by location.

User question: **Which nearby sites have experienced better conditions in our recorded sample?**

Sampling schedules and date ranges must be made comparable; short samples cannot demonstrate long-term climatology or light pollution quality.

### 8.4 Analytics view 3: Observation Planner

**Category: derived/computed metric**

- Retrieve forecast slots for candidate sites and the relevant five-day window.
- Compute celestial altitude and darkness at each location and time.
- Apply eligibility filters.
- Compute the composite suitability score and rank eligible site/time opportunities.
- Apply the user's score threshold and maximum travel radius.

User question: **Which upcoming date, time, and accessible site offers the strongest opportunity for my chosen object?**

The historical charts should use logged observations; the prospective planner should use fresh forecasts and astronomical calculations. This distinction is essential for honest analytics.

### 8.5 Two graded charts at minimum

To make compliance unambiguous, include at least two weather-data charts:

1. A line chart of logged nighttime cloud cover or `S_W` over time, with units and timestamps.
2. A bar chart of average logged nighttime `S_W` by location, with sample counts and matched windows.

An additional object-altitude-over-the-night chart would improve the app but should not replace both weather-data charts.

## 9. Suggested Streamlit views

1. **Observation Planner:** object, origin, travel radius, threshold, date window, ranked recommendations and optional map.
2. **Observation Details:** score components and target altitude across the night.
3. **Weather Analytics:** historical time series and favorable-condition rates.
4. **Location Explorer:** side-by-side site comparisons and rankings.

The interface should make it clear whether the data is a **forecast**, a **recorded observation**, or a **computed score**.

## 10. Proposed Python design

| Class | Responsibility | Course concept |
| --- | --- | --- |
| `BaseAPIClient` | Generic request, status checking, and network error handling | Inheritance base class |
| `OpenWeatherClient` | Weather-specific endpoints, fields, units | Subclass |
| `WeatherObservation` | Typed weather data | Encapsulation, meaningful `__repr__` |
| `WeatherRepository` | SQLite persistence and history queries | Composition |
| `WeatherAnalyzer` | Trend, comparison, and meteorological scoring | Analytics methods |
| `AstronomyCalculator` | Skyfield target positions and solar geometry | Domain logic |
| `ObservationOpportunity` | One site/time/target candidate and score | `@property`; meaningful sorting (`__lt__`) |
| `AstroWeatherService` | Orchestrates fetching, calculations, and ranking | Composition |

Security and robustness requirements remain: secret in `variables.env` excluded from Git; user input validation; distinct handling for invalid cities, bad keys, network failures, and malformed responses; and continuing when one candidate location fails.

## 11. Suggested implementation sequence

1. **Core foundation:** package structure, API client, errors, SQLite observation logging, and tests. Begin collecting history immediately.
2. **Core planner:** selected target and origin, Skyfield visibility calculations, five-day forecasts, hard filters, scores, and ranked time windows.
3. **Travel-radius support:** curated candidate sites, Haversine distances, batch location fetching, and map/list comparison.
4. **Historical analytics:** matched nighttime time series, site rankings, bar and line charts.
5. **Polish and handoff:** documentation, clean-clone test, `PROMPTS.md`, Git history, co-author trailers, and committed genuine sample dataset.

## 12. Decisions and open questions

### Direction chosen

- Product: **AstroWeather**, an astronomical observation planner.
- Personalized target selection, location, maximum travel distance, minimum score, and proposed dates.
- Scoring must combine weather and actual target visibility.
- Favor a small curated list of observation sites for the MVP.
- Store current-weather records for historical views and keep forecast records logically separate.

### Still to decide

- The exact MVP target list (Moon, Mercury, Venus, Mars, Jupiter, Saturn were proposed).
- Whether to support telescope/naked-eye modes in version one.
- Source and quality of candidate observing sites and light pollution information.
- Whether distance means straight-line radius or driving distance.
- Exact scoring thresholds, empirical validation, and object-specific weighting.
- How many days of real logged data can be accumulated before submission.
- The final page count, assignment timeline, and division of group responsibilities.

## 13. References discussed

- [OpenWeatherMap API](https://openweathermap.org/api)
- [OpenWeatherMap current weather](https://openweathermap.org/api/current)
- [OpenWeatherMap 5-day forecast](https://openweathermap.org/api/forecast5)
- [Skyfield](https://rhodesmill.org/skyfield/)
- [OpenStreetMap](https://www.openstreetmap.org/)
- [OpenRouteService](https://openrouteservice.org/)

---

*This document consolidates the conversation as a working project brief. It does not claim that the proposed application has been implemented or that the example outputs are live data.*
