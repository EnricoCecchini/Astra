"""Streamlit analytics views backed by the weather CSV histories."""

from datetime import datetime, time, timedelta

import pandas as pd
import streamlit as st

from .analytics import (components_chart, forecast_chart, heatmap_chart, history_chart,
                        load_weather_history, nighttime_ranking, ranking_chart)
from .storage import DATA_DIR


def render_analytics(planner, timezone):
    sites = planner.sites
    by_id = {site.site_id: site for site in sites}
    st.caption("Weather score S_W uses cloud, humidity, visibility and wind. It is separate from the combined astronomy score.")
    st.button("Refresh recorded data", key="refresh_analytics")
    selected = st.multiselect("Sites", list(by_id), default=list(by_id),
                              format_func=lambda key: by_id[key].name)
    if not selected:
        st.info("Select at least one site to explore its weather.")
        return
    try:
        history = load_weather_history(DATA_DIR / "historical_weather.csv", sites, "current")
        forecasts = load_weather_history(DATA_DIR / "forecast_weather.csv", sites, "forecast")
    except (OSError, ValueError, KeyError, pd.errors.ParserError) as exc:
        st.error(f"Weather history could not be loaded: {exc}")
        return
    now = datetime.now(timezone)
    if not history.empty:
        history["local_time"] = history.timestamp.dt.tz_convert(timezone)
        first = history.local_time.min().date()
        last = history.local_time.max().date()
    else:
        first = last = now.date()
    dates = st.date_input("History date range", value=(first, last))
    if len(dates) != 2:
        st.info("Choose a start and end date for recorded history.")
        return
    if not history.empty:
        history = history[history.site_id.isin(selected)
                          & history.local_time.dt.date.between(*dates)].copy()
    if not history.empty:
        history["is_night"] = False
        for site_id, group in history.groupby("site_id"):
            _, solar_altitude = planner.sky_track(by_id[site_id], "Moon", group.timestamp.dt.to_pydatetime())
            history.loc[group.index, "is_night"] = solar_altitude <= planner.max_sun_altitude_deg
    st.caption(f"Times: {timezone.key}. Night means Sun at or below {planner.max_sun_altitude_deg:g}°. "
               "Repeated observations are counted once. Missing data stays blank. History filters apply to the first four charts.")
    weather_tab, location_tab, forecast_tab = st.tabs(
        ["Weather Analytics", "Location Explorer", "Observation Planner"])
    with weather_tab:
        st.subheader("Score history")
        st.caption("Hourly mean S_W; dashed line = 75. Shaded intervals mark recorded nighttime observations.")
        if history.empty:
            st.info("No recorded weather for these sites and dates yet.")
        else:
            st.plotly_chart(history_chart(history, timezone.key), width="stretch")
        st.subheader("When is it clear?")
        st.caption("Mean observed S_W by local clock hour, from 18:00 through 07:00. Blank cells mean no readings.")
        if not history.empty:
            st.plotly_chart(heatmap_chart(history, timezone.key), width="stretch")
    with location_tab:
        st.subheader("Site ranking")
        st.caption("Mean nighttime S_W over the selected dates. Labels show readings strictly above 75 and sample count n.")
        if history.empty or nighttime_ranking(history).empty:
            st.info("No nighttime observations in this date range yet. Rankings appear as the collector records nights.")
        else:
            st.plotly_chart(ranking_chart(history), width="stretch")
        st.subheader("Why is this site's score what it is?")
        st.caption("Latest observed reading per site within the selected dates. The four weighted contributions sum to S_W.")
        if not history.empty:
            st.plotly_chart(components_chart(history), width="stretch")
    with forecast_tab:
        st.subheader("Tonight's observing window · Forecast")
        site_id = st.selectbox("Forecast site", selected, format_func=lambda key: by_id[key].name)
        target = st.selectbox("Forecast target", list(planner.celestial_bodies),
                              index=list(planner.celestial_bodies).index("Saturn"))
        # Before 08:00, tonight refers to the night already in progress.
        evening = now.date() - timedelta(days=1) if now.hour < 8 else now.date()
        start = datetime.combine(evening, time(18), tzinfo=timezone)
        end = datetime.combine(evening + timedelta(days=1), time(8), tzinfo=timezone)
        st.caption(f"Forecast, not recorded history: {start:%d %b %H:%M}–{end:%d %b %H:%M} ({timezone.key}). "
                   f"Green = forecast S_W ≥75 and target altitude ≥{planner.min_altitude_deg:g}° "
                   "with a dark enough sky (darkness is not required for the Moon).")
        site_forecasts = forecasts[forecasts.site_id == site_id].copy() if not forecasts.empty else forecasts
        if site_forecasts.empty:
            st.info("No saved forecast for this site. The five-minute collector will save forecasts when the API is available.")
            return
        issue = site_forecasts.fetched_at.max()
        st.caption(f"Forecast fetched {issue.tz_convert(timezone):%d %b %H:%M}. "
                   "Nearest three-hour forecast slots are used within 90 minutes; gaps are left blank.")
        if (pd.Timestamp(now) - issue) > pd.Timedelta(hours=6):
            st.warning("This forecast snapshot is more than six hours old. Wait for a successful collection for fresher data.")
        grid = pd.DataFrame({"timestamp": pd.date_range(start, end, freq="5min").tz_convert("UTC")})
        track = pd.merge_asof(grid, site_forecasts[["timestamp", "weather"]].sort_values("timestamp"),
                              on="timestamp", direction="nearest", tolerance=pd.Timedelta(minutes=90))
        track["local_time"] = track.timestamp.dt.tz_convert(timezone)
        altitude, sun = planner.sky_track(by_id[site_id], target, track.timestamp.dt.to_pydatetime())
        track["altitude"] = altitude
        track["dark_enough"] = (sun <= planner.max_sun_altitude_deg) | (planner.celestial_bodies[target]["kind"] == "moon")
        if not track.weather.notna().any():
            st.info("The saved forecast has no valid slots within 90 minutes of tonight's chart times.")
        elif not (track.weather.ge(75) & track.altitude.ge(planner.min_altitude_deg) & track.dark_enough).any():
            st.info("No forecast interval meets both the score and target-visibility thresholds tonight.")
        st.plotly_chart(forecast_chart(track, by_id[site_id].name, timezone.key,
                                       planner.min_altitude_deg), width="stretch")
