"""
The engine on its own: a round run from a scenario, with no database.

Everything else that tests the simulation goes through `TrafficSimulator`, which
needs a game, a map and their rows. These build the scenario by hand — which is
what a calibration script will do — and so prove that the engine needs nothing
from the adapter but the scenario and a generator.
"""

import logging
import random
from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import patch

from django.test import SimpleTestCase

from sim import (
    BUS_COST_PER_VEHICLE_KM,
    DEADLOCK_TICKS,
    BUS_EMISSIONS_G_PER_PERSON_KM,
    BUS_EMISSIONS_G_PER_VEHICLE_KM,
    PT_FARE_EUR,
    TRAIN_COST_PER_VEHICLE_KM,
    TRAIN_EMISSIONS_G_PER_PERSON_KM,
    TRAIN_EMISSIONS_G_PER_VEHICLE_KM,
    TRAM_COST_PER_VEHICLE_KM,
    TRAM_EMISSIONS_G_PER_PERSON_KM,
    TRAM_EMISSIONS_G_PER_VEHICLE_KM,
    TRAM_PCU,
    Engine,
    Line,
    Link,
    LinkQueueEngine,
    Params,
    QueuedVehicle,
    Route,
    Scenario,
    Segment,
    Vehicle,
    pt_emissions_g_per_person_km,
)
from sim.linkqueue import HOME_PASS_EARLIEST_TICK

PEOPLE = 200


@contextmanager
def _quietly():
    """The engine logs its progress at INFO; the run should be a wall of dots."""
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        yield
    finally:
        logging.disable(previous)


def _corridor(east: bool = True) -> tuple[Link, ...]:
    """Three nodes 600 m apart, one lane each way, 50 km/h."""
    ends = [(1, 2), (2, 3)] if east else [(3, 2), (2, 1)]
    base = 10 if east else 20
    return tuple(
        Link(
            edge_id=base + i,
            start_node_id=start,
            end_node_id=end,
            distance_m=600.0,
            is_street=True,
            speed_limit_kmh=50,
            lanes=1,
            label=f"{start} → {end}",
        )
        for i, (start, end) in enumerate(ends)
    )


def _route(pk, links, mode="car", line_id=None, transport_mode=None):
    return Route(
        pk=pk,
        agent_id=pk,
        transport_mode=transport_mode or mode,
        segments=tuple(
            Segment(edge_id=link.edge_id, order=order, mode=mode, pt_line_id=line_id)
            for order, link in enumerate(links, start=1)
        ),
        label=f"Gruppe {pk}",
        total_distance_m=600.0 * len(links),
        estimated_time_min=1.5,
    )


def _scenario(routes, links, lines=(), direction="out", people=PEOPLE, std_dev=5):
    return Scenario(
        params=Params(
            people_per_agent=people,
            walk_speed_kmh=5,
            bike_speed_kmh=20,
            default_car_speed_kmh=50,
            departure_std_dev_min=std_dev,
        ),
        links=tuple(links),
        routes=tuple(routes),
        lines=tuple(lines),
        bus_speeds={7: 25},
        train_speeds={9: 20},
        direction=direction,
        title="Testrunde",
    )


def _run(scenario, seed=1, way_home=None):
    engine = LinkQueueEngine(scenario, random.Random(seed))
    with _quietly():
        engine.run_round(way_home=way_home)
    return engine


