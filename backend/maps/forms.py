import json
from django import forms
from django.core.exceptions import ValidationError
from maps.models import GameMap


class MapUploadForm(forms.Form):
    """Form for uploading a JSON file containing a graph structure to create a map."""

    json_file = forms.FileField(
        label="Map JSON File",
        required=False,
        help_text="Optional — upload a JSON file with the map graph structure, or leave empty to create a blank map.",
        widget=forms.FileInput(
            attrs={
                "accept": ".json",
                "class": "block w-full text-sm text-muted dark:text-darkmutedtext file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-indigo-600 file:text-white hover:file:bg-indigo-700",
            }
        ),
    )

    image_file = forms.ImageField(
        label="Background Image",
        required=False,
        help_text="Optional background image for the map (PNG, JPG, etc.)",
        widget=forms.FileInput(
            attrs={
                "accept": "image/*",
                "class": "block w-full text-sm text-muted dark:text-darkmutedtext file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-indigo-600 file:text-white hover:file:bg-indigo-700",
            }
        ),
    )

    map_name = forms.CharField(
        label="Map Name",
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "block w-full px-3 py-2 border border-subtle dark:border-darksubtle rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 bg-body dark:bg-darkbody text-main dark:text-darktext",
                "placeholder": "e.g., Downtown Map",
            }
        ),
    )

    description = forms.CharField(
        label="Description",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "block w-full px-3 py-2 border border-subtle dark:border-darksubtle rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 bg-body dark:bg-darkbody text-main dark:text-darktext",
                "placeholder": "Optional description of the map",
            }
        ),
    )

    max_players = forms.IntegerField(
        label="Max Players",
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
            raise ValidationError("File must be a JSON file (.json)")

        try:
            file.seek(0)
            content = file.read().decode("utf-8")
            data = json.loads(content)
        except UnicodeDecodeError:
            raise ValidationError("File must be valid UTF-8 encoded.")
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON format: {str(e)}")

        # Validate required structure
        required_keys = {"nodes", "edges"}
        if not isinstance(data, dict):
            raise ValidationError("JSON root must be an object/dictionary.")

        missing_keys = required_keys - set(data.keys())
        if missing_keys:
            raise ValidationError(
                f"JSON must contain the following keys: {', '.join(required_keys)}. "
                f"Missing: {', '.join(missing_keys)}"
            )

        # Validate nodes structure
        if not isinstance(data["nodes"], list):
            raise ValidationError("'nodes' must be a list.")

        if len(data["nodes"]) == 0:
            raise ValidationError("Map must contain at least one node.")

        for i, node in enumerate(data["nodes"]):
            if not isinstance(node, dict):
                raise ValidationError(f"Node {i} must be a dictionary.")
            node_required = {"id", "x", "y"}
            node_missing = node_required - set(node.keys())
            if node_missing:
                raise ValidationError(
                    f"Node {i} missing required keys: {', '.join(node_missing)}"
                )

        # Validate edges structure
        if not isinstance(data["edges"], list):
            raise ValidationError("'edges' must be a list.")

        for i, edge in enumerate(data["edges"]):
            if not isinstance(edge, dict):
                raise ValidationError(f"Edge {i} must be a dictionary.")
            edge_required = {"start_node", "end_node"}
            edge_missing = edge_required - set(edge.keys())
            if edge_missing:
                raise ValidationError(
                    f"Edge {i} missing required keys: {', '.join(edge_missing)}"
                )
            # Validate edge type specification
            if "type" in edge and edge["type"] not in ("street", "train", "both"):
                raise ValidationError(
                    f"Edge {i}: type must be 'street', 'train', or 'both', got '{edge['type']}'"
                )

        # Validate bus lines if present
        self._check_lines(data, "bus_lines", "Bus line")

        # Validate train lines if present
        self._check_lines(data, "train_lines", "Train line")

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
            raise ValidationError(f"'{key}' must be a list.")
        for i, line in enumerate(data[key]):
            if not isinstance(line, dict):
                raise ValidationError(f"{label} {i} must be a dictionary.")
            if "name" not in line or not ("edges" in line or "chains" in line):
                raise ValidationError(
                    f"{label} {i} must have 'name' and either 'edges' or 'chains'"
                )
            if "edges" in line and not isinstance(line["edges"], list):
                raise ValidationError(
                    f"{label} {i} 'edges' must be a list of edge indices"
                )
            if "chains" in line and not isinstance(line["chains"], list):
                raise ValidationError(
                    f"{label} {i} 'chains' must be a list of routes"
                )

    def clean_map_name(self):
        """Validate that map name is unique."""
        map_name = self.cleaned_data.get("map_name", "").strip()

        if not map_name:
            raise ValidationError("Map name is required.")

        if GameMap.objects.filter(name__iexact=map_name).exists():
            raise ValidationError(
                f"A map with the name '{map_name}' already exists. "
                f"Please choose a different name."
            )

        return map_name
