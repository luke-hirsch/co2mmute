import json
from django import forms
from django.core.exceptions import ValidationError
from maps.models import GameMap


class MapUploadForm(forms.Form):
    """Form for uploading a JSON file containing a graph structure to create a map.

    German since S17. It was the last form on the site with English labels,
    English help text and English refusals — staff-only, which is why nobody
    reported it, but `/map/upload/` is the door a map comes back through and the
    only German the file round trip has. `maps/tests/test_portability.py` pins it
    with the join funnel's own detector.

    The JSON keys stay English: `nodes`, `start_node` and `speed_limit` are the
    file's field names, and renaming them would mean renaming the API.
    """

    json_file = forms.FileField(
        label="Kartendatei (JSON)",
        required=False,
        help_text="Optional — lad eine JSON-Datei mit dem Kartengraphen hoch, oder lass das Feld leer für eine leere Karte.",
        widget=forms.FileInput(
            attrs={
                "accept": ".json",
                "class": "block w-full text-sm text-muted dark:text-darkmutedtext file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-indigo-600 file:text-white hover:file:bg-indigo-700",
            }
        ),
    )

    image_file = forms.ImageField(
        label="Hintergrundbild",
        required=False,
        help_text="Optional — das Bild, auf dem der Graph liegt (PNG, JPG).",
        widget=forms.FileInput(
            attrs={
                "accept": "image/*",
                "class": "block w-full text-sm text-muted dark:text-darkmutedtext file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-indigo-600 file:text-white hover:file:bg-indigo-700",
            }
        ),
    )

    map_name = forms.CharField(
        label="Name der Karte",
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "block w-full px-3 py-2 border border-subtle dark:border-darksubtle rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 bg-body dark:bg-darkbody text-main dark:text-darktext",
                "placeholder": "z. B. Berlin Mitte-West",
            }
        ),
    )

    description = forms.CharField(
        label="Beschreibung",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "block w-full px-3 py-2 border border-subtle dark:border-darksubtle rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 bg-body dark:bg-darkbody text-main dark:text-darktext",
                "placeholder": "Optional — worum es auf dieser Karte geht",
            }
        ),
    )

    max_players = forms.IntegerField(
        label="Plätze",
        initial=4,
        min_value=1,
        max_value=20,
        widget=forms.NumberInput(
            attrs={
                "class": "block w-full px-3 py-2 border border-subtle dark:border-darksubtle rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 bg-body dark:bg-darkbody text-main dark:text-darktext"
            }
        ),
    )

    def clean_json_file(self):
        """Validate that the uploaded file is valid JSON with required graph structure."""
        file = self.cleaned_data.get("json_file")

        if not file:
            return None

        # Check file extension
        if not file.name.endswith(".json"):
            raise ValidationError("Die Datei muss eine JSON-Datei sein (.json).")

        try:
            file.seek(0)
            content = file.read().decode("utf-8")
            data = json.loads(content)
        except UnicodeDecodeError:
            raise ValidationError("Die Datei muss UTF-8 kodiert sein.")
        except json.JSONDecodeError as e:
            raise ValidationError(f"Das ist kein gültiges JSON: {str(e)}")

        # Validate required structure
        required_keys = {"nodes", "edges"}
        if not isinstance(data, dict):
            raise ValidationError("Die JSON-Datei muss auf oberster Ebene ein Objekt sein.")

        missing_keys = required_keys - set(data.keys())
        if missing_keys:
            raise ValidationError(
                f"Die Datei braucht diese Schlüssel: {', '.join(required_keys)}. "
                f"Es fehlen: {', '.join(missing_keys)}"
            )

        # Validate nodes structure
        if not isinstance(data["nodes"], list):
            raise ValidationError("'nodes' muss eine Liste sein.")

        if len(data["nodes"]) == 0:
            raise ValidationError("Eine Karte braucht mindestens einen Knoten.")

        for i, node in enumerate(data["nodes"]):
            if not isinstance(node, dict):
                raise ValidationError(f"Knoten {i} muss ein Objekt sein.")
            node_required = {"id", "x", "y"}
            node_missing = node_required - set(node.keys())
            if node_missing:
                raise ValidationError(
                    f"Knoten {i} fehlen Angaben: {', '.join(node_missing)}"
                )

        # Validate edges structure
        if not isinstance(data["edges"], list):
            raise ValidationError("'edges' muss eine Liste sein.")

        for i, edge in enumerate(data["edges"]):
            if not isinstance(edge, dict):
                raise ValidationError(f"Kante {i} muss ein Objekt sein.")
            edge_required = {"start_node", "end_node"}
            edge_missing = edge_required - set(edge.keys())
            if edge_missing:
                raise ValidationError(
                    f"Kante {i} fehlen Angaben: {', '.join(edge_missing)}"
                )
            # Validate edge type specification
            if "type" in edge and edge["type"] not in (
                "street",
                "train",
                "both",
                "path",
            ):
                raise ValidationError(
                    f"Kante {i}: 'type' muss 'street', 'train', 'both' oder "
                    f"'path' sein, hier steht '{edge['type']}'"
                )

        # Validate bus lines if present
        self._check_lines(data, "bus_lines", "Buslinie")

        # Validate train lines if present
        self._check_lines(data, "train_lines", "Bahnlinie")

        return file

    def _check_lines(self, data, key, label):
        """A line states its route, as one `edges` list or as `chains`.

        Since S14 a whole-map file carries a line's route per version, because
        a version that clones a street runs the line over the clone. The two
        keys are alternatives and either satisfies "this line says where it
        runs"; what is checked here is only the shape, the indices are
        `MapUploadView._validate_graph_data`'s.
        """
        if key not in data:
            return
        if not isinstance(data[key], list):
            raise ValidationError(f"'{key}' muss eine Liste sein.")
        for i, line in enumerate(data[key]):
            if not isinstance(line, dict):
                raise ValidationError(f"{label} {i} muss ein Objekt sein.")
            if "name" not in line or not ("edges" in line or "chains" in line):
                raise ValidationError(
                    f"{label} {i} braucht 'name' und entweder 'edges' oder 'chains'."
                )
            if "edges" in line and not isinstance(line["edges"], list):
                raise ValidationError(
                    f"{label} {i}: 'edges' muss eine Liste von Kantennummern sein."
                )
            if "chains" in line and not isinstance(line["chains"], list):
                raise ValidationError(
                    f"{label} {i}: 'chains' muss eine Liste von Routen sein."
                )

    def clean_map_name(self):
        """Validate that map name is unique."""
        map_name = self.cleaned_data.get("map_name", "").strip()

        if not map_name:
            raise ValidationError("Die Karte braucht einen Namen.")

        if GameMap.objects.filter(name__iexact=map_name).exists():
            raise ValidationError(
                f"Eine Karte mit dem Namen „{map_name}“ gibt es schon. "
                f"Nimm einen anderen Namen."
            )

        return map_name