class EngineWithoutDatabaseTests(SimpleTestCase):
    """A round from a hand-built scenario: no game, no map, no rows."""

    def test_everybody_driving_gets_there_and_is_held_up_on_one_lane(self):
        links = _corridor()
        engine = _run(_scenario([_route(1, links)], links))

        results = engine.agent_results[1]
        self.assertEqual(len(results["trip_times"]), PEOPLE)
        self.assertEqual(results["not_arrived"], 0)
        outcome = engine.outcomes[1]
        # 1.2 km at 50 km/h is 1.44 min at the speed limit; two hundred cars
        # leaving within minutes of each other on one lane queue for it.
        self.assertGreater(outcome.mean_trip_time_min, 1.44)
        self.assertGreater(outcome.co2_g, 0)
        self.assertEqual(engine.pass_total_co2_g, outcome.co2_g)
        self.assertTrue(engine.link_samples)
        self.assertEqual(set(engine.observed_speeds()), {10, 11})
        self.assertEqual(engine.progress_percent(), 100)

    def test_the_same_seed_replays_and_another_does_not(self):
        links = _corridor()
        scenario = _scenario([_route(1, links)], links)

        first = _run(scenario, seed=5).outcomes[1]
        again = _run(scenario, seed=5).outcomes[1]
        other = _run(scenario, seed=6).outcomes[1]

        self.assertEqual(first, again)
        self.assertNotEqual(first, other)

    def test_people_board_a_bus_and_society_pays_for_the_timetable(self):
        links = _corridor()
        bus = Line(
            mode="bus",
            line_id=7,
            name="M7",
            edge_ids=tuple(link.edge_id for link in links),
            interval_min=10,
            capacity=85,
        )
        rider = _route(1, links, mode="bus", line_id=7, transport_mode="public")

        engine = _run(_scenario([rider], links, lines=[bus]))

        line = engine.pt_lines[("bus", 7)]
        self.assertEqual(line.boarded, PEOPLE)
        self.assertAlmostEqual(line.line_km, 1.2)
        self.assertEqual(engine.outcomes[1].paid_eur, PT_FARE_EUR * PEOPLE)
        # Everybody rode the one line, so the riders carry all of it.
        self.assertAlmostEqual(engine.outcomes[1].co2_g, line.society_co2_g)
        self.assertEqual(engine.pass_network_co2_g, line.society_co2_g)

    def test_a_round_trip_runs_the_evening_on_a_fresh_network_after_the_morning(self):
        there, back = _corridor(east=True), _corridor(east=False)
        home = _scenario([_route(2, back)], back, direction="home")

        engine = _run(
            _scenario([_route(1, there)], there),
            way_home=lambda rng: LinkQueueEngine(home, rng),
        )

        self.assertIsNotNone(engine.home_pass)
        self.assertEqual(engine.home_pass.outcomes.keys(), {2})
        self.assertGreaterEqual(
            min(sample.time_tick for sample in engine.home_pass.link_samples),
            HOME_PASS_EARLIEST_TICK,
        )
        self.assertEqual(engine.progress_percent(), 100)
        replay = engine.build_replay()
        self.assertEqual({dot["pass"] for dot in replay["dots"]}, {"out", "home"})
        self.assertIn("THE WAY HOME", engine.sim_log.get_text())

    def test_a_scenario_missing_a_link_it_names_is_refused(self):
        links = _corridor()

        with self.assertRaisesRegex(ValueError, r"\[11\]"):
            LinkQueueEngine(
                _scenario([_route(1, links)], links[:1]), random.Random(1)
            )

    def test_the_engine_is_what_the_game_asks_for(self):
        links = _corridor()
        engine = LinkQueueEngine(_scenario([_route(1, links)], links), random.Random(1))

        self.assertIsInstance(engine, Engine)


class AWalkAfterATrainTests(SimpleTestCase):
    """Off a train and on foot again, in the same minute as getting on.

    A train runs free and covers several stops in one tick, so a rider can
    walk up to the platform, board, ride one stop and get off within a single
    pass over the free-running set. The walker who reached the platform was
    noted to leave that set at the end of the pass; getting off put it back in
    for its walk, and the note then took it out again. Nobody moved it after
    that: it walked for ever, the pass ran to its guard, and every line ran on
    for it. On the built box that was 686 people in one round at 75 % car.
    """

    def test_everybody_who_rides_one_stop_and_walks_on_gets_there(self):
        # The train comes from a station 1 km back, so it reaches the platform
        # in the middle of a tick rather than starting there.
        before = Link(44, 0, 2, 1000.0)
        to_platform = Link(40, 1, 2, 400.0, is_street=True, speed_limit_kmh=50)
        one_stop = Link(41, 2, 3, 200.0)
        beyond = Link(42, 3, 5, 2000.0)
        from_platform = Link(43, 3, 4, 400.0, is_street=True, speed_limit_kmh=50)
        links = (before, to_platform, one_stop, beyond, from_platform)
        train = Line(
            mode="train",
            line_id=9,
            name="S9",
            edge_ids=(44, 41, 42),
            interval_min=1,
            capacity=10_000,
        )
        rider = Route(
            pk=1,
            agent_id=1,
            transport_mode="public",
            segments=(
                Segment(edge_id=40, order=1, mode="walk"),
                Segment(edge_id=41, order=2, mode="train", pt_line_id=9),
                Segment(edge_id=43, order=3, mode="walk"),
            ),
            label="Gruppe 1",
            total_distance_m=1000.0,
            estimated_time_min=10.0,
        )

        engine = _run(_scenario([rider], links, lines=[train]))

        self.assertEqual(engine.non_arrivals, {"unfinished": 0, "stranded": 0})
        self.assertEqual(engine.agent_results[1]["not_arrived"], 0)
        self.assertEqual(len(engine.agent_results[1]["trip_times"]), PEOPLE)


