# CO2MMUTE

A game to simulate different means of transportation and their impact to transportation infrastructure and CO2 Emissions based on the master thesis of Sebastian Werblinski.

# Work in Progress

## Noch zu implementieren
- Game Engine
  - Dijkstra Frontend
  - Dijkstra Backend
  - Zeitberechnung
  - Emissionsberechnung
  - Geldberechnung (?)
  - game/views.py: post game view.
- Maps  
  - map mit background
  - 
- Code kommentieren
- Api Docs
- dark light modus switch
- Idee: anklicken zeigt interval der public transport
- Legende fehlt
  

## Bugs
- kritisch
  - ✅ spieler koennen sich noch einloggen, wenn spiel schon gestartet ist
  - Spiel wartet nicht auf eingaben aller User (Ein user kann mehrere Runden spielen ohne die anderen) 
  - Spiel endet nur nach CO2 Limit und nicht nach Runden
- geht so
  - chat enabled nur pausiert, aber wenn wieder aktiviert, gehen alle nachrichten durch
  - Wenn Spieler das Spiel verlässt muss er aus der Liste verschwinden
    - Aus redis rausnehmen? 
- nicht wichtig
  - jwt geht nicht
  - chat fenster hoizontal scroll 
  - messages an falscher stelle 
  - Karte über Bildrand (abgeschnitten)
  - Man sieht gar nicht die Buttons für die Auswahlmöglichkeiten
  - Evtl Füllbalken vertikal an der Seite 
  - Game Name in eine Zeile mit Logo und Game ID
  - Chat evtl. zu Game Stats? Dann Buttons rechts?
  - Edges lassen sich nicht anklicken




# Game Concept

## Spielanleitung

### Spielvorbereitung

1. Spielleiter registriert sich
2. Spielleiter erstellt Session
   1. Karte auswählen 
   2. Spieleranzahl
   3. Agentenanzahl
   4. CO2 Budget / Spielende definieren
   5. Sessionpassword optional
   6. Kartenupdates ja/nein
3. Spieler registrieren sich bei Session und erhalten temp user daten
4. Spielbeginn durch Spielleiter
   
#### Hintergrundprozesse

6. Karte wrid ins Frontend geladen
7. Spielern wird Heimatkiez zugeordnet
8. Agenten wird Arbeitsort zugeordnet

### Spielablauf

1. Spieler wählen Transportmittel für Agenten aus
   1. Vorschau wird bereitgestellt (auf Basis letzter Runde)
   2. finale Auswahl wird berstätigt
2. Nachdem alle Spieler ihre Auswahl abgeschickt haben, berechnet Server die Wegzeiten und CO2 Emissionen 
   1. Abbruchbedingungen werden gecheckt 
   2. Asuwertung pro Runde wird den Spielern zur Verfügung gestellt
3. Aus einer Liste an möglicher Kartenupdates wird ein Update zur Abstimmung freigegeben.
   1. Spieler stimmen ab.
   

# Netzwerkstruktur

### Knotentypen:

- es gibt folgende Typen:
  - **H**ome
  - **W**ork
  - **B**us **S**tation
  - **I**ntersection
  - **T**rain **S**tation
- jeder Knoten hat einen oder mehrere Typen 
  - Beispiel: Knoten ist Intersection aber auch gleichzeitig Busstation

### Kantentypen:

- übergeordneter Typ **Edge** für Kanten mit folgenden Attributen:
  - Fußgänger erlaubt (Default: ja)
  - Fahrrad erlaubt (Default: ja)
  
- abgeleitete Typen:
  - **S**treet mit zusätzlichen Eigenschaften:
    - Fuß und Fahrradweg optional! --> z.B.: Stadtautobahn auch mgl.
  - **T**rain:
    - in übergeordneter Kante dazu muss Fuß- und Fahrradweg aus!   
    T (Pflicht: Fuß und Fahrrad müssen aus)

### ÖPNV Struktur:

- Bus und Zuglinien = Sammlung der entsprechenden Edges (nach wie vor Metaeigenschaft)
- Eigenschaften:
  - 


# Berechnungen: 


- Berechnung der Wegzeiten:
- Idee: Agenten in realistischer Zahl modellieren (Faktor Personen pro Agent in GameSession)
- nach Wahl der Runde werden Personen losgeschickt und bewegen sich auf dem vorher festlegten Weg
- Zeitschritte von ...s in der Simulation --> wieviele befindet sich gleichzeitig auf einer Kante? --> Geschwindigkeit wird für diesen Zeitschritt angepasst
- Bus und Bahn: wenn zuviele Spieler gleichzeitig auf der Zug oder Buskante, dann zufällig für diese Kante Wartezeit (1 bis Frequenz zufällig) oder nicht (Glück gehabt oder Pech)
- 


