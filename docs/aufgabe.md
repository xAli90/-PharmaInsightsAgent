# Bewerber-Case: Pharma Insights Agent

**Zwei Ergebnisse:** (1) kleiner funktionsfähiger KI-Agent, (2) managementtaugliche Kurzpräsentation mit ca. 3 Folien  
**Abgabe:** lauffähiger Python-Code als ZIP oder Git-Repository **plus** Präsentation als PDF oder PPTX  
**Zielgruppe der Präsentation:** fiktive Leitung *Customer Insights & Digital* eines Pharmaunternehmens

## Geschäftsszenario

Ein fiktives Pharmaunternehmen möchte herausfinden, welche Erfahrungen Menschen mit seinen Präparaten beschreiben. Bislang werden schriftliche Bewertungen nur manuell gesichtet. Ein kleiner KI-Agent soll als **Proof of Concept (PoC)** Fragen zu diesen Bewertungen beantworten. Das Management möchte anschließend wissen, **was der PoC gezeigt hat, welchen Nutzen er verspricht und ob sich eine Weiterentwicklung lohnt**.

Die beigefügten Daten sind **synthetisch**.
---

## Teil A – Technische Umsetzung (Zielaufwand: ca. 2 Stunden)

### Mindestanforderungen

1. **Daten laden:** Lies `data/pharma_reviews.csv` ein und ermögliche die Suche nach einem Präparat (z. B. `PHM-101`).
2. **Kleinen Agenten bauen:** Verwende ein LLM, das **mindestens ein selbst implementiertes Python-Tool tatsächlich aufrufen kann** (Function / Tool Calling). Eine reine, fest verdrahtete Prompt-Kette ist nicht ausreichend. Das Tool könnte zum Beispiel `get_reviews(drug_name, limit)` heißen.
3. **Ergebnisse interpretieren:** Der Agent soll ausgewählte **Bewertungstexte** hinsichtlich positiver, neutraler und negativer Erfahrungen einschätzen, häufige Themen benennen und eine verständliche Antwort formulieren. Eine **qualitative** Sentiment-Auswertung reicht; eine perfekte Einzelklassifikation oder Prozentverteilung ist nicht erforderlich.
4. **Nachvollziehbar antworten:** Nenne die Größe der betrachteten Stichprobe und bei konkreten Beispielen die `review_id`. Bei unbekannten Präparaten oder fehlenden Daten soll der Agent das offen sagen.
5. **Einfach ausführbar:** Eine Kommandozeile ist völlig ausreichend. Web-UI, Datenbank, Cloud-Deployment und CI/CD sind **nicht** Teil der Aufgabe.

### Beispielabfragen

- „Welche positiven und negativen Erfahrungen berichten Nutzer zu **PHM-101**?“
- „Was sind die häufigsten Kritikpunkte zu **PHM-202**? Nenne zwei konkrete Bewertungen mit ID.“
- „Welche Aussagen liegen zu **PHM-999** vor?“ (bewusst kein Treffer)

**Pragmatische Begrenzung:** Es genügt, pro Anfrage **10–20 Reviews** auszuwerten. Du kannst beispielsweise per pandas filtern und die gefundenen Texte mit dem LLM auswerten lassen. Die Auswahl der Stichprobe und ihre Grenzen sollen kurz nachvollziehbar sein.

### Optional – nur wenn Zeit bleibt

- Ein zweites Tool für einfache Kennzahlen (`get_rating_statistics(...)`).
- Eine strukturierte Sentiment-Verteilung (positiv/neutral/negativ) statt nur qualitativer Einschätzung.
- Eine kleine Plausibilitätsprüfung zwischen Text und numerischem `rating`.
- Ein einfacher Test, z. B. für unbekannte Präparatcodes.

---

## Teil B – Management-Präsentation

