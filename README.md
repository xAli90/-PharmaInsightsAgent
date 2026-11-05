# Pharma Insights Agent

## Zweck

Proof of Concept: ein Agent für die Kommandozeile, der Fragen zu Patienten-Reviews
fiktiver Präparate (`data/pharma_reviews.csv`) beantwortet. Ein lokales LLM ruft dazu
selbst implementierte Python-Tools auf. Der Agent gibt wieder, was Patienten berichten;
er gibt keinen medizinischen Rat und macht keine Aussagen über reale klinische
Wirksamkeit.

## Voraussetzungen

- Python ab 3.11 (getestet mit 3.11 und 3.14).
- [LM Studio](https://lmstudio.ai) mit dem Modell `Qwen3.8-27B-MLX-4bit` (in LM Studio
  `qwen/qwen3.8-27b`) und gestartetem lokalem Server. MLX läuft nur auf Apple Silicon.
- Andere OpenAI-kompatible Endpunkte oder Modelle werden über `.env` eingetragen.

## Installation und Konfiguration

```sh
git clone https://github.com/xAli90/-PharmaInsightsAgent.git
cd ./-PharmaInsightsAgent
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Die Einstellungen kommen aus Umgebungsvariablen oder aus `.env`; eine gesetzte
Umgebungsvariable hat Vorrang vor `.env`, auch wenn sie leer ist. Ein leerer Wert gilt
als nicht gesetzt.

| Variable | Standard | Bedeutung |
| --- | --- | --- |
| `OPENAI_BASE_URL` | `http://localhost:1234/v1` | OpenAI-kompatibler Endpunkt (LM Studio lokal) |
| `OPENAI_API_KEY` | `lm-studio` | API-Schlüssel; LM Studio akzeptiert jeden Wert |
| `OPENAI_MODEL` | – (Pflicht) | Modellname, wie ihn der Endpunkt nennt |
| `AGENT_MAX_ROUNDS` | `3` | höchstens so viele Modellaufrufe pro Frage, ganze Zahl ab 2 |
| `LLM_REASONING_EFFORT` | `low` | wird als `reasoning_effort` an das Modell geschickt |

Ist in LM Studio die Authentifizierung eingeschaltet, gehört das API-Token in
`OPENAI_API_KEY`. Schlüssel stehen nur in der Umgebung oder in `.env`; `.env` ist per
`.gitignore` vom Repository ausgeschlossen.

## Start und Tests

```sh
.venv/bin/python main.py "Welche positiven und negativen Erfahrungen berichten Nutzer zu PHM-101?"
.venv/bin/python main.py          # interaktiver Modus
.venv/bin/python main.py -v "…"   # mit Angaben pro Runde
```

- Ohne Frage startet ein interaktiver Modus mit dem Prompt `Frage>`; Ende mit `exit`
  oder Strg+D. Jede Frage beginnt neu, ohne Verlauf.
- Die Antwort mit Datenbasis und Warnhinweisen steht auf stdout. Prompt, Fehler und die
  Ausgabe von `-v` (pro Runde Tools mit Argumenten, Tokens ein/aus und Dauer, am Ende
  eine Gesamtzeile) stehen auf stderr.
- Exit-Codes: `0`, sobald das Modell antwortet, auch bei unbekanntem Präparat; `1` bei
  Abbruch durch den Code (z. B. `OPENAI_MODEL` fehlt, `AGENT_MAX_ROUNDS` ungültig,
  Modell nicht erreichbar, leere Antwort, Daten nicht ladbar); `2` bei falschen
  Argumenten; `130` bei Strg+C. Im interaktiven Modus beendet ein Abbruch während einer
  Frage nur diese Frage; die Sitzung endet mit `0`.

Tests:

```sh
.venv/bin/pytest -m "not live"   # ohne Modell
.venv/bin/pytest -m live         # braucht ein erreichbares LM Studio, sonst übersprungen
```

Die Live-Tests prüfen IDs und Präparat-Codes, keinen Wortlaut.

## Beispiele

