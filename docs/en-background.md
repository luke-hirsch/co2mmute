# Background

The idea for the game is based on the [master thesis](./../master_thesis.pdf) by Sebastian
Werblinski. The code here is a complete rewrite rather than a continuation of his prototype, and the
traffic model was rebuilt along the way. This section is what it does and where its numbers come
from.

## Simulation

A round has one question to answer. A few thousand people want to be at work at roughly the same
time, each of them travelling the way a player told them to — what does that morning cost, and how
long does it take?

Congestion has to fall out of that as a **result**. If the model assumed it, the vote between rounds
would be about nothing: the class changes the map, and the map has to answer back.

## Which kind of model, and why this one

There are three levels you can simulate traffic at.

- **Macroscopic** — flow equations over the network, no individual vehicles. Cheap, but there is
  nobody in it, and this game is about a person choosing a mode.
- **Microscopic** — car-following, lane-changing, acceleration per vehicle. Every parameter needs
  data nobody has for a hand-drawn game map, and it will not finish while a class waits for it.
- **Mesoscopic** — individual vehicles, but a street is a queue rather than a stretch of road with
  positions on it.

co2mmute is the third. Specifically it is a **link queue model**, the same family MATSim uses — Kai
Nagel's line of work, at the same institute. That lineage is the reason to prefer it over a
hand-tuned BPR curve: it is a published model somebody can look up and argue with, not a formula
fitted until the output looked plausible.

### A link is three numbers

```
free-flow time     t0 = length / speed limit
flow capacity      Q  = 1800 vehicles/h per car lane
storage capacity   S  = 133 vehicles/km per car lane × length
```

1800 veh/h/lane is the saturation flow of an urban lane, the standard figure from the HCM and the
HBS. 133 veh/km/lane is jam density: one vehicle per 7.5 m, bumper to bumper. So a 900 m single-lane
street holds about 120 vehicles standing still and passes about 150 in a five-minute tick.

Lanes are counted as they are on the street, and infrastructure takes from them:

```
car lanes = lanes − (1 if bus lane) − (1 if bike lane)
```

floored at zero. **Zero car lanes is legal**: the street becomes a _gate_, closed to cars, open to
buses, bikes and pedestrians. That is the model's whole answer to "what does a bus lane do" — it
does not slow cars down by a penalty term, it takes a lane away from them and the queue behind
follows.

### One tick

1. Every link is given its budget for the tick: `Q × tick length`.
2. Everyone whose departure minute has come tries to enter their first link.
3. A vehicle may not leave a link before `t0` has passed. The free-flow time is a floor on the
   journey; it can never be faster than the speed limit allows.
4. Then it joins the link's FIFO queue and waits for budget.
5. It may only leave if the **next** link has storage left. If not it stays where it is, and so does
   everything behind it. That is spillback.
6. Repeat within the tick until nothing moves, because a vehicle can cross several short links in
   five minutes.

Congestion is therefore two mechanisms and no formula: a link discharges only `Q` per hour, and a
full link stops the one feeding it. Queues grow backwards through the network the way they do on a
street.

### Nothing can lock arithmetically, so there is no speed floor

A BPR-style model computes a speed from a volume-over-capacity ratio, which means it has to be
stopped from reaching zero — a floor, or the whole round divides by it. A queue model has no such
term. A vehicle is either released or it is not, and there is no speed anywhere on the input side.

The price of that is that it can gridlock for real: a ring of links, each full of vehicles wanting
the next one. A junction that has moved nothing for four consecutive ticks releases anyway, over
storage, and the release is counted. A non-zero `forced_releases` in the tick log is not a bug, but
it is a reason to read the log.

### Speed is an output

This is the difference that matters most when reading a result. A link's mean speed is its length
divided by the traversal times **actually observed on it**, over cars only — a pedestrian takes ten
minutes over a link a car crosses in one, and letting walkers into the mean would report an empty
street as jammed. Nothing anywhere multiplies a free-flow speed by a congestion factor.

