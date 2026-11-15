from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st
from streamlit_geolocation import streamlit_geolocation

from weather_app import history
from weather_app.astronomy import load_celestial_bodies, load_ephemeris
from weather_app.maps import SiteMarker, sites_map
from weather_app.models import AstroSuitabilityScorer
from weather_app.planner import LOOKAHEAD_HOURS, Planner
from weather_app.client import OpenWeatherClient, WeatherError, forecast_for_time
from weather_app.sites import load_sites
from weather_app.storage import DATA_DIR
from weather_app.utils import compass_point, google_maps_directions_url

DEFAULT_TIMEZONE = "Europe/Madrid"
STATUS_BADGE_COLORS = {"Visible now": "green", "Visible later": "orange", "Not visible soon": "gray"}
# Saved data older than this gets a "start the collector" warning.
STALE_CURRENT = timedelta(hours=1)
STALE_FORECAST = timedelta(hours=6)
COLLECTOR_HINT = "Start `scripts/collect_weather.py` to record fresher data."

st.set_page_config(page_title="Weather Insights", page_icon="\U0001F324️")


@st.cache_resource(show_spinner="Loading planets and constellations...")
def load_astronomy_data():
    # Only the slow-to-load data is cached (once per server). The Planner itself
    # is cheap and built on every run, so edits to planner.py take effect
    # without restarting Streamlit.
    ephemeris = load_ephemeris()
    return ephemeris, load_celestial_bodies(ephemeris)


def get_planner() -> Planner:
    ephemeris, celestial_bodies = load_astronomy_data()
    return Planner(load_sites(), celestial_bodies, ephemeris)


# Only the collector (scripts/collect_weather.py) requests weather from the API.
# The app reads the latest data it saved, so using the app never adds rows to
# the history files.
@st.cache_data(show_spinner=False)
def _saved_fetches(kind: str, modified: float):
    """Parse a log once per change of the file (``modified`` is its mtime)."""
    return history.latest_fetches(kind)


def saved_fetches(kind: str):
    """Latest saved fetch per location for "current" or "forecast" readings."""
    try:
        modified = (DATA_DIR / history.FILES[kind]).stat().st_mtime
    except OSError:
        modified = 0.0
    return _saved_fetches(kind, modified)


@st.cache_data(ttl=86400, show_spinner=False)
def locate_city(city: str):
    """Coordinates for a city name. Geocoding only: no weather is fetched or saved."""
    return OpenWeatherClient().geocode_city(city)


def is_stale(fetched_at: datetime, limit: timedelta) -> bool:
    return datetime.now(timezone.utc) - fetched_at > limit


def show_current_conditions(latitude: float, longitude: float, place: str) -> None:
    """Latest recorded conditions at the observing site nearest the user."""
    current = saved_fetches("current")
    nearby = sorted(
        ((site.distance_km(latitude, longitude), site) for site in planner.sites
         if history.location_key(site.latitude, site.longitude) in current),
        key=lambda pair: pair[0],
    )
    if not nearby:
        st.info(f"No current conditions have been recorded yet. {COLLECTOR_HINT}")
        return
    distance, site = nearby[0]
    fetch = current[history.location_key(site.latitude, site.longitude)]
    reading = fetch.latest_reading
    st.subheader(f"Latest recorded conditions near {place}")

    def shown(number, unit, digits=0):
        return "—" if number is None else f"{number:.{digits}f} {unit}"

    columns = st.columns(5)
    columns[0].metric("Temperature", shown(reading.temperature_c, "°C", 1))
    columns[1].metric("Cloud cover", shown(reading.cloud_cover_percent, "%"))
    columns[2].metric("Humidity", shown(reading.humidity_percent, "%"))
    columns[3].metric("Wind", shown(reading.wind_speed_mps, "m/s", 1))
    visibility_km = None if reading.visibility_m is None else reading.visibility_m / 1000
    columns[4].metric("Visibility", shown(visibility_km, "km", 1))
    st.caption(f"{(reading.description or 'Conditions unavailable').capitalize()} · "
               f"recorded at {site.name}, {distance:.1f} km away · "
               f"observed {reading.timestamp.astimezone(viewer_timezone()):%a %H:%M}.")
    if is_stale(fetch.fetched_at, STALE_CURRENT):
        st.warning(f"This is the most recent reading saved for {site.name}. {COLLECTOR_HINT}")


