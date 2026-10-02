# Hintergrund

Die Idee zum Spiel stammt aus der [Masterarbeit](./../master_thesis.pdf) von Sebastian Werblinski an der
Freien Universität Berlin (2025).
Der Code hier ist eine vollständige Neuentwicklung an der TU Berlin und keine Fortsetzung seines
Prototyps; das Verkehrsmodell ist dabei neu gebaut worden. Hier steht, wie es rechnet und woher
seine Zahlen kommen.

## Simulation

Eine Runde simuliert das Pendelverhalten von tausenden Menschen. Dabei muss die Simulation folgende
Fragen beantworten:

1. Mit welchem Verkehrsmittel ist man am schnellsten?
2. Mit welchem Verkehrsmittel ist man am kostengünstigsten unterwegs?
3. Mit welchem Verkehrsmittel setzt man am wenigsten CO₂ in die Atmosphäre frei?

## Modell

CO2mmute simuliert den Verkehr mit einem mesoskopischen Modell. Dabei bilden Fahrzeuge eine Schlange
auf einem Streckenabschnitt, ohne eine genaue Position auf diesem Abschnitt zu haben.
Streckenabschnitte sind die Kanten (Edges) eines Graphen. Wo Streckenabschnitte zusammenlaufen,
liegen Knoten (Nodes).

### Eine Kante sind drei Zahlen

Für die Simulation hat jede Kante drei Kernzahlen:

```
Freiflusszeit      t0 = Länge / Tempolimit
Abflusskapazität   Q  = 1.800 Fahrzeuge/h je Autospur
Speicherkapazität  S  = 133 Fahrzeuge/km je Autospur × Länge
```

Wir nehmen 1.800 Fz/h und Spur als die Sättigungsverkehrsstärke einer städtischen Spur. 133 Fz/km
und Spur ist die Dichte im Stillstand: ein Fahrzeug je 7,5 m, Stoßstange an Stoßstange. Eine 900 m
lange einspurige Straße fasst also rund 120 stehende Fahrzeuge und lässt in einem Fünf-Minuten-Tick
rund 150 durch.

Spuren werden gezählt, wie sie auf der Straße liegen. Dabei gilt:

```
Autospuren = Spuren − (1 bei Busspur) − (1 bei Radspur)
```

Die Zahl ist nach unten auf null begrenzt, und **null Autospuren sind erlaubt**: Die Straße wird
zur _Busschleuse_ – für Autos gesperrt, offen für Busse und wahlweise auch für Räder und Fußgänger.

### Ein Tick

1. Jede Kante bekommt ihr Budget für den Tick: `Q × Ticklänge`.
2. Alle, deren Abfahrtsminute gekommen ist, versuchen auf ihre erste Kante zu kommen.
3. Ein Fahrzeug darf eine Kante nicht vor Ablauf von `t0` verlassen. Die Freiflusszeit ist die
   Untergrenze der Fahrt; schneller als das Tempolimit geht nie.
4. Danach reiht es sich in die Schlange der Kante ein und wartet auf Budget. Auf einer Spur ist das
   eine einzige FIFO-Schlange. Ab zwei Autospuren hat jede nächste Kante ihre eigene, eine
   Abbiegespur, und alle teilen sich das Budget und den Speicher der Straße.
5. Weiter darf es nur, wenn die **nächste** Kante noch Speicher frei hat. Wenn nicht, bleibt es
   stehen, und alles dahinter in seiner Schlange auch: auf einer Spur also alle, ab zwei Spuren nur,
   wer in dieselbe Richtung will. Ein Stau entsteht.
6. Innerhalb des Ticks wiederholen, bis sich nichts mehr bewegt. Ein Fahrzeug schafft in fünf
   Minuten mehrere kurze Kanten. Die Kanten werden dabei jeden Tick in neu gemischter Reihenfolge
   bedient: Münden mehrere in denselben Knoten, ist über eine Runde jede gleich oft als erste dran.
   Das ist das Reißverschlussprinzip, im Mittel statt Auto für Auto.

Stau entsteht also aus zwei Mechanismen: Eine Kante lässt nur `Q` Fahrzeuge pro Stunde ab, und eine
volle Kante hält die Kante auf, die sie speist. So wachsen Schlangen rückwärts durch das Netz, wie
auf einer echten Straße. Ab zwei Spuren weicht das bewusst von MATSim ab, wo eine Kante bei jeder
Breite eine einzige Schlange hat: Wer in eine volle Straße abbiegen will, hält dort die nicht auf,
die woandershin wollen.

