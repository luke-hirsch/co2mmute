# CO2MMUTE - 101

CO2MMUTE ist ein Mehrspielerspiel. Damit findet ihr gemeinsam heraus, was euer tägliches Pendeln mit der Umwelt macht. Alle Spielenden steuern ein paar Gruppen, und jede Gruppe steht für Hunderte Menschen in einer Stadt — wie viele genau, hängt davon ab, wie viele mitspielen und wie viele Gruppen jede Person hat. Für diese Menschen wählen die Spielenden das Verkehrsmittel. Dann wird der Verkehr simuliert, der daraus entsteht, hin und zurück. Reißt ihr zusammen das CO₂-Budget, ist das Spiel vorbei. Also wähl mit Bedacht.

## So wird gespielt

Das hier ist ein rundenbasiertes Verkehrssimulationsspiel. Jedes Spiel hat eine Spielleitung und kann mehrere Mitspielende haben. Du kannst übers Netz spielen, lokal an einem Rechner oder beides gleichzeitig. Dafür hast du zwei Möglichkeiten: Entweder du gehst auf die offizielle [Seite](https://co2mmute.stsds.tu-berlin.de/), oder du [installierst](../README.md#lokal-starten) das Spiel auf deinem Rechner oder Server.

### Registrieren

Sagen wir, du hast die Startseite des Spiels im Browser offen (das gilt für die offizielle Seite genauso wie für deine eigene Installation). Um ein Spiel anzulegen, musst du dich registrieren. Keine Angst, nur die Spielleitung braucht ein Konto. Die Mitspielenden müssen sich nicht registrieren. Nie. Sie tippen einen Namen ein, und das ist alles, was wir von ihnen wissen.

Was wir für die Registrierung brauchen:

- _Benutzername_: Wie du dich nennst, ist uns egal, aber mit diesem Namen meldest du dich an. Also nimm einen, den du dir merken kannst, wenn du keinen Passwortmanager benutzt.
- _E-Mail-Adresse_: Wir benutzen deine E-Mail nicht. Das ist rein eine Sicherheitsfunktion für dich. Um ein Passwort zurückzusetzen, brauchen wir halt irgendeinen Weg, dich zu erreichen. Das ist alles. Keine Benachrichtigungen und schon gar kein Marketing. Wenn du uns die Adresse wirklich nicht geben willst, kannst du dir eine ausdenken. Jede Adresse geht nur für ein Konto, notyour@email.com ist also vermutlich schon weg — sei kreativ. Aber komm dann bitte nicht heulend an, wenn du dein Passwort nicht zurücksetzen kannst. Und die Mail zum Zurücksetzen geht überhaupt nur raus, wenn der Server Mails verschicken kann; bei deiner eigenen Installation sind das die `DJANGO_EMAIL_*`-Einstellungen in `devops/env_template.txt`.
- _Passwort_: Ich weiß echt nicht, ob das eine Erklärung braucht. Aber falls doch: mindestens 8 Zeichen, mit Ziffer, Groß- und Kleinbuchstaben und einem Sonderzeichen. Außerdem darf es nicht nur aus Ziffern bestehen, keins der häufigsten Passwörter sein und deinem Benutzernamen nicht zu ähnlich. ODEEEEEEER du nimmst einfach einen verdammten Passwortmanager, der das für dich erledigt.

„Angemeldet bleiben“ auf der Anmeldeseite hält dich angemeldet, auch wenn du den Browser schließt. Das ist aus, solange du kein Häkchen setzt. Wenn dein Laptop der am Beamer ist, lass es aus.

Nach der Anmeldung landest du auf deiner eigenen Seite. Da stehen deine Spiele („Deine Spiele“), da legst du ein neues an („Neues Spiel anlegen“), und da änderst du deine Kontodaten, dein Passwort oder löschst dein Konto. Wenn du es löschst, sind dein Name und dein Zugang weg, und jedes Spiel, das bei dir gerade läuft, ist zu Ende. Die Ergebnisse bleiben, nur ohne deinen Namen.

### Ein Spiel anlegen

Jetzt, wo du ein Konto hast, kannst du Spiele anlegen. Super. Gehen wir die Felder im Formular „Spiel anlegen“ einzeln durch:

#### Das Wichtigste

- „Name des Spiels“: Wenn du vorhast, mehrere Spiele zu leiten, nimm einen Namen, der sagt, welches es ist. Als Lehrkraft, die mit mehreren Klassen spielt, würde ich einfach Klasse und Tag nehmen. Alles andere ist purer Wahnsinn.
- „Passwort für die Lobby“: Das Internet ist ein gefährlicher Ort geworden. Wenn du übers Internet spielen willst, solltest du ein Passwort setzen. Ohne kommt jeder rein, der die Spiel-ID hat. Je nachdem, wie helle die Leute sind, mit denen du spielst, musst du Sicherheit gegen „lässt sich leicht tippen“ abwägen.
- „Karte“: Such dir aus, auf welcher Karte du spielen willst. Hoffentlich werden es mit der Zeit mehr. Wenn das Formular warnt, dass diese Karte nie gemessen wurde, sind „Menschen pro Gruppe“ und das CO₂-Budget weiter unten nur Vorgabewerte, und auf einer kleinen Karte sind beide zu hoch.
- „Kartenänderungen“: Karten können mehrere Versionen haben, zum Beispiel eine mit Abkürzungen fürs Auto oder mit zusätzlichen Buslinien. Zwischen den Runden stimmen die Spielenden über diese Änderungen ab. Wenn dir das nicht gefällt, nimm das Häkchen raus, dann wird nur die Grundversion der Karte gespielt. Eine Karte mit nur einer Version hat sowieso nichts zum Abstimmen, da fallen Diskussion und Abstimmung von selbst weg.

#### Wie viele WAS?!? („Wie viele unterwegs sind“)

- „Plätze insgesamt“ (Vorgabe: 16): Wie viele Leute sollen mitspielen dürfen? Egal ob an der Leitstelle oder übers Internet, mehr als das geht nicht. Du als Spielleitung zählst nicht mit.
- „Gruppen pro Person“ (Vorgabe: 4): Wie viele Gruppen jede Person steuern muss. Jede Gruppe bekommt ihr eigenes Zuhause und ihren eigenen Arbeitsplatz auf der Karte und braucht jede Runde ein Verkehrsmittel und eine Route.
- „Menschen pro Gruppe“: Das suchst du dir nicht aus. Die Karte weiß, wie viele Menschen durch sie pendeln — 6.400 auf Berlin Mitte-West — und das Formular verteilt sie auf Plätze × Gruppen. 16 Plätze mit je 4 Gruppen macht 100 Menschen pro Gruppe. Weniger Plätze, mehr Menschen pro Gruppe, damit auf den Straßen gleich viel los ist, ob nun 16 oder 6 spielen. Du kannst die Zahl überschreiben, und „Vorschlag übernehmen“ holt die gerechnete zurück. Lass es, außer du weißt, warum.

Stell die Plätze also auf die Zahl der Leute, die wirklich mitspielen. Wie viele Menschen in einer Gruppe stecken, steht fest, sobald das Spiel angelegt ist: Machst du 16 Plätze auf und es kommen 8, ist auf den Straßen nur halb so viel los, und es staut sich nie.

#### Wann das Spiel endet

- „Runden“ (Vorgabe: 6): So viele Runden werden gefahren, wenn das Budget so lange reicht.
- „CO₂-Budget (kg)“: So viel CO₂ dürfen alle zusammen über das ganze Spiel ausstoßen. Das Formular schlägt vor, was eine Runde laut Karte kosten darf, mal die Runden — 16.000 kg × 6 = 96.000 kg auf Berlin Mitte-West. Ist es aufgebraucht, ist das Spiel vorbei. Fahren auf dieser Karte alle weiter Auto, ist in Runde 4 Schluss; steigen sie um, schaffen sie es bis in die letzte Runde.

#### Weitere Einstellungen

Zugeklappt, weil ein erstes Spiel keine von beiden braucht.

- „Ende nach Tagen ohne Spiel“ (Vorgabe: 30): Ein Spiel, das so lange niemand spielt, endet von selbst, angehalten oder nicht. Einen Tag später werden die Namen der Spielenden entfernt.
- „Chat“: Alle im Spiel können sich schreiben. Vorgabe: an. Du kannst ihn hier oder in der Lobby ausschalten und einzelne Plätze jederzeit stummschalten.

### Ein Spiel teilen / einem Spiel beitreten

#### Lokal

Wenn du an einem Rechner spielen willst, musst du in der Lobby nur Plätze anlegen („Platz anlegen“, dann ein Name). Der Rechner der Spielleitung heißt im Spiel _Leitstelle_. Beim Spielen und beim Abstimmen wechselt ihr euch ab.
Neue Plätze bis zur Höchstzahl kannst du das ganze Spiel über anlegen. Du kannst auch Leute rausnehmen („Entfernen“). Das gilt auch für alle, die von ihrem eigenen Gerät aus spielen. Die Runden, die sie schon gefahren sind, bleiben gespeichert.

#### Übers Netz

Von einem anderen Gerät aus kommst du so in ein Spiel:

1. den QR-Code scannen
2. die Spiel-ID auf der Startseite eintippen, oder hinter „Beitreten“ in der Kopfzeile

Hat die Spielleitung ein Passwort gesetzt, musst du das eintippen. Dann ein Name, und du bist in der Lobby.

Beitreten geht nur, bevor das Spiel startet. Sobald die Spielleitung auf Start drückt, sagt die Seite „Das Spiel läuft schon“. Sie sagt auch Nein, wenn alle Plätze belegt sind.

#### Wer zu spät kommt

Jemand taucht in Runde 3 auf? Leg einen Platz an der Leitstelle an und gib ihn dann aufs Handy weiter (siehe unten). Ab da spielt die Person wie alle anderen.

#### Von lokal zu übers Netz und zurück

Die Spielleitung kann jederzeit Plätze an die Leitstelle holen („Übernehmen“). Das ist praktisch, wenn auf einem Gerät die Sitzung verloren gegangen ist. Die Spielleitung kann Plätze auch auf ein neues Gerät geben. Mit anderen Worten: Die Spielleitung kann deinen Platz bei sich parken und ihn dir jederzeit im Spiel zurückgeben.

Weitergegeben wird ein Platz mit einem Code („Platz-Code“): sechs Zeichen, fünf Minuten gültig und nur einmal. Am neuen Gerät das Spiel öffnen, auf der Beitreten-Seite „Du warst schon dabei? Sitzung fortsetzen“ wählen und den Code eintippen — oder einfach den QR-Code daneben scannen. Ein neuer Code macht den alten wertlos.

Die Spielenden können das auch selbst: „Auf anderes Gerät“ auf ihrem Rundenbildschirm gibt ihnen einen Code für ihr nächstes Gerät. Welches Gerät auch immer einen Code einlöst, das alte ist raus.

### Die Lobby steuern

Die Lobby ist dafür gebaut, am Beamer gezeigt zu werden.

#### Leute übers Netz einladen

- Oben links stehen die Spiel-ID in großen Buchstaben, das Passwort, falls du eins gesetzt hast, und der QR-Code. Zeig das entweder her, oder drück „Einladung kopieren“ und füg die Einladung (Link, ID und Passwort) da ein, wo deine Leute sind.

#### Plätze an der Leitstelle steuern

- Rechts kannst du Plätze an der Leitstelle anlegen („Plätze“). Es gehen nur so viele, wie du beim Anlegen des Spiels eingestellt hast.
- Plätze an der Leitstelle kannst du jederzeit anlegen, vor dem Spiel und mittendrin.
- Einen Platz an der Leitstelle kannst du auf ein anderes Gerät geben, indem du einen Platz-Code erzeugst („Auf anderes Gerät“). Der Code gilt nur 5 Minuten. Danach musst du einen neuen machen.
- Du kannst auch einen Platz von einem Handy an die Leitstelle holen („Übernehmen“). Das Gerät fliegt in dem Moment aus dem Spiel. Das ist in einigen Situationen praktisch, zum Beispiel:
  - Jemand hat keinen Zugang mehr: Der Zugang für Spielende übers Netz läuft über ein Cookie. Cookies im Browser leben ungefähr so lange wie in der Hand eines Kleinkinds. Ist das Cookie weg (privaten Tab zugemacht, anderer Browser), kommt die Person nicht mehr selbst ins Spiel, und neu beitreten geht nicht, sobald das Spiel läuft. Hol den Platz an die Leitstelle, mach einen frischen Code, und gut ist.
  - Vorübergehende Disziplinarmaßnahme. Lehrkräfte werden das lieben. Jemand macht schon wieder Ärger? Platz an die Leitstelle holen, das Handy hat kurz Pause, und weiterspielen. Hat sich die Lage beruhigt, gibt es den Platz mit einem frischen Code zurück. Ich spür jetzt schon, wie irgendeiner pädagogisch besonders wertvollen Lehrkraft der Puls hochgeht, weil sie mir erklären will, dass man das so nicht macht. Jaja jaja..... Immerhin heißt dieses [Kapitel](#die-lobby-steuern) „Die Lobby steuern“.
- In die gleiche Richtung: Du kannst Plätze im Chat stummschalten („Stummschalten“). Mitlesen geht weiter, und aufheben kannst du es jederzeit.

#### Chat

- Der Chat sagt allen, wenn jemand dazugekommen ist, das Spiel verlassen hat oder entfernt wurde.
- Du kannst mit den Spielenden übers Netz schreiben.
- Ausschalten kannst du den Chat in der Lobby („Einstellungen“ → Chat), bevor das Spiel startet. Nach dem Start ist der Schalter weg; schalte dann einzelne Plätze stumm.
- Nachrichten verschwinden nach zwei Stunden.

### Das Spiel leiten

- Schau auf die Liste der Plätze: Jede Person, die mitspielen soll, hat einen Platz, auf dem eigenen Gerät oder an der Leitstelle.
- Drück „Spiel starten“. Dafür muss mindestens ein Platz besetzt sein.
- Ab jetzt kommt niemand mehr über die Spiel-ID rein. Wer zu spät kommt, kommt über dich.

#### Verkehrsmittel wählen

Alle sehen ihre Gruppen, jede mit „zu Hause“ und „Ziel“, und die Karte. Für jede Gruppe gibt es vier Wege hin:

- „Auto“: „schnellste“, „kürzeste“ oder „sparsamste“ Route. Die schnellste und die sparsamste kennen die Staus der letzten Runde.
- „Bus & Bahn“: „schnellste“, „wenig umsteigen“ oder „ohne Bus“.
- „Fahrrad“: bis 15 km.
- „zu Fuß“: bis 5 km. Das ist jeweils etwa eine Stunde. Alles darüber ist Wahnsinn.

Den Rückweg findet das Spiel selbst, mit demselben Verkehrsmittel. Kommt eine Gruppe zur Arbeit, aber nicht wieder nach Hause, muss etwas anderes her.

Auf der Karte gilt: Je dicker und gelber eine Straße, desto langsamer war sie in der letzten Runde. Sobald jede Gruppe eine Route hat, schickt „Losfahren“ sie ab.

Es gibt keinen Timer. Die Runde wird gefahren, sobald alle abgeschickt haben, also bestimmt der oder die Langsamste, wie lange eine Runde dauert. Ist jemand endgültig weg, entfern den Platz, dann geht die Runde ohne diesen Platz weiter.

Plätze an der Leitstelle spielen nacheinander: Drück „Spielen“ neben einem Platz, dann geht ein Vorhang hoch („… ist dran“). Gib den Rechner weiter und drück erst dann „Los“ — sonst sieht der ganze Raum alles mit. Wenn die Person fertig ist: „Nächster Platz“.

#### Die Runde auswerten

Wenn die letzte Wahl drin ist, wird die Runde simuliert („Die Runde wird gefahren …“). Das dauert einen Moment. Danach sehen alle dasselbe:

- die Wiedergabe („Hin und zurück“): der Weg zur Arbeit und der Weg nach Hause in zwei Minuten. Ein Punkt sind zehn Menschen. Punkte, die stehen bleiben, stecken im Stau. Überspringen geht auch.
- die Tabelle: CO₂, Kosten und Zeit für alle Spielenden und die Summe der Runde. „Zahlen anzeigen“ schaltet zwischen einer Person und „alle Pendler“ um.
- „Wie wird gerechnet?“ erklärt die Zahlen: warum eine Gruppe hundert Menschen sind, warum Zeit ein Schnitt ist und keine Summe, was du zahlst und was es kostet, und warum ein leerer Bus trotzdem CO₂ ausstößt.

Alle drücken „Weiter“, wenn sie fertig gelesen haben. Für die Plätze an der Leitstelle macht „Weiter für alle hier“ das in einem Rutsch. Wenn alle durch sind, geht es weiter.

#### Über Änderungen reden

Hat die Karte Versionen und hast du Kartenänderungen zugelassen, sehen jetzt alle, was für die nächste Runde zur Wahl steht — „Was soll sich ändern?“. Redet darüber. Wenn du findest, dass der Raum so weit ist, öffne die Abstimmung („Abstimmung öffnen“).

Was eine Änderung wirklich macht, zeigt „Auf der Karte zeigen“ unter ihr: Straßen, Rad- und Fußwege in Blau, Bus und Bahn in Gelb, und was wegfällt, ist hohl. Das gibt es auf dem Stimmzettel auch.

Steht nichts zur Wahl, fallen dieser Schritt und der nächste weg, und die nächste Runde startet sofort.

#### Abstimmen

Eine Stimme pro Platz. Auf dem Stimmzettel stehen bis zu zwei Änderungen und „So lassen“. Eine Änderung kann auch eine frühere zurücknehmen. Auf einer Tastatur stimmen 1, 2 und 0 ab, ohne dass jemand sieht, wohin die Maus wandert — praktisch am Beamer. Plätze an der Leitstelle stimmen nacheinander ab („Abstimmen“) und geben den Rechner reihum weiter.

Die Mehrheit gewinnt und steht ab der nächsten Runde auf der Karte. Ein Gleichstand bekommt eine zweite Chance („Unentschieden“): Alle entscheiden, ob nochmal abgestimmt wird oder die Karte bleibt, wie sie ist. Steht auch die zweite Abstimmung gleich, bleibt die Karte, wie sie ist. Zieht sich der Gleichstand hin, macht „Abstimmung beenden“ kurzen Prozess, mit demselben Ergebnis.

#### Nochmal

Die nächste Runde startet auf der Karte, für die ihr gestimmt habt. Dieselben Gruppen, dasselbe Zuhause, neue Entscheidungen — und die Staus der letzten Runde stecken jetzt in der Routensuche.

#### Pause

Mitten in der Runde klingelt es? Drück „Pause“. Alle Bildschirme sagen das, niemand kann etwas abschicken, und die Handys bleiben im Spiel — auch wenn sie die ganze Pause über rumliegen. „Weiter“ macht weiter.

### Zum Schluss

Ein Spiel endet, wenn

- das CO₂-Budget aufgebraucht ist,
- alle Runden gefahren sind,
- du „Spiel beenden“ drückst,
- es so viele Tage niemand gespielt hat, wie du eingestellt hast.

Dann bekommen alle die Auswertung („Spiel zu Ende“). Die letzte Runde hat keinen eigenen Auswertungsbildschirm; ihre Zahlen stehen hier. CO₂ insgesamt gegen das Budget, Runde für Runde, und wofür ihr gestimmt habt. Dann drei Listen nebeneinander: am wenigsten CO₂, am günstigsten, am schnellsten. Die sind sich nie einig, und genau darum geht es. Das Spiel kürt keinen Sieger. Wer am besten gespielt hat, darüber dürft ihr streiten.

Die Namen bleiben einen Tag stehen, damit ihr darüber reden könnt. Danach wird aus allen „Spieler 1“, „Spieler 2“ und so weiter, und die Ergebnisse bleiben für die Forschung.

Du kannst ein Spiel auf deiner Seite löschen, aber nicht, solange es läuft — beende es erst, dann weiß das Spiel auch, warum es zu Ende ging. Bitte lösch kein Spiel, das wirklich gespielt wurde. Gespielte Spiele sind die Forschungsdaten dieses Projekts.

## CO2MMUTE-Admin

Ein paar Funktionen der App gibt es nur für Staff und Superuser. Kurz zum Hintergrund: Das Backend des Spiels ist in Python geschrieben. Für die meisten Standardfunktionen haben wir Django benutzt, ein Python-Webframework. Wenn du die App selbst aufgesetzt hast, kannst du den Django-Befehl `createsuperuser` benutzen. Im Terminal oder Container, in dem die App läuft, findest du die ausführbare Datei `manage.py`. Du musst nur

```bash
./manage.py createsuperuser
```

eingeben und das Formular ausfüllen. Glückwunsch, du bist jetzt Superuser. Die genauen Befehle für die native Einrichtung und für den Container stehen im [README](../README.md#spielbereit-machen).

Für die offizielle Seite musst du dich an die aktuelle Administration wenden, um Staff-Zugang zu bekommen.

### Django-Admin

Als Staff oder Superuser kommst du unter `/admin/` auf die Admin-Seite. Das Gute: Django bringt eine eingebaute Admin-Seite mit, auf der du direkt an die Datenbankmodelle und Einträge kommst. In der Oberfläche kannst du Daten bearbeiten, anlegen oder löschen. Das heißt aber auch: Das muss sorgfältig und verantwortungsvoll passieren. Der häufigste Fall dürfte sein, anderen Konten den Staff-Status zu geben. Denn nur mit Staff-Status kannst du im Karteneditor an den Karten des Spiels arbeiten.
Du könntest die Karten auch direkt in der Datenbank über die Admin-Seite ändern, aber das wäre sehr verantwortungslos und dumm. Also lass es. Lösch dort vor allem keine Kartenversion: Die Zeilen, die nur in dieser Version waren, bleiben dann in gar keiner Version zurück.
Außerdem kommst du hier an die anonymisierten Spieldaten. Also alle Forschenden, Hände zusammen für frische Daten.

### Karteneditor

Jetzt, wo du Bescheid weißt über den Staff-Status, können wir uns befördern lassen und in den Karteneditor. Das Werkzeug kann anfangs etwas viel sein. Also Schritt für Schritt.

#### Kartenliste

Die erklärt sich von selbst. Hier („Karten“) siehst du alle Karten. Viele sind es gerade nicht, weil, wie wir gleich sehen, Karten bauen schwer ist. Also schauen wir uns erst an, was wir haben.

Von hier aus kannst du auch eine Karte hochladen („Karte hochladen“): entweder leer anfangen oder eine Kartendatei einlesen. Hochladen legt immer eine neue Karte an. Es überschreibt nie eine vorhandene, ein Spiel auf der alten Karte behält also seine Karte. Wie die Datei aufgebaut ist, steht auf der Seite zum Hochladen.

#### Kartenansicht

Schaust du dir eine Karte an, siehst du ein paar Grunddaten wie Abmessungen, Plätze, Größe des Graphen und so weiter.

In der Kartenansicht kannst du eine Karte als JSON sichern („Karte sichern (JSON)“). Darin stecken alle Versionen der Karte, die Abstimmung zwischen ihnen und das Hintergrundbild. Die Datei für Berlin Mitte-West hat etwa 1 MB; mit großen Bildern kann eine Karte bis zu 10 MB haben. Heutzutage klingt das nach wenig, ist es aber. Glaub mir. Diese Datei ist die einzige Sicherung, die eine Karte hat, also lad sie runter, bevor du irgendwas änderst.

Neben dem JSON-Download ist der Knopf zum Löschen. Vorsicht damit. Spiele auf der Karte behalten ihre Ergebnisse, aber die Karte ist weg. Und lösch keine Karte, während ein Spiel auf ihr läuft — nichts hält dich davon ab.

Auf der anderen Seite findest du den Knopf, um die Karte zu bearbeiten. Dazu gleich mehr.

In der Karte selbst kannst du dir Knoten und Kanten ansehen.

#### Karte bearbeiten

Jetzt, wo wir alles über die Karte wissen, können wir sie bearbeiten. Der Editor braucht einen großen Bildschirm. Unter 1024 Pixeln sagt er dir das, und er meint es ernst. Er hat 5 Ebenen:

- „Einstellungen“
  - Hier änderst du das Grundsätzliche wie Name, Abmessungen, Maßstab und Plätze. Für die Simulation kannst du die Grundgeschwindigkeiten der Karte zu Fuß, mit dem Rad und mit dem Auto einstellen.
- „Hintergrundbild“
  - Die hier ist ziemlich wackelig. Du kannst ein Bild zu einer Karte hochladen. Wir haben damit für mehr Realismus ein Kartenbild hochgeladen. Der Graph liegt dann auf der Karte.
  - Mit den Reglern an der Seite legst du das Bild zurecht: Verschiebung, Größe und Beschnitt. Leider nicht in Echtzeit. Das Bild bewegt sich nicht, während du an den Reglern drehst, du musst also speichern, um zu sehen, was deine Einstellungen mit dem Bild gemacht haben.
  - Löschen kannst du das Bild dort auch.
- „Graph“
  - Die Graph-Ebene gibt dir vier weitere Werkzeuge in der Leiste: „Auswählen“, „Knoten“, „Kante“ und „Löschen“. Damit wählst du aus, was du auf dem Graphen machen willst. Die erklären sich ziemlich von selbst.
  - Wählst du einen Knoten aus, kannst du ihn über die Karte ziehen, wie du willst.
  - Im Knoten-Modus legst du Knoten an, indem du auf die Karte klickst.
  - Kanten legst du im Kanten-Modus an. Klick zwei Knoten an. Das legt die Kante an. Denk dran, Kanten haben eine Richtung. Mit „Einbahn“ hängt die Richtung davon ab, in welcher Reihenfolge du die Knoten angeklickt hast. Oder du wählst „beide Richtungen“, dann werden automatisch beide angelegt.
  - Klick eine Kante an, um sie zu ändern: ob sie eine Straße ist (Spuren, Tempolimit, eigene Busspur), eine Bahn, oder offen für Räder und Fußgänger. Eine Kante ohne Straße und ohne Bahn ist ein Weg, nur für Räder und Fußgänger.
  - Was du in der Grundversion zeichnest, landet in jeder Version der Karte. Was du in einer anderen Version zeichnest, landet in dieser Version und in jeder Kombination, die auf ihr aufbaut.
- „Linien“
  - Bus- und Bahnlinien: Name, Takt in Minuten, Plätze, Geschwindigkeit und die Route — klick die Kanten auf der Karte nacheinander an. Ein Bus braucht unter jeder Kante eine Straße, eine Bahn eine Bahnstrecke.
- „Versionen“
  - Hier legst du neue Versionen an. Eine Version ist keine Kopie der Karte. Es ist derselbe Graph, nur mit ein paar Dingen an- oder ausgeschaltet. Zuerst wählst du die Version aus, auf der du aufbauen willst („Ausgangsversion“). Das ist wichtig, weil es die Abstimmung beeinflusst.
  - Eine neue Version anzulegen geht in mehreren Schritten. Im ersten Schritt schreibst du nur die Abstimmungstexte: einen, um die Änderung einzuführen, und einen, um sie wieder abzuschaffen. Denn über jede Version kann abgestimmt werden, und ist sie angenommen, kann auch dagegen abgestimmt werden. Beispiel: Du hast eine Version, die eine neue Buslinie zwischen zwei wichtigen Knoten anlegt. Sind die Spielenden dafür, kommt die Linie. In einer späteren Runde kann diese Version wieder zur Wahl stehen, nur jetzt andersrum. Also musst du beide Abstimmungstexte schreiben.
  - Im zweiten Schritt änderst du die Karte, mit den Werkzeugen aus der Graph-Ebene und den Linien.
  - Unter „Versionen verwalten“ kannst du vorhandene Versionen ändern: die Texte und „Verträglich mit“. Das Letzte ist der Stimmzettel. Nach einer Runde können die Spielenden nur für Versionen stimmen, die mit der verträglich sind, auf der sie gerade spielen.
  - „Ansehen“ legt eine Version auf die Karte und zeigt, was sie gegenüber der Version ändert, aus der sie gemacht ist — farbig auf der Karte und daneben in Worten. Unter „Verglichen mit“ kannst du sie mit jeder anderen vergleichen. So sieht auch die Abstimmung eine Änderung.
  - „Kombinationen erzeugen“ nimmt zwei oder mehr Versionen und legt jede Kombination aus ihnen an. Aus einer Busspur und einer Umgehungsstraße wird so auch „Busspur + Umgehungsstraße“.
  - Löschen kannst du eine Version hier nicht.

## Selbst betreiben

Alles zum Installieren, Starten, Testen und Deployen steht im README:

- [lokal starten](../README.md#lokal-starten)
- [eine frische Installation spielbereit machen](../README.md#spielbereit-machen)
- [Tests](../README.md#tests)
- [Deployen](../README.md#deployen)

Was das Spiel rechnet und warum, steht im [Hintergrund](de-hintergrund.md).
