import pathlib

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

# co2mmute/tests/test_settings.py -> co2mmute/tests -> co2mmute -> backend
BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[2]


class ResolveSecretKeyTests(SimpleTestCase):
    """Guard against booting production on a placeholder SECRET_KEY.

    Player cookie salts derive from SECRET_KEY (settings._salt_base), so a box
    running on a key that is published in this repository has forgeable player
    identities.
    """

    def _resolve(self, env_value, *, debug):
        from co2mmute.conf import resolve_secret_key

        return resolve_secret_key(env_value, debug=debug)

    # --- DEBUG on: never block the developer ---

    def test_debug_falls_back_to_dev_key_when_unset(self):
        from co2mmute.conf import DEV_SECRET_KEY

        self.assertEqual(self._resolve(None, debug=True), DEV_SECRET_KEY)
        self.assertEqual(self._resolve("", debug=True), DEV_SECRET_KEY)

    def test_debug_still_prefers_a_real_key_when_given(self):
        key = "x" * 60
        self.assertEqual(self._resolve(key, debug=True), key)

    # --- DEBUG off: refuse anything that is not a real key ---

    def test_production_rejects_missing_key(self):
        for value in (None, "", "   "):
            with self.subTest(value=value):
                with self.assertRaises(ImproperlyConfigured):
                    self._resolve(value, debug=False)

    def test_production_rejects_known_placeholders(self):
        from co2mmute.conf import KNOWN_INSECURE_SECRET_KEYS

        self.assertIn("insecure-local-key", KNOWN_INSECURE_SECRET_KEYS)
        for value in KNOWN_INSECURE_SECRET_KEYS:
            with self.subTest(value=value):
                with self.assertRaises(ImproperlyConfigured):
                    self._resolve(value, debug=False)

    def test_production_rejects_short_key(self):
        from co2mmute.conf import MIN_SECRET_KEY_LENGTH

        with self.assertRaises(ImproperlyConfigured):
            self._resolve("a" * (MIN_SECRET_KEY_LENGTH - 1), debug=False)

    def test_production_accepts_a_real_key(self):
        from co2mmute.conf import MIN_SECRET_KEY_LENGTH

        key = "s3cr3t-" + "z" * MIN_SECRET_KEY_LENGTH
        self.assertEqual(self._resolve(key, debug=False), key)

    def test_surrounding_whitespace_is_stripped(self):
        from co2mmute.conf import MIN_SECRET_KEY_LENGTH

        key = "q" * MIN_SECRET_KEY_LENGTH
        self.assertEqual(self._resolve(f"  {key}\n", debug=False), key)

    def test_settings_uses_the_resolver(self):
        """settings.py must go through resolve_secret_key, not os.environ.get directly."""
        source = (BACKEND_ROOT / "co2mmute" / "settings.py").read_text(encoding="utf-8")

        # assertTrue on a precomputed bool, not assertIn on the file: a failing
        # assertIn would print the whole of settings.py into the test output.
        self.assertTrue(
            "resolve_secret_key" in source,
            msg="settings.py does not call resolve_secret_key",
        )
        self.assertFalse(
            'SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY"' in source,
            msg="settings.py still reads DJANGO_SECRET_KEY with an inline fallback",
        )


# ---------------------------------------------------------------------------
# Roadmap.md 1.5 — test settings and CI
#
# co2mmute.settings_test is imported inside the methods below: the module does not
# exist yet, and a top-level import would take ResolveSecretKeyTests down with it.
# ---------------------------------------------------------------------------