![Eine Kante im freien Fluss und im Rückstau](../backend/template/hintergrund/kante.svg)

_Oben fährt jedes Auto seine Freiflusszeit `t0` ab und reiht sich am Ende kurz ein, bevor die Kante
es mit `Q` abgibt. Unten ist die nächste Kante voll: Niemand fährt ab, die Schlange füllt den
ganzen Speicher `S`, und wer ankommt, kommt nicht mehr hinein._

### Die Mindestgeschwindigkeit

Viele Verkehrsmodelle rechnen eine Geschwindigkeit aus dem Verhältnis von Belastung zu Kapazität und
müssen deshalb verhindern, dass sie null erreicht. Wir erinnern uns: Durch null teilen sollte man
vermeiden. Ein Warteschlangenmodell hat diesen Term nicht. Ein Fahrzeug wird freigegeben oder nicht,
und auf der Eingabeseite steht nirgends eine Geschwindigkeit. Eine Mindestgeschwindigkeit braucht es
deshalb nicht.

Dafür kann sich das Netz wirklich verklemmen: ein Ring aus Kanten, jede voll mit Fahrzeugen, die
auf die nächste wollen.

Ein Knoten, der vier Ticks hintereinander nichts bewegt hat, gibt deshalb trotzdem ein Fahrzeug
frei, über die Speichergrenze hinweg, und wartet dann wieder vier Ticks. Jede Freigabe wird gezählt.
Ein `forced_releases` über null im Tick-Log ist kein Fehler, aber ein Grund, das Log zu lesen.

Ein Durchlauf läuft, bis alle angekommen sind. Eine Uhr, nach der der Rest einfach nicht mehr
mitzählt, gibt es nicht. Die Grenze von 1000 Ticks pro Weg fängt nur einen Fehler im Modell ab und
wird als Fehler geloggt. Auf Berlin Mitte-West braucht ein gespielter Weg höchstens 35 Ticks, bei
vierfacher Nachfrage und nur einspurigen Straßen 153.

### Geschwindigkeit ist ein Ergebnis

Die mittlere Geschwindigkeit einer Kante ist ihre Länge geteilt durch die **tatsächlich auf ihr
beobachteten** Fahrzeiten. Gezählt werden dabei nur Autos: Ein Fußgänger braucht zehn Minuten für
eine Kante, die ein Auto in einer Minute schafft, und ließe man ihn in den Mittelwert, meldete eine
leere Straße Stau. Einen Stau-Faktor, mit dem eine Freiflussgeschwindigkeit multipliziert wird, gibt
es nicht.

Die Geschwindigkeit auf der Karte, der CO₂-Faktor einer Fahrt und die Routenvorschau, die ein
Spieler in der nächsten Runde bekommt, beruhen also alle auf derselben gemessenen Zahl.

### Wer trägt alles zum Stau bei?

- **Autos** immer.
- **Busse** stehen im Mischverkehr und fahren auf einer eigenen Busspur frei. Ein Bus zählt 3
  Pkw-Einheiten, nimmt in der gemeinsamen Schlange also den Platz von drei Autos ein. Er steht immer
  in der Schlange seiner Fahrtrichtung, auch wo die Linie auf der Karte auf der Gegenrichtung
  eingezeichnet ist.
- **Räder** stehen nur dort im Verkehr, wo sie sich die Straße mit Autos teilen. Ein Rad hat auf der
  Kante eine eigene Schlange mit eigenem Abflussbudget von 2.000 Rädern/h. Ein Autostau hält also
  keinen Radfahrer auf und ein Radfahrer keinen Autofahrer. Den _Speicher_ der Kante teilen sie sich
  aber: Ein Rad zählt 0,2 Pkw-Einheiten, und so nehmen tausend Radfahrer den Autos Platz weg.
  Abgewiesen wird ein Rad nie, auch nicht von einer vollen Straße.
- **Fußgänger** stehen ganz außerhalb des Warteschlangenmodells.

### Hin und zurück

Ein Pendelweg besteht aus Hin- und Rückweg, und eine Runde rechnet beide. Der Rückweg ist keine
Umkehrung des Hinwegs, sondern eine eigene Suche auf dem Graphen, mit demselben Verkehrsmittel und
derselben Wahl: Der Graph ist gerichtet, eine Einbahnstraße ist eine Kante ohne Gegenkante, und der
Weg zurück kann dann ein anderer sein, im Extremfall ein Kreis. Auf Berlin Mitte-West hat jede Kante
ihre Gegenkante, dort ist der Rückweg derselbe Weg andersherum. Gibt es keinen Weg zurück, lässt
sich der Weg hin nicht abschicken.

