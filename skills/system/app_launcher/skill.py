"""App Launcher skill — launch applications and manage windows by voice."""

import logging
import os
import shlex
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class AppLauncherSkill:
    """Launch apps, close them, and manage window state (fullscreen/minimize/maximize)."""

    def __init__(self, config: dict, tts=None):
        self.config = config
        self.tts = tts
        self.honorific = "sir"
        self.semantic_intents = {}
        self.intents = {}

        # Load app aliases from config
        launcher_config = config.get("app_launcher", {})
        self.apps = launcher_config.get("apps", {})

    def initialize(self) -> bool:
        """Register semantic intents for app launching and window management."""

        self.register_semantic_intent(
            examples=[
                "open chrome",
                "launch brave",
                "start firefox",
                "run vs code",
                "launch the terminal",
                "open the calculator",
                "pull up the file manager",
                "start nautilus",
                "open settings",
            ],
            handler=self.launch_app,
            threshold=0.48,
        )

        self.register_semantic_intent(
            examples=[
                "close chrome",
                "close the browser",
                "shut down firefox",
                "exit vs code",
                "close that application",
            ],
            handler=self.close_app,
            threshold=0.48,
        )

        self.register_semantic_intent(
            examples=[
                "fullscreen",
                "make it fullscreen",
                "go fullscreen",
                "fullscreen please",
                "fullscreen chrome",
                "make the window fullscreen",
            ],
            handler=self.fullscreen_app,
            threshold=0.50,
        )

        self.register_semantic_intent(
            examples=[
                "minimize that",
                "minimize the window",
                "minimize chrome",
                "hide the browser",
                "minimize it",
            ],
            handler=self.minimize_app,
            threshold=0.50,
        )

        self.register_semantic_intent(
            examples=[
                "maximize that",
                "maximize the window",
                "maximize chrome",
                "make it bigger",
                "maximize it",
            ],
            handler=self.maximize_app,
            threshold=0.50,
        )

        self.register_semantic_intent(
            examples=[
                "what apps can you launch",
                "show me available apps",
                "what programs do you know",
                "list your applications",
                "what can you open",
            ],
            handler=self.list_apps,
            threshold=0.55,
        )

        logger.info(f"App Launcher initialized with {len(self.apps)} configured apps")
        return True

    def register_semantic_intent(self, examples: list, handler, threshold: float):
        """Register a semantic intent (called by skill_manager during load)."""
        intent_id = f"<semantic:{handler.__name__}>"
        self.semantic_intents[intent_id] = {
            "examples": examples,
            "handler": handler,
            "threshold": threshold,
        }

    def handle_intent(self, intent: str, entities: dict) -> str:
        """Route intents to handlers."""
        if intent.startswith("<semantic:") and intent.endswith(">"):
            handler_name = intent[10:-1]
            for intent_id, data in self.semantic_intents.items():
                if data["handler"].__name__ == handler_name:
                    return data["handler"](entities.get("original_text", ""))

        handler = self.intents.get(intent, {}).get("handler")
        if handler:
            return handler(entities.get("original_text", ""))
        return f"I'm not sure how to handle that, {self.honorific}."

    def respond(self, text: str) -> str:
        """Return response with honorific placeholder for pipeline resolution."""
        return text

    # ── App name extraction ────────────────────────────────────────────

    def _extract_app_name(self, text: str) -> Optional[str]:
        """Match query text against known app aliases and display names."""
        text_lower = text.lower()
        for alias, app_config in self.apps.items():
            name = app_config.get("name", alias).lower()
            # Check alias first ("chrome"), then display name ("google chrome")
            if alias in text_lower or name in text_lower:
                return alias
        return None

    # ── Launch / Close ─────────────────────────────────────────────────

    def launch_app(self, text: str = "") -> str:
        """Launch an application by name."""
        alias = self._extract_app_name(text)
        if not alias:
            return self.respond(
                f"I don't recognize that application, {self.honorific}. "
                f"Say 'what apps can you launch' to see what's available."
            )

        app = self.apps[alias]
        display_name = app.get("name", alias)
        exec_cmd = app.get("exec", alias)

        try:
            env = os.environ.copy()
            env.setdefault("DISPLAY", ":0")

            cmd_parts = shlex.split(exec_cmd)
            subprocess.Popen(
                cmd_parts,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            logger.info(f"Launched {display_name}: {exec_cmd}")
            return self.respond(f"Launching {display_name}, {self.honorific}.")
        except FileNotFoundError:
            logger.error(f"Executable not found for {alias}: {exec_cmd}")
            return self.respond(
                f"I couldn't find the executable for {display_name}, {self.honorific}."
            )
        except Exception as e:
            logger.error(f"Failed to launch {alias}: {e}")
            return self.respond(
                f"Something went wrong launching {display_name}, {self.honorific}."
            )

    def close_app(self, text: str = "") -> str:
        """Close an application window gracefully via wmctrl."""
        alias = self._extract_app_name(text)
        if not alias:
            return self.respond(
                f"Which application should I close, {self.honorific}?"
            )

        app = self.apps[alias]
        display_name = app.get("name", alias)
        window_id = self._find_window(alias)

        if not window_id:
            return self.respond(
                f"I don't see {display_name} running, {self.honorific}."
            )

        try:
            subprocess.run(
                ["wmctrl", "-i", "-c", window_id],
                timeout=5,
                capture_output=True,
            )
            logger.info(f"Closed {display_name} (window {window_id})")
            return self.respond(f"Closing {display_name}, {self.honorific}.")
        except Exception as e:
            logger.error(f"Failed to close {alias}: {e}")
            return self.respond(
                f"I couldn't close {display_name}, {self.honorific}."
            )

    # ── Window management ──────────────────────────────────────────────

    def fullscreen_app(self, text: str = "") -> str:
        """Make a window fullscreen via wmctrl."""
        window_id = self._resolve_window(text)
        if not window_id:
            return self._no_window_response("fullscreen")

        try:
            # Remove maximized state first (conflicts with fullscreen on some WMs)
            subprocess.run(
                ["wmctrl", "-i", "-r", window_id, "-b", "remove,maximized_vert,maximized_horz"],
                timeout=5, capture_output=True,
            )
            subprocess.run(
                ["wmctrl", "-i", "-r", window_id, "-b", "add,fullscreen"],
                timeout=5, capture_output=True,
            )
            logger.info(f"Fullscreened window {window_id}")
            return self.respond(f"Done, {self.honorific}.")
        except Exception as e:
            logger.error(f"Fullscreen failed: {e}")
            return self.respond(f"I couldn't fullscreen that window, {self.honorific}.")

    def minimize_app(self, text: str = "") -> str:
        """Minimize a window via wmctrl."""
        window_id = self._resolve_window(text)
        if not window_id:
            return self._no_window_response("minimize")

        try:
            # wmctrl minimize: use xdg approach — wmctrl doesn't have native minimize
            # Instead, use xdotool if available, or wmctrl iconic state
            subprocess.run(
                ["wmctrl", "-i", "-r", window_id, "-b", "add,hidden"],
                timeout=5, capture_output=True,
            )
            logger.info(f"Minimized window {window_id}")
            return self.respond(f"Minimized, {self.honorific}.")
        except Exception as e:
            logger.error(f"Minimize failed: {e}")
            return self.respond(f"I couldn't minimize that window, {self.honorific}.")

    def maximize_app(self, text: str = "") -> str:
        """Maximize a window via wmctrl."""
        window_id = self._resolve_window(text)
        if not window_id:
            return self._no_window_response("maximize")

        try:
            # Remove fullscreen first if set
            subprocess.run(
                ["wmctrl", "-i", "-r", window_id, "-b", "remove,fullscreen"],
                timeout=5, capture_output=True,
            )
            subprocess.run(
                ["wmctrl", "-i", "-r", window_id, "-b", "add,maximized_vert,maximized_horz"],
                timeout=5, capture_output=True,
            )
            logger.info(f"Maximized window {window_id}")
            return self.respond(f"Maximized, {self.honorific}.")
        except Exception as e:
            logger.error(f"Maximize failed: {e}")
            return self.respond(f"I couldn't maximize that window, {self.honorific}.")

    def list_apps(self, text: str = "") -> str:
        """List all configured applications."""
        if not self.apps:
            return self.respond(
                f"I don't have any applications configured, {self.honorific}."
            )

        names = [app.get("name", alias) for alias, app in self.apps.items()]
        if len(names) == 1:
            app_list = names[0]
        elif len(names) == 2:
            app_list = f"{names[0]} and {names[1]}"
        else:
            app_list = ", ".join(names[:-1]) + f", and {names[-1]}"

        return self.respond(
            f"I can launch {app_list}, {self.honorific}."
        )

    # ── Helpers ────────────────────────────────────────────────────────

    def _find_window(self, alias: str) -> Optional[str]:
        """Find a window ID matching the app alias using wmctrl -l."""
        app = self.apps.get(alias, {})
        display_name = app.get("name", alias).lower()
        exec_cmd = app.get("exec", "").lower()

        # Build search terms from alias, display name, and executable
        search_terms = [alias.lower(), display_name]
        # Extract base executable name (e.g., "brave-browser" from "brave-browser --ozone...")
        if exec_cmd:
            base_exec = exec_cmd.split()[0].split("/")[-1]
            search_terms.append(base_exec)

        try:
            result = subprocess.run(
                ["wmctrl", "-l"],
                timeout=5,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return None

            for line in result.stdout.strip().splitlines():
                # wmctrl -l format: "0x01234567  0 hostname Window Title"
                parts = line.split(None, 3)
                if len(parts) < 4:
                    continue
                window_id = parts[0]
                title = parts[3].lower()

                for term in search_terms:
                    if term in title:
                        return window_id

        except Exception as e:
            logger.error(f"wmctrl -l failed: {e}")

        return None

    def _resolve_window(self, text: str) -> Optional[str]:
        """Resolve a window from text, or fall back to the active window."""
        # Try to find a named app in the query
        alias = self._extract_app_name(text)
        if alias:
            window_id = self._find_window(alias)
            if window_id:
                return window_id

        # Fall back to the active window (most recently focused)
        try:
            result = subprocess.run(
                ["wmctrl", "-a", ":ACTIVE:", "-v"],
                timeout=5,
                capture_output=True,
                text=True,
            )
            # Get active window via wmctrl -l and xprop
            result = subprocess.run(
                ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
                timeout=5,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and "window id #" in result.stdout.lower():
                # Parse: "_NET_ACTIVE_WINDOW(WINDOW): window id # 0x12345"
                parts = result.stdout.strip().split()
                if parts:
                    window_id = parts[-1]
                    # Normalize to 0x format wmctrl expects
                    if window_id.startswith("0x"):
                        return window_id
        except Exception as e:
            logger.debug(f"Could not get active window: {e}")

        return None

    def _no_window_response(self, action: str) -> str:
        """Response when no window can be found for the requested action."""
        return self.respond(
            f"I couldn't find a window to {action}, {self.honorific}."
        )
