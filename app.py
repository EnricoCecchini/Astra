from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st
from streamlit_geolocation import streamlit_geolocation

from weather_app.astronomy import load_celestial_bodies, load_ephemeris
from weather_app.maps import SiteMarker, sites_map
from weather_app.planner import LOOKAHEAD_HOURS, Planner
from weather_app.scoring import load_sample_scores
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


def viewer_timezone() -> ZoneInfo:
    """The browser's time zone, falling back to Madrid if it is unknown."""
    try:
        return ZoneInfo(st.context.timezone or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TIMEZONE)


planner = get_planner()
SAMPLE_SCORES = load_sample_scores()
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
                scores = SAMPLE_SCORES  # placeholder: same sample row for every site

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
                    return f"{scores['combined']:.0f}/100" if outlook.window_start_utc else "—"

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

                for o in outlooks:
                    status = status_of(o)
                    with st.container(border=True):
                        name_col, badge_col = st.columns([4, 1], vertical_alignment="center")
                        name_col.markdown(f"**{o.site.name}**")
                        badge_col.badge(status, color=STATUS_BADGE_COLORS[status])
                        score_col, from_col, until_col = st.columns(3)
                        score_col.metric("Score", score_text(o))
                        from_col.metric("Visible from", visible_from(o))
                        until_col.metric("Visible until", visible_until(o))
                        sunset = local_time(o.sunset_utc) if o.sunset_utc else "—"
                        st.caption(f"{o.distance_km} km away · Sunset {sunset} · {where_to_look(o)}")
                        st.link_button(
                            "Directions in Google Maps",
                            google_maps_directions_url(lat, lon, o.site.latitude, o.site.longitude),
                            icon=":material/directions_car:",
                        )

                st.caption(
                    f"Times are in {local_tz.key}. Visible means at least "
                    f"{planner.min_altitude_deg:.0f}° above the horizon with a dark enough sky "
                    "(weather not included). Scores are sample values from "
                    "data/scoring_output.csv, the same for every site until per-site scoring "
                    "is implemented."
                )
    # TODO: let the user add/select locations and display current conditions.

elif page == "Analytics":
    st.header("Analytics")
    # TODO: at least 2 charts built from your logged history (see src/weather_app/analytics.py).
