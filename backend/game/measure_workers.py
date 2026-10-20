"""Rounds of `game.measure.MapRounds` played side by side, one process each.

A calibration plays six seeds at every step, and the seeds don't depend on
each other; one after another, all of Berlin took two and a half hours on one
core (2026-10-15). Each worker is a fresh Python (spawned: on macOS a forked
one died before its first round and the pool waited for it for ever) that
sets Django up, takes the calibration's settings and its throwaway database,
and builds the same `MapRounds` from the same rows and routes. They all play
in that one database: a round is its own transaction and is rolled back, so
rounds beside each other see nothing of each other, and a seeded round plays
the same in any process.

Nothing here imports Django at the top: a spawned worker imports this module
to find its entry point before Django is set up.
"""

import logging
import multiprocessing
import os

# The settings a calibration changes for its rounds (`calibrate_map`), carried
# into every worker as they stand in the process that starts them.
CARRIED_SETTINGS = (
    "MEDIA_ROOT",
    "ALLOWED_HOSTS",
    "CACHES",
    "CHANNEL_LAYERS",
    "CELERY_TASK_ALWAYS_EAGER",
)

_rounds = None


def _start(
    database, carried, muted_below, map_pk, version_pk, host_pk, routes, per_home
):
    global _rounds
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "co2mmute.settings")
    django.setup()
    from django.contrib.auth import get_user_model
    from django.db import connection
    from django.test.utils import override_settings

    from game.measure import MapRounds
    from maps.models import GameMap, MapVersion

    override_settings(**carried).enable()
    logging.disable(muted_below)
    connection.settings_dict["NAME"] = database
    _rounds = MapRounds(
        GameMap.objects.get(pk=map_pk),
        MapVersion.objects.get(pk=version_pk),
        routes,
        get_user_model().objects.get(pk=host_pk),
        per_home,
    )


def _play(job):
    return _rounds.play(**job)


class Workers:
    """`count` processes playing the rounds of `rounds`, all on the one
    throwaway database."""

    def __init__(self, rounds, count):
        from django.conf import settings
        from django.db import connection

        self.pool = multiprocessing.get_context("spawn").Pool(
            count,
            initializer=_start,
            initargs=(
                connection.settings_dict["NAME"],
                {
                    name: getattr(settings, name)
                    for name in CARRIED_SETTINGS
                    if hasattr(settings, name)
                },
                logging.root.manager.disable,
                rounds.game_map.pk,
                rounds.version.pk,
                rounds.host.pk,
                {
                    "choice": {"carOptimization": rounds.car_optimization},
                    "commutes": rounds.commutes,
                },
                rounds.per_home,
            ),
        )

    def play(self, jobs):
        """`MapRounds.play`'s arguments, one dict a round → their measures, in
        the same order."""
        return self.pool.map(_play, jobs, chunksize=1)

    def __enter__(self):
        return self

    def __exit__(self, kind, *exc):
        if kind is None:
            self.pool.close()
        else:
            self.pool.terminate()
        self.pool.join()
