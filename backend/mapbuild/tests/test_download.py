"""Overpass: a box too big is fetched in quarters, a server that is down stops the build."""

from unittest import mock

from django.test import SimpleTestCase

from mapbuild import download

BOX = (52.0, 13.0, 52.2, 13.2)


class SplitTests(SimpleTestCase):
    def test_a_box_too_big_comes_in_quarters_each_element_once(self):
        calls = []

        def overpass(q):
            calls.append(q)
            if "(52.0,13.0,52.2,13.2)" in q:
                raise download.TooBig("runtime error: Query timed out")
            return {
                "elements": [
                    {"type": "way", "id": 1},
                    {"type": "way", "id": len(calls)},
                ]
            }

        with mock.patch("mapbuild.download.overpass", overpass), mock.patch(
            "mapbuild.download.say"
        ):
            els = download._osm(download.QUERIES["roads"], BOX)
        self.assertEqual(len(calls), 5)
        self.assertEqual([e["id"] for e in els], [1, 2, 3, 4, 5])

    def test_a_server_that_is_down_is_not_split(self):
        calls = []

        def overpass(q):
            calls.append(q)
            raise download.Missing("nicht erreichbar: HTTP Error 502")

        with mock.patch("mapbuild.download.overpass", overpass), self.assertRaises(
            download.Missing
        ):
            download._osm(download.QUERIES["roads"], BOX)
        self.assertEqual(len(calls), 1)

    def test_a_200_with_an_error_remark_is_too_big(self):
        body = b'{"elements": [], "remark": "runtime error: Query run out of memory"}'
        with mock.patch(
            "mapbuild.download._request", return_value=body
        ), self.assertRaises(download.TooBig):
            download.overpass("[out:json];way(1);out;")

    def test_only_a_504_or_a_timeout_means_too_big(self):
        import urllib.error

        for err, kind in (
            (urllib.error.HTTPError("u", 504, "busy", {}, None), download.TooBig),
            (urllib.error.HTTPError("u", 502, "down", {}, None), download.Missing),
        ):
            with mock.patch("urllib.request.urlopen", side_effect=err), mock.patch(
                "mapbuild.download.time.sleep"
            ), mock.patch("mapbuild.download.say"):
                with self.assertRaises(download.Missing) as cm:
                    download._request("https://example.invalid/")
            self.assertIs(type(cm.exception), kind)
