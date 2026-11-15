from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st
from streamlit_geolocation import streamlit_geolocation

from weather_app.astronomy import load_celestial_bodies, load_ephemeris
from weather_app.maps import SiteMarker, sites_map
from weather_app.models import AstroSuitabilityScorer
from weather_app.planner import LOOKAHEAD_HOURS, Planner
from weather_app.client import OpenWeatherClient, WeatherError, forecast_for_time
from weather_app.sites import load_sites
from weather_app.utils import compass_point, google_maps_directions_url

DEFAULT_TIMEZONE = "Europe/Madrid"
STATUS_BADGE_COLORS = {"Visible now": "green", "Visible later": "orange", "Not visible soon": "gray"}

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


@st.cache_data(ttl=1800, show_spinner=False)
def site_forecast(latitude: float, longitude: float):
    """Reuse successful forecasts for 30 minutes across Streamlit reruns."""
    return OpenWeatherClient().forecast(latitude, longitude)


def viewer_timezone() -> ZoneInfo:
    """The browser's time zone, falling back to Madrid if it is unknown."""
    try:
        return ZoneInfo(st.context.timezone or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TIMEZONE)


planner = get_planner()
CELESTIAL_BODY = planner.celestial_bodies
TRAVEL_DISTANCE_OPTIONS_KM = [5, 10, 15, 30, 50, 100]

st.title("Weather Insights")

page = st.sidebar.radio("View", ["Live Conditions", "Analytics"])

# Location sharing lives in the sidebar so it is available from page load
# without taking space in the main view. streamlit-geolocation only asks the
# browser for the location when its icon is clicked.
with st.sidebar:
    st.caption("📍 Your location")
    location = streamlit_geolocation()
    if location and location.get("latitude") is not None:
        st.session_state["user_location"] = (location["latitude"], location["longitude"])
    if "user_location" in st.session_state:
        st.caption("Location shared ✓")
    else:
        st.caption("Click the icon and allow access in your browser.")

if page == "Live Conditions":
    st.header("Live Conditions")
    body_col, distance_col, button_col = st.columns([3, 2, 1], vertical_alignment="bottom")
    with body_col:
        selected_body = st.selectbox("Celestial body", list(CELESTIAL_BODY))
    with distance_col:
        max_travel_km = st.selectbox(
            "Maximum travel distance",
            TRAVEL_DISTANCE_OPTIONS_KM,
            format_func=lambda km: f"{km} km",
        )
    with button_col:
        if st.button("Get Sites", type="primary", width="stretch"):
            # Remember the query so the results survive later reruns
            # (e.g. when the location arrives after the click).
            st.session_state["sites_query"] = (selected_body, max_travel_km)

    if "sites_query" in st.session_state:
        query_body, query_km = st.session_state["sites_query"]
        if "user_location" not in st.session_state:
            st.warning("Share your location with the 📍 icon in the sidebar to find nearby sites.")
        else:
            lat, lon = st.session_state["user_location"]
            outlooks = planner.site_outlooks(query_body, lat, lon, query_km)
            if not outlooks:
                st.info(f"There are no observing sites within {query_km} km of your location.")
            else:
                local_tz = viewer_timezone()
                forecasts = {}
                scores = {}
                score_errors = {}
                scorer = AstroSuitabilityScorer()
                for outlook in outlooks:
                    if outlook.window_start_utc is None:
                        continue
                    try:
                        readings = site_forecast(outlook.site.latitude, outlook.site.longitude)
                        forecasts[outlook.site.site_id] = (
                            forecast_for_time(readings, outlook.window_start_utc), None
                        )
                    except (WeatherError, ValueError) as exc:
                        forecasts[outlook.site.site_id] = (None, str(exc))

                    reading, error = forecasts[outlook.site.site_id]
                    if error or reading is None:
                        continue
                    weather_inputs = {
                        "cloud_cover_percent": reading.cloud_cover_percent,
                        "relative_humidity_percent": reading.humidity_percent,
                        "visibility_m": reading.visibility_m,
                        "wind_speed_mps": reading.wind_speed_mps,
                    }
                    missing = [name for name, value in weather_inputs.items() if value is None]
                    if missing:
                        score_errors[outlook.site.site_id] = "Missing forecast data: " + ", ".join(missing)
                        continue
                    try:
                        scores[outlook.site.site_id] = scorer.score(
                            site_id=outlook.site.site_id,
                            timestamp=outlook.window_start_utc,
                            **weather_inputs,
                            **planner.scoring_inputs(outlook.site, query_body, outlook.window_start_utc),
                        )
                    except (ValueError, OSError) as exc:
                        score_errors[outlook.site.site_id] = str(exc)

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

                def where_to_look(outlook):
                    if not outlook.window_start_utc:
                        return "Stays below the horizon or in daylight"
                    return (
                        f"Look {compass_point(outlook.azimuth_deg)} ({outlook.azimuth_deg:.0f}°), "
                        f"{outlook.altitude_deg:.0f}° above the horizon"
                    )

                st.subheader(f"{query_body} from sites within {query_km} km")
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
                            f"Score: <b>{score_text(o)}</b><br>"
                            f"Visible from <b>{visible_from(o)}</b> until <b>{visible_until(o)}</b><br>"
                            f"{o.distance_km} km away · Sunset {local_time(o.sunset_utc) if o.sunset_utc else '—'}"
                        ),
                    )
                    for o in outlooks
                ]
                st.plotly_chart(sites_map(lat, lon, query_km, markers), width="stretch")

                ranked_outlooks = sorted(
                    outlooks,
                    key=lambda outlook: (
                        -scores[outlook.site.site_id].combined
                        if outlook.site.site_id in scores else float("inf")
                    ),
                )
                for o in ranked_outlooks:
                    status = status_of(o)
                    with st.container(border=True):
                        name_col, badge_col = st.columns([4, 1], vertical_alignment="center")
                        name_col.markdown(f"**{o.site.name}**")
                        badge_col.badge(status, color=STATUS_BADGE_COLORS[status])
                        score_col, from_col, until_col = st.columns(3)
                        score_col.metric("Score", score_text(o))
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
                                st.write(
                                    f"Forecast at {local_time(reading.timestamp)}: "
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
                    "90 minutes of the start of the viewing window. Scores combine forecast "
                    "weather with target altitude, twilight darkness and lunar illumination "
                    "at the viewing-window start. Astronomy suitability uses planning heuristics; "
                    "lunar observing is not penalized for daylight or moonlight."
                )
    # TODO: let the user add/select locations and display current conditions.

elif page == "Analytics":
    st.header("Analytics")
    # TODO: at least 2 charts built from your logged history (see src/weather_app/analytics.py).
