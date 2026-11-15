# AI collaboration log

Add one entry per feature/class you asked an AI agent to help with, in the order you worked on them.
Keep this running as you go — don't reconstruct it from memory at the end.

## Feature: <short name>

**Asked:** <the actual prompt you gave the agent>

**Got:** <what file/function it produced>

**Checked:** <how you verified it — a hand-made test case, a comparison against a known value, etc.>

**Kept as-is / changed / rejected:** <which, and why>

---

## Feature: Sample observing-sites dataset

**Asked:** "create the data/ dir and create a sample dataset with 10 entries for the Site object using places in Spain"

**Got:** `data/sites.csv` with the `Site` columns from the module plan (site_id, name, latitude, longitude, elevation_m, owm_location_id, sky_brightness) and 10 Spanish sites: Madrid centre (light-polluted baseline), Navacerrada, Gredos and Yebes near Madrid, Javalambre, Montsec, Calar Alto, Sierra Nevada, Teide and Roque de los Muchachos. `owm_location_id` and `sky_brightness` left empty (both optional).

**Checked:** Loaded the file with `pandas.read_csv` (10 rows, 7 columns, accents read correctly as UTF-8). Coordinates and elevations are approximate values from the agent's knowledge — _TODO (student): spot-check them on a map._

**Kept as-is / changed / rejected:** _TODO (student): fill in._

---

## Feature: Haversine distance helper

**Asked:** "Create a utils.py file and add a method to calculate the Haversine distance between 2 sets of coordinates."

**Got:** `src/weather_app/utils.py` with `haversine_km(lat1, lon1, lat2, lon2) -> float` (great-circle distance in km, mean Earth radius 6371.0088 km, rejects out-of-range latitude/longitude with `ValueError`).

**Checked:** Same point → 0 km; 1° of longitude on the equator = 2πR/360 (≈111.195 km); pole to pole and two antipodal equator points = πR; swapping the points gives the same result; Madrid (Sol) → Barcelona (Pl. Catalunya) = 505.2 km, matching the commonly quoted ~505 km straight-line distance; latitude 91 raises `ValueError`.

**Kept as-is / changed / rejected:** _TODO (student): fill in._

---

## Feature: Celestial body dropdown (Skyfield)

**Asked:** "Load the list of planets and constellations from the skyfield API library into a CELESTIAL_BODY dictionary on app start and display the names in a dropdown on the Streamlit Live Conditions tab section"

**Got:** `src/weather_app/astronomy.py` with `load_ephemeris()` (downloads JPL DE421 once into `data/skyfield/`, now git-ignored) and `load_celestial_bodies()`, which returns name → `{"kind", "target"}`: the 7 planets plus the Moon map to Skyfield vectors (outer planets fall back to their barycenters, the only form DE421 has), and the 88 IAU constellations from `load_constellation_names()` map to their 3-letter abbreviations. `app.py` builds `CELESTIAL_BODY` at start-up through `st.cache_resource` and shows a "Celestial body" `selectbox` on Live Conditions.

**Checked:** Ran the app headless with Streamlit's `AppTest`: no exceptions, the dropdown has 96 options (7 planets + Moon + 88 constellations, the official IAU count), Jupiter–Neptune resolve to barycenters, and Orion maps to `Ori`.

**Kept as-is / changed / rejected:** _TODO (student): fill in._

---

## Feature: Confirm button and browser geolocation

**Asked:** "Place the dropdowns on the same line, then add a confirm button. When the confirm button is pressed, prompt the user for access to their location with the streamlit-geolocation library"

**Got:** In `app.py` (Live Conditions): the celestial body and maximum travel distance dropdowns side by side in `st.columns(2)`; a primary "Confirm" button that sets `st.session_state["location_requested"]`; after that, the `streamlit_geolocation()` component plus an instruction, and the shared coordinates stored in `st.session_state["user_location"]` as `(lat, lon)` with a success message. The library only asks the browser for the location when its own icon button is clicked, so the user clicks Confirm and then the location icon.

**Checked:** Ran the app headless with Streamlit's `AppTest`: both dropdowns and the Confirm button render without errors; clicking Confirm sets the flag and shows the instruction and "waiting" caption. The browser permission prompt itself can't be exercised headless — _TODO (student): test in a real browser on localhost (allow and deny)._

