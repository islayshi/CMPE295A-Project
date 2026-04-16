import { useState, useEffect } from "react";

const WMO_CODES = {
  0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
  45: "Foggy", 48: "Icy fog",
  51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
  61: "Light rain", 63: "Rain", 65: "Heavy rain",
  71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
  80: "Rain showers", 81: "Rain showers", 82: "Violent showers",
  85: "Snow showers", 86: "Heavy snow showers",
  95: "Thunderstorm", 96: "Thunderstorm + hail", 99: "Thunderstorm + heavy hail",
};

const WMO_ICON = {
  0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️",
  45: "🌫️", 48: "🌫️",
  51: "🌦️", 53: "🌦️", 55: "🌧️",
  61: "🌧️", 63: "🌧️", 65: "🌧️",
  71: "🌨️", 73: "❄️", 75: "❄️", 77: "❄️",
  80: "🌦️", 81: "🌧️", 82: "⛈️",
  85: "🌨️", 86: "❄️",
  95: "⛈️", 96: "⛈️", 99: "⛈️",
};

// ← FILL IN YOUR ZIP CODE HERE
const HARDCODED_ZIP = "95101";

async function geocodeZip(zip) {
  const res = await fetch(
    `https://geocoding-api.open-meteo.com/v1/search?name=${zip}&count=1&language=en&format=json&countryCode=US`
  );
  const data = await res.json();
  if (!data.results?.length) throw new Error("ZIP code not found");
  return data.results[0];
}

async function fetchWeather(lat, lon) {
  const res = await fetch(
    `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}` +
    `&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum,` +
    `precipitation_probability_max,windspeed_10m_max,uv_index_max,sunrise,sunset` +
    `&hourly=relativehumidity_2m,apparent_temperature` +
    `&current_weather=true` +
    `&temperature_unit=fahrenheit&windspeed_unit=mph&precipitation_unit=inch` +
    `&timezone=auto&forecast_days=7`
  );
  return res.json();
}

function getDayLabel(dateStr, index) {
  if (index === 0) return "Today";
  return new Date(dateStr + "T12:00:00").toLocaleDateString("en-US", {
    weekday: "short",
  });
}

