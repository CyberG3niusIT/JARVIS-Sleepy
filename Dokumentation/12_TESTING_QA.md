# Testing und QA

## Teststruktur

`tests/unit/`, `tests/integration/`, `tests/routing/` und `tests/components/` enthalten getrennte Testbereiche. Mobile hat einen eigenen Android-Test-/Buildpfad im separaten Repository. Kein Test wurde für diese Dokumentationsarbeit ausgeführt.

## Aussagekraft

Unit-Tests mit Fakes/Fixtures belegen Logik unter Testbedingungen, keine Erreichbarkeit externer Dienste, Modellqualität, Hardwareleistung oder reale Datenkorrektheit. Live-Abnahme braucht getrennte Evidenz mit Zeit, Build/HEAD, Dienstgesundheit, Eingabequelle und Resultat.

## School/Mobility

Im Arbeitsbaum liegen neue Testmodule für Contract, Planner, DB, Flow, Skill-Loading und Reiseevents. Auftraggeberseitig wurde zuletzt ein Umfang von 600 Unit-Tests genannt; hier nicht erneut verifiziert. 65-Minuten-DORMANT-Soak und Canary-Angaben sind in [08](08_SCHOOL_MOBILITY.md) als berichtet markiert.

## Voice

Neue Vocal-Direction- und Runtime-Check-Tests liegen uncommittet. Ein erfolgreicher Unit-Test wäre keine hörbasierte Produktfreigabe und kein Nachweis GPU-fähiger Chatterbox-Turbo-Ausführung.

## Modell-/Voice-Umbau (25.09.2026)

Neue Testdateien: `test_turn_assembler`, `test_direct_audio_routing`, `test_speculative_audio_side_effects`, `test_model_handover`, `test_expert_delegation`, `test_vision_gate`, `test_expert_handover_integration`, `test_stop_fastpath_integration`. Sie arbeiten mit Fakes (u. a. Fake-`systemctl`, Fake-LLM) und belegen Logik, keine Hardware-Funktion.

Ausführung (WSL Ubuntu-24.04, venv):

```
wsl.exe -d Ubuntu-24.04 -- /home/alex/jarvis-venv/bin/python3 -m pytest <Testdatei>
```

Es wird **keine** Aussage über eine vollständige Suite gemacht; nur die genannten Dateien wurden gezielt betrachtet. Nicht getestet auf Hardware: Direct-Audio mit Gemma, Handover mit echtem systemd, NPU-Live-Kamera.
