# Hintergrund

Die Idee zum Spiel stammt aus der [Masterarbeit](./../master_thesis.pdf) von Sebastian Werblinski.
Der Code hier ist eine vollständige Neuentwicklung und keine Fortsetzung seines Prototyps; das
Verkehrsmodell ist dabei neu gebaut worden. Dieser Abschnitt sagt, was es tut und woher seine Zahlen
kommen.

## Simulation

Eine Runde hat eine einzige Frage zu beantworten. Ein paar tausend Menschen wollen ungefähr zur
selben Zeit bei der Arbeit sein, jeder von ihnen unterwegs so, wie ein Spieler es entschieden hat —
was kostet dieser Morgen, und wie lange dauert er?

Stau muss dabei als **Ergebnis** herauskommen. Setzte das Modell ihn voraus, ginge die Abstimmung
zwischen den Runden um nichts: Die Klasse ändert die Karte, und die Karte muss antworten.

## Welches Modell, und warum dieses

Verkehr lässt sich auf drei Ebenen simulieren.

- **Makroskopisch** — Flussgleichungen über das Netz, keine einzelnen Fahrzeuge. Billig, aber es
  sitzt niemand darin, und in diesem Spiel geht es um einen Menschen, der ein Verkehrsmittel wählt.
- **Mikroskopisch** — Folgeverhalten, Spurwechsel, Beschleunigung, je Fahrzeug. Jeder Parameter
  braucht Daten, die für eine von Hand gezeichnete Spielkarte niemand hat, und es wird nicht fertig,
  während eine Klasse darauf wartet.
- **Mesoskopisch** — einzelne Fahrzeuge, aber eine Straße ist eine Warteschlange und kein
  Streckenabschnitt mit Positionen darauf.

co2mmute ist das dritte. Genauer: ein **Link-Queue-Modell**, dieselbe Familie, die MATSim benutzt —
die Arbeitslinie von Kai Nagel, am selben Institut. Diese Herkunft ist der Grund, es einer von Hand
angepassten BPR-Kurve vorzuziehen: Es ist ein veröffentlichtes Modell, das jemand nachschlagen und
bestreiten kann, keine Formel, an der so lange gedreht wurde, bis das Ergebnis plausibel aussah.

### Eine Kante sind drei Zahlen

```
Freiflusszeit      t0 = Länge / Tempolimit
Abflusskapazität   Q  = 1.800 Fahrzeuge/h je Autospur
Speicherkapazität  S  = 133 Fahrzeuge/km je Autospur × Länge
```

1.800 Fz/h und Spur ist die Sättigungsverkehrsstärke einer städtischen Spur, der Standardwert aus
HCM und HBS. 133 Fz/km und Spur ist die Dichte im Stillstand: ein Fahrzeug je 7,5 m, Stoßstange an
Stoßstange. Eine 900 m lange einspurige Straße fasst also rund 120 stehende Fahrzeuge und lässt in
einem Fünf-Minuten-Tick rund 150 durch.

Spuren werden gezählt, wie sie auf der Straße liegen, und Infrastruktur nimmt sich davon:

```
Autospuren = Spuren − (1 bei Busspur) − (1 bei Radspur)
```

nach unten auf null begrenzt. **Null Autospuren ist erlaubt**: Die Straße wird zur _Busschleuse_ —
für Autos gesperrt, offen für Busse, Räder und Fußgänger. Das ist die ganze Antwort des Modells auf
„was macht eine Busspur“ — es bremst Autos nicht über einen Strafterm, es nimmt ihnen eine Spur, und
der Rückstau dahinter ergibt sich von selbst.

### Ein Tick

1. Jede Kante bekommt ihr Budget für den Tick: `Q × Ticklänge`.
2. Alle, deren Abfahrtsminute gekommen ist, versuchen auf ihre erste Kante zu kommen.
3. Ein Fahrzeug darf eine Kante nicht vor Ablauf von `t0` verlassen. Die Freiflusszeit ist die
   Untergrenze der Fahrt; schneller als das Tempolimit geht nie.
