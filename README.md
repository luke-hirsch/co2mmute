# CO2MMUTE

A game to simulate different means of transportation and their impact to transportation infrastructure and CO2 Emissions based on the master thesis of Sebastian Werblinski.

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
   

# Design

<svg width="200" height="200" viewBox="0 0 200 200"
     xmlns="http://www.w3.org/2000/svg">
  <path d="M140 40
           A70 70 0 1 0 140 160"
        fill="none"
        stroke="#1E88E5"
        stroke-width="20"
        stroke-linecap="round" />
  <rect x="85" y="85" width="30" height="30"
        fill="#1E88E5"
        rx="4"
        transform="rotate(45 100 100)" />
  <line x1="121" y1="100" x2="165" y2="100"
        stroke="#1E88E5"
        stroke-width="20"
        stroke-linecap="round" />

</svg>