**Kept as-is / changed / rejected:** _TODO (student): fill in._

---

## Feature: Planner — visible sites within range

**Asked:** "Create the Planner class and add a method to obtain a list of sites where the selected celestial body can be seen and are within the selected distance range from the user's location."

**Got:**
- `models.py`: `Site` frozen dataclass (coordinate validation in `__post_init__`, `distance_km()` using `utils.haversine_km`, custom `__repr__`), following the module plan.
- `sites.py`: `load_sites()` reads `data/sites.csv` into `Site` objects (empty optional columns → `None`).
- `astronomy.py`: `constellation_centers()` samples the sky on a 1° grid with Skyfield's constellation map and averages each constellation's points (area-weighted) to get an approximate centre; constellations in `CELESTIAL_BODY` now have a `Star` at that centre as `target`, plus their `abbreviation`.
- `planner.py`: `Planner(sites, celestial_bodies, ephemeris)` with `sites_within()` (Haversine radius filter, nearest first) and `visible_sites(body_name, lat, lon, max_distance_km, when=None)` → list of `SiteVisibility` (site, distance, altitude, azimuth, Sun altitude). Visible = target ≥ 10° above the horizon and Sun ≤ −6° (the Moon is exempt from the darkness rule). Weather is not considered yet.
- `app.py`: one cached `Planner`; after the location is received, a table of visible sites or a message saying why none qualify.

**Checked:** Constellation centres compared with approximate reference positions (Orion 5.6h/+5°, Crux 12.4h/−60°, Cassiopeia 1.0h/+63°). From Puerta del Sol: 50 km → Madrid centre and Navacerrada (48.2 km); 100 km adds Yebes (53.4 km). On 2026-11-14 at 23:00 local, Orion is rising in the east (az ≈ 104°, alt ≈ 23°) and Saturn is high in the south (alt ≈ 49°); Crux never qualifies at Madrid's latitude; at 13:00 local nothing that needs darkness qualifies. Ran the app headless with `AppTest` and a simulated location: no errors, correct "not visible right now" message at midday.

**Kept as-is / changed / rejected:** _TODO (student): fill in._

---

## Feature: Scored sites table with sunset times

**Asked:** "Display the scored sites in a table. Display the sunset time for the locations as well so users know when they could go to the site" — clarified as: use placeholder scores from `data/scoring_output.csv` (it has one row and no site column, and no scoring code exists yet).

