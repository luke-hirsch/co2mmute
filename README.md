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
# UI Color System for co2mmute
# UI Color System for co2mmute

## Primary (Tech Blue)
| Token | Hex |
|-------|------|
| `--color-primary-50`  | <span style= "background-color:#E3F2FD" width=12px>__</span> `#E3F2FD` |
| `--color-primary-100` |  <span style= "background-color:#BBDEFB" width=12px>__</span>  `#BBDEFB` |
| `--color-primary-200` | <span style= "background-color:#90CAF9" width=12px>__</span>  `#90CAF9` |
| `--color-primary-300` | <span style= "background-color:#64B5F6" width=12px>__</span>  `#64B5F6` |
| `--color-primary-400` | <span style= "background-color:#42A5F5" width=12px>__</span>  `#42A5F5` |
| `--color-primary-500` | <span style= "background-color:#1E88E5" width=12px>__</span>  `#1E88E5` |
| `--color-primary-600` | <span style= "background-color:#1565C0" width=12px>__</span>  `#1565C0` |
| `--color-primary-700` |  <span style= "background-color:#0D47A1" width=12px>__</span> `#0D47A1` |
| `--color-primary-800` | <span style= "background-color:#092F6B" width=12px>__</span>  `#092F6B` |
| `--color-primary-900` | <span style= "background-color:#041C3D" width=12px>__</span> `#041C3D` |

---

## Accent
| Token | Hex |
|-------|------|
| `--color-accent` |  <span style= "background-color:#FFB300" width=12px>__</span> `#FFB300` |

---

## Neutrals — Light Mode
| Token | Hex |
|-------|------|
| `--color-bg-body`       |  <span style= "background-color:#F3F4F6" width=12px>__</span> `#F3F4F6` |
| `--color-bg-surface`    | <span style= "background-color:#FFFFFF" width=12px>__</span>  `#FFFFFF` |
| `--color-bg-elevated`   |  <span style= "background-color:#F9FAFB" width=12px>__</span> `#F9FAFB` |
| `--color-border-subtle` |  <span style= "background-color:#E5E7EB" width=12px>__</span> `#E5E7EB` |
| `--color-border-strong` |  <span style= "background-color:#D1D5DB" width=12px>__</span> `#D1D5DB` |
| `--color-text-main`     | <span style= "background-color:#111827" width=12px>__</span>  `#111827` |
| `--color-text-muted`    | <span style= "background-color:#6B7280" width=12px>__</span>  `#6B7280` |
| `--color-text-soft`     | <span style= "background-color:#9CA3AF" width=12px>__</span>  `#9CA3AF` |

---

## Neutrals — Dark Mode
| Token | Hex |
|-------|------|
| `--color-bg-body-dark`       |  <span style= "background-color:#0B1120" width=12px>__</span> `#0B1120` |
| `--color-bg-surface-dark`    | <span style= "background-color:#111827" width=12px>__</span>  `#111827` |
| `--color-bg-elevated-dark`   |  <span style= "background-color:#1F2933" width=12px>__</span> `#1F2933` |
| `--color-border-subtle-dark` |  <span style= "background-color:#1F2937" width=12px>__</span> `#1F2937` |
| `--color-border-strong-dark` | <span style= "background-color:#374151" width=12px>__</span>  `#374151` |
| `--color-text-main-dark`     |  <span style= "background-color:#F9FAFB" width=12px>__</span> `#F9FAFB` |
| `--color-text-muted-dark`    |  <span style= "background-color:#9CA3AF" width=12px>__</span> `#9CA3AF` |
| `--color-text-soft-dark`     |  <span style= "background-color:#6B7280" width=12px>__</span> `#6B7280` |

---

## Semantic Colors

### Success
| Token | Hex |
|-------|------|
| `--color-success-100` | <span style= "background-color:#D1FAE5" width=12px>__</span> `#D1FAE5` |
| `--color-success-500` | <span style= "background-color:#10B981" width=12px>__</span>  `#10B981` |
| `--color-success-700` |  <span style= "background-color:#047857" width=12px>__</span> `#047857` |

### Warning
| Token | Hex |
|-------|------|
| `--color-warning-100` |  <span style= "background-color:#FEF3C7" width=12px>__</span> `#FEF3C7` |
| `--color-warning-500` |  <span style= "background-color:#F59E0B" width=12px>__</span> `#F59E0B` |
| `--color-warning-700` |  <span style= "background-color:#B45309" width=12px>__</span> `#B45309` |

### Danger
| Token | Hex |
|-------|------|
| `--color-danger-100`  |  <span style= "background-color:#FEE2E2" width=12px>__</span> `#FEE2E2` |
| `--color-danger-500`  |  <span style= "background-color:#EF4444" width=12px>__</span> `#EF4444` |
| `--color-danger-700`  |  <span style= "background-color:#B91C1C" width=12px>__</span> `#B91C1C` |