def _rails(*ends, metres=2000.0, first_id=60):
    """Track between the given node pairs, one link each, in that order."""
    return tuple(
        Link(first_id + i, start, end, metres) for i, (start, end) in enumerate(ends)
    )


def _footpath(edge_id, start, end):
    return Link(edge_id, start, end, 400.0, is_street=True, speed_limit_kmh=50)


def _train(links, interval_min=10):
    """Line 9 over the links, at 20 km/h, with room for everybody."""
    return Line(
        mode="train",
        line_id=9,
        name="S9",
        edge_ids=tuple(link.edge_id for link in links),
        interval_min=interval_min,
        capacity=10_000,
    )


def _walk_ride_walk(walk_in, rides, walk_out):
    """Walk to the platform, ride line 9 over `rides`, walk on."""
    return Route(
        pk=1,
        agent_id=1,
        transport_mode="public",
        segments=(
            Segment(edge_id=walk_in.edge_id, order=1, mode="walk"),
            *(
                Segment(edge_id=link.edge_id, order=2 + i, mode="train", pt_line_id=9)
                for i, link in enumerate(rides)
            ),
            Segment(edge_id=walk_out.edge_id, order=2 + len(rides), mode="walk"),
        ),
        label="Gruppe 1",
        total_distance_m=800.0 + sum(link.distance_m for link in rides),
        estimated_time_min=30.0,
    )


def _carried_to_the_end(log) -> list[str]:
    """The warnings for a rider still aboard where its vehicle ends."""
    return [
        call.args[0]
        for call in log.warning.call_args_list
        if "terminus" in str(call.args[0])
    ]


class ALineThatPassesAStopTwiceTests(SimpleTestCase):
    """A line can pass one stop twice, and a vehicle is at one pass at a time.

    Bremen's 94 runs in to Arbeit Lesum and out again past Stader Landstraße;
    the 58 runs from Roland-Center round Huchting and back to Roland-Center;
    Berlin's S41 is a ring. Built from OSM, Bremen had 18 such lines,
    Callenberg 5, all of Berlin 8 (2026-10-14). The engine knew a rider only
    by the node it waits at, so at Stader Landstraße it boarded whichever 94
    came first, also one on its way out that never reaches Arbeit Lesum, and
    carried them to the end of the line. A line that ends where it starts
    goes on round (Lukas, 2026-10-14: "ring can be ring").
    """

    def test_a_rider_boards_only_the_pass_that_still_reaches_its_stop(self):
        # 1 → 2 → 3 and back past 2 to 4: 2 is Stader Landstraße, 3 Arbeit
        # Lesum. Most riders reach 2 while the next train there is one on its
        # way out.
        line = _rails((1, 2), (2, 3), (3, 2), (2, 4), metres=3000.0)
        walk_in, walk_out = _footpath(80, 5, 2), _footpath(81, 3, 6)
        rider = _walk_ride_walk(walk_in, line[1:2], walk_out)

        with patch("sim.linkqueue.logger") as log:
            engine = _run(
                _scenario([rider], (*line, walk_in, walk_out), lines=[_train(line)])
            )

        self.assertEqual(_carried_to_the_end(log), [])
        self.assertEqual(engine.non_arrivals, {"unfinished": 0, "stranded": 0})
        self.assertEqual(len(engine.agent_results[1]["trip_times"]), PEOPLE)

    def test_a_ring_goes_on_round_past_where_it_starts(self):
        # 1 → 2 → 3 → 4 → 1, 2 km each. The rider rides 3 → 4 → 1 → 2, over
        # the point where a run of the timetable ends and the next begins.
        ring = _rails((1, 2), (2, 3), (3, 4), (4, 1))
        walk_in, walk_out = _footpath(80, 5, 3), _footpath(81, 2, 6)
        rider = _walk_ride_walk(walk_in, (ring[2], ring[3], ring[0]), walk_out)

        with patch("sim.linkqueue.logger") as log:
            engine = _run(
                _scenario([rider], (*ring, walk_in, walk_out), lines=[_train(ring)])
            )

        self.assertEqual(_carried_to_the_end(log), [])
        self.assertEqual(engine.non_arrivals, {"unfinished": 0, "stranded": 0})
        # Two walks of 400 m at 5 km/h and 6 km at 20 km/h: nobody is faster.
        # Set down at 1 and walking on from 2, they were 6 minutes faster.
        trips = engine.agent_results[1]["trip_times"]
        self.assertEqual(len(trips), PEOPLE)
        self.assertGreaterEqual(min(trips), 4.8 + 18 + 4.8 - 1e-6)

    def test_getting_off_and_on_the_same_line_at_a_stop_it_passes_twice(self):
        # 1 → 2 → 5 → 3 → 2 → 4. From 3 to 5: ride to 2, get off, and get on
        # the next train there that is on its way in. The router finds that;
        # the two rides, one after the other on one line, read as one, which
        # no train makes.
        line = _rails((1, 2), (2, 5), (5, 3), (3, 2), (2, 4))
        walk_in, walk_out = _footpath(80, 6, 3), _footpath(81, 5, 7)
        rider = _walk_ride_walk(walk_in, (line[3], line[1]), walk_out)

        with patch("sim.linkqueue.logger") as log:
            engine = _run(
                _scenario([rider], (*line, walk_in, walk_out), lines=[_train(line)])
            )

        self.assertEqual(_carried_to_the_end(log), [])
        self.assertEqual(
            [(leg.board_node, leg.alight_node) for leg in engine.route_pt_legs[1]],
            [(3, 2), (2, 5)],
        )
        self.assertEqual(engine.non_arrivals, {"unfinished": 0, "stranded": 0})
        trips = engine.agent_results[1]["trip_times"]
        self.assertEqual(len(trips), PEOPLE)
        self.assertGreaterEqual(min(trips), 4.8 + 12 + 4.8 - 1e-6)


