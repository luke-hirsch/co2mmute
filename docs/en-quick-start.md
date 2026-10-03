# CO2MMUTE - 101

CO2MMUTE is a multiplayer game. It lets groups discover how their daily commute affects the environment. Players control a set of groups (the game calls them _Gruppen_), where each group represents hundreds of people in a city — how many depends on the number of players and groups at their disposal. Players choose the means of transportation for those people. Then the traffic based on those choices is simulated, there and back. If the group exceeds the CO2 limit, the game ends, so choose wisely.

One thing up front: the game itself only speaks German. This guide quotes the buttons as they are written on screen, so you can find them.

## How to Play

This game is a round-based traffic simulation game. Each game has one game host and can have multiple players. You can play this game over the network, locally on one machine, or both at once. To play, you have two options: either visit the official [site](https://co2mmute.stsds.tu-berlin.de/) or [install](../README.md#running-it-locally) the game on your computer or server.

### Signing Up

Let's say you have the landing page of the game open in your browser (this is true for the official website as well as your own installation). To create a game, you need to sign up. Fear not, only the game host needs an account. The players don't have to sign up. Ever. They type in a name and that's all we know about them.

Data we need for signup:

- _username_ ("Benutzername"): we don't care what you call yourself, but this is the name you type in for the login. So make it memorable if you don't use a password manager.
- _email_ ("E-Mail-Adresse"): we will not use your email. This is purely a security feature for you. To reset passwords we just need some way to contact you. That's all. No notifications and definitely no marketing. If you really don't like us having that email, you can make one up. Every address works for one account only, so notyour@email.com is probably taken by now — be creative. But please don't come crying if you can't reset your password then. And the reset mail only goes out if the server can send mail at all; on your own installation that's the `DJANGO_EMAIL_*` settings in `devops/env_template.txt`.
- _password_ ("Passwort"): I really don't know if this needs an explanation. But in case it does: at least 8 characters, with a digit, an uppercase and a lowercase letter and a special character. It also can't be all digits, one of the most common passwords, or too close to your username. OOOOOORRRR just use a freaking password manager that will take care of that for you.

"Angemeldet bleiben" on the login page keeps you logged in after you close the browser. It is off unless you tick it. If your laptop is the one hooked up to the projector, leave it off.

After the login you land on your own page. That's where your games are listed ("Deine Spiele"), where you start a new one ("Neues Spiel anlegen") and where you change your account details, your password or delete your account. Deleting it removes your name and your access and ends every game you have running. The results stay, without your name on them.

### Create A Session

Now that you have an account you can create games. Super. Let's go through each field of the create game form:

#### Basics

- name ("Name des Spiels"): the name of the game. If you plan to host multiple sessions, we would advise you to use a descriptive name. E.g. as a teacher playing it with multiple classes I would just use the class name and the day as the game name. Anything other than that is pure madness.
- lobby password ("Passwort für die Lobby"): the internet has become a dangerous place. If you intend on playing over the internet, you should set a lobby password. Without one, anybody who has the game ID gets in. Depending on the intellect of the people you want to play with, you will have to weigh security against easy to type.
- map select ("Karte"): choose which map you want to play on. Hopefully the selection of maps will grow over time. If the form warns you that nobody measured this map, the people per group and the CO2 budget below are just default numbers, and on a small map both are too high.
- map changes toggle ("Kartenänderungen"): maps can have multiple versions, like versions with shortcuts for cars or additional bus lines. Between rounds, players will vote on those changes. If you don't like that, deselect this and play only with the base version of the map. A map with just one version has nothing to vote on anyway, so there the discussion and the vote drop out on their own.

#### How Many WHAT?!? ("Wie viele unterwegs sind")

- seats ("Plätze insgesamt", 16 by default): how many players do you want to allow? It doesn't matter if they play locally or over the internet, you can't have more players than this. You, the host, don't count.
- groups per person ("Gruppen pro Person", 4 by default): the number of groups each player has to manage. Every group gets its own home and its own workplace on the map, and needs a means of transportation and a route every round.
- people per group ("Menschen pro Gruppe"): you don't pick this one. The map knows how many people commute through it — 6,400 on Berlin Mitte-West — and the form divides them over seats × groups. 16 seats with 4 groups each makes 100 people per group. Fewer seats, more people per group, so the streets carry the same traffic whether 16 or 6 people play. You can type over it, and "Vorschlag übernehmen" puts the computed number back. Don't, unless you know why.

So set the seats to the number of people who will actually play. The number of people per group is fixed when you create the game: if you open 16 seats and 8 people show up, the streets carry half the traffic and the jams never happen.

#### When It Ends ("Wann das Spiel endet")

- rounds ("Runden", 6 by default): how many rounds are played, if the budget lasts that long.
- CO2 budget ("CO₂-Budget (kg)"): how much CO2 the whole class may emit over the whole game. The form suggests what the map thinks a round may cost, times the rounds — 16,000 kg × 6 = 96,000 kg on Berlin Mitte-West. Once it is used up, the game is over. On that map, a class that keeps driving is out in round 4; a class that switches makes it to the last round.

#### More Settings ("Weitere Einstellungen")

Folded away, because a first game doesn't need either of them.

- end after days without play ("Ende nach Tagen ohne Spiel", 30 by default): a game nobody plays for that long ends by itself, paused or not. A day later, the player names are removed.
- chat: the players can write to each other. On by default. You can switch it off now or in the lobby, and mute single players any time.

### Share A Session / Join A Session

#### Local

If you want to play on one machine, you just need to add seats in the lobby ("Platz anlegen", then a name). The host machine is called the _Leitstelle_ in the game. You will take turns while playing and voting.
Creating new seats up to the maximum number of players is possible throughout the complete game session. It is also possible to remove players ("Entfernen"). This is also true for remote players. The rounds they already played stay saved.

#### Remote

Joining a session from a different device can be done by

1. scanning the QR code
2. typing in the game ID ("Spiel-ID") on the landing page or behind "Beitreten" in the header

If the host has set a password, you will need to type that in. Then a name, and you're in the lobby.

Joining only works before the game starts. Once the host presses start, the join page answers "Das Spiel läuft schon". It also refuses when every seat is taken.

#### Late arrivals

Somebody shows up in round 3? Create a seat for them at the Leitstelle, then hand it over to their phone (see below). From then on they play like everybody else.

#### Switch from local to remote or vice versa

The host can pull seats to the host device at any time ("Übernehmen"). This can come in handy if a session was lost on a player's device. The host can also transfer seats to a new device. In other words, the host can park your session on their machine and return it to you any time during the game.

Handing a seat over works with a code ("Platz-Code"): six characters, valid for five minutes and only once. On the new device, open the game, choose "Du warst schon dabei? Sitzung fortsetzen" on the join page and type in the code — or just scan the QR code next to it. A new code makes the old one worthless.

Players can do the same thing themselves: "Auf anderes Gerät" on their round screen gives them a code for their next device. Whichever device redeems a code, the old one is out.

### Controlling The Lobby

The lobby is built to be shown on a projector.

#### invite remote players

- On the upper left, there is the game ID in big letters, the password if you set one, and the QR code. Either show that, or press "Einladung kopieren" and paste the invitation (link, ID and password) wherever your players are.

#### control local players

- you can create seats for local players on the right side ("Plätze"). Seats are limited to the number you have set in the game creation form.
- you can create local seats at any time, before or during the game.
- you can transfer a local seat to a different device by generating a seat code ("Auf anderes Gerät"). This code is only valid for 5 minutes. After that, you will need to create a new one.
- you also can move a session from a remote device to the host device ("Übernehmen"). The player's device drops out of the game the moment you do. This can come in handy in several situations, like
  - a player lost access: the remote player access is handled via a cookie. Cookies in a browser are as long-lived as in the hand of a toddler. If a cookie is lost (private tab closed, different browser), the player can't access the game on their own anymore, and they can't join again once the game runs. Take the seat over to the host device, create a fresh code and you are good to go.
  - temporary disciplinary action. Teachers will love this one. That one little shithead acting up again? Move him to the teacher's desk, confiscate his precious celly, yell a little to assert dominance and continue gaming. After they settle down, reward good behaviour like they are a dog and hand the seat back with a fresh code. Now, I can already feel the blood pumping of a better-than-the-rest educator, who wants to explain to me that this is not how it is done. Yeah yeah yeah..... shut the f\*\*k up. Training kids like dogs is the secret sauce and you know it. After all, this [chapter](#controlling-the-lobby) is called "Controlling The Lobby".
- right in that alley, you also can mute a player in the chat ("Stummschalten"). They can still read along, and you can lift it any time.

#### chat

- the chat tells everyone when players have joined, left or been removed
- you can communicate with remote players
- you can switch the chat off in the lobby ("Einstellungen" → Chat), before the game starts. After the start the switch is gone; mute single seats instead
- messages disappear after two hours

### Hosting The Game

- check the seat list: everybody who should play has a seat, either on their own device or at the Leitstelle
- press "Spiel starten". It needs at least one seat taken
- from now on, nobody joins by the game ID anymore. Late arrivals go through you

#### Choosing transportation

Every player sees their groups, each with a home ("zu Hause") and a destination ("Ziel"), and the map. For every group they pick one of four ways to get there:

- car ("Auto"): "schnellste" (fastest), "kürzeste" (shortest) or "sparsamste" (least CO2). Fastest and least CO2 know the jams of the last round
- public transport ("Bus & Bahn"): "schnellste", "wenig umsteigen" (few changes) or "ohne Bus" (no bus)
- bike ("Fahrrad"): up to 15 km
- walking ("zu Fuß"): up to 5 km. That is about an hour either way. Anything beyond that is lunacy

The way home is found automatically, with the same means of transportation. If a group gets to work but not back home, the player has to pick something else.

On the map, the thicker and more amber a street is, the slower it was in the last round. Once every group has a route, "Losfahren" sends it off.

There is no timer. The round runs once everybody has sent their choice, so the slowest player decides how long a round takes. If somebody has left for good, remove their seat and the round goes on without them.

Seats at the Leitstelle play one after the other: press "Spielen" next to a seat, and a curtain comes up ("… ist dran"). Hand the machine over, and only then press "Los" — otherwise the room sees everything. When they're done, "Nächster Platz".

#### Evaluating The Round

When the last choice is in, the round is simulated ("Die Runde wird gefahren …"). That takes a moment. Then everybody sees the same thing:

- the replay ("Hin und zurück"): the way to work and the way home in two minutes. One dot is ten people. Dots that stand still are stuck in traffic. You can skip it
- the table: CO2, cost and time for every player, and the round's total. "Zahlen anzeigen" switches between one person and all commuters ("alle Pendler")
- "Wie wird gerechnet?" explains the numbers: why one group is a hundred people, why time is an average and not a sum, what you pay versus what it costs, and why an empty bus still emits CO2

Every player presses "Weiter" when they're done reading. For the seats at the Leitstelle, "Weiter für alle hier" does it in one go. When everybody is through, the game moves on.

#### Discuss Changes

If the map has versions and you allowed map changes, the class now sees the options for the next round — "Was soll sich ändern?". Talk about it. When you think the room is ready, open the vote ("Abstimmung öffnen").

If nothing is up for a vote, this step and the next are skipped and the next round starts straight away.

#### Vote

One vote per seat. On the ballot there are up to two changes and "So lassen" (leave the map as it is). A change can also take back an earlier one. On a keyboard, 1, 2 and 0 vote without anyone seeing where the mouse goes — handy on a projector. Seats at the Leitstelle vote one after another ("Abstimmen"), passing the machine around.

The majority wins and is on the map from the next round on. A tie gets a second chance ("Unentschieden"): everybody decides whether to vote again or leave the map as it is. If the second vote ties too, the map stays as it is. If the tie screen drags on, "Abstimmung beenden" cuts it short, same result.

#### Do It Again

The next round starts on the map you voted for. Same groups, same homes, new choices — and the jams of the last round are now in the router.

#### Pause

The bell rings in the middle of a round? Press "Pause". Every screen says so, nobody can send anything, and the phones stay in the game — even if they lie around for the whole break. "Weiter" carries on.

### Finishing Up

A game ends when

- the CO2 budget is used up
- all rounds are played
- you press "Spiel beenden"
- nobody played it for as many days as you set

Then everybody gets the summary ("Spiel zu Ende"). The last round has no evaluation screen of its own; its numbers are in here. Total CO2 against the budget, round by round, and what the class voted for. Then three lists side by side: least CO2, cheapest, fastest. They never agree, and that is the point. The game does not crown a winner. Who played best is for the class to fight about.

The names stay for a day, so you can talk it through. Then every player becomes "Spieler 1", "Spieler 2" and so on, and the results stay for research.

You can delete a game from your page, but not while it is running — end it first, so the game remembers why it ended. Please don't delete a game that was actually played. Played games are the research data of this project.

## CO2MMUTE Admin

This app comes with a few features that are limited to staff users and superusers. As a little background information: the backend of this game is written in Python. We used Django as a Python web framework for most of the standard functions. If you have deployed the app yourself, you can use the Django command `createsuperuser`. In the terminal or container where you have the app running, you will find the executable called `manage.py`. All you have to do is

```bash
./manage.py createsuperuser
```

and fill out the form. Congrats, you are a superuser now. The exact commands for the native and the container setup are in the [README](../README.md#making-it-playable).

For the official release you will have to contact the current admin for staff access.

### Django Admin

As a staff member or superuser you can access the admin page at `/admin/`. The good thing is, Django ships a built-in admin page, where you have direct access to the database models and entries. You can use the GUI to edit, create or delete certain data points. Now, that being said, this needs to be done carefully and responsibly. The most common use case would be to grant other users staff status. Because only with staff status can you work with the maps of the game in the map editor.
You could also change the maps directly in the database via the admin panel, but that would be very irresponsible and stupid. So don't do it. Especially don't delete a map version there: the rows that were only in that version stay behind in no version at all.
Also the anonymised game data can be accessed here. So all the scientists, put your hands together for fresh research data.

### Map Editor

Now that you know about staff status, we can get ourselves promoted and access the map editor. This tool can be a little overwhelming. So let's go step by step.

#### Map List View

This one is self-explanatory. In this view ("Karten"), you can see all the maps. Currently, there aren't many, because as we will see, creating maps is hard. So before we do that, we look at what we have.

From here you can also upload a map ("Karte hochladen"): either start an empty one or read in a map file. Uploading always creates a new map. It never overwrites an existing one, so a game running on the old map keeps its map. The upload page explains the file format.

#### Map Detail View

If you look at a map, you can see some basic information, like dimensions, seats, graph size, etc.

In the detail view, you can store a map as JSON ("Karte sichern (JSON)"). This will store all versions of the map, the vote between them, and the background image. The file for Berlin Mitte-West is about 1 MB; with big images, a map can get up to 10 MB. In this day and age, that might not sound like much, but it is. Trust me. This file is the only backup a map has, so download it before you change anything.

Next to the JSON download is the delete button. Be careful with this one. Games played on the map keep their results, but the map is gone. And don't delete a map while a game is running on it — nothing stops you.

On the other side, you will find the button to edit the map. More on that later.

In the map itself you can look at nodes and edges.

#### Map Edit View

Now that we learned all there is about the map, we can edit it. The editor needs a big screen. Below 1024 pixels it tells you so, and it means it. It comes in 5 different layers:

- settings ("Einstellungen")
  - Here you can edit the basics, like name, dimensions, scale and seats. For the simulation you can set the base speeds of the map for walking, cycling and driving.
- background image ("Hintergrundbild")
  - This one is rather wonky. You can upload an image to a map. We have used it to enhance realism and uploaded a map image. The graph is then placed on the map.
  - The dials on the side can help you place the image: offset, size and crop. This doesn't work in real time, unfortunately. The picture doesn't move while you turn the dials, so you will need to save to see how your settings affected the image.
  - you can also delete the image there.
- graph ("Graph")
  - The graph layer gives you four more controls in the toolbar: "Auswählen", "Knoten", "Kante" and "Löschen" (select, node, edge, delete). Use these to select what you want to do on the graph. They are pretty self-explanatory.
  - When you select a node you can drag it over the map like you want.
  - in node mode you can add nodes by clicking on the map
  - edges are created in edge mode. Click on two nodes. This will create the edge. Keep in mind, edges are directional. With "Einbahn" (one way), the direction depends on the order in which you clicked the nodes. Or you select "beide Richtungen" (both directions) and it will automatically create both directions.
  - click on an edge to change it: whether it is a street (lanes, speed limit, its own bus lane), a railway, or open to bikes and pedestrians. An edge with neither street nor railway is a path, for bikes and pedestrians only.
  - what you draw in the base version ends up in every version of the map. What you draw in another version ends up in that version and in every combination built on it.
- lines ("Linien")
  - bus and train lines: name, interval in minutes, seats, speed, and the route — click the edges on the map, one after the other. A bus needs a street under every edge, a train a railway.
- versions ("Versionen")
  - here you can create new versions. A version is not a copy of the map. It is the same graph with some things switched on or off. First you select a version you want to build on ("Ausgangsversion"). This is important, because it will influence the voting mechanism.
  - creating a new version is a multi-step thing. In the first step you just create the voting texts: one for voting the change in, one for voting it out again. Because each version can be voted for, and once it is accepted it can be voted against. E.g.: you have a version that creates a new bus line connecting two important nodes. If the players are in favour, this line gets created. In a later round it is possible that this version is up for voting again, but now in reverse. So you will have to write both voting texts.
  - in the second step you make the changes on the map, with the tools from the graph layer and the lines.
  - under "Versionen verwalten" you can update existing versions: the texts, the picture shown on the ballot, and "Verträglich mit" (compatible with). That last one is the ballot. After a round, the players can only vote for versions that are compatible with the one they are playing on.
  - "Kombinationen erzeugen" takes two or more versions and creates every combination of them. A bus lane and a bypass give you "bus lane + bypass" as well.
  - you can't delete a version here.

## Running It Yourself

Everything about installing, running, testing and deploying the game is in the README:

- [running it locally](../README.md#running-it-locally)
- [making a fresh installation playable](../README.md#making-it-playable)
- [tests](../README.md#tests-1)
- [deploying](../README.md#deploying)

What the game computes and why is in the [background](en-background.md).
