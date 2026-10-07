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

from django.test import SimpleTestCase

from sim import (
    PT_FARE_EUR,
    TRAIN_COST_PER_VEHICLE_KM,
    TRAIN_EMISSIONS_G_PER_VEHICLE_KM,
    TRAM_COST_PER_VEHICLE_KM,
    TRAM_EMISSIONS_G_PER_VEHICLE_KM,
    TRAM_PCU,
    Engine,
    Line,
    Link,
    LinkQueueEngine,
    Params,
    Route,
    Scenario,
    Segment,
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