**Got:**
- `scoring.py`: `load_sample_scores()` reads the sample row of `data/scoring_output.csv` (placeholder until real per-site scoring exists).
- `planner.py`: `Planner.sunset_for(site, when)` uses `skyfield.almanac.find_settings` searching from 12 h before `when`, so during the day it returns the coming sunset and at night the one that started the current night; `SiteVisibility` gains `sunset_utc`.
- `app.py`: Get Sites results table now has Site, Distance, Sunset (in the browser's time zone via `st.context.timezone`, falling back to Europe/Madrid), Altitude, Azimuth, Weather/Astro/Combined score, with a caption saying the scores are sample values.

**Checked:** Madrid sunset on 2026-11-14 = 16:58 UTC (17:58 CET), matching published tables; at 01:00 UTC it returns the previous evening's sunset (16:59 on the 13th) and at 10:00/17:00/23:00 UTC the 14th's. Yebes (further east) sets earlier at 17:55, Teide at 18:13 UTC. Ran the app headless with the clock patched to 22:00 UTC: Saturn within 100 km shows Madrid, Navacerrada and Yebes with sunset times and the sample scores (84.0 / 94.5 / 88.2).

**Kept as-is / changed / rejected:** _TODO (student): fill in._

---

## Feature: Viewing windows for every site in range

**Asked:** "Show the table even if there are no currently available sites. The user must be able to at least see when they will be able to go"

**Got:**
- `planner.py`: `Planner.site_outlooks(body, lat, lon, max_km, when=None)` returns every site within range (not only those visible now). It samples the next 48 h every 5 minutes (one vectorised Skyfield call per site) and records `visible_now`, the first viewing window (`window_start_utc`, `window_end_utc`) and the altitude/azimuth at the start of that window. Results are ordered: visible now, then earliest window, then distance. `visible_sites()` is now a filter over it.
- `app.py`: Get Sites always shows the table for sites in range, with "Visible from" ("Now", a local day + time, or "Not in next 48 h"), "Visible until", Sunset, where to look, and the sample scores; a note when nothing is visible right now, and a separate message when no site is within range.

**Checked:** From Puerta del Sol, 100 km, on 2026-11-14 at 13:00 local: Saturn becomes visible at 18:30 local (≈30 min after the 17:58 sunset, when the Sun reaches −6°) until 03:25, rising in the ESE at ≈25°; Orion from ≈21:55; the Moon (no darkness rule) 13:55–20:40; Crux has no window. At 23:00 local Saturn shows "Now" for all three sites and `visible_sites()` still returns 3. Each search takes ≈0.1 s. Ran the app headless with the clock patched to midday: the table shows all three sites with their windows, and a 5 km search from an empty area shows the "no sites within range" message.

**Kept as-is / changed / rejected:** _TODO (student): fill in._

---

## Feature: Sites map and highlighted site cards

**Asked:** "Instead of a table, display a map with the user's current location pinned, as well as the suggested locations. Hihglight the scoring, and the Visible From and Until values to make the app more intuitive"

**Got:**
- `maps.py`: `sites_map()` builds a Plotly `Scattermap` (Carto basemap, no API token) with the travel-radius circle, a blue "Your location" pin and site markers coloured by status (green visible now, amber visible later, grey not visible in the next 48 h); hovering a site shows its score, visible from/until, distance and sunset. Helpers `circle_points()` (destination-point formula) and `zoom_for_radius()` (fits the radius circle to the map height).
- `utils.py`: `compass_point()` turns an azimuth into a 16-point direction (e.g. 113° → ESE).
- `app.py`: the table is replaced by the map plus one bordered card per site with a status badge and three large metrics — Score, Visible from, Visible until — and a line with distance, sunset and where to look ("Look ESE (113°), 25° above the horizon"). Sites with no viewing window show "—" as score.

**Checked:** Every point of the 50 km circle is 50.0 km from the centre by `haversine_km`; zoom is 12.1 for 5 km and 7.8 for 100 km around Madrid; `compass_point` gives N/N/NNE/E/ESE/SSW/N for 0/11/12/90/112/197.7/359°. Ran the app headless with the clock at 13:00 local: Saturn within 100 km renders one map and cards with "88/100", "Sat 18:25" → "Sun 03:25"; Crux shows "—" and "Not in next 48 h". The map's look in a real browser still needs checking — _TODO (student)._

**Kept as-is / changed / rejected:** _TODO (student): fill in._

---

## Feature: Map legend labels and Google Maps directions

**Asked:** "Add labels to the legends in the map for current location and suggested sites. Redirect the user to google maps with the location set"

**Got:**
- `maps.py`: legend entries "Your current location" and "Travel radius (N km)", with the site statuses grouped under a "Suggested sites" legend title; a "You are here" text label next to the user's pin.
- `utils.py`: `google_maps_directions_url(origin_lat, origin_lon, dest_lat, dest_lon)` builds a Google Maps URLs-API link (`/maps/dir/?api=1&origin=…&destination=…&travelmode=driving`).
- `app.py`: a "Directions in Google Maps" link button on every site card, from the user's location to that site (opens in a new tab).

**Checked:** The figure's traces are "Travel radius (50 km)", the status traces in legend group "sites" titled "Suggested sites", and "Your current location". The generated URL for Madrid → Navacerrada has the right origin/destination. Headless app run: Saturn within 100 km renders 3 link buttons, the first pointing from 40.4169,-3.7035 to Yebes (40.5247,-3.0886). Opening the link in a browser — _TODO (student)._

**Kept as-is / changed / rejected:** _TODO (student): fill in._

---

## Feature: Scoring branch setup

**Asked:** "create a new branch called feature/scoring"

**Got:** Created and switched to the Git branch `feature/scoring` from the current branch.

**Checked:** Git confirmed the branch was created and selected.

**Kept as-is / changed / rejected:** Kept as-is. The branch name matched the request.

---

## Feature: Scoring pull request

**Asked:** "submit a pull request to move recent branch changes to dev". Follow-ups: "let's try that pr request again, I should have write access now" and "let's try again".

**Got:** Committed the existing changes in `src/weather_app/models.py` as `cf001da` (`feat(scoring): add stargazing suitability scorer`), pushed `feature/scoring`, and created PR #1 targeting `dev`: https://github.com/EnricoCecchini/Astra/pull/1. The file contains `AstroSuitabilityScorer` and the immutable `ScoreResult` data class. The implementation was already present as an uncommitted change when the PR work resumed; its original authoring prompt is not available in this conversation.

**Checked:** Compared the branch against the fetched `origin/dev`, reviewed the diff, and ran `git diff --check` successfully. Automated tests were not run during PR preparation because Python was unavailable on PATH. Git confirmed the eventual push, and the GitHub API returned the PR URL. Earlier attempts either had no changes to submit or failed with a permissions error.

**Kept as-is / changed / rejected:** Kept the existing scoring implementation as-is and submitted it for review. Retried the push after repository access was updated; the PR was created successfully. No merge was performed.

---

## Feature: Sample scoring CSV

**Asked:** "generate a sample output of the scoring system and append it to a csv"

**Got:** Created `sample_scoring_output.csv` with a header and one illustrative row generated directly by `AstroSuitabilityScorer.score()`, using the bundled Python runtime. Inputs: timestamp `2026-11-14T22:00:00+01:00`, cloud cover 10%, relative humidity 40%, visibility 10,000 m, wind speed 2 m/s, target altitude 60 degrees, darkness suitability 95, and moonlight suitability 80. The CSV includes all component scores plus weather, astronomical, and combined totals.

**Checked:** Read the CSV back and verified that exactly one row was added, prior rows were preserved, and the saved combined score matched the scorer result. Inspected the output: weather `84.0`, astronomical `94.5`, combined `88.2`. These are illustrative inputs, not observed weather data.

**Kept as-is / changed / rejected:** Kept the generated CSV as-is. Removed the temporary generation script after verification. The CSV was left uncommitted.

---

## Feature: Historical analysis branch setup

**Asked:** "create a new branch feature/historical-analysis"

**Got:** Created and switched to `feature/historical-analysis` from the current `feature/scoring` branch. No historical analysis implementation was requested or produced in this step.

**Checked:** Git confirmed the branch was created and selected.

**Kept as-is / changed / rejected:** Kept as-is. The branch name matched the request.

---

## Feature: Refresh dev and recreate the historical analysis branch

**Asked:** "do a git stash, git pull and finally git stash pop"; "delete the feature/historical-analysis branch"; "create branch feature/historical-analysis".

**Got:** Stashed the local prompt-log and sample-CSV changes, fast-forwarded `dev` to `origin/dev`, and restored the stash. Resolved the `PROMPTS.md` conflict by retaining both sets of entries. Deleted the old local historical-analysis branch, then recreated and selected it from updated `dev`.

**Checked:** Git reported the successful fast-forward, the resolved conflict, the deletion and recreation of the branch. `git diff --cached --check` passed after conflict resolution. The stash was retained as a backup after the conflicted pop.

**Kept as-is / changed / rejected:** Kept the updated base and preserved local work. These operations supersede the original historical-analysis branch base recorded above.

---

## Feature: Append scoring results to CSV

**Asked:** "add a function to the astrosuitabilityscorer to append the score to the scoring output csv"

**Got:** `AstroSuitabilityScorer.append_score(result, path=None)` in `src/weather_app/models.py`. Appends a `ScoreResult` to `data/scoring_output.csv` by default, supports a custom path, creates missing directories and headers, and serializes the timestamp as ISO 8601. Rejects incompatible CSV headers before writing and handles existing files without a final newline. Added `tests/test_scoring_csv.py`.

**Checked:** All three unittest checks passed using the bundled Python runtime: repeated appends preserve prior rows and one header, empty files and missing final newlines work, and incompatible headers leave the existing file unchanged. The sample combined score was verified as 88.2. `git diff --check` passed. Tests used temporary files and did not modify the project scoring CSV.

**Kept as-is / changed / rejected:** Kept the implementation after verification. Saving is an explicit call after scoring.

---

## Feature: Focused commit workflow

**Asked:** "from now on do partial commits, to ensure proper verion control"

**Got:** Adopted small commits for completed, verified changes. Committed the CSV append helper separately from automatic score saving, and later separated collection code from live data snapshots. Existing unrelated CSV changes were excluded from feature commits.

**Checked:** Git commit output and status confirmed separate commits and preservation of unrelated working-tree changes.

**Kept as-is / changed / rejected:** Kept as the ongoing version-control workflow. Each logical change is committed after its relevant checks pass.

---

## Feature: Automatically save every new score

**Asked:** "call the append score every time a new score is registered"

**Got:** `AstroSuitabilityScorer.score()` now calls `append_score(result)` before returning each new result. The constructor accepts an optional `output_path`; the default remains `data/scoring_output.csv`. Callers should no longer append the same result manually after calling `score()`, since that would duplicate the row. Write errors propagate to the caller.

**Checked:** All six CSV persistence unittest checks passed, including two scoring calls producing two rows, invalid inputs producing no file, and write failures propagating. Tests used temporary files. `git diff --check` passed.

**Kept as-is / changed / rejected:** Changed saving from an explicit follow-up call to automatic persistence. Committed the append helper and automatic-saving behavior separately, excluding unrelated staged files.

---

## Feature: Site identifiers in scoring history

**Asked:** "include the site id attribute to the astrosuitabilityscore"

**Got:** Added required `site_id` to `AstroSuitabilityScorer.score()` and `ScoreResult`, with validation for a nonempty string. Automatically saved CSV rows include the identifier. Added the column to `data/scoring_output.csv`, leaving the historical sample ID blank because no site was originally recorded. Updated `load_sample_scores()` to exclude site metadata from numeric score conversion.

**Checked:** All eight scoring CSV unittest checks passed, including distinct site IDs in results and saved rows, rejection of invalid identifiers, and sample-loader compatibility. `git diff --check` passed.

**Kept as-is / changed / rejected:** Kept after verification. Site identity is supplied for each scoring call so one scorer can process multiple sites.

---

## Feature: Publish historical analysis branch changes

**Asked:** "do git push"; "comit and push"

**Got:** Pushed `feature/historical-analysis` to `origin` and established upstream tracking. On the subsequent commit-and-push request, committed the original sample CSV as `de0640e` and collaboration log as `fc96bf8`, then pushed both.

**Checked:** Git confirmed the remote branch creation and later update. The working directory was clean after that commit-and-push operation.

**Kept as-is / changed / rejected:** Kept. Later feature commits are recorded separately; this entry does not imply they have also been pushed.

---

## Feature: OpenWeather client and forecast integration

**Asked:** Build the weather integration and weather handling with the API,
following the Python II course and the approved implementation plan.

**Got:** Generic JSON client, OpenWeather current and forecast methods, normalized
weather readings, safe error handling, and forecast display for planner sites.
Forecasts are matched to viewing-window starts and cached for 30 minutes. The
combined score is marked unavailable until its astronomy inputs exist.

**Checked:** Offline automated tests cover current and forecast parsing, optional
fields, HTTP errors, timeout, invalid coordinates, invalid JSON, and forecast
matching. After key activation, live current-weather and five-day forecast requests
succeeded for Madrid; the forecast returned 40 slots. A real-browser app check
remains pending.

**Kept as-is / changed / rejected:** Pending team review.

---

## Feature: Weather-to-scoring contract check

**Asked:** Verify that the weather integration output matches the input expected
by scoring, using the project's sample scoring output.

**Got:** `tests/test_weather_scoring_contract.py` passes a mocked OpenWeather
forecast through the client, maps weather fields into `AstroSuitabilityScorer`,
and compares all score components against `data/scoring_output.csv`.

**Checked:** The test passes offline with fixed weather and astronomy inputs. It
checks interface compatibility, not a live API response or the app's unfinished
combined-score integration.

**Kept as-is / changed / rejected:** Pending team review.

---

## Feature: Live site scoring integration

**Asked:** "Run the app and fix the unavailable scoring error"

**Got:** Replaced the unconditional Unavailable score in `app.py` with per-site `AstroSuitabilityScorer` results using normalized weather forecasts and new `Planner.scoring_inputs()`. Astronomy inputs use target altitude, a linear sunset-to-astronomical-darkness heuristic, and the Moon's illuminated fraction when above the horizon; lunar observing is not penalized for daylight or moonlight. Results are saved with site IDs. Missing forecasts, incomplete weather inputs and persistence errors remain explicit. Updated the weather contract test for required site IDs and temporary-file persistence, and added a Streamlit integration test.

**Checked:** Started Streamlit locally on port 8501. AppTest startup produced zero exceptions. All 15 unittest checks passed; the app integration check used real Skyfield calculations and controlled forecasts, displayed numeric scores for three sites, and verified saved site IDs. The live weather check reported that OPENWEATHER_API_KEY must be configured in variables.env, so live forecast-based scores could not be verified in this environment. `git diff --check` passed.

**Kept as-is / changed / rejected:** Kept after verification. Scores use documented planning heuristics rather than placeholder sample scores. Live data requires a configured OpenWeather API key.

---

## Feature: Virgo forecast resilience

**Asked:** "fix the unavailable score error that appears when lookig for virgo in a 100 kilometer radius"

**Got:** Updated `OpenWeatherClient.forecast()` to retain valid forecast slots when another slot contains invalid data. It still raises a weather error when every slot is invalid and preserves the 90-minute forecast matching limit. Added regression tests for mixed valid/invalid slots and entirely invalid forecasts.

**Checked:** Reproduced the live Virgo search from Madrid within 100 km: Navacerrada's later forecast contained humidity 101%, causing the whole forecast to fail. After the fix the same live search showed three scores (31/100, 31/100, 45/100), zero app exceptions and zero warnings. All 17 unittest checks and `git diff --check` passed. Diagnostic scores were saved only to temporary files.

**Kept as-is / changed / rejected:** Kept after verification. Invalid data is skipped rather than altered; valid viewing-time forecasts remain usable.

---

## Feature: Site cards ordered by score

**Asked:** "Order weather insights output cards by score in descending order"

**Got:** Updated `app.py` to render cards by descending combined score, with unscored sites last. Equal scores retain their original planner order.

**Checked:** Reviewed the sort against numeric combined scores and missing-score handling; the existing Streamlit integration check passed. `git diff --check` passed.

**Kept as-is / changed / rejected:** Kept after verification.

---

## Feature: Current and forecast weather CSV history

**Asked:** "Append the current weather data from the api to historical_weather.csv and the forecast data to a forecast_weather.csv in the data directory"

**Got:** Added `storage.append_weather()` and automatic logging in `OpenWeatherClient.current_weather()` and `.forecast()`. Current observations append to `data/historical_weather.csv`; valid forecast slots append to `data/forecast_weather.csv`. Rows include UTC fetch time, API timestamp, coordinates, reading kind, normalized weather values and description. Headers are written once, optional missing values are blank, and existing rows are preserved. The client's optional `data_dir` supports isolated tests.

**Checked:** All 18 unittest checks passed, including repeated appends and separate current/forecast files. Fetched live data for Madrid centre, Navacerrada and Yebes (within 100 km of Madrid): appended 3 current observations and 119 valid forecast slots. Navacerrada's invalid humidity slot was skipped. `git diff --check` passed.

**Kept as-is / changed / rejected:** Kept after verification. Logging occurs on fresh API calls; cached Streamlit forecasts do not generate additional API-history rows.

---

## Feature: Five-minute weather collection

**Asked:** "Execute api calls every 5 minutes to build a historical dataset"

**Got:** Added `scripts/collect_weather.py`, which collects both endpoints for all ten configured sites immediately and every 300 seconds. Failed requests do not stop remaining endpoints or sites. Supports `--once` and configurable intervals. Started one hidden local background process, with logs and PID in the git-ignored `.weather-collector/` directory. Documented running and stopping it in README.md.

**Checked:** Confirmed the running process and first live cycle: 20/20 successful requests, 10 current readings and 397 valid forecast slots appended. Log confirms the next cycle is scheduled at the five-minute interval. All 19 unittest checks passed, including continued collection after an endpoint failure.

**Kept as-is / changed / rejected:** Kept and started after verification. Collection runs while the process and computer remain running; it is not configured to restart after reboot.

---

## Feature: Explain unavailable scores

**Asked:** "What makes a score unavailable?"

**Got:** Explained weather-request failures, no valid forecast within 90 minutes of the viewing-window start, missing required weather fields, invalid scoring inputs and CSV persistence failures. Distinguished unavailable scores from a low numeric score, and from the dash shown when there is no viewing window in the next 48 hours. No code was changed for this explanation.

**Checked:** The explanation follows the weather-fetch, forecast-match, input-validation and persistence branches in `app.py`, `client.py` and `models.py`. The subsequent prompt below requested an explicit time-limit message.

**Kept as-is / changed / rejected:** Kept the explanation; the next change clarified the message in the UI.

---

## Feature: Explain the forecast matching limit

**Asked:** "Specify in the error message that viewing windows are 90 minutes, so that the user knows that in the next 90 minutes there won't be an available score"

**Got:** Updated the missing-forecast message in `app.py` to state that no valid forecast is within 90 minutes before or after the viewing-window start. Clarified that this is the forecast matching limit rather than the duration of a viewing window or a prediction about when a score will become available.

**Checked:** Compared the message with the 90-minute limit in `forecast_for_time()` and ran `git diff --check`.

**Kept as-is / changed / rejected:** Changed the wording to explain the implemented time limit accurately.

---

## Feature: Weather history and observing analytics

**Asked:** "Create the following visializations in the analytics tab", followed by these requirements (the submitted list was repeated twice; recorded once here):

> Score history (line chart, Weather Analytics page)
> Shows: S_W over time for the sites the user picks, with night shaded and a dashed line at the 75 threshold.
> Answers: How have conditions changed at this site, and when did it cross 75?
> Detail: Average the 5-minute scores into hourly values, or a week of data becomes about 2,000 jittery points per site.
>
> Site ranking (horizontal bar chart, Location Explorer page)
> Shows: Mean nighttime score per site over the same date range, sorted best first. Each bar is labelled with its % of readings above 75 and its sample count (n).
> Answers: Which site has had the best skies in our recorded data?
>
> When is it clear? (heatmap, Weather Analytics page)
> Shows: One row per site and one column per hour of the night (18:00–07:00). Each cell’s colour is the mean score at that hour.
> Answers: Is a site usually clear after midnight but cloudy in the evening? 5-minute logging gives enough data for this.
>
> Why is this site’s score what it is? (stacked horizontal bars, Location Explorer or Details page)
> Shows: One bar per site for the latest reading, split into weighted parts (0.50C, 0.20H, 0.15V, 0.15W). The parts add up to S_W because the weights sum to 1.
> Answers: Is the score low because of cloud, or because of wind and humidity?
>
> Tonight’s observing window (line chart with two y-axes, Observation Planner or Details page)
> Shows: The target’s altitude across the night with the forecast score for the same site laid over it. The best window is shaded where both are high.
> Answers: What time should I be there?
> Detail: This chart is forecast plus Skyfield, not history, so label it clearly as a forecast.

**Got:** Added weather analytics calculations and Plotly chart builders in `analytics.py`, vectorized `Planner.sky_track()`, and `analytics_ui.py`, wired into the Analytics page. Three inner tabs provide Weather Analytics, Location Explorer and Observation Planner. Site and date filters apply to observed history; the planner has site and target selectors and shows tonight's forecast. Scores are derived from raw weather using the scorer's default weights, without generating new score-history rows. Current observations are deduplicated by site and API timestamp. Forecast charts use the latest fetched issue per site with the existing 90-minute matching limit. Solar altitude defines recorded nighttime; the heatmap covers the requested local clock hours. A refresh button reloads the recorded data.

**Checked:** All 24 unittest checks passed. Known values cover hourly averages, nighttime ranking and percentages, weighted contributions summing to 84, observation deduplication and latest forecast issue selection. Chart checks cover threshold lines, ordered ranking, empty heatmap cells, two forecast axes and best-window shading. Streamlit AppTest renders all five charts with controlled nighttime observations and forecasts. The real-data Analytics page runs without exceptions and correctly shows no nighttime ranking until nighttime observations are collected. Existing CSV histories were not modified by tests. `git diff --check` passed.

**Kept as-is / changed / rejected:** Kept after verification. Historical charts use observed weather-only S_W; the forecast is labelled separately, and missing data remains blank rather than being filled with invented scores.

---

## Feature: Explain data collection and score generation

**Asked:** "Is the weather updated for all sites or just the selected site?"; "Is the scoreing generated every time the data is updated for all sites?"; "Is real api data being used for the live conditions panel or is it stil running on sample data"

**Got:** Explained that the five-minute collector updates current weather and forecasts for all ten configured sites, independent of Analytics selection. Analytics derives weather-only S_W from saved readings when opened or refreshed; the collector does not append combined scoring-history rows. Live Conditions uses real OpenWeather forecasts, cached for 30 minutes, with Skyfield astronomy for the selected target and viewing-window start. It uses forecasts rather than current observations or sample scores. No implementation changes were requested in these questions.

**Checked:** These behaviors correspond to `scripts/collect_weather.py`, `analytics.py`, `analytics_ui.py` and the cached `site_forecast()` and scoring calls in `app.py`.

**Kept as-is / changed / rejected:** Kept the explanations. Combined-score history remains dependent on Live Conditions searches, rather than periodic weather collection.

---

## Feature: No distance preference

**Asked:** "Let's include an option of no preference in the live conditions tab so that users that don't care about the distance have access to all possible viewing alternatives"

**Got:** Added No preference to the maximum-travel-distance selector. The planner accepts a None distance limit and returns every configured site. Live Conditions headings reflect the unrestricted search, while the map omits the travel-radius circle and fits all sites and the user's location. Score ordering and visibility windows still apply.

**Checked:** All 25 unittest checks passed. Streamlit integration checks confirm the unrestricted search displays ten site cards and the existing 100 km search displays three, with generated scores persisted only to temporary files. `git diff --check` passed.

**Kept as-is / changed / rejected:** Kept after verification. All alternatives means the sites configured in data/sites.csv.

---

## Feature: Requirements gap analysis and fixes

**Asked:** "Read the INSTRUCTIONS_README.md file and review the codebase to identify any missing requirement. Write a report to ANALYSIS_REPORT.md with the observations, but do not modify anything", followed by "Create a feature/fixes branch and implement fixes in the codebase suggested in the ANALYSIS_REPORT.md. Do not implement fixes relating to the repo itself, such as missing commits or contributions, etc. Do partial commits for the code changes and commit the updated datasets as well."

**Got:** A local `ANALYSIS_REPORT.md` (git-ignored) mapping each rubric row to evidence in the code, then these fixes on `feature/fixes`:
- `client.py`: `BaseAPIClient` became provider-neutral, raising a configurable `APIError` subtype with messages built from `service_name`. It now has distinct 404 and 5xx messages. The API key is stored name-mangled (`__api_key`), which replaced an unfinished local rename that imported a nonexistent `get__api_key`. Added `current_weather_for_city()` with input validation before the request, plus `WeatherReading.scoring_inputs` / `missing_scoring_fields` properties.
- `models.py`: `ScoreResult.rating` property, `__lt__` (ranking with `sorted()`/`max()`), `__str__`, and a logged `computed_at` time. `data/scoring_output.csv` gained the column; older rows have it blank.
- `app.py`: current conditions on Live Conditions, which removed the last TODO. A city text box is the fallback when geolocation is unavailable. Scores are cached per site, target and forecast slot, so reruns stop appending duplicate rows. Cards show the score rating.
- `analytics.py`: every chart has a title, and the score axes state their 0–100 scale.
- Removed the unused placeholder `scoring.py` and the root `sample_scoring_output.csv`. Ignored `*.egg-info/`. Rewrote the README description and the outdated notes.

**Checked:** `uv run python -m unittest discover -s tests` passes 36 tests. New tests cover: a distinct message per failure mode; city lookup, unknown city and invalid input with no request sent; the key not being reachable as `_api_key` and absent from `repr`; rating bands and ordering; `computed_at` logging; current conditions and the city fallback in the app; and no duplicate score rows across reruns. All tests use mocks and temporary files. Not checked in a real browser.

**Kept as-is / changed / rejected:** _Pending team review of `feature/fixes`._
