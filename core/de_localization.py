"""
German localization layer for the JARVIS voice core.

Adds German semantic examples without replacing the upstream
English examples. This keeps compatibility while making German
a first-class input language.
"""

GERMAN_EXAMPLES = {

    # App launcher
    "launch_app": [
        "öffne explorer",
        "öffne den explorer",
        "starte explorer",
        "mach den explorer auf",
        "öffne chrome",
        "starte chrome",
        "öffne edge",
        "öffne vs code",
        "starte visual studio code",
        "öffne powershell",
        "öffne das terminal",
        "öffne den editor",
        "öffne notepad",
        "öffne den rechner",
        "öffne die einstellungen",
    ],

    "close_app": [
        "schließe chrome",
        "schließ chrome",
        "mach chrome zu",
        "beende den explorer",
        "schließe das programm",
        "beende die anwendung",
    ],

    "fullscreen_app": [
        "vollbild",
        "mach das fenster auf vollbild",
        "vollbildmodus",
    ],

    "minimize_app": [
        "minimiere das fenster",
        "mach das fenster klein",
        "minimiere chrome",
    ],

    "maximize_app": [
        "maximiere das fenster",
        "mach das fenster groß",
        "maximiere chrome",
    ],

    "list_apps": [
        "welche programme kannst du öffnen",
        "welche apps kannst du starten",
        "was kannst du öffnen",
        "zeig mir deine programme",
    ],

    "volume_up": [
        "lauter",
        "mach lauter",
        "lautstärke hoch",
        "erhöhe die lautstärke",
    ],

    "volume_down": [
        "leiser",
        "mach leiser",
        "lautstärke runter",
        "verringere die lautstärke",
    ],

    "toggle_mute": [
        "stumm",
        "stumm schalten",
        "ton aus",
        "ton wieder an",
        "stumm aufheben",
    ],

    "get_volume": [
        "wie laut ist es",
        "wie hoch ist die lautstärke",
        "welche lautstärke ist eingestellt",
    ],

    # Time
    "get_time": [
        "wie spät ist es",
        "wie viel uhr ist es",
        "sag mir die uhrzeit",
        "welche uhrzeit haben wir",
        "uhrzeit",
    ],

    "get_date": [
        "welches datum haben wir",
        "was ist heute für ein datum",
        "welcher tag ist heute",
        "welches datum ist heute",
        "datum",
    ],

    # Weather
    "get_current_weather": [
        "wie ist das wetter",
        "wie ist das wetter heute",
        "wie warm ist es",
        "wie kalt ist es",
        "wie ist das wetter gerade",
        "wie ist die temperatur",
    ],

    "get_forecast": [
        "wie wird das wetter",
        "wie ist die wettervorhersage",
        "wettervorhersage",
        "wie wird das wetter diese woche",
    ],

    "get_weather_for_period": [
        "wie wird das wetter am wochenende",
        "wie wird das wetter nächste woche",
        "wetter am wochenende",
        "wetter in den nächsten tagen",
    ],

    "get_tomorrow_weather": [
        "wie wird das wetter morgen",
        "wetter morgen",
        "wie ist das wetter morgen",
    ],

    "check_rain_tomorrow": [
        "regnet es morgen",
        "wird es morgen regnen",
        "regnet es heute",
        "wird es regnen",
    ],

    "get_sunrise": [
        "wann geht die sonne auf",
        "wann ist sonnenaufgang",
        "sonnenaufgang",
    ],

    "get_sunset": [
        "wann geht die sonne unter",
        "wann ist sonnenuntergang",
        "sonnenuntergang",
    ],

    # System
    "get_disk_space": [
        "wie viel speicherplatz habe ich",
        "wie voll ist die festplatte",
        "wie viel speicher ist frei",
        "festplattenbelegung",
    ],

    "get_cpu_info": [
        "welchen prozessor habe ich",
        "welche cpu habe ich",
        "zeig mir meine cpu",
        "was ist für eine cpu verbaut",
    ],

    "get_memory_info": [
        "wie viel ram habe ich",
        "wie viel arbeitsspeicher habe ich",
        "zeig mir meinen arbeitsspeicher",
    ],

    "get_all_drives": [
        "welche laufwerke habe ich",
        "zeig mir meine laufwerke",
        "welche festplatten habe ich",
        "wie viel speicher habe ich",
    ],

    "get_gpu_info": [
        "welche grafikkarte habe ich",
        "welche gpu habe ich",
        "zeig mir meine grafikkarte",
        "was ist für eine gpu verbaut",
    ],

    # Web
    "search_web": [
        "suche im internet nach",
        "such im web nach",
        "google nach",
        "such mir im internet",
        "recherchiere im internet",
    ],

    "search_youtube": [
        "such auf youtube nach",
        "suche youtube nach",
        "finde auf youtube",
    ],

    "search_github": [
        "such auf github nach",
        "suche github nach",
        "finde auf github",
    ],
}


def localize_skill(skill):
    """Append German examples to semantic intents by handler name."""

    count = 0

    for intent_id, data in getattr(
        skill, "semantic_intents", {}
    ).items():

        handler = data.get("handler")
        handler_name = getattr(handler, "__name__", "")

        german = GERMAN_EXAMPLES.get(handler_name)
        if not german:
            continue

        current = list(data.get("examples", []))

        for example in german:
            if example not in current:
                current.append(example)
                count += 1

        data["examples"] = current

    return count