4. Danach reiht es sich in die FIFO-Schlange der Kante ein und wartet auf Budget.
5. Weiter darf es nur, wenn die **nächste** Kante noch Speicher frei hat. Wenn nicht, bleibt es
   stehen, und alles dahinter auch. Das ist der Rückstau.
6. Innerhalb des Ticks wiederholen, bis sich nichts mehr bewegt — ein Fahrzeug schafft in fünf
   Minuten mehrere kurze Kanten.

Stau ist damit zwei Mechanismen und keine Formel: Eine Kante lässt nur `Q` pro Stunde ab, und eine
volle Kante hält die auf, die sie speist. Schlangen wachsen rückwärts durch das Netz, so wie auf der
Straße.

### Rechnerisch kann sich nichts verklemmen, also gibt es keine Mindestgeschwindigkeit

Ein Modell vom BPR-Typ rechnet eine Geschwindigkeit aus dem Verhältnis von Belastung zu Kapazität
und muss deshalb daran gehindert werden, null zu erreichen — sonst teilt die ganze Runde dadurch.
Ein Warteschlangenmodell hat diesen Term nicht. Ein Fahrzeug wird freigegeben oder nicht, und auf
der Eingabeseite steht nirgends eine Geschwindigkeit.

Der Preis dafür ist, dass es sich wirklich verklemmen kann: ein Ring aus Kanten, jede voll mit
Fahrzeugen, die auf die nächste wollen. Ein Knoten, der vier Ticks hintereinander nichts bewegt hat,
gibt trotzdem frei, über die Speichergrenze hinweg, und die Freigabe wird gezählt. Ein
`forced_releases` über null im Tick-Log ist kein Fehler, aber ein Grund, das Log zu lesen.

### Geschwindigkeit ist ein Ergebnis

Das ist der Unterschied, auf den es beim Lesen eines Ergebnisses am meisten ankommt. Die mittlere
Geschwindigkeit einer Kante ist ihre Länge geteilt durch die **tatsächlich auf ihr beobachteten**
Fahrzeiten, und zwar nur über Autos — ein Fußgänger braucht zehn Minuten für eine Kante, die ein
Auto in einer überquert, und ließe man ihn in den Mittelwert, meldete eine leere Straße Stau.
Nirgends wird eine Freiflussgeschwindigkeit mit einem Stau-Faktor multipliziert.

Die Geschwindigkeit auf der Karte, der CO₂-Faktor einer Fahrt und die Routenvorschau, die ein
Spieler in der nächsten Runde bekommt, lesen also alle dieselbe gemessene Zahl.

### Wer sich anstellt

- **Autos** immer.
- **Busse** stehen im Mischverkehr und fahren auf einer eigenen Busspur frei. Ein Bus zählt 3
  Pkw-Einheiten, nimmt in der gemeinsamen Schlange also den Platz von drei Autos ein.
- **Räder** stehen nur dort im Verkehr, wo sie sich die Straße mit Autos teilen. Ein Rad hat auf der
  Kante eine eigene Linie: ein eigenes Abflussbudget von 2.000 Rädern/h, damit ein Autostau nie
  einen Radfahrer aufhält und ein Radfahrer nie einen Autofahrer — aber es teilt sich den _Speicher_
  der Kante, mit 0,2 Pkw-Einheiten, und genau so nehmen tausend Radfahrer den Autos Platz weg.
  Abgewiesen wird ein Rad nie; eine volle Straße schickt keinen Radfahrer zurück.
- **Fußgänger** stehen ganz außerhalb des Warteschlangenmodells.

### Der ÖPNV fährt einen Fahrplan

