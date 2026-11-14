import streamlit as st
from streamlit_geolocation import streamlit_geolocation

from weather_app.astronomy import load_celestial_bodies, load_ephemeris
from weather_app.planner import Planner
from weather_app.sites import load_sites

st.set_page_config(page_title="Weather Insights", page_icon="\U0001F324️")


@st.cache_resource(show_spinner="Loading planets and constellations...")
def get_planner() -> Planner:
    # Cached so the ephemeris, sites and constellation centres are loaded once
    # per server, not on every rerun.
    ephemeris = load_ephemeris()
    return Planner(load_sites(), load_celestial_bodies(ephemeris), ephemeris)


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
            visible = planner.visible_sites(query_body, lat, lon, query_km)
            if visible:
                st.subheader(f"Sites where {query_body} is visible now")
                st.dataframe(
                    [
                        {
                            "Site": v.site.name,
                            "Distance (km)": v.distance_km,
                            "Altitude (°)": v.altitude_deg,
                            "Azimuth (°)": v.azimuth_deg,
                        }
                        for v in visible
                    ],
                    hide_index=True,
                )
            else:
                in_range = len(planner.sites_within(lat, lon, query_km))
                st.info(
                    f"{query_body} can't be seen right now from any of the {in_range} "
                    f"site(s) within {query_km} km: it is too low or the sky is not dark yet."
                )
    # TODO: let the user add/select locations and display current conditions.

elif page == "Analytics":
    st.header("Analytics")
    # TODO: at least 2 charts built from your logged history (see src/weather_app/analytics.py).
