"""Weather suitability analytics from observed and forecast weather histories."""

from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .models import AstroSuitabilityScorer

NIGHT_HOURS = list(range(18, 24)) + list(range(8))
SCORE_LABEL = "Weather score S_W (0–100, higher is better)"
PARTS = {"Cloud (0.50C)": "cloud_part", "Humidity (0.20H)": "humidity_part",
         "Visibility (0.15V)": "visibility_part", "Wind (0.15W)": "wind_part"}


def load_weather_history(path: Path, sites, kind: str) -> pd.DataFrame:
    """Deduplicate observations and use only the latest forecast issue per site."""
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    frame = pd.read_csv(path)
    required = ["cloud_cover_percent", "humidity_percent", "visibility_m", "wind_speed_mps"]
    for column in ["latitude", "longitude", *required]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in ("timestamp", "fetched_at"):
        frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce")
    frame = frame[frame["kind"] == kind].dropna(subset=["timestamp", "fetched_at", *required])
    frame = frame[frame.cloud_cover_percent.between(0, 100) & frame.humidity_percent.between(0, 100)
                  & frame.visibility_m.ge(0) & frame.wind_speed_mps.ge(0)].copy()
    lookup = {(round(s.latitude, 6), round(s.longitude, 6)): s.site_id for s in sites}
    names = {s.site_id: s.name for s in sites}
    frame["site_id"] = [lookup.get((round(lat, 6), round(lon, 6)))
                        for lat, lon in zip(frame.latitude, frame.longitude)]
    frame = frame.dropna(subset=["site_id"])
    frame["site"] = frame.site_id.map(names)
    frame = frame.sort_values("fetched_at")
    if kind == "forecast":
        frame = frame[frame.fetched_at == frame.groupby("site_id").fetched_at.transform("max")]
    frame = frame.drop_duplicates(["site_id", "timestamp"], keep="last")
    scorer = AstroSuitabilityScorer()
    c, h, v, w = scorer.weather_weights
    frame["cloud_part"] = (100 - frame.cloud_cover_percent) * c
    frame["humidity_part"] = (100 - frame.humidity_percent) * h
    frame["visibility_part"] = (frame.visibility_m / scorer.ideal_visibility_m * 100).clip(0, 100) * v
    frame["wind_part"] = (100 - frame.wind_speed_mps / scorer.unfavorable_wind_mps * 100).clip(0, 100) * w
    frame["weather"] = frame[list(PARTS.values())].sum(axis=1)
    return frame.sort_values("timestamp").reset_index(drop=True)


def hourly_scores(frame):
    return (frame.set_index("local_time").groupby("site")["weather"].resample("1h")
            .mean().rename("weather").reset_index())


def nighttime_ranking(frame):
    night = frame[frame.is_night].copy()
    night["above_75"] = night.weather.gt(75) * 100
    return (night.groupby("site").agg(mean=("weather", "mean"),
            above_75=("above_75", "mean"), n=("weather", "count"))
            .sort_values("mean", ascending=False).reset_index())


def history_chart(frame, timezone):
    fig = go.Figure()
    for name, group in hourly_scores(frame).groupby("site"):
        fig.add_scatter(x=group.local_time, y=group.weather, name=name,
                        mode="lines+markers", connectgaps=False)
    fig.add_hline(y=75, line_dash="dash", annotation_text="75 threshold")
    for _, group in frame.groupby("site"):
        group = group.sort_values("local_time")
        blocks = group.is_night.ne(group.is_night.shift()).cumsum()
        for _, block in group.groupby(blocks):
            if block.is_night.iloc[0]:
                fig.add_vrect(x0=block.local_time.iloc[0],
                    x1=block.local_time.iloc[-1] + pd.Timedelta(minutes=5),
                    fillcolor="midnightblue", opacity=0.04, line_width=0)
    fig.update_layout(title="Hourly mean weather score by site", yaxis_title=SCORE_LABEL,
                      xaxis_title=f"Time ({timezone})", yaxis_range=[0, 100], legend_title="Site")
    return fig


def ranking_chart(frame):
    ranked = nighttime_ranking(frame)
    fig = go.Figure(go.Bar(x=ranked["mean"], y=ranked.site, orientation="h",
        text=[f"{pct:.0f}% >75 · n={n}" for pct, n in zip(ranked.above_75, ranked.n)],
        textposition="auto"))
    fig.update_layout(title="Sites ranked by mean nighttime weather score",
                      xaxis_title="Mean nighttime S_W (0–100)", yaxis_title="Site",
                      xaxis_range=[0, 100], yaxis_autorange="reversed")
    return fig


def heatmap_chart(frame, timezone):
    frame = frame.copy()
    frame["hour"] = frame.local_time.dt.hour
    table = frame[frame.hour.isin(NIGHT_HOURS)].pivot_table(
        index="site", columns="hour", values="weather", aggfunc="mean")
    table = table.reindex(index=sorted(frame.site.unique()), columns=NIGHT_HOURS)
    fig = go.Figure(go.Heatmap(z=table.values, x=[f"{h:02d}:00" for h in NIGHT_HOURS],
        y=table.index, zmin=0, zmax=100, colorscale="Viridis", colorbar_title="S_W (0–100)",
        hoverongaps=False))
    fig.update_layout(title="Mean weather score by night hour",
                      xaxis_title=f"Hour ({timezone}); blank cells have no observations",
                      yaxis_title="Site")
    return fig


def components_chart(frame):
    latest = frame.sort_values("timestamp").groupby("site").tail(1).sort_values("weather", ascending=False)
    fig = go.Figure()
    for label, column in PARTS.items():
        fig.add_bar(x=latest[column], y=latest.site, name=label, orientation="h")
    fig.update_layout(title="What makes up each site's latest weather score",
                      barmode="stack", xaxis_title="Weighted contribution to S_W (score points, 0–100)",
                      yaxis_title="Site", xaxis_range=[0, 100], yaxis_autorange="reversed",
                      legend_title="Component")
    return fig


def forecast_chart(track, site_name, timezone, min_altitude):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_scatter(x=track.local_time, y=track.altitude, name="Target altitude", secondary_y=False)
    fig.add_scatter(x=track.local_time, y=track.weather, name="Forecast S_W",
                    connectgaps=False, secondary_y=True)
    good = track.weather.ge(75) & track.altitude.ge(min_altitude) & track.dark_enough
    blocks = good.ne(good.shift()).cumsum()
    for _, group in track.assign(good=good, block=blocks).groupby("block"):
        if group.good.iloc[0]:
            fig.add_vrect(x0=group.local_time.iloc[0],
                x1=group.local_time.iloc[-1] + pd.Timedelta(minutes=5),
                fillcolor="green", opacity=0.15, line_width=0)
    fig.update_yaxes(title_text="Altitude (degrees)", secondary_y=False)
    fig.update_yaxes(title_text="Forecast S_W (0–100)", range=[0, 100], secondary_y=True)
    fig.update_layout(title=f"Forecast · {site_name}", xaxis_title=f"Time ({timezone})")
    return fig