Die strukturelle Idee ist, dass ein Linienfahrzeug ein **ganz normales Fahrzeug auf einer
künstlichen Route** ist. Ein Bus steht deshalb in der Schlange, staut zurück, wiegt 3 Pkw-Einheiten
und fährt durch eine Busschleuse, ohne eine einzige eigene Codezeile.

Und es steigen wirklich Leute ein. Gruppen warten an einer Haltestelle, die nach Linie _und_
Knoten unterschieden wird — wer auf die M1 wartet, steigt nicht in die U7 —, steigen bis zur freien
Kapazität ein, steigen dort aus, wo ihre Route die Linie verlässt, und warten beim Umsteigen erneut.
Die Wartezeit wird gemessen und **ausgewiesen, nicht addiert**: Die Uhr läuft seit der Minute, in
der die Person losfahren wollte, das Stehen an der Haltestelle steckt also schon in der Fahrzeit.
Haltezeiten sind nicht modelliert; ein Fahrzeug bedient seine Haltestelle in dem Augenblick, in dem
es ankommt.

Eine Linie fährt, ob jemand mitfährt oder nicht, und genau darum wird sie überhaupt modelliert:

> **Die Gesellschaft bezahlt den Fahrplan.** Eine Linie stößt `Fahrzeuge × Linienkilometer × Faktor`
> aus, nie geteilt durch Sitzplätze. Ein leerer Bus ist nicht sauber, und eine Linie, die niemand
> benutzt hat, kostet die Runde trotzdem.

Der persönliche Anteil daran ist die Summe der Gesellschaft, gewichtet nach **Personenkilometern**,
und nicht pro Kopf geteilt — auf einer 13 km langen Linie darf wer eine Station fährt nicht den
Anteil einer ganzen Fahrt tragen, während das Auto daneben nach Kilometern abgerechnet wird. So
gewichtet gilt `Σ persönlich = Gesellschaft` exakt.

Die Folge, die ein Bildschirm benennen muss: Die Summe einer Runde sind die Zeilen der Spieler
**plus** die Gesellschaftskosten der Linien, die niemand benutzt hat.

## CO₂ und Kosten hängen an einer Geschwindigkeitskurve

Emissionen sind kein fester Wert pro Kilometer. Ein Auto im Stop-and-go verbrennt Kraftstoff, den es
nicht in Strecke umsetzt, und ein Auto bei 130 km/h kämpft gegen den Luftwiderstand. Das Modell
benutzt einen geschwindigkeitsabhängigen Emissionsfaktor der COPERT/HBEFA-Form:

```
EF(v) = a/v + b + c·v²          Gramm CO₂ pro Fahrzeugkilometer
```

`a/v` ist Leerlauf und Stop-and-go, ein fester Verbrauch, verteilt auf weniger Kilometer; `c·v²` ist
der Luftwiderstand; `b` ist alles, was allein mit der Strecke skaliert. `a` und `b` sind **keine
freien Parameter** — sie folgen aus `c` und zwei Bedingungen:

```
1.  das Minimum der Kurve liegt bei 70 km/h  →  a = 2c · v_min³           = 1962,3 g/h
2.  EF(50) = 166,8 g/km, der Autofaktor      →  b = 166,8 − a/50 − c·50²  = 120,4 g/km
```

mit `c = 0,0028605`. So festgelegt gilt der Ankerwert bei 50 km/h als Identität und nicht auf vier
Nachkommastellen, und es gibt eine Zahl zu diskutieren statt drei.

| km/h        | 10   | 20   | 30   | 40   | 50    | 70    | 100  |
| ----------- | ---- | ---- | ---- | ---- | ----- | ----- | ---- |
| g CO₂/km    | 317  | 220  | 188  | 174  | 166,8 | 162,5 | 169  |
| × Basiswert | 1,90 | 1,32 | 1,13 | 1,04 | 1,00  | 0,97  | 1,01 |