So the speed shown on the map, the CO₂ factor applied to a trip and the route preview a player gets
next round are all reading the same measured number.

### Who queues

- **Cars** always.
- **Buses** queue in mixed traffic and free-run on a dedicated bus lane. A bus is 3 car-equivalents
  (PCU), so it takes the room of three cars in the queue it shares with them.
- **Bikes** are in traffic only where they share a street with cars. A bike has a line of its own on
  the link: its own discharge budget of 2000 bikes/h, so a car jam never holds a cyclist up and a
  cyclist never holds a driver up — but it shares the link's _storage_ at 0.2 PCU, which is how a
  thousand cyclists take room away from the cars. It is never refused entry; a full street does not
  turn a cyclist away.
- **Pedestrians** are outside the queue model entirely.

### Public transport runs a timetable

The structural idea is that a line vehicle is an **ordinary vehicle on a synthetic route**. A bus
therefore queues, spills back, weighs 3 PCU and passes a bus gate without a single line of code of
its own.

People actually board it. Riders wait at a stop keyed by line _and_ node — someone waiting for the
M1 does not get on the U7 — board up to free capacity, alight where their route leaves the line, and
wait again at a transfer. The wait is measured and **reported rather than added**: the clock has run
since the minute the person wanted to leave, so standing at the stop is already inside the trip
time. Dwell time is not modelled; a vehicle serves its stop in the instant it arrives.

A line runs whether anybody rides it or not, and that is the point of modelling it at all:

> **Society pays for the timetable.** A line emits `vehicles × line-km × factor`, never divided by
> seats. An empty bus is not clean, and a line nobody rode still costs the round.

A rider's personal share of that is the society total weighted by **person-kilometres**, not split
per head — on a 13 km line a one-stop rider must not carry an end-to-end share when the car beside
them is priced by the kilometre. Weighting that way makes `Σ personal = society` hold exactly.

The consequence a screen has to name: a round's total is the players' own rows **plus** the society
cost of the lines nobody rode.

## CO₂ and cost ride a speed curve

Emissions are not a constant per kilometre. A car in stop-and-go traffic burns fuel it does not
convert into distance, and a car at 130 km/h is fighting drag. The model uses an average-speed
emission factor of the COPERT/HBEFA form:

```
EF(v) = a/v + b + c·v²          grams CO₂ per vehicle-kilometre
```

`a/v` is idling and stop-and-go, a fixed burn spread over fewer kilometres; `c·v²` is aerodynamic
drag; `b` is everything that scales with distance alone. `a` and `b` are **not free parameters** —
they are derived from `c` and two conditions:

```
1.  the curve's minimum sits at 70 km/h   →   a = 2c · v_min³      = 1962.3 g/h
2.  EF(50) = 166.8 g/km, the car's factor →   b = 166.8 − a/50 − c·50²  = 120.4 g/km
```

with `c = 0.0028605`. Fixing it this way means the anchor at 50 km/h holds as an identity, not to
four decimal places, and there is one number to argue about instead of three.

| speed km/h | 10   | 20   | 30   | 40   | 50    | 70    | 100  |
| ---------- | ---- | ---- | ---- | ---- | ----- | ----- | ---- |
| g CO₂/km   | 317  | 220  | 188  | 174  | 166.8 | 162.5 | 169  |
| × the base | 1.90 | 1.32 | 1.13 | 1.04 | 1.00  | 0.97  | 1.01 |

`a/v` diverges as the speed goes to zero, so **the factor is capped at 2.00×** rather than the speed
being floored. A cap is a number a class can hold in its head — "at worst twice as bad" — and it
keeps the diverging term out of the arithmetic. It starts biting below 9.2 km/h.

Two consequences that surprise people:

- **A Tempo-30 street emits about 13 % more per kilometre than a 50 street, even empty.** That is
  real in every average-speed model, and 34 of the shipped map's 82 street edges are 30 zones, so it
  moves the baseline of a real game.
