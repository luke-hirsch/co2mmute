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