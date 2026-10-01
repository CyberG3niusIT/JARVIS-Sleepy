# Installation und Betrieb

## Repository-Einstieg

Die maßgebliche Installation ist durch `docs/SETUP_GUIDE.md`, `start.sh`, GPU-/Chatterbox-Startskripte, Health-/Statusskripte und Systemd-Units beschrieben. Diese älteren Anleitungen wurden nicht als universell aktuelle Installationsfreigabe übernommen; Hardware-, Pfad- und Paketdetails gegen das Zielsystem validieren.

## Betriebsartefakte

Im Repo vorhanden sind `jarvis.service`, `systemd/`, mehrere `.service`-Dateien sowie `start.sh`, `restart.sh`, `stop.sh`, `status.sh` und `startup_checks.sh`. Units/Scriptinhalt ist Versionsstand, kein Beweis installierter oder gestarteter Services.

## Safe operation

1. Git-Root `Main` identifizieren.
2. Nur `.env.example` und öffentliche Config-Struktur lesen; Secrets lokal halten.
3. Python-Umgebung und Modellabhängigkeiten gemäß gepflegtem Setup prüfen.
4. zuerst Config/Health-Checks, dann Console/Textpfad, anschließend STT/TTS- und externe Dienste getrennt prüfen.
5. Live- und synthetische Tests getrennt protokollieren.

Konkrete private Hostpfade und Runtime-Daten werden bewusst nicht als kanonische Setupwerte gespiegelt.