- **Cost rides the same curve at half weight.** Half of the 0.32 €/km is fuel and stop-and-go wear
  and follows the emission factor; the other half — depreciation, insurance, tax — is paid whether
  the car moves today or not. So money caps at 1.50× where CO₂ caps at 2.00×.

Public transport is flat per vehicle-kilometre: 1200 g for a bus, 1500 g for a train. There is no
speed curve on that side, because the vehicle runs to a timetable rather than to traffic.

Beside the cost there is the **fare**: 1.30 € per trip, transfers included, and the out-of-pocket
half of the car's cost. _What you pay_ next to _what it costs_ is the same contrast on both modes,
and the gap between them on the PT side is the subsidy.

### The round is seeded and stochastic

The same choices twice do not give quite the same number, and should not. Each round draws from a
generator seeded off the round, so a round always replays identically — in a test, in a debugger, or
after a worker restart.

There are exactly two dials:

- **Link capacity, drawn once per link per round** (σ = 0.14, clamped to 0.6–1.4×). This is the
  only one that makes round 2 differ from round 1, because per-driver noise averages away over
  thousands of people.
- **Desired speed, drawn once per driver** (σ = 0.12, clamped to 0.7–1.4×), for the spread _within_
  a round. On a multi-lane street the queue is ordered by when each vehicle is ready rather than
  strictly first-in-first-out — which is overtaking, arrived at without a mechanism for it.

Nothing multiplies the _result_ by a random number. The inputs wobble and the model's non-linearity
near capacity amplifies them, which is why the spread has the right shape: about 0.3 % coefficient
of variation in free flow, 16–18 % under load. A jam is unpredictable, an empty road is not.

One detail worth knowing when reading a delay: **delay is measured against the driver's own
free-flow time.** Somebody who chose 45 in a 50 zone is not delayed by anything.

### Units

One agent — a _Fahrgast_ in the interface — stands for `people_per_agent` real commuters, and that
factor is where most unit bugs in this project came from. Two rules:

- A CO₂ or euro figure is **extensive**: it sums over agents and over the people behind each agent.
  Per-person means dividing by both.
- Travel time is **not**. A sum of travel times is not a quantity anybody has, so a mean trip time
  is a mean over agent trips and nothing else.

The factor itself is not a setting anybody picks. See below.

### Calibration

Physics is not the part that needed deciding. 1800 veh/h/lane and 133 veh/km/lane are measurements
somebody else made, and the emission curve's shape follows from its two anchor conditions. What had
to be **chosen** is everything that says how big the world is: how many people are on this map, what
a round may cost, and what one vehicle emits.

Those choices are the calibration, and the method was the same for all of them.

### The method

Not play-testing. A finished round can be replayed under the simulator with a fixed seed, writing
nothing, so a candidate value is swept over the shipped map and read as consequences — mean trip
time, mean delay, CO₂ by mode share — and then held against something outside the game.

Where there is an outside anchor, it decides. Where there is none, the number is chosen for what it
does to a round, and that is said out loud rather than dressed up as a measurement.

### Two numbers belong to the map, not to the code

`district_commuters` and `co2_budget_kg_per_round` sit on the map, not in a constants file. Both are
properties of _this graph_: how much traffic its corridors carry, and what a playable round costs on
its distances and its timetable. Another city is another pair, and a module constant would have
frozen one neighbourhood's measurements into the software. Both travel through the map's JSON export
and come back on import.

For Berlin Mitte-West they are **6400 commuters** and **8000 kg per round**.

### 6400 is what the graph can carry

It is not what the district holds — Berlin Mitte-West has far more commuters than that. But the
graph abstracts a district down to its main corridors, so the population it can carry is the
population **those corridors** carry.

