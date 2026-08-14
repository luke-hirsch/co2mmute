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
