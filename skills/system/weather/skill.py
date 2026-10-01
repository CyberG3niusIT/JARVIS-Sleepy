"""
Weather Skill

Provides current weather information, forecasts, and sunrise/sunset times.
Queries local SQLite cache (populated by WeatherPoller) for instant responses.
Falls back to live OpenWeatherMap API if DB is empty or stale.
"""

import os
import re
import requests
from datetime import datetime, date, timedelta
from core.base_skill import BaseSkill
from core.weather_db import get_weather_db, parse_temporal_phrase


class WeatherSkill(BaseSkill):
    """Weather information skill"""

    def initialize(self) -> bool:
        """Initialize the skill"""
        # API key is optional for the native skill itself.
        # Local cached weather remains usable without OpenWeather access;
        # only live fallback/location requests are unavailable.
        self.api_key = os.environ.get("OPENWEATHER_API_KEY")
        if not self.api_key:
            self.logger.warning(
                "OPENWEATHER_API_KEY not set - live weather fallback disabled"
            )

        # Default location (Gardendale, Alabama)
        self.default_location = "Gardendale,AL,US"
        self.default_lat = 33.6662
        self.default_lon = -86.8128

        # DB reference (may be None if weather system not initialized yet)
        self._db = None

        # Register intents
        # ===== EXACT PATTERNS (high priority) =====
        self.register_intent("what's the weather like today", self.get_current_weather, priority=10)
        self.register_intent("what's the weather today", self.get_current_weather, priority=10)
        self.register_intent("weather today", self.get_current_weather, priority=10)

        # ===== SEMANTIC INTENT MATCHING =====
        # Current weather
        self.register_semantic_intent(
            examples=[
                "what's the weather like today",
                "what's the weather today",
                "how's the weather today",
                "weather right now",
                "current weather",
                "what are the current meteorological conditions",
                "how are the weather conditions today",
                "what's the weather in the news",
                "look into the current meteorological conditions",
                "what's the weather in paris",
                "how's the weather like in london",
                "weather for new york",
                "temperature in chicago",
                "tell me the weather in tokyo",
                "what's the temperature",
                "how hot is it",
                "how cold is it",
                "what's the temp",
            ],
            handler=self.get_current_weather,
            threshold=0.60
        )

        # Weather forecast
        self.register_semantic_intent(
            examples=[
                "what's the forecast",
                "weather forecast",
                "forecast for this week",
                "what is the forecast",
                "extended forecast",
                "forecast for the week",
                "what's the forecast looking like",
                "give me the forecast",
            ],
            handler=self.get_forecast,
            threshold=0.70
        )

        # Period / temporal weather ("this weekend", "next week", etc.)
        self.register_semantic_intent(
            examples=[
                "what's the weather this weekend",
                "how's the weather looking this weekend",
                "weather this weekend",
                "what will the weather be like this weekend",
                "what's it going to be like this weekend",
                "weather next week",
                "what's the weather next week",
                "how's the weather looking next week",
                "what about this weekend",
                "what's the weather for the next few days",
                "how's the next few days looking",
                "weather for the coming days",
                "what's the weather like for the rest of the week",
                "end of the week weather",
                "next weekend weather",
                "what's next weekend looking like",
            ],
            handler=self.get_weather_for_period,
            threshold=0.62
        )

        # Rain specific
        self.register_semantic_intent(
            examples=[
                "will it rain",
                "is it raining",
                "will it rain tomorrow",
                "is it going to rain",
                "is it supposed to rain today",
                "will it rain today",
            ],
            handler=self.check_rain_tomorrow,
            threshold=0.70
        )

        # Tomorrow's weather
        self.register_semantic_intent(
            examples=[
                "weather tomorrow",
                "tomorrow's forecast",
                "forecast for tomorrow",
                "what's the forecast for tomorrow",
                "what will the weather be tomorrow",
                "how's it going to be tomorrow",
                "whats the weather gonna be like tomorrow",
                "whats the weather gonna be tomorrow",
                "how's it gonna be tomorrow",
            ],
            handler=self.get_tomorrow_weather,
            threshold=0.65
        )

        # Sunrise
        self.register_semantic_intent(
            examples=[
                "what time is sunrise",
                "when does the sun come up",
                "sunrise today",
                "sunrise tomorrow",
                "when is sunrise",
                "what time does the sun rise",
            ],
            handler=self.get_sunrise,
            threshold=0.70
        )

        # Sunset
        self.register_semantic_intent(
            examples=[
                "what time is sunset",
                "when does the sun go down",
                "sunset today",
                "sunset tomorrow",
                "when is sunset",
                "what time does the sun set",
            ],
            handler=self.get_sunset,
            threshold=0.70
        )

        return True

    @property
    def db(self):
        """Lazy-load weather DB reference."""
        if self._db is None:
            self._db = get_weather_db()
        return self._db

    def _get_away_geo(self) -> tuple[float, float] | None:
        """Check if current request is from an away mobile user."""
        try:
            from core.conversation_router import _router_thread_ctx
            ctx = getattr(_router_thread_ctx, 'ctx', None)
            if ctx and ctx.away_geo:
                return ctx.away_geo
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Current Weather
    # ------------------------------------------------------------------

    def _check_non_local(self) -> str | None:
        """If the user asked about a non-local location, return None to decline.

        The LLM tool path handles geocoding via get_weather(location=...).
        This skill only serves local/home weather from the DB cache. (B9 fix)
        """
        command = getattr(self, '_last_user_text', '') or ''
        if self._has_non_local_location(command):
            self.logger.info("Weather skill declining — non-local location: %s", command[:80])
            return None
        return "OK"  # sentinel — caller checks for None

    def get_current_weather(self) -> str:
        """Get current weather for default location with conversational response"""
        if self._check_non_local() is None:
            return None

        # Away mobile user — use their GPS coords
        away = self._get_away_geo()
        if away:
            return self._fetch_current_for_coords(*away)

        # Home user — try DB first
        if self.db and not self.db.is_current_stale():
            current = self.db.get_current()
            if current:
                return self._format_current_response(current)

        # Fallback to live API
        return self._fetch_current_live()

    def _format_current_response(self, data: dict) -> str:
        """Format current conditions from DB into conversational response."""
        temp = round(data["temp"])
        feels_like = round(data["feels_like"])
        weather_main = data.get("weather_main", "").lower()
        description = data.get("description", "")
        wind_speed = round(data.get("wind_speed", 0))
        humidity = data.get("humidity", 0)

        response_parts = []

        # Temperature commentary with feels-like
        if temp >= 95:
            if feels_like > temp + 5:
                response_parts.append(f"Draußen ist es sehr heiß, {self.honorific}: {temp} Grad, gefühlt {feels_like}.")
            else:
                response_parts.append(f"Draußen ist es heiß, {self.honorific}: {temp} Grad.")
        elif temp >= 85:
            if feels_like > temp + 5:
                response_parts.append(f"Es ist warm, {self.honorific}: {temp} Grad, gefühlt {feels_like}.")
            else:
                response_parts.append(f"Draußen ist es warm, {self.honorific}: {temp} Grad.")
        elif temp >= 70:
            response_parts.append(f"Draußen ist es angenehm, {self.honorific}: {temp} Grad.")
        elif temp >= 50:
            if feels_like < temp - 5:
                response_parts.append(f"Es ist mild, {self.honorific}: {temp} Grad, gefühlt kühler mit etwa {feels_like} Grad.")
            else:
                response_parts.append(f"Draußen ist es mild, {self.honorific}: {temp} Grad.")
        elif temp >= 32:
            if feels_like < temp - 5:
                response_parts.append(f"Es ist kühl, {self.honorific}: {temp} Grad, mit dem Wind gefühlt {feels_like} Grad.")
            else:
                response_parts.append(f"Es ist kühl, {self.honorific}: {temp} Grad.")
        else:
            response_parts.append(f"Es ist kalt, {self.honorific}: {temp} Grad.")

        # Weather conditions
        if "rain" in weather_main or "drizzle" in weather_main:
            response_parts.append("Es regnet gerade.")
        elif "thunderstorm" in weather_main:
            response_parts.append("In der Umgebung gibt es Gewitter.")
        elif "snow" in weather_main:
            response_parts.append("Es schneit.")
        elif "clear" in weather_main:
            response_parts.append("Der Himmel ist gerade klar.")
        elif "cloud" in weather_main:
            if "few" in description or "scattered" in description:
                response_parts.append("Es gibt wenige Wolken.")
            elif "overcast" in description:
                response_parts.append("Der Himmel ist bedeckt.")
            else:
                response_parts.append("Es ist bewölkt.")

        # Wind advisory if significant
        if wind_speed >= 20:
            response_parts.append(f"Es ist windig mit {wind_speed} Meilen pro Stunde.")
        elif wind_speed >= 15:
            response_parts.append(f"Es weht Wind mit {wind_speed} Meilen pro Stunde.")

        response_text = " ".join(response_parts)
        return self.respond(response_text)

    def _fetch_current_live(self) -> str:
        """Fallback: fetch current weather from live API."""
        if not self.api_key:
            return self.respond(
                f"Aktuelle Wetterdaten sind derzeit nicht verfügbar, {self.honorific}."
            )

        try:
            url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                "lat": self.default_lat,
                "lon": self.default_lon,
                "appid": self.api_key,
                "units": "imperial"
            }

            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            current = {
                "temp": data["main"]["temp"],
                "feels_like": data["main"]["feels_like"],
                "humidity": data["main"]["humidity"],
                "wind_speed": data["wind"]["speed"],
                "description": data["weather"][0]["description"],
                "weather_main": data["weather"][0]["main"].lower(),
            }
            return self._format_current_response(current)

        except requests.exceptions.RequestException as e:
            self.logger.error("Weather operation failed (%s)", type(e).__name__)
            return self.respond(f"Ich kann die Wetterdaten gerade nicht abrufen, {self.honorific}.")
        except Exception as e:
            self.logger.error("Weather operation failed (%s)", type(e).__name__)
            return self.respond(f"Die aktuellen Wetterdaten konnten nicht verarbeitet werden, {self.honorific}.")

    def _fetch_current_for_coords(self, lat: float, lon: float) -> str:
        """Fetch current weather for arbitrary coordinates via live API."""
        if not self.api_key:
            return self.respond(
                f"Aktuelle Wetterdaten sind derzeit nicht verfügbar, {self.honorific}."
            )

        try:
            url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                "lat": lat, "lon": lon,
                "appid": self.api_key, "units": "imperial"
            }
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            current = {
                "temp": data["main"]["temp"],
                "feels_like": data["main"]["feels_like"],
                "humidity": data["main"]["humidity"],
                "wind_speed": data["wind"]["speed"],
                "description": data["weather"][0]["description"],
                "weather_main": data["weather"][0]["main"].lower(),
            }
            return self._format_current_response(current)

        except requests.exceptions.RequestException as e:
            self.logger.error("Weather operation failed (%s)", type(e).__name__)
            return self.respond(f"Ich kann die Wetterdaten gerade nicht abrufen, {self.honorific}.")
        except Exception as e:
            self.logger.error("Weather operation failed (%s)", type(e).__name__)
            return self.respond(f"Die aktuellen Wetterdaten konnten nicht verarbeitet werden, {self.honorific}.")

    # ------------------------------------------------------------------
    # Location-based weather (always live API)
    # ------------------------------------------------------------------

    def get_weather_for_location(self, location: str = None) -> str:
        """Get weather for a specific location"""
        if not self.api_key:
            return self.respond(
                f"Aktuelle Wetterdaten sind derzeit nicht verfügbar, {self.honorific}."
            )

        if not location:
            return self.get_current_weather()

        try:
            # Geocode the location
            geo_url = "http://api.openweathermap.org/geo/1.0/direct"
            geo_params = {
                "q": location,
                "limit": 1,
                "appid": self.api_key
            }

            geo_response = requests.get(geo_url, params=geo_params, timeout=5)
            geo_response.raise_for_status()
            geo_data = geo_response.json()

            if not geo_data:
                return self.respond(f"Ich konnte keine Wetterdaten für {location} finden, {self.honorific}.")

            lat = geo_data[0]["lat"]
            lon = geo_data[0]["lon"]
            city_name = geo_data[0]["name"]

            # Get weather for this location
            url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                "lat": lat,
                "lon": lon,
                "appid": self.api_key,
                "units": "imperial"
            }

            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            temp = round(data["main"]["temp"])
            feels_like = round(data["main"]["feels_like"])
            description = data["weather"][0]["description"]

            response_text = f"In {city_name} sind es {temp} Grad"
            if abs(temp - feels_like) > 3:
                response_text += f", gefühlt {feels_like}"
            response_text += f". Quellenbeschreibung: „{description}“."

            return self.respond(response_text)

        except requests.exceptions.RequestException as e:
            self.logger.error("Weather operation failed (%s)", type(e).__name__)
            return self.respond(f"Ich kann die Wetterdaten für {location} gerade nicht abrufen, {self.honorific}.")
        except Exception as e:
            self.logger.error("Weather operation failed (%s)", type(e).__name__)
            return self.respond(f"Die Wetterdaten für {location} konnten nicht verarbeitet werden, {self.honorific}.")

    # ------------------------------------------------------------------
    # Forecast
    # ------------------------------------------------------------------

    def get_forecast(self) -> str:
        """Get 5-day forecast summary with conversational response"""
        if self._check_non_local() is None:
            return None

        # Away mobile user — use their GPS coords
        away = self._get_away_geo()
        if away:
            return self._fetch_forecast_for_coords(*away)

        # Home user — try DB first
        if self.db:
            rows = self.db.get_forecast(days=5)
            if rows:
                return self._format_forecast_response(rows)

        # Fallback to live API
        self.tts.speak(f"Ich rufe die erweiterte Vorhersage ab, {self.honorific}.")
        return self._fetch_forecast_live()

    def _format_forecast_response(self, rows: list) -> str:
        """Format forecast rows from DB into conversational response."""
        response_parts = []
        for row in rows[:3]:
            dt = datetime.strptime(row["date"], "%Y-%m-%d")
            day_name = dt.strftime("%d.%m.%Y")
            high = round(row["temp_high"])
            weather_main = row.get("weather_main", "").lower()

            day_parts = [day_name]
            if high >= 95:
                day_parts.append(f"wird heiß mit bis zu {high} Grad")
            elif high >= 85:
                day_parts.append(f"wird warm mit einem Höchstwert von {high} Grad")
            elif high >= 70:
                day_parts.append(f"wird angenehm mit einem Höchstwert von {high} Grad")
            elif high >= 50:
                day_parts.append(f"wird mild mit einem Höchstwert von {high} Grad")
            else:
                day_parts.append(f"wird kühl mit einem Höchstwert von {high} Grad")

            if "thunderstorm" in weather_main:
                day_parts.append("mit wahrscheinlichen Gewittern")
            elif "rain" in weather_main or "drizzle" in weather_main:
                day_parts.append("mit erwartetem Regen")
            elif "clear" in weather_main:
                day_parts.append("und klarem Himmel")
            elif "cloud" in weather_main:
                day_parts.append("mit bewölktem Himmel")

            response_parts.append(", ".join(day_parts))

        response_text = f"Das ist die Vorhersage, {self.honorific}. " + ". ".join(response_parts) + "."
        return self.respond(response_text)

    def _fetch_forecast_live(self) -> str:
        """Fallback: fetch forecast from live API."""
        if not self.api_key:
            return self.respond(
                f"Aktuelle Wetterdaten sind derzeit nicht verfügbar, {self.honorific}."
            )

        try:
            url = "https://api.openweathermap.org/data/2.5/forecast"
            params = {
                "lat": self.default_lat,
                "lon": self.default_lon,
                "appid": self.api_key,
                "units": "imperial"
            }

            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            forecasts_by_day = {}
            for item in data["list"][:32]:
                dt = datetime.fromtimestamp(item["dt"])
                day_name = dt.strftime("%d.%m.%Y")
                weather_main = item["weather"][0]["main"].lower()

                if day_name not in forecasts_by_day:
                    forecasts_by_day[day_name] = {
                        "temp_high": item["main"]["temp_max"],
                        "temp_low": item["main"]["temp_min"],
                        "description": item["weather"][0]["description"],
                        "weather_main": weather_main,
                    }
                else:
                    forecasts_by_day[day_name]["temp_high"] = max(
                        forecasts_by_day[day_name]["temp_high"],
                        item["main"]["temp_max"]
                    )
                    forecasts_by_day[day_name]["temp_low"] = min(
                        forecasts_by_day[day_name]["temp_low"],
                        item["main"]["temp_min"]
                    )
                    if "thunderstorm" in weather_main:
                        forecasts_by_day[day_name]["weather_main"] = "thunderstorm"
                    elif ("rain" in weather_main or "drizzle" in weather_main) and \
                            "thunderstorm" not in forecasts_by_day[day_name]["weather_main"]:
                        forecasts_by_day[day_name]["weather_main"] = weather_main

            # Convert to list format and use shared formatter
            rows = []
            for day_name, f in list(forecasts_by_day.items())[:3]:
                dt_approx = datetime.now()
                rows.append({
                    "date": dt_approx.strftime("%Y-%m-%d"),
                    "temp_high": f["temp_high"],
                    "temp_low": f["temp_low"],
                    "weather_main": f["weather_main"],
                })
            # Use direct formatting since dates won't map cleanly
            response_parts = []
            for day_name, forecast in list(forecasts_by_day.items())[:3]:
                high = round(forecast["temp_high"])
                weather_main = forecast["weather_main"]
                day_parts = [day_name]
                if high >= 95:
                    day_parts.append(f"wird heiß mit bis zu {high} Grad")
                elif high >= 85:
                    day_parts.append(f"wird warm mit einem Höchstwert von {high} Grad")
                elif high >= 70:
                    day_parts.append(f"wird angenehm mit einem Höchstwert von {high} Grad")
                elif high >= 50:
                    day_parts.append(f"wird mild mit einem Höchstwert von {high} Grad")
                else:
                    day_parts.append(f"wird kühl mit einem Höchstwert von {high} Grad")

                if "thunderstorm" in weather_main:
                    day_parts.append("mit wahrscheinlichen Gewittern")
                elif "rain" in weather_main or "drizzle" in weather_main:
                    day_parts.append("mit erwartetem Regen")
                elif "clear" in weather_main:
                    day_parts.append("und klarem Himmel")
                elif "cloud" in weather_main:
                    day_parts.append("mit bewölktem Himmel")
                response_parts.append(", ".join(day_parts))

            response_text = f"Das ist die Vorhersage, {self.honorific}. " + ". ".join(response_parts) + "."
            return self.respond(response_text)

        except Exception as e:
            self.logger.error("Weather operation failed (%s)", type(e).__name__)
            return self.respond(f"Ich kann die Vorhersage gerade nicht abrufen, {self.honorific}.")

    def _fetch_forecast_for_coords(self, lat: float, lon: float) -> str:
        """Fetch forecast for arbitrary coordinates via live API."""
        if not self.api_key:
            return self.respond(
                f"Aktuelle Wetterdaten sind derzeit nicht verfügbar, {self.honorific}."
            )

        try:
            url = "https://api.openweathermap.org/data/2.5/forecast"
            params = {
                "lat": lat, "lon": lon,
                "appid": self.api_key, "units": "imperial"
            }
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            forecasts_by_day = {}
            for item in data["list"][:32]:
                dt = datetime.fromtimestamp(item["dt"])
                day_name = dt.strftime("%d.%m.%Y")
                weather_main = item["weather"][0]["main"].lower()

                if day_name not in forecasts_by_day:
                    forecasts_by_day[day_name] = {
                        "temp_high": item["main"]["temp_max"],
                        "temp_low": item["main"]["temp_min"],
                        "weather_main": weather_main,
                    }
                else:
                    forecasts_by_day[day_name]["temp_high"] = max(
                        forecasts_by_day[day_name]["temp_high"], item["main"]["temp_max"])
                    forecasts_by_day[day_name]["temp_low"] = min(
                        forecasts_by_day[day_name]["temp_low"], item["main"]["temp_min"])
                    if "thunderstorm" in weather_main:
                        forecasts_by_day[day_name]["weather_main"] = "thunderstorm"
                    elif ("rain" in weather_main or "drizzle" in weather_main) and \
                            "thunderstorm" not in forecasts_by_day[day_name]["weather_main"]:
                        forecasts_by_day[day_name]["weather_main"] = weather_main

            response_parts = []
            for day_name, forecast in list(forecasts_by_day.items())[:3]:
                high = round(forecast["temp_high"])
                weather_main = forecast["weather_main"]
                day_parts = [day_name]
                if high >= 95:
                    day_parts.append(f"wird heiß mit bis zu {high} Grad")
                elif high >= 85:
                    day_parts.append(f"wird warm mit einem Höchstwert von {high} Grad")
                elif high >= 70:
                    day_parts.append(f"wird angenehm mit einem Höchstwert von {high} Grad")
                elif high >= 50:
                    day_parts.append(f"wird mild mit einem Höchstwert von {high} Grad")
                else:
                    day_parts.append(f"wird kühl mit einem Höchstwert von {high} Grad")

                if "thunderstorm" in weather_main:
                    day_parts.append("mit wahrscheinlichen Gewittern")
                elif "rain" in weather_main or "drizzle" in weather_main:
                    day_parts.append("mit erwartetem Regen")
                elif "clear" in weather_main:
                    day_parts.append("und klarem Himmel")
                elif "cloud" in weather_main:
                    day_parts.append("mit bewölktem Himmel")
                response_parts.append(", ".join(day_parts))

            response_text = f"Das ist die Vorhersage, {self.honorific}. " + ". ".join(response_parts) + "."
            return self.respond(response_text)

        except Exception as e:
            self.logger.error("Weather operation failed (%s)", type(e).__name__)
            return self.respond(f"Ich kann die Vorhersage gerade nicht abrufen, {self.honorific}.")

    # ------------------------------------------------------------------
    # Period-based Weather (temporal phrases)
    # ------------------------------------------------------------------

    def get_weather_for_period(self) -> str:
        """Get weather for a date range parsed from temporal phrases."""
        # Get the original command text from thread-local context
        command_text = self._get_command_text()
        period = parse_temporal_phrase(command_text) if command_text else None

        if not period:
            # Couldn't parse a temporal phrase — fall back to 3-day forecast
            return self.get_forecast()

        start_date, end_date = period
        today = date.today()
        max_forecast = today + timedelta(days=15)  # 16-day window

        # Clamp to available forecast window
        if start_date > max_forecast:
            return self.respond(
                f"{self.honorific}, das liegt außerhalb meines Vorhersagefensters von 16 Tagen. "
                f"Ich kann nur bis zum {max_forecast.strftime('%d.%m.%Y')} vorhersagen."
            )
        if end_date > max_forecast:
            end_date = max_forecast

        # Away mobile user — live API (no DB range query)
        away = self._get_away_geo()
        if away:
            return self._fetch_forecast_for_coords(*away)

        # Home user — query DB
        if self.db:
            rows = self.db.get_forecast(days=16)
            filtered = [
                r for r in rows
                if start_date.isoformat() <= r["date"] <= end_date.isoformat()
            ]
            if filtered:
                return self._format_period_response(filtered, start_date, end_date)

        # Fallback
        return self.get_forecast()

    def _get_command_text(self) -> str | None:
        """Get the original user command text set by SkillManager."""
        return getattr(self, '_last_user_text', None)

    def _format_period_response(self, rows: list, start: date, end: date) -> str:
        """Format a date-range forecast into conversational response."""
        # Build a human-friendly label for the period
        label = self._period_label(start, end)

        response_parts = []
        for row in rows:
            dt = datetime.strptime(row["date"], "%Y-%m-%d")
            day_name = dt.strftime("%d.%m.%Y")
            high = round(row["temp_high"])
            low = round(row["temp_low"])
            weather_main = row.get("weather_main", "").lower()
            rain_chance = row.get("rain_chance", 0)

            day_desc = f"{day_name}: Höchstwert {high}, Tiefstwert {low}"

            if "thunderstorm" in weather_main:
                day_desc += ", Gewitter wahrscheinlich"
            elif "rain" in weather_main or "drizzle" in weather_main:
                day_desc += ", Regen erwartet"
            elif "snow" in weather_main:
                day_desc += ", Schnee erwartet"
            elif "clear" in weather_main:
                day_desc += ", klarer Himmel"
            elif "cloud" in weather_main:
                day_desc += ", bewölkt"

            if not rain_chance or rain_chance < 1:
                day_desc += ", keine Regenwahrscheinlichkeit"
            else:
                day_desc += f", {round(rain_chance)} Prozent Regenwahrscheinlichkeit"

            response_parts.append(day_desc)

        joined = ". ".join(response_parts) + "."
        return self.respond(f"Das ist die Vorhersage für {label}, {self.honorific}. {joined}")

    @staticmethod
    def _period_label(start: date, end: date) -> str:
        """Build a human-friendly label for a date range."""
        today = date.today()

        # Single day
        if start == end:
            if start == today:
                return "heute"
            return start.strftime("%d.%m.%Y")

        # Weekend detection
        if start.weekday() == 5 and end.weekday() == 6 and (end - start).days == 1:
            days_out = (start - today).days
            if 0 <= days_out <= 6:
                return "dieses Wochenende"
            elif 7 <= days_out <= 13:
                return "nächstes Wochenende"
            return f"das Wochenende ab {start.strftime('%d.%m.%Y')}"

        # Full week
        if start.weekday() == 0 and end.weekday() == 6 and (end - start).days == 6:
            if (start - today).days <= 7:
                return "nächste Woche"
            return f"die Woche ab {start.strftime('%d.%m.%Y')}"

        # Generic range
        return f"{start.strftime('%d.%m.%Y')} bis {end.strftime('%d.%m.%Y')}"

    # ------------------------------------------------------------------
    # Rain Check
    # ------------------------------------------------------------------

    def _rain_check_is_today(self) -> bool:
        """Return True if the user's rain query refers to today, not tomorrow."""
        text = (getattr(self, '_last_user_text', None) or "").lower()
        return "today" in text or "right now" in text or "currently" in text

    def check_rain_tomorrow(self) -> str:
        """Check if it will rain today or tomorrow with conversational response"""
        asking_today = self._rain_check_is_today()
        target_date = date.today() if asking_today else date.today() + timedelta(days=1)

        # Away mobile user — use their GPS coords
        away = self._get_away_geo()
        if away:
            return self._fetch_rain_for_coords(*away)

        # Home user — try DB first
        if self.db:
            target_str = target_date.isoformat()
            rows = self.db.get_forecast(days=5)
            target_row = next((r for r in rows if r["date"] == target_str), None)
            if target_row:
                return self._format_rain_response(target_row, today=asking_today)

        # Fallback to live API
        self.tts.speak(f"Ich prüfe die Vorhersage, {self.honorific}.")
        return self._fetch_rain_live()

    def _format_rain_response(self, row: dict, today: bool = False) -> str:
        """Format rain check from DB forecast row."""
        weather_main = row.get("weather_main", "").lower()
        rain_chance = row.get("rain_chance", 0)
        when = "heute" if today else "morgen"

        has_storm = "thunderstorm" in weather_main
        has_rain = "rain" in weather_main or "drizzle" in weather_main

        if has_storm:
            if rain_chance > 70:
                text = f"Ja, {self.honorific}, Gewitter sind {when} sehr wahrscheinlich: etwa {round(rain_chance)} Prozent. Halten Sie Ihre Pläne möglichst flexibel."
            else:
                text = f"Gewitter sind {when} möglich, {self.honorific}. Behalten Sie die Vorhersage im Blick."
        elif has_rain:
            if rain_chance >= 80:
                text = f"Ja, {self.honorific}, Regen ist {when} wahrscheinlich: {round(rain_chance)} Prozent. Nehmen Sie einen Regenschirm mit."
            elif rain_chance >= 50:
                text = f"Die Regenwahrscheinlichkeit liegt {when} bei {round(rain_chance)} Prozent, {self.honorific}. Ein Regenschirm ist sinnvoll."
            elif rain_chance > 0:
                text = f"Es gibt {when} eine geringe Regenwahrscheinlichkeit von etwa {round(rain_chance)} Prozent, {self.honorific}."
            else:
                text = f"Regen wird {when} erwartet, {self.honorific}. Seien Sie darauf vorbereitet."
        else:
            text = f"Nein, {self.honorific}, {when} wird kein Regen erwartet. Es sollte trocken bleiben."

        return self.respond(text)

    def _fetch_rain_live(self) -> str:
        """Fallback: fetch rain check from live API."""
        if not self.api_key:
            return self.respond(
                f"Aktuelle Wetterdaten sind derzeit nicht verfügbar, {self.honorific}."
            )

        try:
            url = "https://api.openweathermap.org/data/2.5/forecast"
            params = {
                "lat": self.default_lat,
                "lon": self.default_lon,
                "appid": self.api_key,
                "units": "imperial"
            }

            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            tomorrow = datetime.now().day + 1
            will_rain = False
            rain_chance = 0
            has_thunderstorm = False

            for item in data["list"][:16]:
                dt = datetime.fromtimestamp(item["dt"])
                if dt.day == tomorrow:
                    weather_main = item["weather"][0]["main"].lower()
                    if "thunderstorm" in weather_main:
                        has_thunderstorm = True
                        will_rain = True
                    elif "rain" in weather_main or "drizzle" in weather_main:
                        will_rain = True
                    if "pop" in item:
                        rain_chance = max(rain_chance, item["pop"] * 100)

            if has_thunderstorm:
                if rain_chance > 70:
                    text = f"Ja, {self.honorific}, Gewitter sind morgen sehr wahrscheinlich: etwa {round(rain_chance)} Prozent. Halten Sie Ihre Pläne möglichst flexibel."
                else:
                    text = f"Gewitter sind morgen möglich, {self.honorific}. Behalten Sie die Vorhersage im Blick."
            elif will_rain:
                if rain_chance >= 80:
                    text = f"Ja, {self.honorific}, Regen ist morgen wahrscheinlich: {round(rain_chance)} Prozent. Nehmen Sie einen Regenschirm mit."
                elif rain_chance >= 50:
                    text = f"Die Regenwahrscheinlichkeit liegt morgen bei {round(rain_chance)} Prozent, {self.honorific}. Ein Regenschirm ist sinnvoll."
                elif rain_chance > 0:
                    text = f"Es gibt morgen eine geringe Regenwahrscheinlichkeit von etwa {round(rain_chance)} Prozent, {self.honorific}."
                else:
                    text = f"Regen wird morgen erwartet, {self.honorific}. Seien Sie darauf vorbereitet."
            else:
                text = f"Nein, {self.honorific}, morgen wird kein Regen erwartet. Es sollte trocken bleiben."

            return self.respond(text)

        except Exception as e:
            self.logger.error("Weather operation failed (%s)", type(e).__name__)
            return self.respond(f"Ich kann die Vorhersage für morgen gerade nicht prüfen, {self.honorific}.")

    def _fetch_rain_for_coords(self, lat: float, lon: float) -> str:
        """Fetch rain check for arbitrary coordinates via live API."""
        if not self.api_key:
            return self.respond(
                f"Aktuelle Wetterdaten sind derzeit nicht verfügbar, {self.honorific}."
            )

        try:
            url = "https://api.openweathermap.org/data/2.5/forecast"
            params = {
                "lat": lat, "lon": lon,
                "appid": self.api_key, "units": "imperial"
            }
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            tomorrow = datetime.now().day + 1
            will_rain = False
            rain_chance = 0
            has_thunderstorm = False

            for item in data["list"][:16]:
                dt = datetime.fromtimestamp(item["dt"])
                if dt.day == tomorrow:
                    weather_main = item["weather"][0]["main"].lower()
                    if "thunderstorm" in weather_main:
                        has_thunderstorm = True
                        will_rain = True
                    elif "rain" in weather_main or "drizzle" in weather_main:
                        will_rain = True
                    if "pop" in item:
                        rain_chance = max(rain_chance, item["pop"] * 100)

            if has_thunderstorm:
                if rain_chance > 70:
                    text = f"Ja, {self.honorific}, Gewitter sind morgen sehr wahrscheinlich: etwa {round(rain_chance)} Prozent. Halten Sie Ihre Pläne möglichst flexibel."
                else:
                    text = f"Gewitter sind morgen möglich, {self.honorific}. Behalten Sie die Vorhersage im Blick."
            elif will_rain:
                if rain_chance >= 80:
                    text = f"Ja, {self.honorific}, Regen ist morgen wahrscheinlich: {round(rain_chance)} Prozent. Nehmen Sie einen Regenschirm mit."
                elif rain_chance >= 50:
                    text = f"Die Regenwahrscheinlichkeit liegt morgen bei {round(rain_chance)} Prozent, {self.honorific}. Ein Regenschirm ist sinnvoll."
                elif rain_chance > 0:
                    text = f"Es gibt morgen eine geringe Regenwahrscheinlichkeit von etwa {round(rain_chance)} Prozent, {self.honorific}."
                else:
                    text = f"Regen wird morgen erwartet, {self.honorific}. Seien Sie darauf vorbereitet."
            else:
                text = f"Nein, {self.honorific}, morgen wird kein Regen erwartet. Es sollte trocken bleiben."

            return self.respond(text)

        except Exception as e:
            self.logger.error("Weather operation failed (%s)", type(e).__name__)
            return self.respond(f"Ich kann die Vorhersage für morgen gerade nicht prüfen, {self.honorific}.")

    # ------------------------------------------------------------------
    # Tomorrow's Weather
    # ------------------------------------------------------------------

    def get_tomorrow_weather(self) -> str:
        """Get tomorrow's weather summary with conversational response"""
        if self._check_non_local() is None:
            return None
        # Away mobile user — use their GPS coords
        away = self._get_away_geo()
        if away:
            return self._fetch_tomorrow_for_coords(*away)

        # Home user — try DB first
        if self.db:
            tomorrow_str = (date.today() + timedelta(days=1)).isoformat()
            rows = self.db.get_forecast(days=5)
            tomorrow_row = next((r for r in rows if r["date"] == tomorrow_str), None)
            if tomorrow_row:
                return self._format_tomorrow_response(tomorrow_row)

        # Fallback to live API
        self.tts.speak(f"Ich prüfe das für Sie, {self.honorific}.")
        return self._fetch_tomorrow_live()

    def _format_tomorrow_response(self, row: dict) -> str:
        """Format tomorrow's weather from DB forecast row."""
        high = round(row["temp_high"])
        low = round(row["temp_low"])
        weather_main = row.get("weather_main", "").lower()
        description = row.get("description", "")

        response_parts = []

        if high >= 95:
            response_parts.append(f"Morgen wird es sehr heiß, {self.honorific}, mit einem Höchstwert von {high} Grad.")
        elif high >= 85:
            response_parts.append(f"Morgen wird es warm, {self.honorific}, mit einem Höchstwert von {high} Grad.")
        elif high >= 70:
            response_parts.append(f"Morgen wird es angenehm, {self.honorific}, mit einem Höchstwert von {high} Grad.")
        elif high >= 50:
            response_parts.append(f"Morgen wird es mild, {self.honorific}, mit einem Höchstwert von {high} Grad.")
        elif high >= 32:
            response_parts.append(f"Morgen wird es kühl, {self.honorific}, mit höchstens {high} Grad.")
        else:
            response_parts.append(f"Morgen wird es kalt, {self.honorific}, mit einem Höchstwert von {high} Grad.")

        if abs(high - low) > 20:
            response_parts.append(f"Nachts sinkt die Temperatur auf {low} Grad.")

        if "rain" in weather_main or "drizzle" in weather_main:
            response_parts.append("Es wird Regen erwartet. Nehmen Sie einen Regenschirm mit.")
        elif "thunderstorm" in weather_main:
            response_parts.append(f"Gewitter sind vorhergesagt, {self.honorific}.")
        elif "snow" in weather_main:
            response_parts.append("Es wird Schnee erwartet.")
        elif "clear" in weather_main:
            response_parts.append("Es wird klarer Himmel erwartet.")
        elif "cloud" in weather_main:
            if "few" in description or "scattered" in description:
                response_parts.append("Es wird teilweise bewölkt.")
            else:
                response_parts.append("Es wird bedeckter Himmel erwartet.")

        return self.respond(" ".join(response_parts))

    def _fetch_tomorrow_live(self) -> str:
        """Fallback: fetch tomorrow's weather from live API."""
        if not self.api_key:
            return self.respond(
                f"Aktuelle Wetterdaten sind derzeit nicht verfügbar, {self.honorific}."
            )

        try:
            url = "https://api.openweathermap.org/data/2.5/forecast"
            params = {
                "lat": self.default_lat,
                "lon": self.default_lon,
                "appid": self.api_key,
                "units": "imperial"
            }

            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            tomorrow = datetime.now().day + 1
            tomorrow_data = []
            for item in data["list"][:16]:
                dt = datetime.fromtimestamp(item["dt"])
                if dt.day == tomorrow:
                    tomorrow_data.append(item)

            if not tomorrow_data:
                return self.respond(f"Die Vorhersage für morgen ist nicht verfügbar, {self.honorific}.")

            row = {
                "temp_high": max(item["main"]["temp"] for item in tomorrow_data),
                "temp_low": min(item["main"]["temp"] for item in tomorrow_data),
                "weather_main": tomorrow_data[0]["weather"][0]["main"].lower(),
                "description": tomorrow_data[0]["weather"][0]["description"],
            }
            return self._format_tomorrow_response(row)

        except Exception as e:
            self.logger.error("Weather operation failed (%s)", type(e).__name__)
            return self.respond(f"Ich kann das Wetter für morgen gerade nicht abrufen, {self.honorific}.")

    def _fetch_tomorrow_for_coords(self, lat: float, lon: float) -> str:
        """Fetch tomorrow's weather for arbitrary coordinates via live API."""
        if not self.api_key:
            return self.respond(
                f"Aktuelle Wetterdaten sind derzeit nicht verfügbar, {self.honorific}."
            )

        try:
            url = "https://api.openweathermap.org/data/2.5/forecast"
            params = {
                "lat": lat, "lon": lon,
                "appid": self.api_key, "units": "imperial"
            }
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            tomorrow = datetime.now().day + 1
            tomorrow_data = []
            for item in data["list"][:16]:
                dt = datetime.fromtimestamp(item["dt"])
                if dt.day == tomorrow:
                    tomorrow_data.append(item)

            if not tomorrow_data:
                return self.respond(f"Die Vorhersage für morgen ist nicht verfügbar, {self.honorific}.")

            row = {
                "temp_high": max(item["main"]["temp"] for item in tomorrow_data),
                "temp_low": min(item["main"]["temp"] for item in tomorrow_data),
                "weather_main": tomorrow_data[0]["weather"][0]["main"].lower(),
                "description": tomorrow_data[0]["weather"][0]["description"],
            }
            return self._format_tomorrow_response(row)

        except Exception as e:
            self.logger.error("Weather operation failed (%s)", type(e).__name__)
            return self.respond(f"Ich kann das Wetter für morgen gerade nicht abrufen, {self.honorific}.")

    # ------------------------------------------------------------------
    # Sunrise / Sunset
    # ------------------------------------------------------------------

    def get_sunrise(self) -> str:
        """Get sunrise time (today or tomorrow based on user text)."""
        return self._get_sun_time("sunrise")

    def get_sunset(self) -> str:
        """Get sunset time (today or tomorrow based on user text)."""
        return self._get_sun_time("sunset")

    def _get_sun_time(self, which: str) -> str:
        """Get sunrise or sunset time from DB."""
        user_text = getattr(self, "_last_user_text", "").lower()
        is_tomorrow = "tomorrow" in user_text

        from datetime import timedelta
        target_date = date.today() + timedelta(days=1) if is_tomorrow else date.today()
        target_str = target_date.isoformat()
        day_label = "morgen" if is_tomorrow else "heute"

        if self.db:
            sun = self.db.get_sun_times(target_str)
            if sun:
                time_val = sun.get(which, "")
                if time_val:
                    return self.respond(
                        f"{'Sonnenaufgang' if which == 'sunrise' else 'Sonnenuntergang'} {day_label} ist um {time_val}, {self.honorific}."
                    )

        # No DB data available
        return self.respond(
            f"Die Daten für den {'Sonnenaufgang' if which == 'sunrise' else 'Sonnenuntergang'} sind derzeit nicht verfügbar, {self.honorific}. "
            "Die Daten werden noch geladen."
        )

    # ------------------------------------------------------------------
    # Intent dispatch
    # ------------------------------------------------------------------

    # Detect non-local location in weather queries — decline so the LLM
    # tool path handles geocoding via get_weather(location=...). (B9 fix)
    _LOCATION_PATTERN = re.compile(
        r'\b(?:in|for|at|near)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',
    )
    _LOCAL_NAMES = {"gardendale", "birmingham", "here", "home", "outside", "my area"}

    def _has_non_local_location(self, command: str) -> bool:
        """Check if the command mentions a non-local location."""
        match = self._LOCATION_PATTERN.search(command)
        if match:
            place = match.group(1).lower()
            return place not in self._LOCAL_NAMES
        return False

    def handle_intent(self, intent: str, entities: dict) -> str:
        """Handle matched intent.

        Returns None for non-local location queries so they fall through
        to the LLM tool path where get_weather can geocode the location.
        """
        # Check original command for non-local locations
        command = entities.get("original_text", "")
        if command and self._has_non_local_location(command):
            self.logger.info(
                "Weather skill declining — non-local location detected in: %s",
                command[:80],
            )
            return None

        if intent.startswith("<semantic:") and intent.endswith(">"):
            handler_name = intent[10:-1]
            for intent_id, data in self.semantic_intents.items():
                if data['handler'].__name__ == handler_name:
                    handler = data['handler']
                    location = entities.get("location")
                    if location:
                        return handler(location=location)
                    return handler()
            self.logger.error(f"Semantic handler not found: {handler_name}")
            return "Diese Wetteranfrage habe ich nicht verstanden."

        handler = self.intents.get(intent, {}).get("handler")
        if handler:
            location = entities.get("location")
            if location:
                return handler(location=location)
            return handler()
        return "Diese Wetteranfrage habe ich nicht verstanden."


def create_skill(config, conversation, tts, responses, llm):
    """Factory function to create skill instance"""
    return WeatherSkill(config, conversation, tts, responses, llm)