def viewer_timezone() -> ZoneInfo:
    """The browser's time zone, falling back to Madrid if it is unknown."""
    try:
        return ZoneInfo(st.context.timezone or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TIMEZONE)


planner = get_planner()
CELESTIAL_BODY = planner.celestial_bodies
TRAVEL_DISTANCE_OPTIONS_KM = [5, 10, 15, 30, 50, 100, None]

st.title("Weather Insights")

page = st.sidebar.radio("View", ["Live Conditions", "Analytics"])

# Location sharing lives in the sidebar so it is available from page load
# without taking space in the main view. streamlit-geolocation only asks the
# browser for the location when its icon is clicked.
# A city name is the fallback when the browser cannot or may not share a location.
with st.sidebar:
    st.caption("📍 Your location")
    location = streamlit_geolocation()
    if location and location.get("latitude") is not None:
        coords = (location["latitude"], location["longitude"])
        # The component returns the same fix on every rerun; only a new fix
        # should replace a city the user typed afterwards.
        if st.session_state.get("geolocation") != coords:
            st.session_state["geolocation"] = coords
            st.session_state["user_location"] = coords
            st.session_state["location_label"] = "your location"
    with st.form("city_form", border=False):
        city = st.text_input("Or enter a city", placeholder="e.g. Madrid or Granada,ES")
        use_city = st.form_submit_button("Use this city")
    if use_city:
        try:
            place = locate_city(OpenWeatherClient.validate_city(city))
        except (WeatherError, ValueError) as exc:
            st.error(str(exc))
        else:
            st.session_state["user_location"] = (place.latitude, place.longitude)
            st.session_state["location_label"] = place.label
    if "user_location" in st.session_state:
        st.caption(f"Using {st.session_state.get('location_label', 'your location')} ✓")
    else:
        st.caption("Click the icon and allow access in your browser, or enter a city.")

