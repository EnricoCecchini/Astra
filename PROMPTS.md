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

## Feature: Append scoring results to CSV

**Asked:** "add a function to the astrosuitabilityscorer to append the score to the scoring output csv"

**Got:** `AstroSuitabilityScorer.append_score(result, path=None)` in `src/weather_app/models.py`. Appends a `ScoreResult` to `data/scoring_output.csv` by default, supports a custom path, creates missing directories and headers, and serializes the timestamp as ISO 8601. Rejects incompatible CSV headers before writing and handles existing files without a final newline. Added `tests/test_scoring_csv.py`.

**Checked:** All three unittest checks passed using the bundled Python runtime: repeated appends preserve prior rows and one header, empty files and missing final newlines work, and incompatible headers leave the existing file unchanged. The sample combined score was verified as 88.2. `git diff --check` passed. Tests used temporary files and did not modify the project scoring CSV.

**Kept as-is / changed / rejected:** Kept the implementation after verification. Saving is an explicit call after scoring.

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