`a/v` divergiert, wenn die Geschwindigkeit gegen null geht, deshalb ist **der Faktor bei 2,00×
gedeckelt** und nicht die Geschwindigkeit nach unten begrenzt. Ein Deckel ist eine Zahl, die eine
Klasse im Kopf behalten kann — „schlimmstenfalls doppelt so schlecht“ — und er hält den
divergierenden Term aus der Rechnung heraus. Er greift unterhalb von 9,2 km/h.

Zwei Folgen, die überraschen:

- **Eine Tempo-30-Straße stößt pro Kilometer rund 13 % mehr aus als eine 50er, auch leer.** Das ist
  in jedem geschwindigkeitsabhängigen Modell so, und 34 der 82 Straßenkanten der ausgelieferten
  Karte sind 30er-Zonen — es verschiebt also den Boden einer echten Runde.
- **Die Kosten hängen mit halbem Gewicht an derselben Kurve.** Die Hälfte der 0,32 €/km ist
  Kraftstoff und Verschleiß im Stop-and-go und folgt dem Emissionsfaktor; die andere Hälfte —
  Abschreibung, Versicherung, Steuer — fällt an, ob das Auto heute fährt oder nicht. Geld ist
  deshalb bei 1,50× gedeckelt, wo CO₂ bei 2,00× gedeckelt ist.

Der ÖPNV liegt flach bei den Fahrzeugkilometern: 1.200 g für einen Bus, 1.500 g für einen Zug. Auf
dieser Seite gibt es keine Geschwindigkeitskurve, weil das Fahrzeug nach Fahrplan fährt und nicht
nach Verkehrslage.

Neben den Kosten steht der **Fahrpreis**: 1,30 € pro Fahrt, Umstiege eingeschlossen, und beim Auto
der Teil der Kosten, den man aus der eigenen Tasche zahlt. _Was du zahlst_ neben _was es kostet_ ist
auf beiden Seiten derselbe Gegensatz, und der Abstand dazwischen ist beim ÖPNV die Subvention.

### Die Runde ist stochastisch, mit festem Seed

Dieselben Entscheidungen zweimal ergeben nicht ganz dieselbe Zahl, und das sollen sie auch nicht.
Jede Runde zieht aus einem Generator, der aus der Runde geseedet ist, also läuft eine Runde immer
identisch nach — im Test, im Debugger oder nach einem Worker-Neustart.

Es gibt genau zwei Stellschrauben:

- **Die Kapazität einer Kante, einmal je Kante und Runde gezogen** (σ = 0,14, begrenzt auf
  0,6–1,4×). Nur sie sorgt dafür, dass sich Runde 2 von Runde 1 unterscheidet, weil sich Rauschen
  pro Fahrer über tausende Menschen herausmittelt.
- **Die Wunschgeschwindigkeit, einmal je Fahrer gezogen** (σ = 0,12, begrenzt auf 0,7–1,4×), für die
  Streuung _innerhalb_ einer Runde. Auf einer mehrspurigen Straße ist die Schlange danach geordnet,
  wann ein Fahrzeug bereit ist, und nicht streng nach dem Eintreffen — das ist Überholen, ohne einen
  eigenen Mechanismus dafür.

Nirgends wird das _Ergebnis_ mit einer Zufallszahl multipliziert. Die Eingaben wackeln, und die
Nichtlinearität des Modells nahe der Kapazität verstärkt das — deshalb hat die Streuung die richtige
Form: rund 0,3 % Variationskoeffizient im freien Fluss, 16–18 % unter Last. Ein Stau ist
unvorhersehbar, eine leere Straße nicht.

Eine Einzelheit lohnt sich beim Lesen einer Verspätung: **Verspätung wird gegen die Freiflusszeit
des Fahrers selbst gemessen.** Wer in einer 50er-Zone 45 gewählt hat, ist durch nichts verspätet.

### Einheiten