if page == "Live Conditions":
    st.header("Live Conditions")
    if "user_location" in st.session_state:
        here_lat, here_lon = st.session_state["user_location"]
        show_current_conditions(here_lat, here_lon,
                                st.session_state.get("location_label", "your location"))
    else:
        st.info("Share your location with the 📍 icon in the sidebar, or enter a city, "
                "to see current conditions and nearby observing sites.")
    body_col, distance_col, button_col = st.columns([3, 2, 1], vertical_alignment="bottom")
    with body_col:
        selected_body = st.selectbox("Celestial body", list(CELESTIAL_BODY))
    with distance_col:
        max_travel_km = st.selectbox(
            "Maximum travel distance",
            TRAVEL_DISTANCE_OPTIONS_KM,
            format_func=lambda km: "No preference" if km is None else f"{km} km",
        )
    with button_col:
        if st.button("Get Sites", type="primary", width="stretch"):
            # Remember the query so the results survive later reruns
            # (e.g. when the location arrives after the click).
            st.session_state["sites_query"] = (selected_body, max_travel_km)

    if "sites_query" in st.session_state:
        query_body, query_km = st.session_state["sites_query"]
        if "user_location" not in st.session_state:
            st.warning("Share your location with the 📍 icon in the sidebar, or enter a city, "
                       "to find nearby sites.")
        else:
            lat, lon = st.session_state["user_location"]
            outlooks = planner.site_outlooks(query_body, lat, lon, query_km)
            if not outlooks:
                st.info("There are no configured observing sites." if query_km is None
                        else f"There are no observing sites within {query_km} km of your location.")
            else:
                local_tz = viewer_timezone()
                forecasts = {}
                saved_forecasts = saved_fetches("forecast")
                forecast_saved_at = {}
                scores = {}
                score_errors = {}
                scorer = AstroSuitabilityScorer()
                # Streamlit reruns this script on every interaction; score (and log) each
                # site, target and forecast slot once per session instead of every rerun.
                score_cache = st.session_state.setdefault("score_cache", {})
                for outlook in outlooks:
                    if outlook.window_start_utc is None:
                        continue
                    fetch = saved_forecasts.get(
                        history.location_key(outlook.site.latitude, outlook.site.longitude))
                    if fetch is None:
                        forecasts[outlook.site.site_id] = (
                            None, f"no forecast has been recorded for this site yet. {COLLECTOR_HINT}")
                    else:
                        forecast_saved_at[outlook.site.site_id] = fetch.fetched_at
                        forecasts[outlook.site.site_id] = (
                            forecast_for_time(list(fetch.readings), outlook.window_start_utc), None)

                    reading, error = forecasts[outlook.site.site_id]
                    if error or reading is None:
                        continue
                    if reading.missing_scoring_fields:
                        score_errors[outlook.site.site_id] = (
                            "Missing forecast data: " + ", ".join(reading.missing_scoring_fields))
                        continue
                    cache_key = (outlook.site.site_id, query_body, reading)
                    if cache_key not in score_cache:
                        try:
                            score_cache[cache_key] = scorer.score(
                                site_id=outlook.site.site_id,
                                timestamp=outlook.window_start_utc,
                                **reading.scoring_inputs,
                                **planner.scoring_inputs(outlook.site, query_body, outlook.window_start_utc),
                            )
                        except (ValueError, OSError) as exc:
                            score_errors[outlook.site.site_id] = str(exc)
                            continue
                    scores[outlook.site.site_id] = score_cache[cache_key]

                def local_time(moment):
                    return moment.astimezone(local_tz).strftime("%a %H:%M")

                def status_of(outlook):
                    if outlook.visible_now:
                        return "Visible now"
                    return "Visible later" if outlook.window_start_utc else "Not visible soon"

                def visible_from(outlook):
                    if outlook.visible_now:
                        return "Now"
                    if outlook.window_start_utc:
                        return local_time(outlook.window_start_utc)
                    return f"Not in next {LOOKAHEAD_HOURS} h"

                def visible_until(outlook):
                    if outlook.window_end_utc:
                        return local_time(outlook.window_end_utc)
                    return f"Beyond {LOOKAHEAD_HOURS} h" if outlook.window_start_utc else "—"

                def score_text(outlook):
                    # No score for a site where the body never becomes visible.
                    result = scores.get(outlook.site.site_id)
                    if result is not None:
                        return f"{result.combined:.0f}/100"
                    return "Unavailable" if outlook.window_start_utc else "—"

                def rating_suffix(outlook):
                    result = scores.get(outlook.site.site_id)
                    return f" ({result.rating})" if result is not None else ""

                def where_to_look(outlook):
                    if not outlook.window_start_utc:
                        return "Stays below the horizon or in daylight"
                    return (
                        f"Look {compass_point(outlook.azimuth_deg)} ({outlook.azimuth_deg:.0f}°), "
                        f"{outlook.altitude_deg:.0f}° above the horizon"
                    )

                st.subheader(f"{query_body} from all observing sites" if query_km is None
                             else f"{query_body} from sites within {query_km} km")
                if not any(o.visible_now for o in outlooks):
                    st.info(
                        f"{query_body} can't be seen from any of these sites right now. "
                        "Each site below shows when it will be."
                    )

                markers = [
                    SiteMarker(
                        name=o.site.name,
                        latitude=o.site.latitude,
                        longitude=o.site.longitude,
                        status=status_of(o),
                        hover=(
                            f"<b>{o.site.name}</b><br>"
                            f"Score: <b>{score_text(o)}</b>{rating_suffix(o)}<br>"
                            f"Visible from <b>{visible_from(o)}</b> until <b>{visible_until(o)}</b><br>"
                            f"{o.distance_km} km away · Sunset {local_time(o.sunset_utc) if o.sunset_utc else '—'}"
                        ),
                    )
                    for o in outlooks
                ]
                st.plotly_chart(sites_map(lat, lon, query_km, markers), width="stretch")

                # ScoreResult orders by combined score; unscored sites keep their planner order.
                scored = [o for o in outlooks if o.site.site_id in scores]
                ranked_outlooks = (
                    sorted(scored, key=lambda o: scores[o.site.site_id], reverse=True)
                    + [o for o in outlooks if o.site.site_id not in scores]
                )
                for o in ranked_outlooks:
                    status = status_of(o)
                    with st.container(border=True):
                        name_col, badge_col = st.columns([4, 1], vertical_alignment="center")
                        name_col.markdown(f"**{o.site.name}**")
                        badge_col.badge(status, color=STATUS_BADGE_COLORS[status])
                        score_col, from_col, until_col = st.columns(3)
                        result = scores.get(o.site.site_id)
                        score_col.metric("Score", score_text(o),
                                         delta=result.rating if result is not None else None,
                                         delta_color="off")
                        if o.site.site_id in score_errors:
                            st.warning(f"Score unavailable: {score_errors[o.site.site_id]}")
                        from_col.metric("Visible from", visible_from(o))
                        until_col.metric("Visible until", visible_until(o))
                        sunset = local_time(o.sunset_utc) if o.sunset_utc else "—"
                        st.caption(f"{o.distance_km} km away · Sunset {sunset} · {where_to_look(o)}")
                        if o.window_start_utc:
                            reading, error = forecasts[o.site.site_id]
                            if error:
                                st.warning(f"Weather unavailable: {error}")
                            elif reading is None:
                                st.info(
                                    "Score unavailable for this viewing window: no valid weather "
                                    "forecast is within 90 minutes before or after its start time. "
                                    "A score requires a forecast within that range."
                                )
                            else:
                                def value(number, unit):
                                    return f"{number:g}{unit}" if number is not None else "Unavailable"
                                saved_at = forecast_saved_at[o.site.site_id]
                                if is_stale(saved_at, STALE_FORECAST):
                                    st.warning(f"This forecast was saved {local_time(saved_at)}. "
                                               f"{COLLECTOR_HINT}")
                                st.write(
                                    f"Forecast at {local_time(reading.timestamp)} "
                                    f"(saved {local_time(saved_at)}): "
                                    f"{reading.description or 'Conditions unavailable'} · "
                                    f"Clouds {value(reading.cloud_cover_percent, '%')} · "
                                    f"Humidity {value(reading.humidity_percent, '%')} · "
                                    f"Visibility {value(reading.visibility_m, ' m')} · "
                                    f"Wind {value(reading.wind_speed_mps, ' m/s')} · "
                                    f"Temperature {value(reading.temperature_c, ' °C')}"
                                )
                        st.link_button(
                            "Directions in Google Maps",
                            google_maps_directions_url(lat, lon, o.site.latitude, o.site.longitude),
                            icon=":material/directions_car:",
                        )

                st.caption(
                    f"Times are in {local_tz.key}. Visible means at least "
                    f"{planner.min_altitude_deg:.0f}° above the horizon with a dark enough sky "
                    "(weather not included). Forecasts use the nearest three-hour slot within "
                    "90 minutes of the start of the viewing window, taken from the latest forecast "
                    "the collector saved. Scores combine forecast "
                    "weather with target altitude, twilight darkness and lunar illumination "
                    "at the viewing-window start. Astronomy suitability uses planning heuristics; "
                    "lunar observing is not penalized for daylight or moonlight."
                )

elif page == "Analytics":
    st.header("Analytics")
    from weather_app.analytics_ui import render_analytics
    render_analytics(planner, viewer_timezone())