class TestSettingsModuleTests(SimpleTestCase):
    """A run must be fast, need no Redis, and still speak Postgres."""

    def load(self):
        import importlib

        return importlib.import_module("co2mmute.settings_test")

    def test_the_module_imports(self):
        self.assertIsNotNone(self.load())

    def test_the_password_hasher_is_the_fast_one(self):
        """_helpers.create_host runs in most setUp methods and PBKDF2 is
        deliberately slow."""
        settings_test = self.load()

        self.assertEqual(
            settings_test.PASSWORD_HASHERS,
            ["django.contrib.auth.hashers.MD5PasswordHasher"],
        )

    def test_the_channel_layer_needs_no_redis(self):
        settings_test = self.load()

        self.assertEqual(
            settings_test.CHANNEL_LAYERS["default"]["BACKEND"],
            "channels.layers.InMemoryChannelLayer",
        )

    def test_the_cache_needs_no_redis(self):
        settings_test = self.load()

        self.assertEqual(
            settings_test.CACHES["default"]["BACKEND"],
            "django.core.cache.backends.locmem.LocMemCache",
        )

    def test_celery_runs_eager_and_propagates(self):
        """Without EAGER_PROPAGATES a failing task swallows its exception into a
        result object and looks like a silent no-op."""
        settings_test = self.load()

        self.assertTrue(settings_test.CELERY_TASK_ALWAYS_EAGER)
        self.assertTrue(settings_test.CELERY_TASK_EAGER_PROPAGATES)

    def test_the_database_is_postgres_not_sqlite(self):
        """settings.py falls back to sqlite whenever DEBUG is on, and sqlite
        treats select_for_update() as a no-op — so the row locks 1.4 and 1.3
        depend on would go untested while the tests still passed."""
        settings_test = self.load()

        self.assertEqual(
            settings_test.DATABASES["default"]["ENGINE"],
            "django.db.backends.postgresql",
        )

    def test_media_root_is_outside_the_repo(self):
        """GameSession.save() renders a QR code on every create."""
        settings_test = self.load()

        self.assertFalse(
            str(settings_test.MEDIA_ROOT).startswith(str(BACKEND_ROOT)),
            msg="test runs must not write QR codes into the repo",
        )

    def test_debug_is_off(self):
        self.assertFalse(self.load().DEBUG)

    def test_it_re_derives_the_secure_cookie_flags(self):
        """settings.py freezes these at import from DJANGO_DEBUG, which
        defaults to True — so a runner that sets nothing leaves them False
        while DEBUG here is False, the one combination the hardening test in
        game.tests.test_auth rejects. Compose sets the variable, a CI runner
        does not, which is why four CI runs were red against a green
        container. Deleting the two lines from settings_test was enough to
        redden CI again; this keeps that visible where it is typed."""
        settings_test = self.load()

        self.assertTrue(settings_test.SESSION_COOKIE_SECURE)
        self.assertTrue(settings_test.CSRF_COOKIE_SECURE)


class DatabaseEngineChoiceTests(SimpleTestCase):
    """Which engine is a decision of its own, not a side effect of DEBUG.

    It used to ride DEBUG alone, which meant a natively-run
    `./manage.py runserver` silently used sqlite while the container and the box
    used Postgres 18. That is not a cosmetic difference: sqlite reuses a rowid
    after each TestCase and Postgres sequences do not, so the round pk — which
    the simulation is seeded off — climbs in one and repeats in the other.

    settings.py derives this at import from os.environ, and DiscoverRunner
    forces settings.DEBUG to False for every run, so the only way to test it is
    to reload the module under a patched environment and read the values off the
    reloaded module (the pattern game/tests/test_auth.py uses).
    """

    def engine_for(self, debug, db=None):
        """The engine settings.py picks for DJANGO_DEBUG=<debug>, DJANGO_DB=<db>.

        db=None means the variable is absent, which is the case that has to keep
        behaving the way it did before the split. patch.dict cannot express
        "absent" — its values go straight into os.environ and must be strings —
        so the key is popped inside the context, which patch.dict restores on
        exit along with everything else.
        """
        import importlib
        import os
        import tempfile
        from unittest import mock

        import co2mmute.settings as settings_module

        env = {"DJANGO_DEBUG": debug}
        if db is not None:
            env["DJANGO_DB"] = db
        # Importing settings mkdir()s MEDIA_ROOT. Keep that out of the repo.
        env["DJANGO_MEDIA_ROOT"] = tempfile.mkdtemp(prefix="co2mmute-settings-")
        # resolve_secret_key refuses to boot with DEBUG off and no key — the
        # phase-0 guard, tested by ResolveSecretKeyTests above. It is not what
        # this class is about, so give it one.
        env["DJANGO_SECRET_KEY"] = "engine-choice-test-key-0123456789abcdef"

        with mock.patch.dict(os.environ, env, clear=False):
            if db is None:
                os.environ.pop("DJANGO_DB", None)
            reloaded = importlib.reload(settings_module)
            engine = reloaded.DATABASES["default"]["ENGINE"]
        # Leave the module as the rest of the suite found it.
        importlib.reload(settings_module)
        return engine

    def test_a_debug_run_still_defaults_to_sqlite(self):
        """The behaviour before the split, unchanged."""
        self.assertEqual(
            self.engine_for("True"),
            "django.db.backends.sqlite3",
        )

    def test_a_production_run_still_defaults_to_postgres(self):
        self.assertEqual(
            self.engine_for("False"),
            "django.db.backends.postgresql",
        )

    def test_debug_can_be_told_to_use_postgres(self):
        """What the native development stack needs: DEBUG on for the cookie
        flags and the error pages, Postgres underneath so the seeds and the row
        locks match CI."""
        self.assertEqual(
            self.engine_for("True", "postgres"),
            "django.db.backends.postgresql",
        )

    def test_the_choice_is_explicit_both_ways(self):
        self.assertEqual(
            self.engine_for("False", "sqlite"),
            "django.db.backends.sqlite3",
        )
