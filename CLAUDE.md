# Pharma Insights Agent – Projektregeln

## Arbeitsweise
- Erst planen, dann bauen. Nichts bauen oder ändern ohne Freigabe.
- Das Decision Log `docs/decision-log.md` ist verbindlich. Neue oder geänderte
  Entscheidungen erst nach Zustimmung eintragen. Verworfene bleiben mit
  Verweis auf die Nachfolgerin stehen.
- Teil A in Issues nach D-58 (#1–#9), Teil B (#10) zum Schluss.
- Jedes Issue wird im PR geprüft, bevor das nächste beginnt.
- Die Hauptsitzung orchestriert und entwickelt nicht selbst (D-61): Sie plant,
  brieft die Agents, prüft deren Ergebnisse und stimmt sich ab. Suche geht an
  `scout`, Code an `implementer`, Reviews an `reviewer`.
- Ablauf eines Issues: `/issue <n>` (Issue lesen, Branch, Plan vorschlagen und
  stoppen, nach Freigabe bauen lassen, `/check`, Review bis keine P1/P2 offen,
  Bericht und stoppen). Prüfkette: `/check`.
- Das Issue ist das Briefing und gilt als Vertrag. Ist es falsch, korrigiert
  die Hauptsitzung es nach Rückfrage.
- Aussagen über die Daten vorher vollständig an der CSV prüfen
  (pandas, `encoding="utf-8-sig"`).

## Code
- Python, getestet mit 3.14 (D-55). Reiner `openai`-Client mit eigener
  Tool-Schleife, kein Framework (D-02).
- Code, Docstrings, Kommentare und Bezeichner auf Englisch. Texte, die Nutzer
  sehen (`SYSTEM_PROMPT`, Datenbasis, Warnhinweise), bleiben deutsch (D-60).
- Nur Pakete aus `requirements.txt` mit festen Versionen (D-44).
  Installation nur nach Freigabe.
- Schlicht und lesbar: Der Code soll sich ohne KI-Hilfe lesen und ändern
  lassen. Kurze Funktionen, sprechende Namen, ein Docstring je Funktion,
  kein toter Code, keine Abstraktion auf Vorrat.
- Der System-Prompt liegt als `SYSTEM_PROMPT` in `prompts.py` (D-23),
  Vorlage ist `docs/system-prompt-entwurf.md`. Der `implementer` übernimmt ihn
  wörtlich; danach macht der `reviewer` ein Prompt-Injection-Review.
- Geheimnisse nur aus Umgebungsvariablen. `.env` nie anlegen oder lesen,
  nur `.env.example` mit Platzhaltern (D-45).

## Tests
- `.venv/bin/pytest -m "not live"` ist nach jedem Issue grün (D-35).
- Der LLM-Client wird übergeben, im Test ersetzt ihn ein Fake (D-36).
- `@pytest.mark.live` läuft nur, wenn LM Studio unter `localhost:1234`
  erreichbar ist. Diese Tests prüfen IDs und Codes, keinen Wortlaut.

## Git und Issues
- Board ist der Issues-Tab des Repos.
- Je Issue ein Branch `issue/<n>-<name>` und ein PR mit „Closes #n“,
  Squash-Merge durch den Repo-Owner (D-59). Nie auf `main` arbeiten.
- Commit-Nachrichten, Branch-Namen, PR-Titel und -Beschreibung auf Englisch
  (D-60). Commits mit `#<n>`, ohne Attribution-Trailer
  (kein `Co-Authored-By`, keine „Generated with“-Zeile, D-61).
- Commit nur auf ein ausdrückliches „commit“. Zustimmung zum Plan oder
  „umsetzen“ zählen nicht. Push und PR ebenso nur auf Anweisung.
- PR-Beschreibung nennt: `/check` grün, Review-Funde behandelt (offene P3
  genannt), ab #8 ein Satz zum Live-Nachweis. Ebenfalls ohne Attribution.

## Agents (`.claude/agents/`)
- `scout`: liest und prüft Fakten, ändert nichts.
- `reviewer`: adversariales Review mit Stufen P1–P3, je Aufruf ein Review mit einem Thema,
  ändert nichts.
- `implementer`: baut ein Issue nach Briefing und Log. Committet, pusht und
  wechselt Branches nie.
- Commands (`.claude/commands/`): `/issue`, `/check`. Permissions:
  `.claude/settings.json`.
