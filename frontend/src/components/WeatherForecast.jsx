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

export default function WeatherForecast({ userLocation }) {
  const [weather, setWeather] = useState(null);
  const [selectedDay, setSelectedDay] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Bay Area fallback if userLocation is not yet available
  const lat = userLocation?.lat ?? 37.6688;
  const lon = userLocation?.lon ?? -122.0828;

  useEffect(() => {
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const data = await fetchWeather(lat, lon);
        setWeather(data);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, [lat, lon]);

  if (loading) return <LoadingSkeleton />;
  if (error) return <div className="text-red-500 p-4 font-mono">Error: {error}</div>;
  if (!weather) return null;

  const day = selectedDay;
  const d = weather.daily;
  const hourNow = new Date().getHours();

  const currentTemp = Math.round(weather.current_weather.temperature);
  const currentCode = weather.current_weather.weathercode;
  const currentWind = Math.round(weather.current_weather.windspeed);
  const feelsLike = Math.round(weather.hourly.apparent_temperature[hourNow] ?? weather.hourly.apparent_temperature[0]);
  const humidity = Math.round(weather.hourly.relativehumidity_2m[hourNow] ?? weather.hourly.relativehumidity_2m[0]);

  // Since we use coordinates directly (no ZIP geocoding), display a generic label.
  // The cityName from Dashboard's reverse geocoder could be passed as a prop in the future.
  const locName = "Your Location";

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
    <div className="max-w-[860px] mx-auto py-6 px-4 font-sans text-slate-800">
      {/* Header */}
      <div className="flex flex-col gap-1 mb-5">
        <span className="text-xs font-medium uppercase tracking-[0.1em] text-slate-800">7-Day Forecast</span>
        <span className="text-2xl font-bold text-slate-800">{locName}</span>
      </div>

      {/* Today card */}
      <div className="border border-slate-200 rounded-xl bg-white px-6 py-5 mb-4 flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <span className="text-5xl leading-none">{WMO_ICON[currentCode] ?? "🌡️"}</span>
          <div>
            <div className="text-5xl font-bold leading-none text-slate-800 font-mono">{currentTemp}°F</div>
            <div className="text-[15px] text-slate-800 mt-1 font-medium">{WMO_CODES[currentCode] ?? "Unknown"}</div>
          </div>
        </div>
        <div className="flex gap-6 flex-wrap">
          {[
            ["Feels like", `${feelsLike}°F`],
            ["Humidity", `${humidity}%`],
            ["Wind", `${currentWind} mph`],
            ["UV Index", Math.round(d.uv_index_max[0])],
          ].map(([label, value]) => (
            <div key={label} className="text-right">
              <div className="text-[11px] uppercase tracking-[0.08em] text-slate-800 font-medium">{label}</div>
              <div className="text-[15px] font-bold font-mono text-slate-800 mt-0.5">{value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 7-day strip */}
      <div className="overflow-x-auto flex gap-2 mb-4 pb-2 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
        {d.time.map((date, i) => {
          const code = d.weathercode[i];
          const precip = Math.round(d.precipitation_probability_max[i] ?? 0);
          return (
            <div
              key={date}
              className={`border rounded-xl px-2 py-3 flex flex-col items-center gap-1.5 cursor-pointer transition-colors min-w-[80px] shrink-0 ${
                i === selectedDay
                  ? "border-orange-600 bg-orange-50"
                  : "border-slate-200 bg-white hover:bg-slate-50"
              }`}
              onClick={() => setSelectedDay(i)}
            >
              <div className={`text-[11px] font-medium uppercase tracking-[0.08em] ${
                i === selectedDay ? "text-orange-600" : "text-slate-800"
              }`}>
                {getDayLabel(date, i)}
              </div>
              <div className="text-2xl leading-none">{WMO_ICON[code] ?? "🌡️"}</div>
              <div className="text-sm font-bold font-mono text-slate-800">{Math.round(d.temperature_2m_max[i])}°</div>
              <div className="text-xs font-mono text-slate-400">{Math.round(d.temperature_2m_min[i])}°</div>
              <div className="w-full h-[3px] bg-slate-100 rounded-sm overflow-hidden">
                <div className="h-full rounded-sm bg-orange-400 transition-all duration-300" style={{ width: `${precip}%` }} />
              </div>
              <div className="text-[10px] text-slate-400 font-mono">{precip}%</div>
            </div>
          );
        })}
      </div>

      {/* Detail panel */}
      <div className="border border-slate-200 rounded-xl bg-white px-5 py-4">
        <div className="text-[13px] font-medium text-slate-800 mb-3">
          {day === 0 ? "Today's details" : `${getDayLabel(d.time[day], day)} — ${d.time[day]}`}
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(110px,1fr))] gap-3">
          {detailMetrics.map(({ label, value }) => (
            <div key={label} className="bg-slate-50 rounded-lg py-2.5 px-3 border border-slate-100">
              <div className="text-[11px] uppercase tracking-[0.08em] text-slate-800 font-medium mb-1">{label}</div>
              <div className="text-lg font-bold font-mono text-slate-800">{value}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="max-w-[860px] mx-auto py-6 px-4">
      {[120, 100, 80, 80, 80, 80, 80, 80, 80].map((h, i) => (
        <div key={i} className="bg-slate-100 rounded-lg animate-pulse mb-2" style={{ height: h }} />
      ))}
    </div>
  );
}