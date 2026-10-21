# Gebaute Karten

Karten, die `manage.py build_map` aus OpenStreetMap gebaut hat (Skill `map-create`), gemessen
(`calibrate_map --out`) und im Repo behalten. Die handgezeichnete Karte eine Ebene höher bleibt die
gespielte, bis ein gebautes Berlin sie ersetzt.

CI prüft mit `check_map` nur die Dateien eine Ebene höher (`maps/tests/test_example_map.py`). Eine
Karte hier ist vorher von Hand durch `manage.py check_map` gelaufen.