Zwischen den beiden Spitzen liegen Stunden. Der Abend ist deshalb ein zweiter Durchlauf auf einem
frischen Netz und kein zweiter Teil derselben Uhr. Auf einer Uhr würden die Linien den ganzen Tag
weiterfahren, weil die Leute vom Abend schon in der Liste warten, und die Gesellschaft würde CO₂
für Busse zahlen, die niemand besteigen kann. So fährt der Fahrplan zweimal, und beide Fahrpläne
zählen. CO₂ und Kosten einer Gruppe sind die Summe beider Wege, ihre Fahrzeit ist die für Hin- und
Rückweg zusammen, gemittelt über die Gruppen. Weil in einer Runde damit alles zweimal anfällt, ist
das Budget pro Runde doppelt so groß wie für einen Weg.

Der Abend ist heute ein Abbild des Morgens, mit derselben Streuung der Abfahrten. Die Wiedergabe
zeigt beide Wege, dazwischen eine kurze Mittagspause.

## Der ÖPNV fährt einen Fahrplan

Ein Linienfahrzeug ist in der Simulation ein **ganz normales Fahrzeug auf einer künstlichen Route**.
Ein Bus steht deshalb in der Schlange und staut zurück wie jedes Auto, es sei denn, er hat eine
eigene Busspur.

Menschen steigen an Haltestellen ein, die nach Linie _und_ Knoten unterschieden werden: Wer auf die
M1 wartet, steigt nicht in die U7. Einsteigen kann man nur, wenn Platz ist, sonst wartet man weiter.
Plätze werden frei, wenn jemand aussteigt. Beim Umsteigen wartet man erneut, diesmal auf die neue
Linie. Die Wartezeit wird gemessen und **ausgewiesen, nicht addiert**: Die Uhr läuft seit der
Minute, in der die Person losfahren wollte, das Stehen an der Haltestelle steckt also schon in der
Fahrzeit. Haltezeiten sind nicht modelliert; ein Fahrzeug bedient seine Haltestelle in dem
Augenblick, in dem es ankommt.

Eine Linie fährt ihren Fahrplan, ob jemand mitfährt oder nicht:

> **Die Gesellschaft bezahlt den Fahrplan.** Eine Linie stößt `Fahrzeuge × Linienkilometer × Faktor`
> aus. Auch ein leerer Bus stößt CO₂ aus, und eine Linie, die niemand benutzt hat, kostet die Runde
> trotzdem.

Der Fahrplan deckt das Abfahrtsfenster von zwei Stunden ab. Danach fährt eine Linie weiter, solange
noch jemand unterwegs ist, im Auto, auf dem Rad, zu Fuß oder an einer Haltestelle, auch wenn niemand
mitfährt: Busse fahren auch in den ruhigen Stunden. Steckt der letzte Autofahrer im Stau, fahren die
Linien weiter, und die Gesellschaft bezahlt sie.

Auf die Mitfahrenden verteilt wird diese Summe nach **Personenkilometern**, nicht pro Kopf: Wer auf
einer 13 km langen Linie eine Station fährt, soll nicht den Anteil einer ganzen Fahrt tragen,
während das Auto daneben nach Kilometern abgerechnet wird. Die persönlichen Anteile ergeben zusammen
genau die Summe der Linie: `Σ persönlich = Gesellschaft`.

Die Summe einer Runde sind deshalb die Zeilen der Spieler **plus** die Gesellschaftskosten der
Linien, die niemand benutzt hat.

## CO₂ und Kosten hängen an einer Geschwindigkeitskurve

Emissionen sind kein fester Wert pro Kilometer. Ein Auto im Stop-and-go verbrennt Kraftstoff, den es
nicht in Strecke umsetzt, und ein Auto bei 130 km/h kämpft gegen den Luftwiderstand. Das Modell
benutzt einen geschwindigkeitsabhängigen Emissionsfaktor der COPERT/HBEFA-Form:

```
EF(v) = a/v + b + c·v²          Gramm CO₂ pro Fahrzeugkilometer
```

`a/v` ist Leerlauf und Stop-and-go, ein fester Verbrauch, verteilt auf weniger Kilometer; `c·v²` ist
der Luftwiderstand; `b` ist alles, was allein mit der Strecke skaliert. `a` und `b` sind **keine
freien Parameter**, sie folgen aus `c` und zwei Bedingungen:

