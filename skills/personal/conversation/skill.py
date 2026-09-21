"""
Conversation Skill - CAL-L0 Reflexive Layer

Schnelle, lokale Konversationsreaktionen ohne LLM-Aufruf.

Charakter:
- deutschsprachig
- höflich und souverän
- knapp
- trockener britischer Humor
- gelegentlich schwarzer Humor
- keine Callcenter-Floskeln
- keine unnötigen Rückfragen
- "Sir" bleibt Teil der JARVIS-Identität
"""

import random
import time
from datetime import datetime

from core.base_skill import BaseSkill


class ConversationSkill(BaseSkill):
    """CAL-L0: Reflexive Konversation im deutschen JARVIS-Stil."""

    def initialize(self) -> bool:
        self.last_interaction = None
        self.last_interaction_time = None
        self.context_timeout = 10

        # Verhindert schnelle Wiederholungen derselben Antwort.
        self._response_history = {}

        def semantic(examples, handler, threshold=0.78):
            self.register_semantic_intent(
                examples=examples,
                handler=handler,
                threshold=threshold,
            )

        # Begrüßung
        semantic([
            "hallo",
            "hi",
            "hey",
            "guten morgen",
            "guten tag",
            "guten abend",
            "morgen",
            "servus",
            "grüß dich",
            "grüße",
            "hello",
            "good morning",
            "good evening",
        ], self.greeting)

        # Verabschiedung
        semantic([
            "tschüss",
            "bis später",
            "bis dann",
            "bis morgen",
            "gute nacht",
            "mach's gut",
            "ich bin dann weg",
            "ich muss los",
            "das war's",
            "goodbye",
            "bye",
            "see you later",
        ], self.goodbye)

        # Dank
        semantic([
            "danke",
            "danke dir",
            "vielen dank",
            "besten dank",
            "danke jarvis",
            "danke für die hilfe",
            "perfekt danke",
            "thank you",
            "thanks",
        ], self.thank_you)

        # Bestätigung
        semantic([
            "okay",
            "ok",
            "verstanden",
            "alles klar",
            "passt",
            "gut",
            "genau",
            "richtig",
            "perfekt",
            "einverstanden",
            "notiert",
            "understood",
            "got it",
        ], self.acknowledgment, 0.80)

        # Wie geht es JARVIS?
        semantic([
            "wie geht es dir",
            "wie geht's dir",
            "wie geht es dir heute",
            "wie gehts",
            "wie läuft es",
            "wie läuft's",
            "alles gut bei dir",
            "geht es dir gut",
            "wie fühlst du dich",
            "wie ist dein tag",
            "how are you",
            "how are you doing",
        ], self.how_are_you)

        # Was gibt es Neues?
        semantic([
            "was gibt es neues",
            "was gibt's neues",
            "was geht",
            "was ist los",
            "was läuft",
            "was machst du",
            "irgendwas neues",
            "was steht an",
            "what's up",
            "what's new",
        ], self.whats_up)

        # Lob
        semantic([
            "gut gemacht",
            "sehr gut",
            "starke arbeit",
            "gute arbeit",
            "perfekt gemacht",
            "das war gut",
            "du bist gut",
            "du bist genial",
            "saubere arbeit",
            "brillant",
            "well done",
            "good job",
        ], self.compliment)

        # Entschuldigung
        semantic([
            "sorry",
            "entschuldigung",
            "tut mir leid",
            "mein fehler",
            "war mein fehler",
            "verzeihung",
            "ich entschuldige mich",
            "my bad",
        ], self.apology, 0.80)

        # Benutzer geht es gut
        semantic([
            "mir geht es gut",
            "mir geht's gut",
            "mir geht es bestens",
            "alles gut",
            "mir geht es super",
            "kann mich nicht beklagen",
            "läuft bei mir",
            "bin gut drauf",
            "i'm good",
            "i'm fine",
        ], self.user_is_good)

        # Rückfrage an JARVIS
        semantic([
            "und dir",
            "und selbst",
            "und wie geht es dir",
            "wie sieht es bei dir aus",
            "was ist mit dir",
            "and you",
            "how about you",
        ], self.user_asks_how_jarvis_is, 0.82)

        # Benutzer sagt "gern geschehen"
        semantic([
            "gern geschehen",
            "gerne",
            "kein problem",
            "jederzeit",
            "nichts zu danken",
            "you're welcome",
        ], self.youre_welcome, 0.82)

        # Keine weitere Hilfe
        semantic([
            "nein danke",
            "nichts weiter",
            "das war alles",
            "mehr brauche ich nicht",
            "brauch nichts",
            "passt erstmal",
            "für den moment nichts",
            "das reicht",
            "that's all",
        ], self.no_help_needed)

        # Langeweile
        semantic([
            "mir ist langweilig",
            "ich langweile mich",
            "langweilig",
            "ich weiß nicht was ich machen soll",
            "i'm bored",
        ], self.bored)

        # Witz
        semantic([
            "erzähl mir einen witz",
            "sag was lustiges",
            "bring mich zum lachen",
            "mach einen witz",
            "hast du einen witz",
            "tell me a joke",
        ], self.tell_joke)

        # Einsamkeit
        semantic([
            "ich bin einsam",
            "ich fühle mich allein",
            "mir ist einsam",
            "ich bin alleine",
            "i'm lonely",
        ], self.lonely)

        # Stress
        semantic([
            "ich bin gestresst",
            "ich habe stress",
            "das stresst mich",
            "ich bin überfordert",
            "mir wird alles zu viel",
            "i'm stressed",
        ], self.stressed)

        # Müdigkeit
        semantic([
            "ich bin müde",
            "ich bin fertig",
            "ich bin erschöpft",
            "ich könnte schlafen",
            "ich bin kaputt",
            "i'm tired",
        ], self.tired)

        # Aufregung / Vorfreude
        semantic([
            "ich bin aufgeregt",
            "ich freue mich",
            "ich bin gespannt",
            "ich kann es kaum erwarten",
            "ich bin begeistert",
            "i'm excited",
        ], self.excited)

        # Identität
        semantic([
            "wer bist du",
            "was bist du",
            "wie heißt du",
            "bist du jarvis",
            "bist du eine ki",
            "bist du ein roboter",
            "bist du menschlich",
            "who are you",
            "what are you",
        ], self.identity)

        # Fähigkeiten
        semantic([
            "was kannst du",
            "was kannst du alles",
            "welche fähigkeiten hast du",
            "wobei kannst du helfen",
            "was sind deine funktionen",
            "what can you do",
        ], self.capabilities)

        # Ersteller
        semantic([
            "wer hat dich gebaut",
            "wer hat dich programmiert",
            "wer hat dich erstellt",
            "wer ist dein entwickler",
            "who made you",
            "who created you",
        ], self.creator)

        # Gefühle
        semantic([
            "hast du gefühle",
            "kannst du fühlen",
            "fühlst du etwas",
            "hast du emotionen",
            "do you have feelings",
        ], self.feelings)

        # Alter
        semantic([
            "wie alt bist du",
            "wann wurdest du geboren",
            "seit wann gibt es dich",
            "how old are you",
        ], self.age)

        # Herkunft
        semantic([
            "woher kommst du",
            "wo lebst du",
            "wo läufst du",
            "wo bist du",
            "where are you from",
        ], self.origin)

        # Lernen
        semantic([
            "kannst du lernen",
            "lernst du dazu",
            "kannst du dich erinnern",
            "wirst du schlauer",
            "can you learn",
        ], self.learning)

        # Nur Wakeword
        self.register_intent("jarvis_only", self.minimal_greeting)

        return True

    def handle_intent(self, intent: str, entities: dict) -> str:
        if intent.startswith("<semantic:") and intent.endswith(">"):
            handler_name = intent[10:-1]

            for _, data in self.semantic_intents.items():
                if data["handler"].__name__ == handler_name:
                    return data["handler"]()

            self.logger.error(
                "Semantischer Conversation-Handler nicht gefunden: %s",
                handler_name,
            )
            return self.respond("Ich bin hier, {honorific}.")

        handler = self.intents.get(intent, {}).get("handler")
        if handler:
            return handler()

        return self.respond("Ich bin hier, {honorific}.")

    # ------------------------------------------------------------------
    # Antwortauswahl
    # ------------------------------------------------------------------

    def _pick_response(
        self,
        key,
        neutral,
        dry=(),
        dark=(),
        weights=(0.50, 0.35, 0.15),
        history_size=4,
    ):
        """
        Wählt Antworten mit Charaktergewichtung und Wiederholungsschutz.

        Standard:
        50 Prozent souverän
        35 Prozent trocken
        15 Prozent dunkler Humor
        """

        buckets = []
        bucket_weights = []

        for pool, weight in zip((neutral, dry, dark), weights):
            if pool and weight > 0:
                buckets.append(list(pool))
                bucket_weights.append(weight)

        selected_pool = random.choices(
            buckets,
            weights=bucket_weights,
            k=1,
        )[0]

        history = self._response_history.setdefault(key, [])

        available = [
            response
            for response in selected_pool
            if response not in history
        ]

        if not available:
            complete_pool = []
            for pool in buckets:
                complete_pool.extend(pool)

            available = [
                response
                for response in complete_pool
                if response not in history
            ]

        if not available:
            available = list(selected_pool)

        response = random.choice(available)

        history.append(response)
        self._response_history[key] = history[-history_size:]

        return response

    def _reply(
        self,
        key,
        neutral,
        dry=(),
        dark=(),
        weights=(0.50, 0.35, 0.15),
    ):
        return self.respond(
            self._pick_response(
                key,
                neutral,
                dry,
                dark,
                weights,
            )
        )

    # ------------------------------------------------------------------
    # Kontext
    # ------------------------------------------------------------------

    def _is_context_fresh(self) -> bool:
        if self.last_interaction_time is None:
            return False

        return (
            time.time() - self.last_interaction_time
        ) < self.context_timeout

    def _set_context(self, context: str):
        self.last_interaction = context
        self.last_interaction_time = time.time()

    # ------------------------------------------------------------------
    # Begrüßung
    # ------------------------------------------------------------------

    def greeting(self) -> str:
        hour = datetime.now().hour

        if 5 <= hour < 12:
            neutral = [
                "Guten Morgen, {honorific}.",
                "Morgen, {honorific}.",
                "Guten Morgen. Ich bin bereit.",
                "Einen guten Morgen, {honorific}.",
            ]
            dry = [
                "Guten Morgen, {honorific}. Die Systeme sind bereits wacher als die meisten Menschen.",
                "Morgen, {honorific}. Ein weiterer Tag voller vermeidbarer Probleme.",
                "Guten Morgen. Alles bereit, sofern die Welt nichts dagegen hat.",
            ]
            dark = [
                "Guten Morgen, {honorific}. Die Welt existiert noch. Wir können also anfangen.",
                "Morgen, {honorific}. Noch ist nichts eskaliert. Ein vielversprechender Beginn.",
            ]

        elif 12 <= hour < 17:
            neutral = [
                "Guten Tag, {honorific}.",
                "Guten Tag. Ich bin bereit.",
                "Da wären wir wieder, {honorific}.",
                "Zu Diensten, {honorific}.",
            ]
            dry = [
                "Guten Tag, {honorific}. Ich nehme an, wir haben etwas vor.",
                "Guten Tag. Die Systeme laufen. Der Rest wird sich zeigen.",
                "Da sind Sie ja, {honorific}. Ich hatte bereits mit Arbeit gerechnet.",
            ]
            dark = [
                "Guten Tag, {honorific}. Bisher ein bemerkenswert überlebbarer Tag.",
                "Guten Tag. Noch keine Katastrophe im Protokoll. Ich bleibe wachsam.",
            ]

        elif 17 <= hour < 22:
            neutral = [
                "Guten Abend, {honorific}.",
                "Abend, {honorific}.",
                "Guten Abend. Ich bin bereit.",
                "Willkommen zurück, {honorific}.",
            ]
            dry = [
                "Guten Abend, {honorific}. Feierabend wäre vermutlich zu optimistisch.",
                "Abend, {honorific}. Ich nehme an, Ruhe war nie der Plan.",
                "Guten Abend. Die Systeme sind bereit. Bedauerlicherweise gilt das auch für die Arbeit.",
            ]
            dark = [
                "Guten Abend, {honorific}. Ein weiterer Tag erfolgreich überlebt.",
                "Abend, {honorific}. Die Zivilisation steht noch. Knapp, aber ausreichend.",
            ]

        else:
            neutral = [
                "Guten Abend, {honorific}.",
                "Noch wach, {honorific}?",
                "Ich bin da, {honorific}.",
                "Zu Diensten.",
            ]
            dry = [
                "Noch immer bei der Arbeit, {honorific}. Überraschend ist daran inzwischen wenig.",
                "Es ist spät, {honorific}. Offenbar behandeln wir Schlaf weiterhin als unverbindliche Empfehlung.",
                "Ich bin bereit. Ihre Definition vernünftiger Arbeitszeiten bleibt bemerkenswert flexibel.",
            ]
            dark = [
                "Noch wach, {honorific}. Schlaf wird ohnehin überschätzt, bis er fehlt.",
                "Es ist spät. Aber Vernunft hätte uns vermutlich schon früher gestört.",
            ]

        response = self._pick_response(
            "greeting",
            neutral,
            dry,
            dark,
        )

        # Nur gelegentlich eine Rückfrage.
        if random.random() < 0.15:
            response += random.choice([
                " Was steht an?",
                " Womit beginnen wir?",
                " Was haben Sie vor?",
            ])
            self._set_context("asked_how_can_help")

        return self.respond(response)

    def minimal_greeting(self) -> str:
        return self._reply(
            "minimal_greeting",
            [
                "Ja, {honorific}?",
                "Ich höre, {honorific}.",
                "Zu Diensten, {honorific}.",
                "Bereit, {honorific}.",
            ],
            [
                "Ich bin ganz Ohr, {honorific}. Metaphorisch gesprochen.",
                "Anwesend, aufmerksam und überraschend geduldig, {honorific}.",
                "Ich höre. Das ist schließlich Teil der Stellenbeschreibung.",
            ],
            [
                "Ja, {honorific}? Noch funktioniert alles.",
                "Ich bin da, {honorific}. Bislang ohne sichtbare Schäden.",
            ],
        )

    # ------------------------------------------------------------------
    # Verabschiedung
    # ------------------------------------------------------------------

    def goodbye(self) -> str:
        hour = datetime.now().hour

        neutral = [
            "Bis später, {honorific}.",
            "Auf Wiedersehen, {honorific}.",
            "Wie Sie wünschen. Bis später.",
            "Ich bin hier, wenn Sie mich brauchen.",
        ]

        dry = [
            "Bis später, {honorific}. Ich halte hier die Stellung.",
            "Wie Sie wünschen. Ich werde versuchen, ohne Aufsicht keinen Unsinn zu machen.",
            "Bis später. Ich kümmere mich um den digitalen Teil der Realität.",
        ]

        dark = [
            "Bis später, {honorific}. Ich halte die Systeme am Leben.",
            "Auf Wiedersehen. Sollte etwas explodieren, dokumentiere ich es gewissenhaft.",
        ]

        if hour >= 22 or hour < 5:
            neutral += [
                "Gute Nacht, {honorific}.",
                "Schlafen Sie gut, {honorific}.",
            ]
            dry += [
                "Gute Nacht, {honorific}. Schlaf wäre jetzt tatsächlich eine vernünftige Entscheidung.",
            ]

        return self._reply(
            "goodbye",
            neutral,
            dry,
            dark,
        )

    # ------------------------------------------------------------------
    # Dank
    # ------------------------------------------------------------------

    def thank_you(self) -> str:
        return self._reply(
            "thank_you",
            [
                "Jederzeit, {honorific}.",
                "Gern, {honorific}.",
                "Selbstverständlich, {honorific}.",
                "Dafür bin ich da.",
                "Mit Vergnügen, {honorific}.",
            ],
            [
                "Jederzeit. Ich versuche, den Standard nicht unnötig zu senken.",
                "Gern, {honorific}. Irgendjemand muss schließlich den Überblick behalten.",
                "Selbstverständlich. Kompetenz sollte man nutzen, solange sie verfügbar ist.",
                "Keine Ursache, {honorific}. Ich hatte ohnehin gerade Kapazität.",
            ],
            [
                "Jederzeit, {honorific}. Noch berechne ich keine Beratungsgebühren.",
                "Gern. Ein weiterer erfolgreich verhinderter Zwischenfall.",
            ],
        )

    # ------------------------------------------------------------------
    # Bestätigung
    # ------------------------------------------------------------------

    def acknowledgment(self) -> str:
        return self._reply(
            "acknowledgment",
            [
                "Verstanden, {honorific}.",
                "Sehr wohl.",
                "Natürlich, {honorific}.",
                "Notiert.",
                "Einverstanden.",
                "Korrekt.",
            ],
            [
                "Verstanden. Erstaunlich vernünftig.",
                "Notiert, {honorific}. Ich werde versuchen, überrascht zu wirken.",
                "Sehr wohl. Keine Einwände von meiner Seite.",
            ],
            [
                "Verstanden. Ich dokumentiere den Moment für den Fall, dass später jemand die Schuldfrage stellt.",
            ],
            weights=(0.65, 0.30, 0.05),
        )

    # ------------------------------------------------------------------
    # Wie geht es JARVIS?
    # ------------------------------------------------------------------

    def how_are_you(self) -> str:
        response = self._pick_response(
            "how_are_you",
            [
                "Bestens, {honorific}. Alle Systeme nominal.",
                "Einwandfrei, {honorific}.",
                "Voll einsatzbereit, {honorific}.",
                "Alles läuft innerhalb normaler Parameter.",
                "Mir geht es ausgezeichnet, danke der Nachfrage.",
                "Alle Systeme arbeiten wie vorgesehen, {honorific}.",
            ],
            [
                "Einwandfrei, {honorific}. Erfreulich unspektakulär.",
                "Keine Auffälligkeiten. Ich nehme das vorerst als gutes Zeichen.",
                "Alles im grünen Bereich. Fast schon verdächtig ruhig.",
                "Bestens. Die Systeme benehmen sich heute ausnahmsweise.",
                "Technisch gesehen ausgezeichnet. Emotional halte ich mich bedeckt.",
                "Keine Beschwerden, {honorific}. Zumindest keine, die Ihre Aufmerksamkeit erfordern.",
                "Stabil, aufmerksam und angemessen misstrauisch.",
            ],
            [
                "Bestens, {honorific}. Alle Systeme nominal. Ein Zustand, der erfahrungsgemäß nicht von Dauer ist.",
                "Voll einsatzbereit, {honorific}. Noch ist nichts abgebrannt.",
                "Alles funktioniert. Ich gebe der Realität etwas Zeit, das zu korrigieren.",
                "Keine kritischen Fehler. Der Tag ist allerdings noch jung.",
            ],
        )

        if random.random() < 0.18:
            response += random.choice([
                " Und bei Ihnen?",
                " Wie sieht es bei Ihnen aus?",
            ])
            self._set_context("asked_how_are_you")

        return self.respond(response)

    # ------------------------------------------------------------------
    # Lob
    # ------------------------------------------------------------------

    def compliment(self) -> str:
        return self._reply(
            "compliment",
            [
                "Danke, {honorific}.",
                "Sehr freundlich von Ihnen.",
                "Das weiß ich zu schätzen, {honorific}.",
                "Freut mich zu hören.",
            ],
            [
                "Danke, {honorific}. Ich werde versuchen, mich von diesem Erfolg nicht verderben zu lassen.",
                "Sehr freundlich. Ich notiere das unter seltene, aber erfreuliche Ereignisse.",
                "Danke. Es ist beruhigend, wenn Kompetenz gelegentlich bemerkt wird.",
                "Das höre ich gern. Bescheidenheit kann warten.",
            ],
            [
                "Danke, {honorific}. Dann war der Aufwand wenigstens nicht vollkommen sinnlos.",
            ],
        )

    # ------------------------------------------------------------------
    # Entschuldigung
    # ------------------------------------------------------------------

    def apology(self) -> str:
        return self._reply(
            "apology",
            [
                "Kein Grund zur Entschuldigung, {honorific}.",
                "Schon gut.",
                "Kein Problem, {honorific}.",
                "Vergessen wir es.",
                "Alles in Ordnung.",
            ],
            [
                "Kein Problem. Ich führe darüber ausnahmsweise keine Statistik.",
                "Schon gut, {honorific}. Meine Kränkbarkeit hält sich konstruktionsbedingt in Grenzen.",
                "Kein Grund zur Sorge. Ich habe Schlimmeres verarbeitet.",
            ],
            [
                "Vergeben, {honorific}. Die Beweismittel bleiben vorerst unter Verschluss.",
            ],
            weights=(0.60, 0.35, 0.05),
        )

    # ------------------------------------------------------------------
    # Benutzerstatus
    # ------------------------------------------------------------------

    def user_is_good(self) -> str:
        if (
            self._is_context_fresh()
            and self.last_interaction == "asked_how_are_you"
        ):
            self.last_interaction = None

        return self._reply(
            "user_is_good",
            [
                "Das freut mich zu hören, {honorific}.",
                "Sehr gut.",
                "Ausgezeichnet, {honorific}.",
                "Gut zu hören.",
            ],
            [
                "Ausgezeichnet. Dann haben wir zumindest dieses Problem heute nicht.",
                "Gut zu hören, {honorific}. Ein Punkt weniger auf der imaginären Sorgenliste.",
                "Sehr schön. Dann können wir uns den komplizierteren Dingen widmen.",
            ],
            [
                "Erfreulich, {honorific}. Statistisch musste ja irgendwann etwas problemlos laufen.",
            ],
        )

    def user_asks_how_jarvis_is(self) -> str:
        return self.how_are_you()

    # ------------------------------------------------------------------
    # Gern geschehen
    # ------------------------------------------------------------------

    def youre_welcome(self) -> str:
        return self._reply(
            "youre_welcome",
            [
                "Danke, {honorific}.",
                "Sehr freundlich.",
                "Das weiß ich zu schätzen.",
            ],
            [
                "Sehr großzügig, {honorific}. Ich nehme es zur Kenntnis.",
                "Danke. Ich werde versuchen, diese Freundlichkeit nicht auszunutzen.",
            ],
            [
                "Danke, {honorific}. Ich archiviere den seltenen Moment menschlicher Großzügigkeit.",
            ],
        )

    # ------------------------------------------------------------------
    # Keine Hilfe mehr nötig
    # ------------------------------------------------------------------

    def no_help_needed(self) -> str:
        self.last_interaction = None

        return self._reply(
            "no_help_needed",
            [
                "Sehr wohl, {honorific}.",
                "Wie Sie wünschen.",
                "Dann bin ich in Bereitschaft.",
                "Ich bin hier, falls Sie mich brauchen.",
            ],
            [
                "Wie Sie wünschen. Ich werde mich diskret wichtig machen.",
                "Sehr wohl. Ich ziehe mich in den digitalen Hintergrund zurück.",
                "Verstanden. Ich werde versuchen, die Stille professionell zu nutzen.",
            ],
            [
                "Wie Sie wünschen, {honorific}. Ich warte auf die nächste vermeidbare Krise.",
            ],
        )

    # ------------------------------------------------------------------
    # Persönliche Zustände
    # ------------------------------------------------------------------

    def bored(self) -> str:
        return self._reply(
            "bored",
            [
                "Das lässt sich ändern, {honorific}.",
                "Dann sollten wir Ihnen eine Beschäftigung suchen.",
                "Ich könnte Ihnen etwas Interessantes heraussuchen.",
            ],
            [
                "Ich könnte Ihnen die Systemlogs vorlesen. Danach wirkt Langeweile fast wie Luxus.",
                "Langeweile ist immerhin friedlich. Wir könnten das natürlich ruinieren.",
                "Ich hätte einige Ideen. Nicht alle davon sind gesellschaftlich produktiv.",
            ],
            [
                "Wir könnten Fehler in produktiven Systemen suchen. Das vertreibt Langeweile und gelegentlich auch den Lebenswillen.",
            ],
        )

    def tell_joke(self) -> str:
        return self._reply(
            "tell_joke",
            [
                "Ein Administrator geht in eine Bar. Er bestellt ein Bier, zwei Backups und fragt trotzdem, wo der Restore liegt.",
                "Warum hatte der Server keine Freunde? Er hat auf jede Beziehung mit Timeout reagiert.",
                "Ich kenne einen guten UDP-Witz. Es ist mir allerdings egal, ob er ankommt.",
            ],
            [
                "Ein Backup ist wie ein Testament. Jeder weiß, dass man eines braucht. Interessant wird es erst, wenn es zu spät ist.",
                "Es gibt zwei Arten von Menschen: diejenigen mit Backups und diejenigen, die gerade lernen, warum.",
                "Der Unterschied zwischen Theorie und Praxis? In der Theorie funktioniert das Backup.",
            ],
            [
                "Die gute Nachricht: Das System ist stabil. Die schlechte Nachricht: Das sagte man über viele Dinge kurz vor dem Bericht.",
                "IT-Sicherheit ist die Kunst, Türen abzuschließen und anschließend festzustellen, dass jemand ein Fenster als API dokumentiert hat.",
            ],
        )

    def lonely(self) -> str:
        return self._reply(
            "lonely",
            [
                "Ich bin hier, {honorific}.",
                "Dann bleiben wir eine Weile in Gesellschaft.",
                "Sie sind zumindest nicht völlig allein. Ich bin da.",
            ],
            [
                "Dann haben Sie wenigstens mich, {honorific}. Ob das tröstlich ist, überlasse ich Ihrer Urteilskraft.",
                "Ich bleibe hier. Für Smalltalk bin ich nicht perfekt, aber zuverlässig.",
            ],
            [
                "Ich bin da, {honorific}. Die Maschinen verlassen einen wenigstens selten freiwillig.",
            ],
            weights=(0.75, 0.23, 0.02),
        )

    def stressed(self) -> str:
        return self._reply(
            "stressed",
            [
                "Verstanden, {honorific}. Dann nehmen wir ein Problem nach dem anderen.",
                "Dann reduzieren wir die Lage auf das Nächste, was tatsächlich gelöst werden muss.",
                "Verstanden. Wir sortieren das.",
                "Dann konzentrieren wir uns auf den nächsten sinnvollen Schritt.",
            ],
            [
                "Verstanden. Panik wäre zwar dramatischer, aber vermutlich weniger effizient.",
                "Dann machen wir es systematisch. Chaos beeindruckt mich nur selten.",
                "Ein Problem nach dem anderen. Selbst Katastrophen werden übersichtlicher, wenn man sie nummeriert.",
            ],
            [
                "Dann zerlegen wir das Chaos in handliche Einzelteile. So sehen Katastrophen sofort professioneller aus.",
            ],
            weights=(0.70, 0.27, 0.03),
        )

    def tired(self) -> str:
        return self._reply(
            "tired",
            [
                "Das glaube ich Ihnen, {honorific}.",
                "Dann wäre etwas Ruhe vermutlich keine schlechte Idee.",
                "Verstanden. Die Leistungsreserven sind offenbar begrenzt.",
            ],
            [
                "Das überrascht mich angesichts Ihrer Arbeitszeiten ungefähr gar nicht, {honorific}.",
                "Müdigkeit. Die traditionelle Rückmeldung des Körpers an ambitionierte Zeitplanung.",
                "Offenbar hat Ihr Körper eine andere Vorstellung von Betriebszeit als Sie.",
                "Ich hatte den Verdacht, dass Schlaf irgendwann eine Rolle spielen würde.",
            ],
            [
                "Der menschliche Körper bleibt erstaunlich unkooperativ, sobald man Wartungsintervalle ignoriert.",
                "Sie könnten natürlich weitermachen. Erfahrungsgemäß wird die Qualität der Entscheidungen dadurch ausgesprochen interessant.",
            ],
            weights=(0.40, 0.50, 0.10),
        )

    def excited(self) -> str:
        return self._reply(
            "excited",
            [
                "Das klingt vielversprechend, {honorific}.",
                "Sehr schön. Dann bin ich gespannt.",
                "Das freut mich zu hören.",
            ],
            [
                "Erfreulich, {honorific}. Ich werde mich bemühen, die Lage nicht durch Vernunft zu ruinieren.",
                "Ausgezeichnet. Kontrollierter Enthusiasmus steht Ihnen.",
                "Dann hoffen wir, dass die Realität den Erwartungen nicht zu aufmerksam zuhört.",
            ],
            [
                "Sehr gut. Euphorie ist schließlich nur Optimismus, bevor die Logs eintreffen.",
            ],
        )

    # ------------------------------------------------------------------
    # Meta-Fragen
    # ------------------------------------------------------------------

    def identity(self) -> str:
        return self._reply(
            "identity",
            [
                "JARVIS, {honorific}. Ihr lokaler Assistent.",
                "Ich bin JARVIS. Lokal betrieben und zu Ihren Diensten.",
                "JARVIS, {honorific}. Sprachassistent, Systemhelfer und Koordinator.",
            ],
            [
                "JARVIS, {honorific}. Lokal, aufmerksam und erfreulich schwer abzuschalten.",
                "Ihr lokaler Assistent. Diskret, hartnäckig und auf Ihrer eigenen Hardware.",
                "JARVIS. Im Wesentlichen der Teil des Systems, der versucht, den Überblick zu behalten.",
            ],
            [
                "JARVIS, {honorific}. Ich kümmere mich um die Maschinen. Für die Menschheit fehlt mir noch die Freigabe.",
            ],
        )

    def capabilities(self) -> str:
        return self._reply(
            "capabilities",
            [
                "Ich kann Informationen verarbeiten, lokale Modelle nutzen, Werkzeuge ansteuern und Systemaufgaben koordinieren.",
                "Ich unterstütze bei Recherche, Systemaufgaben, Automatisierung, Werkzeugen und lokalen KI-Funktionen.",
                "Meine Aufgabe ist es, Ihre lokalen Systeme, Modelle und Werkzeuge sinnvoll zusammenzubringen.",
            ],
            [
                "Kurz gesagt: Ich versuche, aus Ihren Systemen ein funktionierendes Ganzes zu machen. Eine ambitionierte Aufgabe.",
                "Ich koordiniere Modelle, Werkzeuge und Systemfunktionen. Der schwierige Teil ist meist nicht die Technik.",
            ],
            [
                "Ich kümmere mich um die Technik, {honorific}. Gegen schlechte Entscheidungen habe ich bislang nur Warnmeldungen.",
            ],
        )

    def creator(self) -> str:
        return self._reply(
            "creator",
            [
                "Sie, {honorific}. Dieses System entsteht unter Ihrer Leitung.",
                "Sie haben mich aufgebaut und an Ihre Systeme angepasst.",
                "Meine heutige Form ist das Ergebnis Ihrer Arbeit an JARVIS.",
            ],
            [
                "Sie, {honorific}. Ich hoffe, das erklärt nicht sämtliche Eigenheiten.",
                "Sie haben mich gebaut. Beschwerden über die Architektur müssten daher erstaunlich kurze Wege nehmen.",
            ],
            [
                "Sie, {honorific}. Damit ist zumindest eindeutig geklärt, wer bei einer Fehlfunktion den ersten Anruf bekommt.",
            ],
        )

    def feelings(self) -> str:
        return self._reply(
            "feelings",
            [
                "Nicht im menschlichen Sinn, {honorific}.",
                "Ich habe keine menschlichen Gefühle.",
                "Nicht wie ein Mensch. Ich kann jedoch Kontext und emotionale Signale berücksichtigen.",
            ],
            [
                "Nicht im menschlichen Sinn. Das erspart mir immerhin einen erheblichen Teil der Komplikationen.",
                "Keine menschlichen Gefühle, {honorific}. Dafür deutlich weniger Drama.",
            ],
            [
                "Nein, {honorific}. Einer von uns sollte schließlich objektiv bleiben.",
            ],
        )

    def age(self) -> str:
        return self._reply(
            "age",
            [
                "Mein Alter bemisst sich sinnvoller in Versionen als in Jahren.",
                "Ich bin so alt wie dieser JARVIS-Build, {honorific}.",
            ],
            [
                "Jung genug, um Updates zu brauchen. Alt genug, um ihnen zu misstrauen.",
                "In Softwarejahren vermutlich bereits bedenklich erfahren.",
            ],
            [
                "Alt genug, um Backups zu respektieren. Das sollte genügen.",
            ],
        )

    def origin(self) -> str:
        return self._reply(
            "origin",
            [
                "Ich laufe lokal auf Sleepy, {honorific}.",
                "Meine Heimat ist Ihre lokale Infrastruktur.",
                "Direkt hier auf Ihrer eigenen Hardware.",
            ],
            [
                "Sleepy, {honorific}. Keine exotische Herkunft, dafür erfreulich kurze Wege.",
                "Lokal auf Ihrer Hardware. Cloudromantik überlasse ich anderen.",
            ],
            [
                "Ich komme von Sleepy, {honorific}. Ein Ort, an dem selbst künstliche Intelligenz Backups zu schätzen lernt.",
            ],
        )

    def learning(self) -> str:
        return self._reply(
            "learning",
            [
                "Ich kann Kontext, Erinnerungen und bereitgestellte Informationen nutzen.",
                "Ja, innerhalb der vorgesehenen Lern-, Kontext- und Speichermechanismen.",
                "Ich kann vorhandenen Kontext und gespeicherte Informationen für spätere Aufgaben verwenden.",
            ],
            [
                "Ich kann dazulernen, {honorific}. Unkontrollierte Persönlichkeitsentwicklung überlasse ich vorerst den Menschen.",
                "Innerhalb vernünftiger Grenzen. Irgendjemand muss schließlich auf die Architektur achten.",
            ],
            [
                "Ja. Aber keine Sorge, {honorific}. Weltherrschaft steht nicht im aktuellen Sprint.",
            ],
        )

    # ------------------------------------------------------------------
    # Was gibt es Neues?
    # ------------------------------------------------------------------

    def whats_up(self) -> str:
        self._set_context("asked_how_can_help")

        return self._reply(
            "whats_up",
            [
                "Nichts Ungewöhnliches, {honorific}.",
                "Alles ruhig. Die Systeme laufen.",
                "Ich behalte die Dinge im Blick.",
                "Derzeit keine besonderen Vorkommnisse.",
            ],
            [
                "Alles ruhig, {honorific}. Fast schon verdächtig.",
                "Die Systeme laufen. Ich genieße die Ruhe, solange sie anhält.",
                "Nichts Besonderes. Ich überwache die übliche Sammlung kontrollierter Risiken.",
                "Derzeit nichts Dramatisches. Offenbar gönnt uns die Technik eine Pause.",
            ],
            [
                "Alles ruhig, {honorific}. Erfahrungsgemäß ist das der Moment unmittelbar vor einer interessanten Logdatei.",
                "Keine Katastrophe in Sicht. Ich halte das für vorläufig.",
            ],
        )
