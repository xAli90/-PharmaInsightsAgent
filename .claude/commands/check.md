---
description: Prüfkette ausführen und ehrlich berichten, ohne etwas zu beheben
argument-hint: "[live]"
---

Führe die Prüfkette aus und berichte. Behebe nichts ungefragt und melde nie einen
Schritt als grün, der nicht gelaufen ist.

1. `.venv/bin/pytest -m "not live"` – muss grün sein (D-35).
2. Nur wenn `$ARGUMENTS` `live` enthält: Ist LM Studio unter `localhost:1234`
   erreichbar (`curl -s localhost:1234/v1/models`), dann `.venv/bin/pytest -m live`.
   Sonst als „nicht gelaufen, LM Studio nicht erreichbar“ melden.
3. `git status --short`: keine `.env`, keine Caches, keine fremden Dateien im
   Arbeitsbaum.

Bericht: je Schritt grün, rot oder nicht gelaufen. Bei Rot die echte Ausgabe der
fehlgeschlagenen Tests, gekürzt auf das Wesentliche.
