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

if page == "Live Conditions":
    st.header("Live Conditions")
    body_col, distance_col = st.columns(2)
    with body_col:
        selected_body = st.selectbox("Celestial body", list(CELESTIAL_BODY))
    with distance_col:
        max_travel_km = st.selectbox(
            "Maximum travel distance",
            TRAVEL_DISTANCE_OPTIONS_KM,
            format_func=lambda km: f"{km} km",
        )

    if st.button("Confirm", type="primary"):
        st.session_state["location_requested"] = True

    # Kept in session_state so the location widget stays on screen across reruns.
    if st.session_state.get("location_requested"):
        st.write("Click the location icon below and allow access in your browser to share your location.")
        location = streamlit_geolocation()
        if location and location.get("latitude") is not None:
            st.session_state["user_location"] = (location["latitude"], location["longitude"])

        if "user_location" in st.session_state:
            lat, lon = st.session_state["user_location"]
            st.success(f"Location received: {lat:.4f}, {lon:.4f}")

            visible = planner.visible_sites(selected_body, lat, lon, max_travel_km)
            if visible:
                st.subheader(f"Sites where {selected_body} is visible now")
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
                in_range = len(planner.sites_within(lat, lon, max_travel_km))
                st.info(
                    f"{selected_body} can't be seen right now from any of the {in_range} "
                    f"site(s) within {max_travel_km} km: it is too low or the sky is not dark yet."
                )
        else:
            st.caption(
                "Waiting for your location. If nothing happens, check that location access "
                "is allowed for this site in your browser settings."
            )
    # TODO: let the user add/select locations and display current conditions.

elif page == "Analytics":
    st.header("Analytics")
    # TODO: at least 2 charts built from your logged history (see src/weather_app/analytics.py).