Ein Agent — in der Oberfläche eine _Gruppe_ — steht für `people_per_agent` echte Pendler, und aus
diesem Faktor stammen die meisten Einheitenfehler dieses Projekts. Zwei Regeln:

- Eine CO₂- oder Euro-Zahl ist **extensiv**: Sie summiert über Gruppen und über die Menschen
  hinter jeder Gruppe. Pro Person heißt: durch beides teilen.
- Die Fahrzeit ist es **nicht**. Eine Summe von Fahrzeiten ist keine Größe, die irgendwem gehört,
  also ist eine mittlere Fahrzeit ein Mittel über die Fahrten der Gruppen und sonst nichts.

Der Faktor selbst ist keine Einstellung, die jemand wählt. Siehe unten.

### Kalibrierung

Die Physik war nicht der Teil, über den entschieden werden musste. 1.800 Fz/h und Spur und 133 Fz/km
und Spur sind Messwerte, die jemand anders erhoben hat, und die Form der Emissionskurve folgt aus
ihren zwei Ankerbedingungen. **Gewählt** werden musste alles, was sagt, wie groß die Welt ist: wie
viele Menschen auf dieser Karte unterwegs sind, was eine Runde kosten darf und was ein Fahrzeug
ausstößt.

Diese Entscheidungen sind die Kalibrierung, und die Methode war bei allen dieselbe.

### Die Methode

Kein Play-Test. Eine fertige Runde lässt sich mit festem Seed unter dem Simulator nachspielen, ohne
dass dabei etwas geschrieben wird. Ein Kandidatenwert wird also über die ausgelieferte Karte
gefahren und als Folgen gelesen — mittlere Fahrzeit, mittlere Verspätung, CO₂ nach Modalsplit — und
dann gegen etwas außerhalb des Spiels gehalten.

Wo es einen Anker draußen gibt, entscheidet er. Wo es keinen gibt, wird die Zahl danach gewählt, was
sie mit einer Runde macht, und das wird ausgesprochen statt als Messung verkleidet.

### Zwei Zahlen gehören zur Karte, nicht zum Code

`district_commuters` und `co2_budget_kg_per_round` stehen an der Karte, nicht in einer
Konstantendatei. Beides sind Eigenschaften _dieses Graphen_: wie viel Verkehr seine Achsen tragen,
und was eine spielbare Runde auf seinen Entfernungen und mit seinem Fahrplan kostet. Eine andere
Stadt ist ein anderes Paar, und als Konstante im Code hätten die Messwerte eines Stadtteils eine
Eigenschaft der Software festgeschrieben. Beide gehen mit dem JSON-Export der Karte mit und kommen
beim Import zurück.

Für Berlin Mitte-West sind es **6.400 Pendler** und **8.000 kg pro Runde**.

### 6.400 ist, was der Graph verkraftet

Nicht, was der Stadtteil hat — Berlin Mitte-West hat weit mehr Pendler. Aber der Graph abstrahiert
den Stadtteil auf seine Hauptachsen, also ist die Zahl, die er tragen kann, die Zahl, die **diese
Achsen** tragen.

Bei 6.400 und 100 % Autoanteil laufen die meistbelasteten Kanten auf etwa 115 % ihrer
Abflusskapazität, und 7,66 km Arbeitsweg dauern 20,4 statt 9,5 Minuten im freien Fluss. Der
Berufsverkehr in der Berliner Innenstadt läuft mit rund 24 km/h — das sind dieselben elf Minuten
Verspätung. Das ist der Anker draußen: Die Zahl hängt an einer gemessenen Stadt, nicht am
Spielgefühl.

Was sie ersetzt hat, ist es wert, genannt zu werden, weil es zeigt, wie unkalibriert aussieht.
Ausgeliefert wurden 1.000 Menschen pro Gruppe, für eine volle Klasse also 64.000 Autos auf einer
Karte mit 82 Straßenkanten. Das Modell hat es verkraftet — kein Gridlock, keine erzwungenen
Freigaben, alle kamen an — und meldete eine **mittlere Fahrzeit von 298 Minuten für 7,66 km**. Fünf
Stunden. Damit die Karte diesen Verkehr aufnehmen könnte, bräuchte sie ungefähr fünfmal so viele
Spuren, und Berlin-Mitte ist kein zehnspuriges Raster. Das Modell war richtig, die Nachfrage nicht.

