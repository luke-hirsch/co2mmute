# Spielanleitung

## Spielvorbereitung

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
   
### Hintergrundprozesse

6. Karte wrid ins Frontend geladen
7. Spielern wird Heimatkiez zugeordnet
8. Agenten wird Arbeitsort zugeordnet

## Spielablauf

1. Spieler wählen Transportmittel für Agenten aus
   1. Vorschau wird bereitgestellt (auf Basis letzter Runde)
   2. finale Auswahl wird berstätigt
2. Nachdem alle Spieler ihre Auswahl abgeschickt haben, berechnet Server die Wegzeiten und CO$_2$ Emissionen 
   1. Abbruchbedingungen werden gecheckt 
   2. Asuwertung pro Runde wird den Spielern zur Verfügung gestellt
3. Aus einer Liste an möglicher Kartenupdates wird ein Update zur Abstimmung freigegeben.
   1. Spieler stimmen ab.
   
## ToDo

Projectmanagement aufsetzen
Schere Stein Papier prototyp
Spielebeschreibung finalisieren
Models und Tests anlegen 