```
1.  das Minimum der Kurve liegt bei 70 km/h  →  a = 2c · v_min³           = 1962,3 g/h
2.  EF(50) = 166,8 g/km, der Autofaktor      →  b = 166,8 − a/50 − c·50²  = 120,4 g/km
```

mit `c = 0,0028605`. So gilt der Ankerwert bei 50 km/h exakt, und frei gewählt ist nur noch eine
Zahl statt drei.

| km/h        | 10   | 20   | 30   | 40   | 50    | 70    | 100  |
| ----------- | ---- | ---- | ---- | ---- | ----- | ----- | ---- |
| g CO₂/km    | 317  | 220  | 188  | 174  | 166,8 | 162,5 | 169  |
| × Basiswert | 1,90 | 1,32 | 1,13 | 1,04 | 1,00  | 0,97  | 1,01 |

`a/v` wächst ohne Grenze, wenn die Geschwindigkeit gegen null geht. Deshalb ist **der Faktor bei
2,00× gedeckelt**, statt die Geschwindigkeit nach unten zu begrenzen: Schlimmstenfalls stößt ein Auto
doppelt so viel aus wie bei 50 km/h. Der Deckel greift unterhalb von 9,2 km/h.

![Die Emissionskurve eines Autos über der Geschwindigkeit](../backend/template/hintergrund/co2-kurve.svg)

_Gramm CO₂ pro Kilometer über der mittleren Geschwindigkeit auf einer Kante. Der Anker liegt bei
50 km/h, das Minimum bei 70 km/h, und unterhalb von 9,2 km/h hält der Deckel die Kurve bei 333,6 g._

Daraus folgt:

- **Eine Tempo-30-Straße stößt pro Kilometer rund 13 % mehr aus als eine 50er, auch leer.** Das ist
  in jedem geschwindigkeitsabhängigen Modell so, und 34 der 82 Straßenkanten der ausgelieferten
  Karte sind 30er-Zonen. Das hebt die Emissionen einer Runde schon ohne Stau an.
- **Die Kosten hängen mit halbem Gewicht an derselben Kurve.** Die Hälfte der 0,32 €/km ist
  Kraftstoff und Verschleiß im Stop-and-go und folgt dem Emissionsfaktor; die andere Hälfte
  (Abschreibung, Versicherung, Steuer) fällt an, ob das Auto heute fährt oder nicht. Die Kosten sind
  deshalb bei 1,50× gedeckelt, CO₂ bei 2,00×.

Beim ÖPNV gilt ein fester Wert pro Fahrzeugkilometer: 1.200 g für einen Bus, 1.500 g für einen Zug.
Eine Geschwindigkeitskurve gibt es hier nicht, weil die Fahrzeuge nach Fahrplan fahren und nicht
nach Verkehrslage.

Neben den Kosten steht der **Fahrpreis**: 1,30 € pro Fahrt, Umstiege eingeschlossen, und beim Auto
der Teil der Kosten, den man aus der eigenen Tasche zahlt. Es gibt also einen Unterschied zwischen
_was du zahlst_ und _was es kostet_, den man bei der Rundenauswertung benennen sollte.

## Zufälle gibt's

Dieselben Entscheidungen ergeben in zwei Runden nicht ganz dieselben Zahlen. Das ist gewollt. Jede
Runde zieht ihre Zufallszahlen aus einem Generator, dessen Seed aus der Runde abgeleitet wird;
dieselbe Runde lässt sich also jederzeit identisch nachspielen.

Zufällig sind genau zwei Dinge:

- **Die Kapazität einer Kante, einmal je Kante und Runde gezogen** (σ = 0,14, begrenzt auf
  0,6–1,4×). Nur sie sorgt dafür, dass sich Runde 2 von Runde 1 unterscheidet, weil sich Rauschen
  pro Fahrer über tausende Menschen herausmittelt.
- **Die Wunschgeschwindigkeit, einmal je Fahrer gezogen** (σ = 0,12, begrenzt auf 0,7–1,4×), für die
  Streuung _innerhalb_ einer Runde. Auf einer mehrspurigen Straße ist die Schlange danach geordnet,
  wann ein Fahrzeug bereit ist, und nicht streng nach dem Eintreffen. So entsteht Überholen, ohne
  dass es dafür einen eigenen Mechanismus braucht.