At 6400 with everybody driving, the busiest links run at about 115 % of their flow capacity, and a
7.66 km commute takes 20.4 minutes against 9.5 in free flow. Inner Berlin's morning peak runs at
roughly 24 km/h, which is the same eleven minutes of delay. That is the outside anchor: the number
is tied to a measured city, not to how the game feels.

What it replaced is worth naming, because it shows what uncalibrated looks like. The shipped default
was 1000 people per agent, which for a full class is 64 000 cars on a map with 82 street edges. The
model handled it — no gridlock, no forced releases, everybody arrived — and reported a **298-minute
commute for 7.66 km.** Five hours. The engine was right; the demand was not. For the map to absorb
that traffic it would need roughly five times the lanes it has, and Berlin-Mitte is not a ten-lane
grid.

Congestion stays a consequence of decisions rather than a certainty, which is the lesson the game is
built around:

| car share | round total | mean trip | mean delay |
| --------: | ----------: | --------: | ---------: |
|     100 % |   11 140 kg |  20.4 min |   11.3 min |
|      75 % |    8 616 kg |  13.9 min |    4.8 min |
|      50 % |    6 236 kg |   9.5 min |    0.4 min |
|      25 % |    4 385 kg |   9.5 min |    0.1 min |
|       0 % |    2 449 kg |         — |          — |

Half the class switching removes the jam entirely. That is physically right — congestion is a
threshold phenomenon close to capacity, not a gradient — and it is the point of the exercise.

Those rows were measured before the map data pass further down. The timetable's own floor is 2864 kg
today rather than 2449, and every row with people on a bus is cheaper than it reads here. The shape
is what the table is for.

### The scale is derived, never picked

```
people_per_agent = district_commuters / (seats × agents per seat)
```

A map depicts a place, and a place has a commuter population. The class **divides** that population
between its agents; it does not summon a new one because more students turned up. Holding the
district constant while the seats vary keeps a round the same round:

| seats | agents | people/agent |  car CO₂ | mean trip | mean delay |
| ----: | -----: | -----------: | -------: | --------: | ---------: |
|    16 |     64 |          100 | 8 691 kg |  20.4 min |   11.3 min |
|     8 |     32 |          200 | 8 630 kg |  20.2 min |   11.0 min |
|     4 |     16 |          400 | 8 904 kg |  20.8 min |   11.4 min |
|     2 |      8 |          800 | 8 652 kg |  20.7 min |   11.5 min |

CO₂ within 3 %, delay within half a minute. Pin `people_per_agent` to a fixed number instead and a
half-full class sees **0.4 minutes of delay against 11.3** on the same map, and emits 44 % of the
CO₂ — a different game depending on who came to the lesson.

### The budget is per round

Because the demand is constant, a round costs what it costs however many students play, so the
budget needs no agent term at all:

```
CO₂ budget = the map's budget per round × rounds
```

Over six rounds on this map, a class that never gets out of the car spends 66 840 kg; one that works
its way down — 100 / 75 / 50 / 50 / 25 / 25 % car — spends about 41 000. A budget has to sit between
those two or it is not a budget. 8000 kg a round, 48 000 for six, does: the all-car class runs out
in round 5, and a class that improves finishes with about seven tonnes to spare.

It is not the tightest number that works. It is the roundest number inside the range, because the
class has to be able to hold it in its head.

Those two totals come from the table above and carry its caveat: after the map repair an improving
class spends less, so the budget sits in the range by a smaller margin than it did. It still sits in
it — all-car busts it, an improving class finishes — but it is the number to look at first after the
next play-test.

### The emission factors, and one that was wrong

Each factor is per vehicle-kilometre, and each one has to be checkable by a class that wants to
check it:

| mode  | factor          | where it comes from                                              |
| ----- | --------------- | ---------------------------------------------------------------- |
| car   | 166.8 g/km      | fleet average, one person per vehicle                            |
| bus   | 1200 g/bus-km   | a 12 m city bus at ~45 l/100 km diesel × 2.64 kg CO₂ per litre   |
| train | 1500 g/train-km | ~4 kWh/train-km including auxiliaries × 363 g CO₂/kWh (UBA 2024) |