class FirstComeFirstServedTests(SimpleTestCase):
    """Off a bus lane, the bus that got there first goes on first.

    Berlin's X83 leaves its bus lane at Egestorffstraße onto a 45 m street
    with room for one bus, and comes every five minutes, once a tick. Cars
    had filled the street, a bus or two waited at the end of the lane, and
    from then on one bus a tick went on and one came. The engine took the
    buses on lanes and rails in the order of a set, so which one went on was
    arbitrary: one with riders was passed by a later, empty run every tick for
    ~30 h, and every line ran on for its riders (2026-10-15).
    """

    def _round(self, seed):
        lane = Link(1, 1, 2, 1000.0, True, 50, has_dedicated_bus_lane=True)
        short = Link(2, 2, 3, 45.0, True, 50)
        on = Link(3, 3, 4, 1000.0, True, 50)
        feeder = Link(4, 5, 2, 600.0, True, 50)
        walk_in, walk_out = _footpath(80, 6, 1), _footpath(81, 4, 7)
        line = Line(
            mode="bus",
            line_id=7,
            name="X83",
            edge_ids=(1, 2, 3),
            interval_min=5,
            capacity=85,
        )
        rider = Route(
            pk=1,
            agent_id=1,
            transport_mode="public",
            segments=(
                Segment(edge_id=80, order=1, mode="walk"),
                *(
                    Segment(edge_id=edge_id, order=order, mode="bus", pt_line_id=7)
                    for order, edge_id in enumerate((1, 2, 3), start=2)
                ),
                Segment(edge_id=81, order=5, mode="walk"),
            ),
            label="Gruppe 1",
            total_distance_m=2845.0,
            estimated_time_min=20.0,
        )
        drivers = [_route(pk, (feeder, short, on)) for pk in range(10, 16)]
        return _run(
            _scenario(
                [rider, *drivers],
                (lane, short, on, feeder, walk_in, walk_out),
                lines=[line],
                people=40,
            ),
            seed=seed,
        )

    def test_runs_of_a_line_get_to_its_end_in_the_order_they_left(self):
        for seed in range(1, 9):
            with self.subTest(seed=seed):
                engine = self._round(seed)

                runs = sorted(
                    (pt.departure_min, engine.vehicles[vehicle_id].arrived_min)
                    for vehicle_id, pt in engine.pt_by_vehicle.items()
                    if pt.finished
                )
                arrivals = [arrived for _, arrived in runs]
                self.assertEqual(arrivals, sorted(arrivals))
                # Five minutes' walk each way and three of riding: a rider
                # waits for a bus and the street, not for hours.
                self.assertLess(max(engine.agent_results[1]["trip_times"]), 60)


def _with_rails(links, track, lanes=1):
    """The corridor with rails along it, `track` saying where they lie."""
    return tuple(replace(link, tram_track=track, lanes=lanes) for link in links)