Das _Ergebnis_ wird nie mit einer Zufallszahl multipliziert. Zufällig sind nur die Eingaben, und nahe
der Kapazität verstärkt das Modell ihre Schwankungen. Im freien Fluss streut eine Runde deshalb kaum
(Variationskoeffizient rund 0,3 %), unter Last deutlich (16–18 %). Wie im echten Verkehr ist eine
leere Straße vorhersehbar und ein Stau nicht.

**Verspätung wird gegen die eigene Freiflusszeit des Fahrers gemessen.** Wer in einer 50er-Zone
lieber 45 fährt, ist dadurch nicht verspätet.

## Einheiten

Eine Gruppe (in der Forschung Agent genannt) steht für viele Pendler, und aus diesem Faktor stammen
die meisten Einheitenfehler dieses Projekts. Zwei Regeln:

- Eine CO₂- oder Euro-Zahl ist **extensiv**: Sie summiert über Gruppen und über die Menschen
  hinter jeder Gruppe. Pro Person heißt: durch beides teilen.
- Eine Fahrzeit ist es **nicht**: Zwei Gruppen mit je 30 Minuten Fahrzeit brauchen zusammen nicht
  60. Die Fahrzeit einer Gruppe ist Hin- und Rückweg zusammen, eine mittlere Fahrzeit ein Mittel über
  die Gruppen.

Wie groß der Faktor, wird aus der Karte abgeleitet.

## Kalibrierung

Die Verkehrsphysik oben gilt für jede Karte: 1.800 Fz/h und 133 Fz/km pro Spur sind Messwerte aus
der Verkehrstechnik, und die Emissionskurve hängt an ihren zwei Ankerbedingungen. Was sich von Karte
zu Karte ändert, ist die Größe der Welt: wie viele Menschen auf der Karte pendeln und wie viel CO₂
eine Runde kosten darf. Beides muss für jede Karte gemessen werden. Liegen die Zahlen daneben,
verliert das Spiel seinen Spass:

- **Zu viele Pendler**, und das Netz steht still, egal was gespielt wird. Berlin Mitte-West wurde
  anfangs mit 1.000 Menschen pro Gruppe gespielt, bei voller Besetzung also mit 64.000 Autos. Das
  Modell kam damit zurecht und meldete eine mittlere Fahrzeit von **298 Minuten für 7,66 km**.
- **Zu wenige Pendler**, und es gibt keinen Stau, den man durch Umsteigen auflösen könnte.
- **Ein zu knappes Budget** ist schon in der ersten Runde aufgebraucht, **ein zu großes** spielt
  keine Rolle.

Wie man die beiden Zahlen für eine Karte findet, steht in diesem Kapitel. Als Beispiel dient Berlin
Mitte-West.

### Zwei Zahlen pro Karte

Jede Karte trägt:

```
district_commuters        Pendler, die die Karte trägt
co2_budget_kg_per_round   CO₂-Budget pro Runde in kg
calibrated                ob beide für diese Karte gemessen sind
```

Die Werte stehen in der JSON-Datei der Karte, lassen sich im Admin ändern und gehen beim Export mit.
Eine neue Karte übernimmt 6.400 und 16.000 von Berlin Mitte-West, bis jemand für sie misst. Erst wenn
`calibrated` gesetzt ist, verschwindet der Hinweis bei „Spiel anlegen“.

Alles andere wird daraus abgeleitet:

```
Menschen pro Gruppe = Pendler / (Plätze × Gruppen pro Platz)
CO₂-Budget          = CO₂-Budget pro Runde × Runden
```

Wer mitspielt, **teilt** die Pendler der Karte unter den Gruppen auf; mehr Plätze erzeugen keine
neuen. Eine Runde kostet deshalb gleich viel, egal wie viele mitspielen, und das Budget braucht
keinen Term für die Plätze. Gemessen wird also einmal pro Karte und nicht für jede Spielerzahl neu.

### Erst die Kartendaten prüfen

Gemessen wird die Karte, wie sie in der Datei steht. Ist dort etwas kaputt, misst die Kalibrierung
den Fehler mit. Vorher prüfen:

- Jede Linie fährt ihre Strecke ohne Lücke.
- Hin- und Rückrichtung einer Linie halten an denselben Haltestellen.
- Busse haben 85 Plätze, Züge 1.000.
- Jedes Paar aus Wohnort und Arbeitsplatz ist mit Bus und Bahn erreichbar.

