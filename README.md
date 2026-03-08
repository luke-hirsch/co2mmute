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
  - ✅ chat enabled nur pausiert, aber wenn wieder aktiviert, gehen alle nachrichten durch
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
  - logout dark mode nicht lesbar

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
- ## Eigenschaften:

# Berechnungen:

- Berechnung der Wegzeiten:
- Idee: Agenten in realistischer Zahl modellieren (Faktor Personen pro Agent in GameSession)
- nach Wahl der Runde werden Personen losgeschickt und bewegen sich auf dem vorher festlegten Weg
- Zeitschritte von ...s in der Simulation --> wieviele befindet sich gleichzeitig auf einer Kante? --> Geschwindigkeit wird für diesen Zeitschritt angepasst
- Bus und Bahn: wenn zuviele Spieler gleichzeitig auf der Zug oder Buskante, dann zufällig für diese Kante Wartezeit (1 bis Frequenz zufällig) oder nicht (Glück gehabt oder Pech)
-

# Berechnung Public Transport aus Sebs ABM

## Erklärung:

- nutzt Dijkstra Algorithmus der von NetworkX zur Verfügung gestellt wird (nx.shortest_path)
- dem Dijkstra kann eine Weight Function für die kanten übergeben werden (hier weight function in travel_time_along_edge)
- schachtelung in travel_time_along_edge von weight function war nötig um implizit der weight function den transport_mode mit übergeben zu können, weil diese den transport_mode braucht um festzulegen wie schnell die kante passiert werden kann --> Bsp.: gleiche Straßenkante mit auto vs. bus ist unterschiedlich
- die weight function gibt letztlich einfach die zeit für das passieren der kante zurück (unter der auslastung der **letzten** runde)
- edges für transport mode (also auch pt) werden in der funktion find_shortest_path vorgefiltert (wobei pt eigentlich alle edges nutzen darf) bevor sie dem shortest_path algorithmus übergeben werden
- weight_function in travel_time_along_edge schaut welcher transport mode ausgewählt wurde und welcher kantentyp vorliegt um festzulegen mit welchem verkehrsmittel (transport_means) und damit mit welcher geschwindigkeit sich der agent bzw. die agenten entlang der kante bewegen
- wenn entlang von straße dann schaut er ob eine buslinie vorhanden ist
- wenn eine buslinie existiert und auch eine busspur  nimmt er als geschwindigkeit einfach die höchstgeschwindigkeit der kante
- wenn keine busspur vorhanden ist dann einfach den speed unter der aktuellen auslastung (dafür gibt es eine funktion die den speed für die aktuelle auslastung berechnet)
- außerdem schaut er, nachdem er den bus_speed festgelegt hat (also ob busspur vorhanden oder nicht) ob der bus_speed größer als der pedestrian_speed ist
- wenn bus langsamer als laufen dann nimmt er pedestrian speed und läuft
- nachdem der nx.shortest_path mithilfe der weight function den kürzesten weg gefunden hat muss nochmal eine funktion für diesen weg die einzelnen transport_means ermitteln (transport mode wäre zum beispiel public transport und transport_means kann dann halt bus, bahn oder laufen sein), weil nx.shortest_path immer entweder nur den weg oder die zeit zurückgeben kann, aber keine zusätzlichen dinge


    def travel_time_along_edge(self, transport_mode):
        def weight_function(node1,node2,attributes):
            '''Travel Time Along Edge

            This function calculates the time for travelling along an edge using the means of transport stated in
            transport_mode. The formula for this is distance / speed. The distance is calculated from the node positions
            of the edge and the speed is either set to RAILWAYSPEEDLIMIT, PEDESTRIANSPEED, BIKESPEED or calculated through 
            use of the function self.streetedge_speed_based_on_load. 
            For cases where a train station is placed at an intersection and the distance therefore is 0 a generic time to reach the 
            platform TRAVELTIMEPLATFORM is assumed
            
            :node1 first node of edge traveled
            :node2 second node of edge traveled
            :edge edge traveled connecting node1 and node2
            :transport_mode means of transport used to travel along the edge
            '''
            # calculate the distance from the positions of the node
            x1, y1 = self.graph.nodes[node1]['xcoord'], self.graph.nodes[node1]['ycoord']
            x2, y2 = self.graph.nodes[node2]['xcoord'], self.graph.nodes[node2]['ycoord']
            distance = math.sqrt(((x2-x1)*self.scale)**2+((y2-y1)*self.scale)**2)
            #print(f"The coordinates are {(x1, y1)} and {x2,y2} and the distance therefore {distance}")
            
            # if nodes are at the same coordinates distance is 0 --> can happen for transfer from walking to train or vice versa  
            if distance == 0:
                nodetype1 = self.graph.nodes[node1]['nodetype'] 
                nodetype2 = self.graph.nodes[node2]['nodetype'] 

                # train station can be at same place as other nodetypes
                if (nodetype1 == "TS" and nodetype2 in ["I", "H", "W"]) or (nodetype1 in ["I", "H", "W"] and nodetype2 == "TS"):
                    # if train station is at same place as other node type agent transfers from or to the station 
                    if transport_mode == Utils.TRANSPORTMODES["Public Transport"]:
                        #print(f"Changing to or from train network. Adding traveltime to plattform of {Utils.TRAVELTIMEPLATFORM}")
                        return Utils.TRAVELTIMEPLATFORM
                    else: 
                    # car should not go to train station 
                        raise ValueError('Transfer to train system only possible in transport mode "PT"')
                else: 
                    # only train stations and another nodetype can be at the same place
                    raise ValueError(f"Nodes of type {nodetype1} and {nodetype2} shouldnt be at identical positions.")
                
            # initialise speed variable
            speed = None

            # read edgetype
            edgetype = attributes.get('edgetype')
            transport_means = None
   
            # determine speed based on edgetype and transport mode
            if edgetype == "T": # trains
                # train ride possbile only in public transport mode
                if transport_mode != "PT": 
                    raise Exception("Can't ride the train if not using public transport!")
                #print(f"Travelling with rail. Speedlimit is {Utils.RAILWAYSPEEDLIMIT}")
                speed = attributes.get("speedlimit")
                transport_means = "Train"
            # pedestrian walk only possible in public transport mode
            elif edgetype == "PW":
                if transport_mode != "PT":
                    raise Exception("Can't use pedestrian walk if not using public transport!")
                #print(f"Travelling by foot. Speed is {Utils.PEDESTRIANSPEED}")
                speed = Utils.PEDESTRIANSPEED
                transport_means = "Walking"
            # street can be used by cars and with public transport (bus or walking)
            elif edgetype == "S":

                # for public transport check if bus line runs along the street
                if transport_mode == "PT":

                    # if no bus line runs along the street simply walk
                    if attributes.get('bus_lines') == []:
                        #print(f"Travelling by foot. Speed is {Utils.PEDESTRIANSPEED}")
                        speed = Utils.PEDESTRIANSPEED
                        transport_means = "Walking"
                    else:
                        # init bus speed
                        bus_speed = 0
                        # if street has bus lane the bus travels at speedlimit (not affected by the other cars on the street)
                        if attributes.get("bus_lane"):
                            bus_speed = attributes.get("speedlimit")
                        # if street has no bus lane bus travels with speed under load of street
                        else:
                            bus_speed = self.streetedge_speed_based_on_load((node1, node2))     

                        # if bus is faster than walking take the bus
                        if bus_speed > Utils.PEDESTRIANSPEED:
                            speed = bus_speed
                            #print(f"Travelling with the bus at {speed}")
                            transport_means = "Bus"
                        # if walking is faster walk! 
                        else:
                            speed = Utils.PEDESTRIANSPEED
                            transport_means = "Walking"
                elif transport_mode == "BK": # bike
                    speed = Utils.BIKESPEED
                    transport_means = "Bike"
                elif transport_mode == "C": # car
                    speed = self.streetedge_speed_based_on_load((node1,node2)) 
                    transport_means = "Car"

            # check if speed has been correctly set
            if speed is None:
                raise ValueError(f"Unknown edgetype {attributes.get('edgetype')} for edge {node1}-{node2})")
            # return traveltime along the edge: distance / speed
            #print(f"For the distance of {distance} between {node1} and {node2} at {speed} it takes {distance/speed} using {transport_means}")
            
            # return distance (km) / speed (kmh) --> returns time as h
            return distance / speed
        
        return weight_function 
    
    def find_shortest_path(self,startnode, endnode,transport_mode):
        """ Find shortest path
        
        Calculate the shortest path between two nodes using a certain transport mode:
        
        PT - Public Transport will inlcude nodes of the type H, W, BS, TS, I and edges of the type S, T, PW 
        C - Car will only include  nodes of I, H and W and edges of S
        BK - Bike will only include edges of type I, H, W and edges of the type S, BK

        The correct subgraph is filtered out using generate_edge_set and the nx.shortest_path routine is used to 
        calculate the shortest path for getting from startnode to endnode. This path is returned as a subgraph. 

        :self 
        :startnode starting node for the trip
        :endnode destination node for the trip
        :transport_mode means of transport choosen for the trip
        """

        # filter edges accoording to selected transport type
        if transport_mode in Utils.TRANSPORTMODES.values():
            edges = self._generate_edge_set(Utils.TRANSPORTMODE_EDGESETS[transport_mode])
        else:
            print(f"The transport mode is: {transport_mode}")
            raise ValueError('Unknown traveltype! Can not find shortest path.')
        
        # create subgraph including only the matching edge types
        subgraph = self.graph.edge_subgraph(edges)

        # check that startnode and endnode are part of the subgraph
        if startnode in subgraph:
            if endnode in subgraph:
                # create instance of closure for weight function of shortest path
                weight_function = self.travel_time_along_edge(transport_mode)
                # calculate shortest path
                path = nx.shortest_path(subgraph, source=startnode, target=endnode, weight=weight_function)
                #print(path)
                # determine which transport type was taken along the path 
                path_with_transport_type = self.path_transport_modes(path, transport_mode)
            else:
                raise ValueError('Can\'t find path. Endnode not part of the subgraph.')
        else:
            raise ValueError('Can\'t find path. Startnode not part of subgraph.')
        
        return path_with_transport_type