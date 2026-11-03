---
description: Eine Scheibe (Issue) von Teil A planen, delegiert bauen lassen, prüfen und berichten
argument-hint: <issue-nummer>
---

Bearbeite die Scheibe aus Issue #$ARGUMENTS. Die Hauptsitzung orchestriert: Sie plant,
brieft die Agents, prüft deren Ergebnisse und stimmt sich ab. Code schreibt der
`implementer`.

Alle `gh`-Aufrufe mit `-R xAli90/-PharmaInsightsAgent`.

1. **Issue lesen:** `gh issue view $ARGUMENTS`. Das Issue ist das Briefing: Ziel,
   Umfang, Nicht im Umfang, Prüfung, Fertig, wenn. Lies die genannten Einträge im
   Decision Log `docs/decision-log.md`.
2. **Vorgänger prüfen:** Ist die vorige Scheibe nach D-58 nicht geschlossen
   (`gh issue view <n-1> --json state`), frage nach, bevor du weitermachst. Entfällt
   bei #1.
3. **Branch:** Keine uncommitteten Änderungen an getrackten Dateien. `git fetch`, dann
   `git switch -c slice/$ARGUMENTS-<name> origin/main` (D-59). Nie auf `main` arbeiten.
   Nur bei #1, nach Freigabe, als Vorlauf der Hauptsitzung: `README.md` nach
   `docs/aufgabe.md` verschieben (D-40), `git init`, `git remote add origin
   https://github.com/xAli90/-PharmaInsightsAgent.git`, `git fetch`, dann der Branch
   wie oben. Kein lokaler Commit auf `main`.
4. **Lesen vor dem Planen:** `scout` liest die betroffenen Stellen und prüft jede
   Aussage des Issues gegen Log, Daten und Code. Abweichungen benennen.
5. **Plan vorschlagen und stoppen:** Dateien, Funktionen, Tests, was nicht dazugehört.
   Bei Zweifeln den Plan vorher vom `reviewer` widerlegen lassen. Dann auf die
   Freigabe warten. Ist das Issue falsch, korrigiert die Hauptsitzung es nach
   Rückfrage (`gh issue edit`); es gilt als Vertrag.
6. **Bauen lassen:** Nach der Freigabe brieft die Hauptsitzung den `implementer` mit
   Ziel, Umfang, Plan, betroffenen Log-Einträgen und Tests. Große Scheiben in mehrere
   Aufträge teilen.
7. **Prüfen:** `/check`. Rot geht mit der echten Ausgabe an den `implementer` zurück.
8. **Review:** Erst `git add -A` (Staging, kein Commit), damit neue Dateien im Diff
   stehen; vorher mit `git status --short` prüfen, dass `.gitignore` `.venv/` und
   `.env` ausschließt. Dann `reviewer` auf `git diff --cached origin/main`, eine Linse je Aufruf,
   z. B. Anforderungen, Daten, Prompt Injection, Lesbarkeit. Funde P1 und P2 gehen an
   den `implementer`, danach erneut `/check` und Review, bis keine P1/P2 offen sind.
9. **Bericht und stoppen:** was gebaut wurde, Ausgabe von `/check`, Review-Funde und
   wie sie behandelt wurden, offene P3, ab #8 der Live-Nachweis. Kein Commit, kein
   Push, kein PR ohne ausdrückliche Anweisung.