def _tram(links, kind="tram", capacity=10_000):
    """The M1 over the corridor, every ten minutes.

    Room for everybody by default, so a rider's time is the wait for the
    timetable and the ride, never a full tram.
    """
    return Line(
        mode="train",
        line_id=9,
        name="M1",
        edge_ids=tuple(link.edge_id for link in links),
        interval_min=10,
        capacity=capacity,
        kind=kind,
    )


class TramTests(SimpleTestCase):
    """Where a tram's rails lie decides whether it waits with the cars.

    Friedrichstraße north, where the M1 and 12 run: the rails are in the one
    car lane, so the tram stands in the cars' queue and the cars behind it
    wait for it. Landsberger Allee: the track runs down the middle beside
    three lanes each way, and the tram passes the jam. "Die Tram bekommt ein
    eigenes Gleis" is the ballot change between the two, and like a Busspur it
    takes a lane from the cars — the last one, on a one-lane street.
    """

    def _engine(self, links, lines=(), routes=None):
        routes = routes if routes is not None else [_route(1, links)]
        return LinkQueueEngine(
            _scenario(routes, links, lines=lines), random.Random(1)
        )

    def test_rails_in_the_car_lane_put_the_tram_in_the_cars_queue(self):
        links = _with_rails(_corridor(), "lane")

        engine = self._engine(links, lines=[_tram(links)])
        state = engine.edge_states[10]

        self.assertTrue(state.rails_in_car_lane)
        self.assertTrue(engine._queues_for_traffic("train", state))
        # The rails take nothing from the cars: they drive on them.
        self.assertEqual(state.car_lanes, 1)

    def test_its_own_track_takes_a_lane_and_runs_free(self):
        links = _with_rails(_corridor(), "own", lanes=2)

        engine = self._engine(links, lines=[_tram(links)])
        state = engine.edge_states[10]

        self.assertFalse(state.rails_in_car_lane)
        self.assertFalse(engine._queues_for_traffic("train", state))
        self.assertEqual(state.car_lanes, 1)

    def test_its_own_track_on_a_one_lane_street_closes_it_to_cars(self):
        links = _with_rails(_corridor(), "own", lanes=1)

        engine = self._engine(links, lines=[_tram(links)])
        state = engine.edge_states[10]

        self.assertEqual(state.car_lanes, 0)
        self.assertFalse(state.open_to_cars)

    def test_rails_beside_or_under_the_street_stay_out_of_the_queue(self):
        """The U2 under Bismarckstraße, the median track on Landsberger Allee."""
        links = _with_rails(_corridor(), "", lanes=2)

        engine = self._engine(links, lines=[_tram(links, kind="")])
        state = engine.edge_states[10]

        self.assertFalse(state.rails_in_car_lane)
        self.assertFalse(engine._queues_for_traffic("train", state))
        self.assertEqual(state.car_lanes, 2)

    def test_the_jam_holds_the_tram_up_only_where_its_rails_lie_in_the_lane(self):
        """The same cars on the same one car lane; only the rails differ.

        1500 cars on one lane is a jam: they take about 13 minutes for 1.2 km
        that is 1.44 at the speed limit. In the lane the tram's riders sit in
        it with them; on its own track they take what the timetable and 20
        km/h give, about 8.5, whatever the cars do.
        """

        def minutes(track, lanes):
            links = _with_rails(_corridor(), track, lanes=lanes)
            drivers = _route(1, links)
            riders = _route(2, links, mode="train", line_id=9, transport_mode="public")
            engine = LinkQueueEngine(
                _scenario([drivers, riders], links, lines=[_tram(links)], people=1500),
                random.Random(3),
            )
            with _quietly():
                engine.run_round()
            self.assertEqual(engine.edge_states[10].car_lanes, 1)
            outcomes = engine.outcomes
            return outcomes[1].mean_trip_time_min, outcomes[2].mean_trip_time_min

        cars, riders = minutes("lane", lanes=1)
        self.assertGreater(cars, 10)
        self.assertGreaterEqual(riders, cars - 1)

        cars, riders = minutes("own", lanes=2)
        self.assertGreater(cars, 10)
        self.assertLess(riders, cars - 3)

    def test_a_tram_takes_a_trams_room_in_the_queue(self):
        """Nothing but the tram on the street, so its length is all there is."""
        rails = _with_rails(_corridor(), "lane")
        other_way = _corridor(east=False)

        engine = _run(
            _scenario(
                [_route(1, other_way)], rails + other_way, lines=[_tram(rails)]
            )
        )

        self.assertEqual(engine.edge_states[10].peak_occupancy_pcu, TRAM_PCU)

    def test_society_pays_a_tram_per_tram_km(self):
        rails = _with_rails(_corridor(), "")
        other_way = _corridor(east=False)

        engine = _run(
            _scenario(
                [_route(1, other_way)], rails + other_way, lines=[_tram(rails)]
            )
        )

        line = engine.pt_lines[("train", 9)]
        self.assertEqual(line.kind, "tram")
        self.assertGreater(line.vehicle_km, 0)
        self.assertAlmostEqual(
            line.society_co2_g, TRAM_EMISSIONS_G_PER_VEHICLE_KM * line.vehicle_km
        )
        self.assertAlmostEqual(
            line.society_cost_eur, TRAM_COST_PER_VEHICLE_KM * line.vehicle_km
        )

    def test_a_train_line_with_no_kind_is_still_a_train(self):
        rails = _with_rails(_corridor(), "")
        other_way = _corridor(east=False)

        engine = _run(
            _scenario(
                [_route(1, other_way)],
                rails + other_way,
                lines=[_tram(rails, kind="")],
            )
        )

        line = engine.pt_lines[("train", 9)]
        self.assertAlmostEqual(
            line.society_co2_g, TRAIN_EMISSIONS_G_PER_VEHICLE_KM * line.vehicle_km
        )
        self.assertAlmostEqual(
            line.society_cost_eur, TRAIN_COST_PER_VEHICLE_KM * line.vehicle_km
        )