Stau bleibt so eine Folge von Entscheidungen statt einer Gewissheit, und genau darum herum ist das
Spiel gebaut:

| Autoanteil | Runde gesamt | Fahrzeit | Verspätung |
| ---------: | -----------: | -------: | ---------: |
|      100 % |    11.140 kg | 20,4 min |   11,3 min |
|       75 % |     8.616 kg | 13,9 min |    4,8 min |
|       50 % |     6.236 kg |  9,5 min |    0,4 min |
|       25 % |     4.385 kg |  9,5 min |    0,1 min |
|        0 % |     2.449 kg |        — |          — |

Steigt die Hälfte der Klasse um, ist der Stau vollständig weg. Das ist physikalisch richtig — Stau
ist ein Schwellenphänomen dicht an der Kapazität und kein Verlauf — und es ist der Punkt der Übung.

Diese Zeilen sind vor dem Kartendaten-Durchgang weiter unten gemessen. Der Boden des Fahrplans liegt
heute bei 2.864 kg statt 2.449, und jede Zeile mit Leuten im Bus ist billiger, als sie hier steht.
Die Tabelle ist für die Form da.

### Der Maßstab wird abgeleitet, nicht gewählt

```
Menschen pro Gruppe = Pendler des Stadtteils / (Plätze × Gruppen pro Platz)
```

Eine Karte bildet einen Ort ab, und ein Ort hat eine Zahl von Pendlern. Die Klasse **teilt** diese
Pendler unter ihren Gruppen auf; sie erzeugt keine neuen, weil mehr Schüler gekommen sind. Hält
man den Stadtteil konstant, während die Platzzahl sich ändert, bleibt die Runde dieselbe Runde:

| Plätze | Gruppen | Menschen/Gruppe | CO₂ Auto | Fahrzeit | Verspätung |
| -----: | --------: | ----------------: | -------: | -------: | ---------: |
|     16 |        64 |               100 | 8.691 kg | 20,4 min |   11,3 min |
|      8 |        32 |               200 | 8.630 kg | 20,2 min |   11,0 min |
|      4 |        16 |               400 | 8.904 kg | 20,8 min |   11,4 min |
|      2 |         8 |               800 | 8.652 kg | 20,7 min |   11,5 min |

CO₂ auf 3 % genau, Verspätung auf eine halbe Minute. Nagelt man `people_per_agent` stattdessen auf
eine feste Zahl, sieht eine halb besetzte Klasse auf derselben Karte **0,4 Minuten Verspätung statt
11,3** und stößt 44 % des CO₂ aus — ein anderes Spiel, je nachdem, wer zum Unterricht gekommen ist.

### Das Budget gilt pro Runde

Weil die Nachfrage konstant ist, kostet eine Runde, was sie kostet, egal wie viele Schüler spielen.
Das Budget braucht deshalb gar keinen Term für die Gruppengröße:

```
CO₂-Budget = CO₂-Budget der Karte pro Runde × Runden
```

Über sechs Runden gibt eine Klasse, die nie aus dem Auto steigt, 66.840 kg aus; eine, die sich
herunterarbeitet — 100 / 75 / 50 / 50 / 25 / 25 % Autoanteil — rund 41.000. Ein Budget muss zwischen
diesen beiden liegen, sonst ist es keins. 8.000 kg pro Runde, 48.000 für sechs, tut das: Wer
durchgehend fährt, ist in Runde 5 raus, und wer sich verbessert, kommt mit etwa sieben Tonnen Rest
durch.