Auf Berlin Mitte-West hatte eine Buslinie anfangs gar keine Kanten, eine andere riss in der Mitte,
und jedes Fahrzeug hatte 60 Plätze. Sechs der 36 Paare hatten dadurch keine ÖPNV-Verbindung, und eine
Runde ganz ohne Auto kostete fast doppelt so viel wie heute. Wie man das prüft, zeigt
`backend/maps/tests/test_example_map.py` für die mitgelieferte Karte.

### Mit Testrunden messen

Gemessen wird mit Testrunden, nicht mit einem Play-Test. Ein Play-Test zeigt, wie sich ein Spiel
anfühlt, aber nicht, wie viel Verkehr eine Karte trägt.

1. Die Karte auf einer lokalen Instanz hochladen (`devops/dev.sh up`), nicht auf dem Server, auf dem
   gespielt wird.
2. Ein Spiel mit wenigen Plätzen anlegen. Kartenänderungen nicht zulassen, damit jede Runde auf der
   Basisversion fährt, und das CO₂-Budget so hoch setzen, dass das Spiel nicht endet.
3. Bei „Menschen pro Gruppe“ den Kandidaten eintragen: Pendler ÷ (Plätze × Gruppen pro Platz).
4. Die Plätze an der Leitstelle anlegen und für jede Gruppe Verkehrsmittel und Weg selbst wählen.
5. Nach jeder Runde CO₂ und mittlere Fahrzeit ablesen. Unter Last streut eine Runde um 16–18 %,
   also mehrere Runden mit derselben Wahl spielen und mitteln.

Wer programmiert, kann eine fertige Runde auch mit `TrafficSimulator` aus
`backend/game/simulation.py` und festem Seed nachspielen und über beliebig viele Seeds mitteln.

Weil sich der Maßstab aus der Platzzahl ergibt, reichen dafür wenige Plätze. Auf Berlin Mitte-West
ergeben zwei Plätze fast dieselbe Runde wie sechzehn:

| Plätze | Gruppen | Menschen/Gruppe |  CO₂ Auto | Fahrzeit | Verspätung |
| -----: | ------: | --------------: | --------: | -------: | ---------: |
|     16 |      64 |             100 | 10.194 kg | 22,5 min |   12,5 min |
|      8 |      32 |             200 | 10.211 kg | 22,6 min |   12,6 min |
|      4 |      16 |             400 |  9.857 kg | 21,0 min |   11,0 min |
|      2 |       8 |             800 |  9.784 kg | 22,3 min |   12,5 min |

![Dieselben 6.400 Pendler, verschieden aufgeteilt](../backend/template/hintergrund/massstab.svg)

_Jede Zeile sind dieselben 6.400 Pendler, nur anders auf Gruppen verteilt. Die letzte Zeile hält
die Gruppe bei 100 Menschen fest: Mit acht Plätzen ist dann nur der halbe Stadtteil unterwegs._

CO₂ stimmt auf gut 4 %, die Verspätung auf anderthalb Minuten. Hält man die Gruppe dagegen bei einer
festen Zahl von Menschen, wird ein halb besetztes Spiel zu einem anderen Spiel: 1,0 Minuten
Verspätung statt 12,5 und nur 42 % des CO₂.

### Die Pendlerzahl

Die Pendlerzahl soll so gewählt sein, dass ein Morgen, an dem alle Auto fahren, ungefähr so lange
dauert wie der Berufsverkehr in der echten Stadt.

1. Die mittlere Länge eines Arbeitswegs auf der Karte bestimmen. Auf Berlin Mitte-West sind es
   7,66 km.
2. Nachschlagen, wie schnell der Berufsverkehr in der abgebildeten Stadt fließt. In der Berliner
   Innenstadt sind es rund 24 km/h, für 7,66 km also 19 Minuten.
3. Testrunden spielen, in denen alle Auto fahren, und die Pendlerzahl anpassen, bis die mittlere
   Fahrzeit in dieser Gegend liegt.

Das Ergebnis ist nicht die echte Pendlerzahl des Stadtteils, die ist viel höher. Der Graph bildet
aber nur die Hauptachsen ab, und gesucht ist, wie viel Verkehr **diese Achsen** tragen. Für Berlin
Mitte-West sind es **6.400 Pendler**: Fahren alle Auto, dauern 7,66 km dann 22,5 Minuten, 12,5 davon
Verspätung. Das Modell liegt damit etwas über der echten Stadt.

