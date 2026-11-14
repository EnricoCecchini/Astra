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
