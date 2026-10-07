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
Autospuren = Spuren − (1 bei Busspur) − (1 bei Radspur) − (1 bei eigenem Tramgleis)
```

Die Zahl ist nach unten auf null begrenzt, und **null Autospuren sind erlaubt**: Die Straße wird
zur _Busschleuse_ – für Autos gesperrt, offen für Busse, Trams und wahlweise auch für Räder und
Fußgänger. Ein Tramgleis in der Autospur nimmt keine Spur weg: Die Autos fahren darauf.

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
- **Trams** stehen dort im Stau, wo ihr Gleis in der Autospur liegt, wie die M1 auf der
  Friedrichstraße nördlich des Bahnhofs, und die Autos hinter ihnen warten auf sie. Auf einem eigenen
  Gleis fahren sie frei, wie in der Mitte der Landsberger Allee. Eine Tram zählt 5,3
  Pkw-Einheiten: 40 m Flexity durch 7,5 m je Auto im Stau. S- und U-Bahn stehen nie im Stau.
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
eigene Busspur. Eine Tram ebenso, wo ihr Gleis in der Autospur liegt.

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
noch jemand unterwegs ist, im Auto, auf dem Rad, zu Fuß, im Bus oder an einer Haltestelle, auch wenn
niemand mitfährt: Busse fahren auch in den ruhigen Stunden. Steckt der letzte Autofahrer im Stau,
fahren die Linien weiter, und die Gesellschaft bezahlt sie. Am meisten macht das aus, wenn viele
umsteigen: Mit Bus und Bahn ist man länger unterwegs als mit dem Auto, und solange einer noch
unterwegs ist, fahren alle Linien.

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

Beim ÖPNV gilt ein fester Wert pro Fahrzeugkilometer: 1.200 g für einen Bus, 1.400 g für eine Tram,
1.500 g für einen Zug.
Eine Geschwindigkeitskurve gibt es hier nicht, weil die Fahrzeuge nach Fahrplan fahren und nicht
nach Verkehrslage.

Neben den Kosten steht der **Fahrpreis**: 1,30 € pro Fahrt, Umstiege eingeschlossen, und beim Auto
der Teil der Kosten, den man aus der eigenen Tasche zahlt. Es gibt also einen Unterschied zwischen
_was du zahlst_ und _was es kostet_, den man bei der Rundenauswertung benennen sollte.

Das **Rad** kostet 0,03 €/km: Verschleiß, Reparaturen, Wertverlust und, im Mittel, Diebstahl. Das
zahlt man ganz selbst, also ist es beides, _was du zahlst_ und _was es kostet_, und es hängt an
keiner Kurve, denn ein Stau nutzt keine Kette ab. Zu Fuß kostet nichts. Nicht eingerechnet ist der
Nutzen für die Gesundheit; mit ihm wären Rad und Fußweg für die Gesellschaft billiger als umsonst. Ob
er in die Rechnung gehört, ist noch offen.

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
zu Karte ändert, ist die Größe der Welt: wie viele Menschen auf der Karte pendeln. Das muss für jede
Karte gemessen werden. Das CO₂-Budget dagegen ist pro Person und Runde auf jeder Karte dasselbe; zu
messen ist nur, was es auf einer Karte reicht. Liegen die Zahlen daneben, verliert das Spiel seinen
Spass:

- **Zu viele Pendler**, und das Netz steht still, egal was gespielt wird. Berlin Mitte-West wurde
  anfangs mit 1.000 Menschen pro Gruppe gespielt, bei voller Besetzung also mit 64.000 Autos. Das
  Modell kam damit zurecht und meldete eine mittlere Fahrzeit von **298 Minuten für 7,66 km**.
- **Zu wenige Pendler**, und es gibt keinen Stau, den man durch Umsteigen auflösen könnte.
- **Ein zu knappes Budget** ist schon in der ersten Runde aufgebraucht, **ein zu großes** spielt
  keine Rolle.

Wie man die Pendlerzahl für eine Karte findet und was das Budget auf ihr reicht, steht in diesem
Kapitel. Als Beispiel dient Berlin Mitte-West.

### Eine Zahl pro Karte, ein Budget pro Person

Jede Karte trägt:

```
district_commuters        Pendler, die die Karte trägt
calibrated                ob die Zahl für diese Karte gemessen ist
```

Die Werte stehen in der JSON-Datei der Karte, lassen sich im Admin ändern und gehen beim Export mit.
Eine neue Karte übernimmt die 6.800 von Berlin Mitte-West, bis jemand für sie misst. Erst wenn
`calibrated` gesetzt ist, verschwindet der Hinweis bei „Spiel anlegen“.

Das Budget gehört nicht zur Karte. Es ist eine Zahl pro Person und Runde, auf jeder Karte dieselbe,
und „Spiel anlegen“ stellt sie ein: 1,0 bis 6,0 kg in Schritten von 0,2, normal 2,4. Alles andere
wird abgeleitet:

```
Menschen pro Gruppe = Pendler / (Plätze × Gruppen pro Platz)
CO₂-Budget          = kg pro Person und Runde × Pendler × Runden
```

Wer mitspielt, **teilt** die Pendler der Karte unter den Gruppen auf; mehr Plätze erzeugen keine
neuen. Eine Runde kostet deshalb gleich viel, egal wie viele mitspielen, und das Budget braucht
keinen Term für die Plätze. Gemessen wird also einmal pro Karte und nicht für jede Spielerzahl neu.

### Erst die Kartendaten prüfen

Gemessen wird die Karte, wie sie in der Datei steht. Ist dort etwas kaputt, misst die Kalibrierung
den Fehler mit. Vorher prüfen:

- Jede Linie fährt ihre Strecke ohne Lücke.
- Hin- und Rückrichtung einer Linie halten an denselben Haltestellen.
- Busse haben 85 Plätze, Trams 248, Züge 1.000.
- Jedes Paar aus Wohnort und Arbeitsplatz ist mit Bus und Bahn erreichbar.

Auf Berlin Mitte-West hatte eine Buslinie anfangs gar keine Kanten, eine andere riss in der Mitte,
und jedes Fahrzeug hatte 60 Plätze. Sechs der 36 Paare hatten dadurch keine ÖPNV-Verbindung, und eine
Runde ganz ohne Auto kostete fast doppelt so viel wie heute. `./manage.py check_map karte.json`
prüft das und mehr für jede Karte, die Regeln stehen in `backend/maps/checks.py`.

### Mit Testrunden messen

Gemessen wird mit Testrunden, nicht mit einem Play-Test. Ein Play-Test zeigt, wie sich ein Spiel
anfühlt, aber nicht, wie viel Verkehr eine Karte trägt.

Für eine fertige Karte erledigt das ein Befehl: `./manage.py calibrate_map karte.json --speed 19`
spielt die Runden in einer Wegwerf-Datenbank, mit den Wegen, die der Router des Spiels findet, sucht
die Pendlerzahl nach der Regel aus `docs/kalibrierung.md`, Abschnitt 12, und zeigt, was das Budget
pro Person auf der Karte reicht (Abschnitt 13). Er braucht Node und `npm ci` in `frontend/`. Von Hand
geht es so:

1. Die Karte auf einer lokalen Instanz hochladen (`devops/dev.sh up`), nicht auf dem Server, auf dem
   gespielt wird.
2. Ein Spiel mit wenigen Plätzen anlegen. Kartenänderungen nicht zulassen, damit jede Runde auf der
   Basisversion fährt, und das CO₂ pro Person auf 6,0 kg stellen, damit das Spiel nicht vorzeitig
   endet.
3. Bei „Menschen pro Gruppe“ den Kandidaten eintragen: Pendler ÷ (Plätze × Gruppen pro Platz).
4. Die Plätze an der Leitstelle anlegen und für jede Gruppe Verkehrsmittel und Weg selbst wählen.
5. Nach jeder Runde CO₂ und mittlere Fahrzeit ablesen. Unter Last streut eine Runde um 16–18 %,
   also mehrere Runden mit derselben Wahl spielen und mitteln.

Wer programmiert, kann eine fertige Runde auch mit `TrafficSimulator` aus
`backend/game/simulation.py` und festem Seed nachspielen und über beliebig viele Seeds mitteln.
Die Simulation selbst, `LinkQueueEngine` in `backend/sim/linkqueue.py`, braucht dafür keine
Datenbank: Sie rechnet eine Runde aus einem Szenario (`backend/sim/scenario.py`), von Hand gebaut
oder aus einer gespielten Runde übernommen (`.scenario` an jedem `TrafficSimulator`).

Weil sich der Maßstab aus der Platzzahl ergibt, reichen dafür wenige Plätze. Auf Berlin Mitte-West
ergeben zwei Plätze fast dieselbe Runde wie sechzehn (gemessen mit 6.400 Pendlern, der Zahl bis
Oktober 2026):

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

Die Pendlerzahl soll so gewählt sein, dass ein Morgen, an dem alle Auto fahren, ungefähr so langsam
ist wie der Berufsverkehr in der echten Stadt.

1. Die mittlere Länge eines Arbeitswegs auf der Karte bestimmen. Auf Berlin Mitte-West sind es
   7,66 km.
2. Nachschlagen, wie schnell der Berufsverkehr in der abgebildeten Stadt fließt, mit Quelle. Für
   Berlin sagt der TomTom Traffic Index (Daten von 2025, 15. Ausgabe, Januar 2026): 19,0 km/h im
   morgendlichen Berufsverkehr, für 7,66 km also 24 Minuten.
3. Testrunden spielen, in denen alle Auto fahren, und die Pendlerzahl anpassen, bis die Autos im
   Mittel so schnell fahren.

`calibrate_map` sucht die Zahl selbst und braucht dafür nur das Tempo aus Schritt 2 (`--speed`).

Das Ergebnis ist nicht die echte Pendlerzahl des Stadtteils, die ist viel höher. Der Graph bildet
aber nur die Hauptachsen ab, und gesucht ist, wie viel Verkehr **diese Achsen** tragen. Für Berlin
Mitte-West sind es **6.800 Pendler**: Fahren alle Auto, fahren sie morgens 19,4 km/h, und ein Weg
dauert 23,7 Minuten statt 10,0 bei freier Fahrt.

Die Zahl ist ein Anker, keine Statistik, und das aus zwei Gründen:

- **Sie zählt Autos, keine Menschen.** TomTom misst den Verkehr, während der Rest der Stadt schon in
  der U-Bahn und auf dem Rad sitzt. Die 6.800 sind die Autonachfrage, die auf diesem Graphen den
  Berufsverkehr ergibt, wenn alle fahren. Mit Berlins echter Verkehrsmittelwahl zu eichen, geht
  nicht: Die Karte hat mehr Busse und weniger Schiene als die Stadt.
- **Sie steht für die Ampeln mit.** Das Modell hat keine. Seine freie Fahrt ist das Tempolimit,
  46,1 km/h, TomToms Berlin fährt nachts um 30. Wer das Tempo trifft, lässt den Stau die Ampeln
  mittragen: Ein Weg dauert 2,4-mal so lang wie bei freier Fahrt, in der Stadt das 1,59-fache. Auf
  das Stauniveau geeicht statt auf das Tempo, wären es 4.800 Pendler.

Danach prüfen, ob der Stau von den Entscheidungen abhängt. Darum geht es im Spiel. Dafür Runden mit
weniger Autos spielen, etwa mit drei Vierteln, der Hälfte und einem Viertel:

| Autoanteil | pro Person | Runde gesamt |      Auto |  Fahrplan | Fahrzeit Auto hin / zurück |
| ---------: | ---------: | -----------: | --------: | --------: | -------------------------: |
|      100 % |    4,17 kg |    28.379 kg | 21.080 kg |  7.299 kg |            23,7 / 22,4 min |
|       75 % |    3,16 kg |    21.498 kg | 14.773 kg |  6.725 kg |            16,8 / 15,4 min |
|       50 % |    2,41 kg |    16.420 kg |  9.122 kg |  7.299 kg |            11,6 / 11,7 min |
|       25 % |    1,96 kg |    13.340 kg |  4.449 kg |  8.890 kg |            10,2 / 10,3 min |
|        0 % |    1,53 kg |    10.402 kg |         — | 10.402 kg |                          — |

![Was eine Runde kostet, nach Autoanteil](../backend/template/hintergrund/runde.svg)

_Jeder Balken ist eine Runde mit Hin- und Rückweg: Auto in Blau, der Fahrplan in Gelb. Der Fahrplan
fährt so oder so und wird teurer, je mehr Leute einsteigen, weil die Linien fahren, bis der Letzte
zu Hause ist; das Auto bestimmt, wie lang der Balken wird. Die Linie ist das Budget einer Runde bei
normal, 2,4 kg × 6.800 Pendler = 16.320 kg._

Auf Berlin Mitte-West ist der Stau weg, wenn die Hälfte umsteigt. Stau ist ein Schwellenphänomen
dicht an der Kapazität: Knapp darunter fließt der Verkehr, knapp darüber staut er. Bleibt der Stau
auch bei halbem Autoanteil, ist die Pendlerzahl zu hoch. Staut es schon dann kaum, wenn alle Auto
fahren, ist sie zu niedrig.

Beim ÖPNV zeigt sich zu viel Nachfrage als Wartezeit. Auf Berlin Mitte-West brauchen Bus und Bahn 32
bis 43 Minuten, und die Wartezeit an der Haltestelle wächst von 21 auf 44 Minuten, je mehr Leute
umsteigen, weil die Fahrzeuge voll sind.

Gemessen mit `calibrate_map` auf der Basisversion von Berlin Mitte-West, auf Postgres: 72 Gruppen zu
je 94 Menschen, gleichmäßig über die 36 Paare aus Wohnort und Arbeitsplatz verteilt, jedes Paar
fährt seinen Anteil Auto und der Rest Bus und Bahn, gemittelt über sechs Seeds. Pro Person heißt: die
Runde geteilt durch die 6.800 Pendler, so wie das Budget sie zählt.

### Das Budget

Das Budget ist eine Zahl pro Person und Runde, auf jeder Karte dieselbe. Ein Budget pro Karte, an
ihr selbst gemessen, ließe jede Stadt gleich schwer aussehen; pro Person ist eine Stadt mit langen
Wegen oder wenig Bus und Bahn von selbst schwerer. Das ist die Lektion, kein Fehler.

**Normal sind 2,4 kg.** So viel kostet eine Runde auf Berlin Mitte-West pro Person, wenn die Hälfte
der Gruppen Auto fährt (2,41 kg), auf den Schritt des Reglers gerundet. Die Zahl ist einmal gemessen
und bleibt, ein Anker für alle Karten. Auf Berlin Mitte-West reicht normal, wenn 49 % der Gruppen
Auto fahren; für eine neue Karte sagt `calibrate_map`, welcher Anteil es dort ist. Der Regler bei
„Spiel anlegen“ geht von 1,0 bis 6,0 kg in Schritten von 0,2, weil auf Berlin 0,5 kg etwa ein Viertel
der Klasse ist, das umsteigt. Das Spiel speichert, mit wie viel Kilo es gespielt wurde.

Gerechnet wird mit den Pendlern der Karte, nicht mit den Menschen, die die Gruppen auf die Karte
bringen (106 × 64 = 6.784). Überschreibt jemand die Menschen pro Gruppe, um eine Runde leichter zu
machen, schrumpft das Budget nicht mit: Der Fahrplan fährt, ob jemand einsteigt oder nicht.

Was das Budget im Spiel bedeutet, zeigen zwei Spiele über sechs Runden: eines, in dem niemand aus dem
Auto steigt, und eines, das sich herunterarbeitet, mit 100 / 75 / 50 / 50 / 25 / 25 % Autoanteil.
Nach unten begrenzt es der Fahrplan, der auch fährt, wenn niemand einsteigt: 1,53 kg pro Person, und
darunter ist keine Runde zu schaffen.

Bei normal sind das 97.920 kg für sechs Runden. Wer durchgehend fährt, ist in Runde 4 raus. Wer sich
herunterarbeitet, kommt auf 109.397 kg, 16,09 kg pro Person gegen 14,4, und überschreitet das Budget
in der letzten Runde. Das liegt am Fahrplan: Die Linien fahren, bis der Letzte zu Hause ist, und je
mehr umsteigen, desto länger sind Leute unterwegs. Mit 2,8 kg käme das zweite Spiel durch. Wer alle
sechs Runden schaffen will, muss bei normal früher umsteigen.

Bis zum 7. Oktober 2026 war das Budget eine Zahl der Karte, auf Berlin Mitte-West 16.000 kg pro
Runde; wie es dahin kam, steht in `docs/kalibrierung.md`.

### Emissionsfaktoren nachrechnen

Die Emissionsfaktoren gelten für alle Karten und stehen in `backend/sim/constants.py`. Jeder gilt
pro Fahrzeugkilometer und muss sich nachrechnen lassen:

| Modus | Faktor         | woher er kommt                                                   |
| ----- | -------------- | ---------------------------------------------------------------- |
| Auto  | 166,8 g/km     | Flottendurchschnitt, eine Person pro Fahrzeug                    |
| Bus   | 1.200 g/Bus-km | ein 12-m-Stadtbus mit ~45 l/100 km Diesel × 2,64 kg CO₂ je Liter |
| Tram  | 1.400 g/Tram-km | 3,9 kWh/Tram-km einer 240-Platz-Niederflurtram (Deiters 2009) × 363 g CO₂/kWh |
| Zug   | 1.500 g/Zug-km | ~4 kWh/Zug-km mit Nebenverbrauchern × 363 g CO₂/kWh (UBA 2024)   |

Nachgerechnet wird über den Verbrauch: Energie pro Fahrzeugkilometer mal CO₂ pro Energieeinheit. So
fiel der Zugfaktor auf, der anfangs bei 3.500 g/Zug-km stand. Das entspricht rund 9,6 kWh pro
Zugkilometer, also einem dieselgeführten Fernzug. Eine Berliner U- oder S-Bahn braucht etwa 4 kWh,
mit dem deutschen Strommix sind das 1.450 g, gerundet 1.500.

Ein falscher ÖPNV-Faktor wiegt schwer, weil der Fahrplan auch fährt, wenn niemand einsteigt. Bei 3.500 g
machte der Fahrplan 39 % einer Runde aus, in der alle Auto fahren; bei 1.500 g waren es 22 %, und
seit die Linien fahren, bis alle zu Hause sind, sind es 25 %. Den Fahrplan kann beim Spielen niemand
abbestellen.

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

Die Pendlerzahl gilt für eine Karte und ein Modell, ebenso der Anteil, den normal auf ihr kauft.
Neu messen, wenn

- sich die Kapazität der Karte ändert: neue Straßen, andere Spuren, neue Linien;
- sich die Nachfrage im Modell ändert. Die Abfahrten streuen heute mit σ = 10 Minuten um die
  Abfahrtsstunde, viel enger als echter Berufsverkehr. Verteilen sie sich breiter, tragen dieselben
  Achsen mehr Pendler;
- der Abend eine eigene Spitze bekommt. Heute ist er ein Abbild des Morgens, mit derselben Streuung
  der Abfahrten; eine andere Spitze trägt dasselbe Netz mit mehr oder weniger Pendlern;
- sich ein Emissionsfaktor ändert oder wie lange die Linien fahren. Dann verschiebt sich, was normal
  auf der Karte kauft — und auf Berlin vielleicht normal selbst.

Danach die Pendlerzahl in die Kartendatei oder in den Admin eintragen, `calibrated` setzen und die
Karte exportieren, damit die Messung mit der Datei mitgeht (`calibrate_map --out` schreibt beides). Die Messungen für Berlin Mitte-West
stehen mit allen Tabellen in `docs/kalibrierung.md` und `backend/game/calibration.py`.