- [„Welche positiven und negativen Erfahrungen berichten Nutzer zu **PHM-101**?“](examples/phm-101.txt)
- [„Was sind die häufigsten Kritikpunkte zu **PHM-202**? Nenne zwei konkrete Bewertungen mit ID.“](examples/phm-202.txt)
- [„Welche Aussagen liegen zu **PHM-999** vor?“](examples/phm-999.txt) (bewusst kein Treffer)

Die Dateien stammen aus echten Läufen mit `-v`, unbearbeitet; die erste Zeile nennt den
Befehl.

## Architektur kurz

Frage → Agenten-Schleife → Nachbearbeitung der Antwort. Der Agent nutzt den reinen
`openai`-Client mit eigener Tool-Schleife, ohne Framework.

- Die Schleife ruft das Modell höchstens `AGENT_MAX_ROUNDS`-mal auf (Standard 3); der
  letzte Aufruf geht ohne Tools, damit das Modell antworten muss. Zwei Tools:
  - `get_reviews(drug)`: geschichtete Stichprobe von 12 Reviews eines Präparats, je 4
    mit Rating 1–4, 5–6 und 7–10, mit festem Seed.
  - `get_rating_statistics(drug?)`: Anzahl, Verteilung auf die drei Rating-Bänder,
    Durchschnitt und Beschwerden über alle Reviews, für ein oder alle Präparate.
  - Beide normalisieren den Präparat-Code und melden bei unbekanntem Code die bekannten.
- Review-Texte erreichen das Modell als Daten: als JSON im Rahmen `<daten>` … `</daten>`
  in der Rolle `tool`, spitze Klammern maskiert, dazu eine Regel im System-Prompt
  (Schutz gegen Prompt Injection).
- Die Nachbearbeitung entfernt Fettdruck, hängt die Datenbasis an (pro Präparat
  Statistik und abgerufene IDs) und warnt, wenn die Antwort eine nie abgerufene
  `review_id` oder gar keine nennt, obwohl Reviews abgerufen wurden.

Projektaufbau:

```text
main.py              Kommandozeile, Konfiguration, Ausgabe und Exit-Codes
agent.py             Agenten-Schleife mit Rundenlimit
tools.py             die beiden Tools und ihr Schema
data.py              CSV laden, Präparat-Code normalisieren, Stichprobe ziehen
prompts.py           System-Prompt und Daten-Rahmen für Tool-Ergebnisse
answer.py            Nachbearbeitung: Fettdruck, Datenbasis, Warnhinweise
data/                der Datensatz pharma_reviews.csv
tests/               Tests ohne Modell und Live-Tests (Marker live)
docs/                Aufgabe, Decision Log, Prompt-Entwurf, Kontrolllauf
examples/            die drei Beispielläufe
requirements.txt     Pakete mit festen Versionen
.env.example         Vorlage für .env mit Platzhaltern
pytest.ini           Testpfad, pythonpath und Marker live
CLAUDE.md, .claude/  Projektregeln, Agenten und Befehle für Claude Code
```

## Grenzen

Der PoC wertet pro Frage eine Stichprobe von 12 Reviews (je 4 mit niedrigem, mittlerem
und hohem Rating) qualitativ mit einem lokalen LLM aus, ohne Abgleich mit gelabelten
Daten. Er merkt sich keine früheren Fragen. Der Datensatz ist fiktiv und klein: 420
Reviews aus wenigen Textbausteinen.

Die Zeilen, die der Code anhängt (Datenbasis, Warnhinweise), bleiben deutsch, auch bei
englischen Fragen. In den drei Beispielläufen dauerte eine Antwort mit dem 27B-Modell
auf einem Apple-Silicon-Rechner zwischen 9,1 und 56,5 Sekunden.

## KI-Hilfsmittel

Claude Code habe ich für Planung, Review, Code, Tests und Entwürfe von README und Folien
genutzt.

## Entscheidungen

Alle Entscheidungen mit Begründung stehen im [Decision Log](docs/decision-log.md). Die
ursprüngliche Aufgabenstellung liegt in [`docs/aufgabe.md`](docs/aufgabe.md), der
Kontrolllauf zur Prompt Injection in
[`docs/injection-kontrolllauf.md`](docs/injection-kontrolllauf.md).