def _ring_round(ring, seed, people=200):
    """A square with a ring round it, Ernst-Reuter-Platz in miniature.

    Four corners, a 40 m link between each and the next, one lane, one way
    round; at every corner a street in and a street out, 300 m each. Every
    car drives in at one corner, two links round and out: so the cars on a
    ring link are bound either for the next ring link or out, and a ring
    full of cars each waiting for the next link closes on itself.
    """
    corners = (1, 2, 3, 4)
    links, routes = [], []
    for at, corner in enumerate(corners):
        after = corners[(at + 1) % 4]
        links += [
            Link(100 + corner, corner, after, 40.0, True, 50, ring=ring),
            Link(200 + corner, 10 + corner, corner, 300.0, True, 50),
            Link(300 + corner, corner, 20 + corner, 300.0, True, 50),
        ]
    for at, corner in enumerate(corners):
        after, out = corners[(at + 1) % 4], corners[(at + 2) % 4]
        edge_ids = (200 + corner, 100 + corner, 100 + after, 300 + out)
        routes.append(
            Route(
                pk=at + 1,
                agent_id=at + 1,
                transport_mode="car",
                segments=tuple(
                    Segment(edge_id=edge_id, order=order, mode="car")
                    for order, edge_id in enumerate(edge_ids, start=1)
                ),
                label=f"Gruppe {at + 1}",
                total_distance_m=680.0,
                estimated_time_min=0.8,
            )
        )
    return _run(_scenario(routes, links, people=people), seed=seed)