Es ist nicht die knappste Zahl, die funktioniert. Es ist die rundeste Zahl innerhalb der Spanne,
weil die Klasse sie im Kopf behalten können muss.

Die beiden Summen stammen aus der Tabelle oben und tragen deren Vorbehalt: Nach der Kartenreparatur
gibt eine Klasse, die umsteigt, weniger aus, das Budget liegt also mit kleinerem Abstand in der
Spanne als vorher. Es liegt weiter darin — durchgehend fahren sprengt es, wer umsteigt kommt durch —
aber es ist die Zahl, auf die man nach dem nächsten Play-Test zuerst schaut.

### Die Emissionsfaktoren, und einer, der falsch war

Jeder Faktor gilt pro Fahrzeugkilometer, und jeder muss nachprüfbar sein für eine Klasse, die ihn
nachprüfen will:

| Modus | Faktor         | woher er kommt                                                   |
| ----- | -------------- | ---------------------------------------------------------------- |
| Auto  | 166,8 g/km     | Flottendurchschnitt, eine Person pro Fahrzeug                    |
| Bus   | 1.200 g/Bus-km | ein 12-m-Stadtbus mit ~45 l/100 km Diesel × 2,64 kg CO₂ je Liter |
| Zug   | 1.500 g/Zug-km | ~4 kWh/Zug-km mit Nebenverbrauchern × 363 g CO₂/kWh (UBA 2024)   |

Der Zugfaktor ist der, den man erzählen sollte, weil er zeigt, wofür Kalibrierung da ist.
Ausgeliefert wurde er mit **3.500 g/Zug-km**, und im Spiel sah nichts kaputt aus. 3.500 entsprechen
aber rund 9,6 kWh pro Zugkilometer, und das ist ein dieselgeführter Fernzug — eine Berliner U- oder
S-Bahn braucht etwa 4, und der deutsche Strommix macht daraus 1.450, gerundet 1.500.

Es fiel weit stärker ins Gewicht als seine Größe vermuten lässt, weil der Fahrplan fährt, ob jemand
mitfährt oder nicht. Auf einer Karte mit sechs Zuglinien war diese eine Zahl **39 % einer
100-%-Auto-Runde**; bei 1.500 sind es 22 %. Vorher bestimmte der Fahrplan fast vier Zehntel jeder
Runde, ohne dass die Klasse daran etwas ändern konnte. Jetzt liegen 78 % einer Runde in ihrer Hand.

In dieser einen Zahl stecken zwei Entscheidungen, und bei beiden geht es um Verteidigbarkeit, nicht
um Genauigkeit:

- **Der Strommix, nicht der Ökostromtarif des Betreibers.** Das ist die konservative Zahl und die,
  die eine Klasse nachschlagen kann.
- **Der CO₂-Faktor wurde korrigiert und die Kosten blieben unangetastet.** Sie stammen aus
  verschiedenen Quellen. Den einen dem anderen nachzuziehen ist genau der Weg, auf dem zwei Metriken
  aufhören, sich darüber einig zu sein, welcher Modus teuer ist.

### Die Streuung ist auf eine Form kalibriert, nicht auf einen Literaturwert

σ = 0,14 auf der Kantenkapazität ist über zwanzig Seeds gefahren worden: 0,10 ergibt 12,7 % Streuung
unter Last, 0,18 ergibt 22,1 %, und 0,14 landet auf den 16–18 %, auf die das Modell zielt.

Die Verkehrsliteratur läge eher bei 25 %. Das wird **bewusst nicht benutzt.** Mehr als die Hälfte
des realen Staus sind Störfälle und Wetter, und davon steckt nichts in diesem Modell. Die
Kapazitätsstreuung aufzublasen, um das abzudecken, hieße, eine realistisch aussehende Zahl aus dem
falschen Grund auf den Bildschirm zu schreiben — und das Modell wäre nicht mehr mit dem erklärbar,
was darin steht.

