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
