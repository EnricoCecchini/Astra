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