class RingHasRightOfWayTests(SimpleTestCase):
    """On a ring, whoever is on it goes first.

    A roundabout (sign 215) and a ring square like Ernst-Reuter-Platz: a car
    driving in waits while a car on the ring is bound for the same link
    (StVO §8 1a). Without it, cars driving in take the room on the ring as
    often as the ring's own, the ring's links fill with cars each waiting for
    the next, and only the deadlock escape moves them, one car a link every
    twenty minutes: on the box's seed 106 for 22 hours (2026-10-15).

    The ring here: 2 → 3 → 4 → 2. A street in at 2 from 1, out at 3 to 5
    and at 2 to 6.
    """

    def _engine(self):
        ring = [
            Link(31, 2, 3, 50.0, True, 50, ring=True),
            Link(32, 3, 4, 50.0, True, 50, ring=True),
            Link(33, 4, 2, 50.0, True, 50, ring=True),
        ]
        links = ring + [
            Link(41, 1, 2, 100.0, True, 50),
            Link(51, 3, 5, 100.0, True, 50),
            Link(61, 2, 6, 100.0, True, 50),
            Link(42, 1, 2, 100.0, True, 50, lanes=2),
        ]
        by_id = {link.edge_id: link for link in links}
        chains = {
            1: (41, 31, 51),  # drives in at 2, round to 3, out
            2: (33, 31, 51),  # on the ring, bound for the same link
            3: (33, 61),  # on the ring, out at 2
            4: (32, 33, 31),  # on the ring, bound for the link into 2
            5: (42, 31, 51),  # drives in on two lanes, round to 3
            6: (42, 61),  # drives in on two lanes and straight out at 2
        }
        routes = [
            _route(pk, tuple(by_id[edge_id] for edge_id in chain))
            for pk, chain in chains.items()
        ]
        engine = LinkQueueEngine(_scenario(routes, links), random.Random(1))
        for state in engine.edge_states.values():
            state.release_budget = 10.0
        return engine

    def _place(self, engine, route_pk, segment_index=0, ready_at_min=0.0):
        """A car of route `route_pk` at the end of that route's Nth link."""
        vehicle_id = 1000 + route_pk
        engine.vehicles[vehicle_id] = Vehicle(
            route_pk=route_pk, person_index=0, mode="car", segment_index=segment_index
        )
        state = engine._state_for_segment(route_pk, segment_index)
        state.queue.append(QueuedVehicle(vehicle_id, ready_at_min, 1.0, 0.0))
        state.occupancy_pcu += 1.0
        return state

    def test_a_car_driving_in_waits_for_a_ring_car_bound_for_the_same_link(self):
        engine = self._engine()
        entry = self._place(engine, 1)
        ring = self._place(engine, 2)

        self.assertIsNone(engine._pick_head(entry, tick_end=5.0))
        self.assertEqual(engine._pick_head(ring, tick_end=5.0), (0, False))

    def test_it_goes_when_the_ring_car_leaves_the_ring_here(self):
        engine = self._engine()
        entry = self._place(engine, 1)
        self._place(engine, 3)

        self.assertEqual(engine._pick_head(entry, tick_end=5.0), (0, False))

    def test_it_goes_when_the_ring_car_is_not_through_yet(self):
        engine = self._engine()
        entry = self._place(engine, 1)
        self._place(engine, 2, ready_at_min=7.0)

        self.assertEqual(engine._pick_head(entry, tick_end=5.0), (0, False))

    def test_it_goes_when_the_ring_link_has_sent_all_it_can_this_tick(self):
        engine = self._engine()
        entry = self._place(engine, 1)
        self._place(engine, 2).release_budget = 0.5

        self.assertEqual(engine._pick_head(entry, tick_end=5.0), (0, False))

    def test_a_car_on_the_ring_never_gives_way(self):
        """Round the ring to the link into 2, past a car waiting to drive in
        on it: the ring is the ring's."""
        engine = self._engine()
        ring = self._place(engine, 4)
        self._place(engine, 2)

        self.assertEqual(engine._pick_head(ring, tick_end=5.0), (0, False))

    def test_on_two_lanes_a_car_bound_elsewhere_passes_the_one_giving_way(self):
        engine = self._engine()
        entry = self._place(engine, 5)
        self._place(engine, 6)
        self._place(engine, 2)

        self.assertEqual(engine._pick_head(entry, tick_end=5.0), (1, False))

    def test_giving_way_is_not_being_stuck(self):
        """The ring is moving, so the deadlock escape never pushes a car in."""
        engine = self._engine()
        entry = self._place(engine, 1)
        self._place(engine, 2)
        engine.current_tick = entry.blocked_since_tick + DEADLOCK_TICKS + 1

        self.assertIsNone(engine._pick_head(entry, tick_end=5.0))

    def test_without_its_tag_a_ring_is_a_crossing_like_any_other(self):
        engine = self._engine()
        for state in engine.edge_states.values():
            state.ring = False
        entry = self._place(engine, 1)
        self._place(engine, 2)

        self.assertEqual(engine._pick_head(entry, tick_end=5.0), (0, False))

    def test_a_ring_square_that_locks_without_it_flows_with_it(self):
        """800 cars in a few minutes: without the right of way the square
        stands for hours on these seeds, with it nobody takes a quarter of
        an hour."""

        def worst(engine):
            return max(
                max(result["trip_times"]) for result in engine.agent_results.values()
            )

        for seed in (1, 2, 3):
            with self.subTest(seed=seed):
                plain = _ring_round(ring=False, seed=seed)
                ring = _ring_round(ring=True, seed=seed)

                self.assertGreater(plain.forced_releases, 100)
                self.assertGreater(worst(plain), 8 * 60)
                self.assertEqual(ring.forced_releases, 0)
                self.assertLess(worst(ring), 15)


