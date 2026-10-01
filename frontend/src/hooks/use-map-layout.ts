import { useCallback, useState } from "react";

import { browserStorage } from "@/lib/game/draft-storage";
import {
  readMapLayout,
  writeMapLayout,
  type MapLayout,
} from "@/lib/game/map-layout";

/**
 * The map's place on a large screen, remembered on this device (S24).
 *
 * Read once on mount: the round screen and the vote are separate screens that
 * mount in turn, so each reads what the last one wrote, and nothing needs a
 * subscription. Below `lg` the value is ignored — the classes that act on it all
 * carry the `lg:` prefix — which is why this hook knows nothing about widths.
 */
export function useMapLayout(): [MapLayout, (layout: MapLayout) => void] {
  const [layout, setLayout] = useState<MapLayout>(() =>
    readMapLayout(browserStorage()),
  );
  const update = useCallback((next: MapLayout) => {
    setLayout(next);
    writeMapLayout(browserStorage(), next);
  }, []);
  return [layout, update];
}