Danach prüfen, ob der Stau von den Entscheidungen abhängt. Darum geht es im Spiel. Dafür Runden mit
weniger Autos spielen, etwa mit drei Vierteln, der Hälfte und einem Viertel:

| Autoanteil | Runde gesamt |      Auto | Fahrplan | Fahrzeit Auto | Verspätung |
| ---------: | -----------: | --------: | -------: | ------------: | ---------: |
|      100 % |    13.059 kg | 10.194 kg | 2.864 kg |      22,5 min |   12,5 min |
|       75 % |     9.884 kg |  6.903 kg | 2.981 kg |      15,4 min |    5,4 min |
|       50 % |     7.184 kg |  4.164 kg | 3.020 kg |      10,6 min |    0,7 min |
|       25 % |     5.345 kg |  2.207 kg | 3.139 kg |      10,8 min |    0,1 min |
|        0 % |     3.194 kg |         — | 3.194 kg |             — |          — |

![Was eine Runde kostet, nach Autoanteil](../backend/template/hintergrund/runde.svg)

_Jeder Balken ist eine Runde: Auto in Blau, der Fahrplan in Gelb. Der Fahrplan fährt so oder so und
wird nur etwas teurer, wenn mehr Leute einsteigen; das Auto bestimmt, wie lang der Balken wird. Die
Linie ist das halbe Budget von 16.000 kg pro Runde, also das für einen Weg._

Auf Berlin Mitte-West ist der Stau weg, wenn die Hälfte umsteigt. Stau ist ein Schwellenphänomen
dicht an der Kapazität: Knapp darunter fließt der Verkehr, knapp darüber staut er. Bleibt der Stau
auch bei halbem Autoanteil, ist die Pendlerzahl zu hoch. Staut es schon dann kaum, wenn alle Auto
fahren, ist sie zu niedrig.

Beim ÖPNV zeigt sich zu viel Nachfrage als Wartezeit. Auf Berlin Mitte-West brauchen Bus und Bahn 33
bis 44 Minuten, und die Wartezeit an der Haltestelle wächst von 9 auf 22 Minuten, je mehr Leute
umsteigen, weil die Fahrzeuge voll sind.

Die Tabelle gilt für einen Weg, den Hinweg. Sie ist auf der Basisversion von Berlin Mitte-West gemessen: 64 Gruppen zu je 100 Menschen,
gleichmäßig über die 36 Paare aus Wohnort und Arbeitsplatz verteilt, wer nicht Auto fährt, fährt Bus
und Bahn, gemittelt über sechs Seeds. Die Streuung zwischen den Seeds liegt unter 2 %.

### Das Budget

Für das Budget zwei Spiele über die geplante Rundenzahl messen: eines, in dem niemand aus dem Auto
steigt, und eines, das sich herunterarbeitet, zum Beispiel mit 100 / 75 / 50 / 50 / 25 / 25 %
Autoanteil. Das Budget muss zwischen beiden liegen: Das erste Spiel soll es sprengen, das zweite
damit auskommen. Nach unten begrenzt es der Fahrplan, der auch fährt, wenn niemand einsteigt, auf Berlin
Mitte-West 2.864 kg pro Runde. Die Zahl sollte rund sein, damit alle sie im Kopf behalten.

Eine Runde rechnet Hin- und Rückweg, die Tabelle oben gilt für einen Weg. Gemessen auf Berlin
Mitte-West (dieselben 64 Gruppen, sechs Seeds) kostet eine Runde mit Hin- und Rückweg 1,96- bis
2,06-mal so viel wie der Hinweg allein:

| Autoanteil | Runde gesamt |      Auto | Fahrplan |
| ---------: | -----------: | --------: | -------: |
|      100 % |    25.614 kg | 19.885 kg | 5.729 kg |
|       75 % |    19.626 kg | 13.673 kg | 5.953 kg |
|       50 % |    14.470 kg |  8.337 kg | 6.134 kg |
|       25 % |    10.883 kg |  4.415 kg | 6.468 kg |
|        0 % |     6.582 kg |         — | 6.582 kg |

Das erste Spiel kostet damit über sechs Runden 153.684 kg, das zweite 95.946 kg. Die eingetragenen
16.000 kg pro Runde, 96.000 für sechs, liegen wie vorher am Rand: Wer durchgehend fährt, ist in
Runde 4 raus, und wer sich verbessert, bleibt 54 kg unter dem Budget. Mit 18.000 kg pro Runde wäre
durchgehend Fahren erst in Runde 5 vorbei, und wer umsteigt, behielte rund zwölf Tonnen. Welche Zahl
bleibt, soll der nächste Play-Test zeigen.