class TimetableFactorTests(SimpleTestCase):
    """The class pays its share of the timetable, not all of it.

    The lines run the real city's timetable, made for its millions; the class
    is a few thousand of them. `Params.timetable_factor` is the share it pays:
    every vehicle-km's CO2 and cost times the factor, the riders' shares, the
    lines nobody rode and the runs past the timetable alike. The round itself
    does not change, and nor does the ticket.
    """

    def _round(self, factor, mode="bus"):
        links = _corridor()
        bus = Line(
            mode="bus",
            line_id=7,
            name="M7",
            edge_ids=tuple(link.edge_id for link in links),
            interval_min=10,
            capacity=85,
        )
        if mode == "bus":
            gruppe = _route(1, links, mode="bus", line_id=7, transport_mode="public")
        else:
            gruppe = _route(1, links)
        scenario = _scenario([gruppe], links, lines=[bus])
        params = replace(scenario.params, timetable_factor=factor)
        return _run(replace(scenario, params=params))

    def test_the_class_pays_its_share_of_every_vehicle_km(self):
        whole, share = self._round(1.0), self._round(0.25)
        line = share.pt_lines[("bus", 7)]

        self.assertEqual(line.vehicles, whole.pt_lines[("bus", 7)].vehicles)
        self.assertEqual(line.boarded, whole.pt_lines[("bus", 7)].boarded)
        self.assertAlmostEqual(
            line.society_co2_g,
            0.25 * BUS_EMISSIONS_G_PER_VEHICLE_KM * line.vehicle_km,
        )
        self.assertAlmostEqual(
            line.society_cost_eur, 0.25 * BUS_COST_PER_VEHICLE_KM * line.vehicle_km
        )
        self.assertAlmostEqual(share.outcomes[1].co2_g, 0.25 * whole.outcomes[1].co2_g)
        self.assertAlmostEqual(
            share.outcomes[1].cost_eur, 0.25 * whole.outcomes[1].cost_eur
        )
        self.assertAlmostEqual(
            share.pass_network_co2_g, 0.25 * whole.pass_network_co2_g
        )

    def test_the_ticket_is_the_riders_own(self):
        share = self._round(0.25)

        self.assertEqual(share.outcomes[1].paid_eur, PT_FARE_EUR * PEOPLE)

    def test_a_line_nobody_rides_is_shared_too(self):
        whole, share = self._round(1.0, mode="car"), self._round(0.25, mode="car")

        self.assertEqual(share.pt_lines[("bus", 7)].person_km, 0)
        self.assertAlmostEqual(
            share.pass_network_co2_g, 0.25 * whole.pass_network_co2_g
        )
        self.assertAlmostEqual(
            share.pass_total_co2_g - share.outcomes[1].co2_g,
            0.25 * (whole.pass_total_co2_g - whole.outcomes[1].co2_g),
        )

    def test_unless_told_the_class_pays_all_of_it(self):
        links = _corridor()

        self.assertEqual(_scenario([], links).params.timetable_factor, 1.0)

    def test_a_line_says_what_its_riders_emit_at_germanys_occupancy(self):
        """What the factor is measured from: the riders' person-km at UBA's
        g per person-km, against the base timetable as it runs, whole."""
        line = self._round(0.25).pt_lines[("bus", 7)]

        self.assertGreater(line.person_km, 0)
        self.assertAlmostEqual(
            line.average_co2_g, BUS_EMISSIONS_G_PER_PERSON_KM * line.person_km
        )
        self.assertAlmostEqual(
            line.base_co2_g,
            BUS_EMISSIONS_G_PER_VEHICLE_KM * line.base_vehicles * line.line_km,
        )

    def test_germanys_occupancy_by_what_runs_the_line(self):
        """UBA, TREMOD 6.71B, 2024: Linienbus Nahverkehr, Straßen-, Stadt- und
        U-Bahn, Eisenbahn Nahverkehr."""
        self.assertEqual(pt_emissions_g_per_person_km("bus"), 90.0)
        self.assertEqual(pt_emissions_g_per_person_km("tram"), 42.0)
        self.assertEqual(pt_emissions_g_per_person_km("train"), 44.0)
        self.assertEqual(BUS_EMISSIONS_G_PER_PERSON_KM, 90.0)
        self.assertEqual(TRAM_EMISSIONS_G_PER_PERSON_KM, 42.0)
        self.assertEqual(TRAIN_EMISSIONS_G_PER_PERSON_KM, 44.0)
