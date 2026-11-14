import streamlit as st

from weather_app.astronomy import load_celestial_bodies

st.set_page_config(page_title="Weather Insights", page_icon="\U0001F324️")


@st.cache_resource(show_spinner="Loading planets and constellations...")
def get_celestial_bodies() -> dict[str, dict]:
    # Cached so the ephemeris is loaded once per server, not on every rerun.
    return load_celestial_bodies()


CELESTIAL_BODY = get_celestial_bodies()

st.title("Weather Insights")

page = st.sidebar.radio("View", ["Live Conditions", "Analytics"])

if page == "Live Conditions":
    st.header("Live Conditions")
    selected_body = st.selectbox("Celestial body", list(CELESTIAL_BODY))
    # TODO: let the user add/select locations and display current conditions.

elif page == "Analytics":
    st.header("Analytics")
    # TODO: at least 2 charts built from your logged history (see src/weather_app/analytics.py).
