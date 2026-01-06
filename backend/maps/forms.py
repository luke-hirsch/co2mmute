import json
from django import forms
from django.core.exceptions import ValidationError
from maps.models import GameMap


class MapUploadForm(forms.Form):
    """Form for uploading a JSON file containing a graph structure to create a map."""

    json_file = forms.FileField(
        label="Map JSON File",
        help_text="Upload a JSON file containing the map graph structure",
        widget=forms.FileInput(
            attrs={
                "accept": ".json",
                "class": "block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100",
            }
        ),
    )

    map_name = forms.CharField(
        label="Map Name",
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500",
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
                "class": "block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500",
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
                "class": "block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
            }
        ),
    )

    def clean_json_file(self):
        """Validate that the uploaded file is valid JSON with required graph structure."""
        file = self.cleaned_data.get("json_file")

        if not file:
            raise ValidationError("Please upload a JSON file.")

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
        if "bus_lines" in data:
            if not isinstance(data["bus_lines"], list):
                raise ValidationError("'bus_lines' must be a list.")
            for i, bus_line in enumerate(data["bus_lines"]):
                if not isinstance(bus_line, dict):
                    raise ValidationError(f"Bus line {i} must be a dictionary.")
                if "name" not in bus_line or "edges" not in bus_line:
                    raise ValidationError(
                        f"Bus line {i} must have 'name' and 'edges' keys"
                    )
                if not isinstance(bus_line["edges"], list):
                    raise ValidationError(
                        f"Bus line {i} 'edges' must be a list of edge indices"
                    )

        # Validate train lines if present
        if "train_lines" in data:
            if not isinstance(data["train_lines"], list):
                raise ValidationError("'train_lines' must be a list.")
            for i, train_line in enumerate(data["train_lines"]):
                if not isinstance(train_line, dict):
                    raise ValidationError(f"Train line {i} must be a dictionary.")
                if "name" not in train_line or "edges" not in train_line:
                    raise ValidationError(
                        f"Train line {i} must have 'name' and 'edges' keys"
                    )
                if not isinstance(train_line["edges"], list):
                    raise ValidationError(
                        f"Train line {i} 'edges' must be a list of edge indices"
                    )

        return file

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