Wo ein Mechanismus fehlt, ist der ehrliche Zug, die Lücke zu benennen, und nicht, an einem Parameter
zu drehen, bis das Ergebnis der Wirklichkeit ähnelt. Aus demselben Grund ist Überholen auf
mehrspurigen Straßen eine Ordnung in der Warteschlange und kein kleineres σ: Die Streuung zu
verkleinern hätte den fehlenden Mechanismus versteckt, statt ihn zu bauen.

### Was Kalibrierung nicht repariert: die Kartendaten

Der erste Kalibrierungsdurchgang wurde auf einer Karte gemessen, deren Daten kaputt waren. Eine
Buslinie hatte **gar keine Kanten** — vier Haltestellen auf dem Plan und kein Fahrzeug, das sie
erreicht. Eine andere riss in der Mitte und wurde mit Gesellschafts-CO₂ für Kilometer belastet, die
ihre Fahrzeuge nie fahren konnten. Jedes Fahrzeug beider Modi hatte 60 Plätze, also zwangen 6.400
Menschen eine 60-Plätze-U-Bahn zu Fahrt um Fahrt.

Die Folge war, dass sechs der 36 Wohnort-Arbeitsplatz-Paare überhaupt keine ÖPNV-Verbindung hatten.
Eine Klasse, die aus dem Auto wollte, konnte es nicht, und elf von 64 Gruppen fuhren Auto, was
auch immer entschieden wurde — 1.313 kg, die die Klasse nicht vermeiden konnte. Die Zahlen waren
korrekt gerechnet, auf einer Karte, die nicht beschrieb, was auf dem Bildschirm stand.

Die Reparatur der Daten änderte auf der Autoseite **nichts**: 10.103 → 10.150 kg bei 100 % Auto,
innerhalb der 1,4 % Streuung von sechs Seeds, bei gleicher Fahrzeit und gleicher Verspätung. Sie
änderte den Lohn fürs Umsteigen vollständig — eine Runde ohne ein einziges Auto kostet jetzt 3.191
kg, wo sie 5.936 kg gekostet hat.

Also: die Daten vor den Konstanten prüfen. Eine Kartendatei ist Produktionsdaten und verdient
dasselbe Misstrauen wie Code.

### Nachrechnen

Runden auf der betreffenden Karte mit festen Seeds nachspielen und lesen, was ein Kandidat tut.
Nicht an den Werten drehen, bis sich ein Play-Test gut anfühlt — das passt das Modell an einen
Nachmittag an.

- `backend/game/calibration.py` — die Herleitung und jeder Messwert hinter den ausgelieferten
  Vorgabewerten.
- `docs/kalibrierung.md` — dieselbe Aufzeichnung, mit den vollständigen Vorher-Nachher-Tabellen.
- `backend/game/tests/test_join.py` — wofür jede Zahl da ist, als Testfall festgehalten.

### Was nicht kalibriert ist

- **Jede neue Karte startet bei 6.400 und 8.000.** Das sind die Zahlen von Berlin Mitte-West. Für
  eine kleinere Karte sind beide zu hoch, und nichts warnt davor.
- **Die Abfahrten werden mit σ = 10 Minuten** um die Abfahrtsstunde gezogen, praktisch alle fahren
  also innerhalb von zwanzig Minuten los. Ein echter Berufsverkehr verteilt sich über eine Stunde
  und mehr; bei σ = 45 sinkt die Verspätung einer 100-%-Auto-Runde von 56,9 auf 16,5 Minuten. Das
  ist eine Modellfrage und keine Kalibrierungsfrage, und sie bleibt bewusst offen.
- **Der Abendverkehr wird nicht simuliert**, und beide Richtungen einer Straße teilen sich eine
  Warteschlange. Harmlos, solange alle morgens zur Arbeit fahren; falsch an dem Tag, an dem der
  Rückweg dazukommt.