export default function WeatherForecast() {
  const [weather, setWeather] = useState(null);
  const [location, setLocation] = useState(null);
  const [selectedDay, setSelectedDay] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const loc = await geocodeZip(HARDCODED_ZIP);
        const data = await fetchWeather(loc.latitude, loc.longitude);
        setLocation(loc);
        setWeather(data);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <LoadingSkeleton />;
  if (error) return <div style={styles.error}>Error: {error}</div>;
  if (!weather) return null;

  const day = selectedDay;
  const d = weather.daily;
  const hourNow = new Date().getHours();

  const currentTemp = Math.round(weather.current_weather.temperature);
  const currentCode = weather.current_weather.weathercode;
  const currentWind = Math.round(weather.current_weather.windspeed);
  const feelsLike = Math.round(weather.hourly.apparent_temperature[hourNow] ?? weather.hourly.apparent_temperature[0]);
  const humidity = Math.round(weather.hourly.relativehumidity_2m[hourNow] ?? weather.hourly.relativehumidity_2m[0]);

  const locName = [location.name, location.admin1].filter(Boolean).join(", ");

  const detailMetrics = [
    { label: "High", value: `${Math.round(d.temperature_2m_max[day])}°F` },
    { label: "Low", value: `${Math.round(d.temperature_2m_min[day])}°F` },
    { label: "Max wind", value: `${Math.round(d.windspeed_10m_max[day])} mph` },
    { label: "UV index", value: Math.round(d.uv_index_max[day]) },
    { label: "Precipitation", value: `${(d.precipitation_sum[day] ?? 0).toFixed(2)}"` },
    { label: "Sunrise", value: d.sunrise[day].split("T")[1] },
    { label: "Sunset", value: d.sunset[day].split("T")[1] },
  ];

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <span style={styles.headerLabel}>7-Day Forecast</span>
        <span style={styles.headerLocation}>{locName}</span>
      </div>

      {/* Today card */}
      <div style={styles.todayCard}>
        <div style={styles.todayLeft}>
          <span style={styles.todayIcon}>{WMO_ICON[currentCode] ?? "🌡️"}</span>
          <div>
            <div style={styles.todayTemp}>{currentTemp}°F</div>
            <div style={styles.todayDesc}>{WMO_CODES[currentCode] ?? "Unknown"}</div>
          </div>
        </div>
        <div style={styles.todayStats}>
          {[
            ["Feels like", `${feelsLike}°F`],
            ["Humidity", `${humidity}%`],
            ["Wind", `${currentWind} mph`],
            ["UV Index", Math.round(d.uv_index_max[0])],
          ].map(([label, value]) => (
            <div key={label} style={styles.statItem}>
              <div style={styles.statLabel}>{label}</div>
              <div style={styles.statValue}>{value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 7-day strip */}
      <div style={styles.weekGrid}>
        {d.time.map((date, i) => {
          const code = d.weathercode[i];
          const precip = Math.round(d.precipitation_probability_max[i] ?? 0);
          return (
            <div
              key={date}
              style={{
                ...styles.dayCard,
                ...(i === selectedDay ? styles.dayCardActive : {}),
              }}
              onClick={() => setSelectedDay(i)}
            >
              <div style={{
                ...styles.dayName,
                ...(i === selectedDay ? styles.dayNameActive : {}),
              }}>
                {getDayLabel(date, i)}
              </div>
              <div style={styles.dayIcon}>{WMO_ICON[code] ?? "🌡️"}</div>
              <div style={styles.dayHi}>{Math.round(d.temperature_2m_max[i])}°</div>
              <div style={styles.dayLo}>{Math.round(d.temperature_2m_min[i])}°</div>
              <div style={styles.precipBarWrap}>
                <div style={{ ...styles.precipBar, width: `${precip}%` }} />
              </div>
              <div style={styles.precipLabel}>{precip}%</div>
            </div>
          );
        })}
      </div>

      {/* Detail panel */}
      <div style={styles.detailPanel}>
        <div style={styles.detailDayLabel}>
          {day === 0 ? "Today's details" : `${getDayLabel(d.time[day], day)} — ${d.time[day]}`}
        </div>
        <div style={styles.detailGrid}>
          {detailMetrics.map(({ label, value }) => (
            <div key={label} style={styles.detailMetric}>
              <div style={styles.detailMetricLabel}>{label}</div>
              <div style={styles.detailMetricValue}>{value}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div style={styles.container}>
      {[120, 100, 80, 80, 80, 80, 80, 80, 80].map((h, i) => (
        <div key={i} style={{ ...styles.skeleton, height: h, marginBottom: 8 }} />
      ))}
    </div>
  );
}

const styles = {
  container: {
    fontFamily: "'Syne', 'Segoe UI', sans-serif",
    maxWidth: 860,
    margin: "0 auto",
    padding: "1.5rem 1rem 2rem",
  },
  header: {
    marginBottom: "1.25rem",
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  headerLabel: {
    fontSize: 12,
    fontWeight: 500,
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    color: "#888",
  },
  headerLocation: {
    fontSize: 22,
    fontWeight: 700,
    color: "#111",
  },
  todayCard: {
    border: "0.5px solid #e0e0e0",
    borderRadius: 12,
    background: "#fff",
    padding: "1.25rem 1.5rem",
    marginBottom: "1rem",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    flexWrap: "wrap",
    gap: "1rem",
  },
  todayLeft: { display: "flex", alignItems: "center", gap: "1rem" },
  todayIcon: { fontSize: 48, lineHeight: 1 },
  todayTemp: { fontSize: 48, fontWeight: 700, lineHeight: 1, color: "#111", fontFamily: "monospace" },
  todayDesc: { fontSize: 15, color: "#666", marginTop: 4, fontWeight: 500 },
  todayStats: { display: "flex", gap: "1.5rem", flexWrap: "wrap" },
  statItem: { textAlign: "right" },
  statLabel: { fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "#999", fontWeight: 500 },
  statValue: { fontSize: 15, fontWeight: 700, fontFamily: "monospace", color: "#111", marginTop: 2 },
  weekGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(7, minmax(0, 1fr))",
    gap: 8,
    marginBottom: "1rem",
  },
  dayCard: {
    border: "0.5px solid #e0e0e0",
    borderRadius: 12,
    background: "#fff",
    padding: "12px 8px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 6,
    cursor: "pointer",
    transition: "border-color 0.15s, background 0.15s",
  },
  dayCardActive: {
    borderColor: "#7F77DD",
    background: "#f5f5ff",
  },
  dayName: { fontSize: 11, fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.08em", color: "#999" },
  dayNameActive: { color: "#7F77DD" },
  dayIcon: { fontSize: 22, lineHeight: 1 },
  dayHi: { fontSize: 14, fontWeight: 700, fontFamily: "monospace", color: "#111" },
  dayLo: { fontSize: 12, fontFamily: "monospace", color: "#bbb" },
  precipBarWrap: { width: "100%", height: 3, background: "#eee", borderRadius: 2, overflow: "hidden" },
  precipBar: { height: "100%", borderRadius: 2, background: "#378ADD", transition: "width 0.4s ease" },
  precipLabel: { fontSize: 10, color: "#bbb", fontFamily: "monospace" },
  detailPanel: {
    border: "0.5px solid #e0e0e0",
    borderRadius: 12,
    background: "#fff",
    padding: "1rem 1.25rem",
  },
  detailDayLabel: { fontSize: 13, fontWeight: 500, color: "#666", marginBottom: 12 },
  detailGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: 12 },
  detailMetric: { background: "#f7f7f7", borderRadius: 8, padding: "10px 12px" },
  detailMetricLabel: { fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "#999", fontWeight: 500, marginBottom: 4 },
  detailMetricValue: { fontSize: 18, fontWeight: 700, fontFamily: "monospace", color: "#111" },
  skeleton: { background: "#f0f0f0", borderRadius: 8, animation: "pulse 1.2s ease-in-out infinite" },
  error: { color: "red", padding: "1rem", fontFamily: "monospace" },
};