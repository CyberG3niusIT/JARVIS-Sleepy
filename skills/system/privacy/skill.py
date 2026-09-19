"""Privacy Skill

Local voice-control path for core.privacy_gate.PrivacyGate (see that
module for the actual enforcement — this skill only flips the mode).
Per the requirement that "if no separate secure control plane exists, a
local CLI/control path is acceptable for now": this runs in-process, so
enter()/exit() take effect immediately for every other component sharing
the same PrivacyGate singleton — no IPC needed.
"""

from core.base_skill import BaseSkill
from core.privacy_gate import get_privacy_gate, PrivacyMode


class PrivacySkill(BaseSkill):
    """Enter/exit PRIVACY and PRIVACY_LOCK via voice."""

    def initialize(self) -> bool:
        self._gate = get_privacy_gate(self.config)

        self.register_intent("privatsphäre aktivieren", self.enter_privacy)
        self.register_intent("privatsphäre an", self.enter_privacy)
        self.register_intent("privatsphäre ein", self.enter_privacy)
        self.register_intent("privatmodus aktivieren", self.enter_privacy)
        self.register_intent("privatmodus an", self.enter_privacy)
        self.register_intent("aktiviere privatsphäre", self.enter_privacy)
        self.register_intent("aktiviere den privatmodus", self.enter_privacy)
        self.register_intent("schalte in den privatmodus", self.enter_privacy)
        self.register_intent("schalte den privatmodus ein", self.enter_privacy)

        self.register_intent("privacy lock aktivieren", self.enter_privacy_lock)
        self.register_intent("privatsphäre sperren", self.enter_privacy_lock)
        self.register_intent("aktiviere privacy lock", self.enter_privacy_lock)
        self.register_intent("sperre die privatsphäre", self.enter_privacy_lock)

        self.register_intent("privatsphäre beenden", self.exit_privacy)
        self.register_intent("privatsphäre aus", self.exit_privacy)
        self.register_intent("privatmodus beenden", self.exit_privacy)
        self.register_intent("privatmodus deaktivieren", self.exit_privacy)
        self.register_intent("beende privatsphäre", self.exit_privacy)
        self.register_intent("beende den privatmodus", self.exit_privacy)
        self.register_intent("verlasse den privatmodus", self.exit_privacy)
        self.register_intent("schalte den privatmodus aus", self.exit_privacy)

        self.register_intent("bist du im privatmodus", self.status)
        self.register_intent("privatsphäre status", self.status)
        self.register_intent("welcher privatsphäre modus ist aktiv", self.status)

        return True

    def enter_privacy(self) -> str:
        if self._gate.mode() != PrivacyMode.NORMAL:
            return f"Privatsphäre ist bereits aktiv, {self.honorific}."
        self._gate.enter(PrivacyMode.PRIVACY, actor="voice")
        return f"Privatsphäre aktiviert, {self.honorific}. Ich höre und beobachte jetzt nichts mehr mit."

    def enter_privacy_lock(self) -> str:
        self._gate.enter(PrivacyMode.PRIVACY_LOCK, actor="voice")
        return f"Privacy Lock aktiviert, {self.honorific}. Auch externe und Cloud-Zugriffe sind jetzt gesperrt."

    def exit_privacy(self) -> str:
        if self._gate.mode() == PrivacyMode.NORMAL:
            return f"Privatsphäre war nicht aktiv, {self.honorific}."
        self._gate.exit(actor="voice")
        return f"Privatsphäre beendet, {self.honorific}. Nur neue Eingaben werden wieder verarbeitet."

    def status(self) -> str:
        mode = self._gate.mode()
        if mode == PrivacyMode.NORMAL:
            return f"Normalmodus, {self.honorific}. Keine Einschränkungen aktiv."
        if mode == PrivacyMode.PRIVACY:
            return f"Privatsphäre ist aktiv, {self.honorific}."
        return f"Privacy Lock ist aktiv, {self.honorific}."