The train factor is the one worth telling, because it shows what calibration is for. It shipped at
**3500 g/train-km** and nothing in the game looked broken. But 3500 implies about 9.6 kWh per
train-kilometre, which is a diesel mainline train — a Berlin U- or S-Bahn needs about 4, and the
German grid mix turns that into 1450, rounded to 1500.

It mattered far out of proportion to its size, because the timetable runs whether it is ridden or
not. On a map with six train lines that single number was **39 % of an all-car round**; at 1500 it
is 22 %. Before the correction the timetable decided almost four tenths of every round and the class
could do nothing about it. Now 78 % of a round is in their hands.

Two decisions sit inside that one number, and both are about defensibility rather than accuracy:

- **The grid mix, not the operator's green tariff.** It is the conservative figure and the one a
  class can look up.
- **The CO₂ factor was corrected and the cost was not touched.** They come from different sources.
  Moving one to match the other is exactly how two metrics stop agreeing about which mode is
  expensive.

### The randomness was calibrated to a shape, not to a literature value

σ = 0.14 on link capacity was swept over twenty seeds: 0.10 gives 12.7 % variation under load, 0.18
gives 22.1 %, and 0.14 lands on the 16–18 % the model was aiming at.

The traffic literature would suggest something nearer 25 %. That is **deliberately not used.** Over
half of real-world congestion is incidents and weather, and none of that is in this model. Inflating
capacity variance to cover it would put a realistic-looking number on the screen for the wrong
reason, and the model could no longer be explained by what is in it.

Where a mechanism is missing, the honest move is to name the gap, not to tune a parameter until the
output resembles reality. The same rule is why overtaking on multi-lane streets is a queue ordering
rather than a smaller σ: shrinking the spread would have hidden the missing mechanism instead of
building it.

### What calibration cannot fix: the map data

The first calibration pass was measured on a map whose data was broken. One bus line had **no edges
at all** — four stops drawn on the plan and no vehicle that reaches them. Another broke mid-chain
and was being charged society CO₂ for kilometres its vehicles could never drive. Every vehicle of
both modes had 60 seats, so 6400 people forced run after run of a 60-seat U-Bahn.

The effect was that six of the 36 home-and-workplace pairs had no public transport connection at
all. A class that wanted to get out of the car could not, and eleven of 64 agents drove whatever was
decided — 1313 kg the class had no way to avoid. The numbers were correct arithmetic on a map that
did not describe what was on the screen.

Repairing the data changed **nothing** on the car side: 10 103 → 10 150 kg at 100 % car, inside the
1.4 % spread of six seeds, with the same trip time and delay. It changed the reward for switching
completely — a round with nobody in a car costs 3191 kg where it had cost 5936.

So: check the data before the constants. A map file is production data and deserves the same
suspicion as code.

### Doing it again

Replay rounds on the map in question with fixed seeds and read what a candidate does. Do not turn
the values until a play-test feels right — that fits the model to one afternoon.

- `backend/game/calibration.py` — the derivation and every measurement behind the shipped defaults.
- `docs/kalibrierung.md` — the same record in German, with the full before-and-after tables.
- `backend/game/tests/test_join.py` — what each number is _for_, asserted as test cases.

### What is not calibrated

- **Every new map starts at 6400 and 8000.** Those are Berlin Mitte-West's numbers. For a smaller
  map both are too high, and there is nothing that warns you.
- **Departures are drawn σ = 10 minutes** around the departure hour, so practically everybody leaves
  within a twenty-minute window. A real morning peak spreads over an hour and more; at σ = 45 the
  delay in an all-car round falls from 56.9 to 16.5 minutes. That is a model question rather than a
  calibration question, and it is deliberately left open.
- **The evening commute is not simulated**, and both directions of a street share one queue.
  Harmless while everybody drives to work in the morning, wrong the day the return trip is switched
  on.