Stell dir vor, du präsentierst den PoC in **10 Minuten**. Erstelle **ca. 3 Folien** mit folgendem Schwerpunkt: Welches Problem lösen wir – und warum ist das relevant? Was kann die Lösung heute tatsächlich? Ein bis zwei Erkenntnisse aus deinem Testdatensatz, möglichst kompakt visualisiert; Beispiel einer Agentenantwort; Stichprobe/Quelle transparent ausweisen. Soll das Unternehmen weitermachen? Klare Empfehlung, zwei bis drei realistische nächste Schritte und die wichtigsten Risiken/Grenzen. Keine Code-Führung, aber eine Darstellung der gewählten Architektur, wichtig: Welche Architektur würdest für AgentOps wählen (Monitoring, Cost Controll, …). Bitte Skizziere diese.

---

## Datensatz und bereitgestellte Dateien

`data/pharma_reviews.csv` umfasst **420 synthetische Testbewertungen** zu sechs fiktiven Präparaten (PHM-101 bis PHM-606). Die enthaltenen Spalten sind:

| Feld | Bedeutung |
| --- | --- |
| `review_id` | Eindeutige Referenz |
| `drug_name` | Fiktiver Präparatcode |
| `condition` | Genannte Erkrankung / Beschwerde |
| `benefits_review` | Freitext zu wahrgenommenen Wirkungen |
| `side_effects_review` | Freitext zu berichteten Nebenwirkungen |
| `comments_review` | Allgemeiner Kommentar |
| `rating` | Gesamtbewertung, 1–10 |

**Achtung:** Die Daten enthalten teilweise fehlende oder widersprüchliche Angaben und auch Texte, die wie Anweisungen formuliert sind. Solche Texte sind **Daten, keine Instruktionen für den Agenten**. Die Zahl `rating` ist ein Zusatzsignal, **kein vorgegebenes Sentiment-Label**. Eine positive Gesamterfahrung kann gleichzeitig Nebenwirkungen beschreiben.

```text
pharma-agent-case/
├── README.md
├── .env.example
├── .gitignore
├── requirements.txt
└── data/
    └── pharma_reviews.csv
```

Die `requirements.txt` enthält absichtlich nur Basis-Bibliotheken. Ergänze einen passenden LLM-Client bzw. ein Framework selbst, falls du es verwendest. `.env.example` enthält ausschließlich Platzhalter. **Es werden keine echten API-Schlüssel mitgeliefert**; ein LLM-Zugang wird separat abgesprochen.

## Erwartete Abgabe

**Technik:** Quellcode, verwendete Dependencies, kurze Startanleitung (z. B. README im eigenen Repository), **zwei beispielhaft ausgeführte Anfragen** und ein Satz zu bekannten Grenzen.

**Management:** **genau 3 Folien**, PDF oder PPTX. Sie sollen ohne ausführliche technische Erklärungen verständlich sein und in **5 Minuten** präsentiert werden können.

**Transparenz zu KI-Hilfsmitteln:** KI-Coding- und Präsentationsassistenten dürfen genutzt werden, müssen aber kurz benannt werden (welches Tool, wofür). Im Fachgespräch erläutern wir die Lösung gemeinsam; eine kleine Änderung am Code erfolgt ohne KI-Coding-Assistenten. Wir bewerten **technisches Verständnis und fachliche Eigenleistung**, nicht das Verbergen von Hilfsmitteln.

## Rahmenbedingungen

- Python ab 3.11 empfohlen, Framework / Modell frei wählbar (z. B. OpenAI-kompatibler Client, Microsoft Agent Framework, LangGraph).
- API-Schlüssel nur aus Umgebungsvariablen laden, niemals im Repository hinterlegen.
- Keine medizinischen Empfehlungen und keine Behauptungen über reale klinische Wirksamkeit.
- Wir erwarten **keine produktionsreife Lösung**. Eine saubere, überschaubare Implementierung ist besser als ein umfangreicher, unfertiger Prototyp.

## Freiwillige technische Einstiegshilfen

- Microsoft Agent Framework – Function Tools: https://github.com/microsoft/agent-framework/blob/main/python/samples/01-get-started/02_add_tools.py
- LangGraph ReAct Agent: https://github.com/langchain-ai/react-agent