### Emissionsfaktoren nachrechnen

Die Emissionsfaktoren gelten für alle Karten und stehen in `backend/sim/constants.py`. Jeder gilt
pro Fahrzeugkilometer und muss sich nachrechnen lassen:

| Modus | Faktor         | woher er kommt                                                   |
| ----- | -------------- | ---------------------------------------------------------------- |
| Auto  | 166,8 g/km     | Flottendurchschnitt, eine Person pro Fahrzeug                    |
| Bus   | 1.200 g/Bus-km | ein 12-m-Stadtbus mit ~45 l/100 km Diesel × 2,64 kg CO₂ je Liter |
| Zug   | 1.500 g/Zug-km | ~4 kWh/Zug-km mit Nebenverbrauchern × 363 g CO₂/kWh (UBA 2024)   |

Nachgerechnet wird über den Verbrauch: Energie pro Fahrzeugkilometer mal CO₂ pro Energieeinheit. So
fiel der Zugfaktor auf, der anfangs bei 3.500 g/Zug-km stand. Das entspricht rund 9,6 kWh pro
Zugkilometer, also einem dieselgeführten Fernzug. Eine Berliner U- oder S-Bahn braucht etwa 4 kWh,
mit dem deutschen Strommix sind das 1.450 g, gerundet 1.500.

Ein falscher ÖPNV-Faktor wiegt schwer, weil der Fahrplan auch fährt, wenn niemand einsteigt. Bei 3.500 g
machte der Fahrplan 39 % einer Runde aus, in der alle Auto fahren; bei 1.500 g sind es 22 %. An
diesem Anteil kann beim Spielen niemand etwas ändern.

Zwei Regeln:

- **Den Strommix nehmen, nicht den Ökostromtarif des Betreibers.** Das ist die vorsichtige Zahl,
  und jeder kann sie nachschlagen.
- **CO₂ und Kosten getrennt korrigieren.** Sie kommen aus verschiedenen Quellen. Zieht man die
  Kosten einem korrigierten CO₂-Faktor nach, sind sich die beiden Kennzahlen bald nicht mehr einig,
  welches Verkehrsmittel teuer ist.

### Die Streuung bleibt

Die Zufallsstreuung der Kantenkapazität (σ = 0,14) ist für alle Karten gleich und wird für eine neue
Karte nicht nachgestellt. Sie wurde über zwanzig Seeds auf 16–18 % Streuung unter Last eingestellt:
0,10 ergibt 12,7 %, 0,18 ergibt 22,1 %.

Die Verkehrsliteratur nennt eher 25 %. Mehr als die Hälfte des echten Staus kommt aber von Unfällen
und Wetter, und davon steckt nichts im Modell. Würde man die Kapazitätsstreuung aufblasen, um das
abzudecken, stünde eine realistisch aussehende Zahl aus dem falschen Grund auf dem Bildschirm.

Allgemein gilt: Fehlt dem Modell ein Mechanismus, wird die Lücke benannt und nicht an einem
Parameter gedreht, bis das Ergebnis passt. Aus demselben Grund ist Überholen auf mehrspurigen
Straßen eine Ordnung in der Warteschlange und kein kleineres σ.

### Wann neu gemessen werden muss

Die beiden Zahlen gelten für eine Karte und ein Modell. Neu messen, wenn

- sich die Kapazität der Karte ändert: neue Straßen, andere Spuren, neue Linien;
- sich die Nachfrage im Modell ändert. Die Abfahrten streuen heute mit σ = 10 Minuten um die
  Abfahrtsstunde, viel enger als echter Berufsverkehr. Verteilen sie sich breiter, tragen dieselben
  Achsen mehr Pendler;
- der Abend eine eigene Spitze bekommt. Heute ist er ein Abbild des Morgens, mit derselben Streuung
  der Abfahrten; eine andere Spitze trägt dasselbe Netz mit mehr oder weniger Pendlern;
- sich ein Emissionsfaktor ändert. Dann verschiebt sich das Budget.

Danach beide Zahlen in die Kartendatei oder in den Admin eintragen, `calibrated` setzen und die
Karte exportieren, damit die Messung mit der Datei mitgeht. Die Messungen für Berlin Mitte-West
stehen mit allen Tabellen in `docs/kalibrierung.md` und `backend/game/calibration.py`.
