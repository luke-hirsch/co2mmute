# CO2MMUTE - 101

CO2MMUTE is a multiplayer game. It lets groups discover, how their daily commute behavior impacts the environment. Players controll a set of agents, where each agent represents hundreds (depending on the number of players and agents at their disposal) of people in a city. Players chosse the means of transportation for those people. Then the traffic based on those choices is simulated. If the group exceeds the CO2 limit, the game ends, so choose wisely.

## How to Play

This game is a roundbased traffic simulation game. Each game has one game host and can have multiple players. You can play this game over the network or local on one machine. To play this game you have multiple options. You can either visit the official [site](https://co2mmute.stsds.tu-berlin.de/) or you can [install](#how-to-set-up-the-game-on-your-computerserver) the game on you computer or server.

### Singing Up

Lets say you have the landingpage of the game open in your browser (this is true for the official website as well as your own installation). To create a game, you need to sign up. Fear not, only the game host needs an account. The players don't have to sign up.

Data we need for signup:

- _username_: we don't care how you call yourself, but this is the name you type in for the login. So make it memorable if you don't use a password manager.
- _email_: we will not use your email. This is a pure security feature for you. To reset passwords we just need some kind of way to contact you. That's all. No notification and definitely no marketing. If you really dont like us to have that email, you can use notyour@email.com or any other made up email. But please don't come crying, if you can't reset your password then.
- _password_: In really don't know, if this needs an explanation. But in case it does: Your password should be strong. That means, it should be at least 8 characters long, contain at least one uppercase letter, one lowercase letter. Throw in s special character OOOOOORRRR just use a freaking password manager that will take care of that for you.

### Create A Session

Now that you have an account you can create games. Super. Lets go through each field of the create game form:

#### Basics

- name: the name of the game. If you plan to host multiple sessions, we would advise you to use a descriptive name. E.g. as a teacher playing it multiple classes i would jsut use the class name as the game name. Anthing other than that is pure madness.
- lobby password: now the internet has become a dangerous place. If you intent on playing over the internet, you should set a lobby password. Depending on the intelekt of the people you want to play with you will have to way security with easy to type.
- map select: choose which map you want to play on. Hopefully the selection of maps will grow over time.
- map changes toggle: Maps can have multiple version like versions with short cuts for cars, or additional bus lines. During the game, players will have to vote on those changes. If you dont like that, deselct this and play only with the base version of the map.

#### How Many WHAT?!?

- seats: how many players you want to allow? It doesn't matter if local or over the internet, you can't have more players than this.
- groups per person: the amount of groups the player have to manage.
- people per group: the amount of people in one group.

### Share A Session / Join A Session

#### Local

If yo want to play on one machine, you just need to add seats in the Lobby. You will take turns while playing and voting.
Creating new seats up to the maximum of players is possible through out the complete game session. It is also possible to remove players. THis is also true for remote players.

#### Remote

Joining a session from a different device can be done by

1. scanning the qr code
2. typing in the session id on the join page / landingpage

If the host has set a password, you will need to type that in.

#### Switch from local to remote or vice versa

The host can pull seats to the host device at any time. This can come in handy, if a session was lost on a players device. The host can also transfer seats to a new device. In other words, the host can park your session on their account and return it to you any given time during the game.

### Controlling The Lobby

#### invite remote players

- On the left upper side, there is the game link. you can eigther show the qr code or invite people via the ID

#### controll loacal players

- you can create seats for local players on the right side. Seats are limited to the number you have set in the game creation form.
- you can create local seats at any time.
- you can transfer the local seat to a different device by generating a seat qr code. This code is only valid for 5 minutes. After that, you will need to create a new one.
- you also can move a session from a remote device to the host device. This can come in handy for several situations, like
  - pausing the game: move all seats to the host machine and hit pause game. when resuming, you can move the sessions back to the player devices. This way, no player looses access to the game
  - a player lost access: the remote player access is handled via a cookie. Cookies in a browser are as long lived as in the hand of a toddler. If a cookie is lost, the player can't access the game one their own anymore. Move the session to the host device and create a fresh qr code and you are good to go.
  - temporary disciplinary action. Teachers will love this one. That one little shithead acting up again? Move him to the teachers desk, confiscate his precious celly, yell a little to assert dominance and continue gaming. After they settle down, reward good beahviour like they are a dog and hand out the device with a fresh qr code. Now, I already can feel the blood pumping of a better-than-the-rest educator, who wants to explain to me, that this is not how it is done. yeah yeah yeah..... shut the f\*\*k up. Training kids like dogs is the secret souce and you know it. Afterall this [chapter](#controlling-the-lobby) is called "Controlling The Lobby".
- right in that alley, cou also can mute player for the chat

#### chat

- the chat notifies if players have joined
- you can comunicate with remote players
<!-- currently false statement -->
- you can disable the chat

### Hosting The Game

-

#### Choosing transportation

#### Evaluating The Round

#### Discuss Changes

#### Vote

#### Do It Again

### Finishing Up

## CO2MMUTE Admin

This app comes with a few features that are limited to staff users and superuser. As a little background information: The backend of this game is written in Python. We used Django as a Python Webframework for most of the standard functions. If you have deployed the app yourslef, you can use the Django command `createsuperuser`. In the terminal or container where you have the app running, you will find the executable called `manage.py`. All you have to do is

```bash
./manage.py createsuperuser
```

and fill out the form. Congrats, you are a superuser now.

For the official release you will have to contact the current admin for staff access.

### Django Admin

As a staff member or superuser you can access the commute admin page. The good thing is, Django ships a built-in admin page, where you have direct access to the database models and entries. You can use the GUI to edit, create or delete certain data points. Now, that being said, this needs to be done carefull and responsible. The most common usecase would be to grant other staff members the staff status. Because only with the staff status, you can work with the maps of the game in the map editor.
You could also change the maps directly in the database via the admin panel, but that would be very inresponsible and stupid. So dont do it.
ALso the anonymised game data can be accessed here. So all the scientist put your hands together for fresh research data.

### Map Editor

Now you know about staff status, we cann get ourselfs promoted and access the map editor. This tool can be a little overwhelming. So lets go step by step

#### Map List View

This one is self explanetory. In this view, you can see all the maps. Currently, there aren't much, because as we will see, creating maps is hard. So before we do that, we look at what we have.

#### Map Detail View

If you look at map, you can see some basic information, like dimensions, seats, graph size, etc.

In the detail view, you can store a map as JSON. This will store all Versions of the map a long with the background images. Depending on the map version this json file can be up to 10 MB. In this day and age, that might not sound much, but it is. trust me.

Next to the JSON download is the delete button. Be careful with this one

On the other side, you will find the button to edit the map. More on that later.

In the map itslef you can look at nodes and edges.

#### Map Edit View

Now that we learned all there is about the map, we can edit it. The map editor comes in 5 different layers.

- settings
  - Here you can edit the basics, like name, dimensions,etc. For the simulation you can set the base speeds of the map.
- background image
  - This is one is rather wonky. You can upload images to a map. We have used it to enhance realism and uploaded a map image. The graph is then placed on the map.
  - The dials on the side can help you to place the image. This doesn't work in realtime unfortunatly. So you will need to save and reload to see, how your settings affected the image.
  - you can also delete the image there.
- graph
  - The graph layer gives you three more controls in the layer bar. You can select between "select", "+node", and "+edge". Use these to select what you want to do on the graph. They are pretty self explanatory.
  - When you select a node you can drag it over the map like you want.
  - in +node mode you can add nodes by clicking on the map
  - edges are created in +edge mode. click on two nodes. this will create the edge. Keep in mind, the edges are directional. So the direction depends on the order you have clicked on the nodes.Or you select "both directions" and it will automatically create both directions.
- versions

## How To Set Up The Game On Your Computer/Server

### Install Requirements

### Set Up

#### Local

#### Server

#### TUB

## Technical Overview

## Testing

## Maintance
