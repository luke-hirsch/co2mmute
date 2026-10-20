import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import Loading from "@/components/Loading";
import { de } from "@/lib/de";

describe("Loading", () => {
  it("shows the three vehicles and the label, with no spinning ring", () => {
    const html = renderToStaticMarkup(<Loading label="Wird angelegt …" />);

    expect(html).toContain("Wird angelegt …");
    expect(html.match(/<svg/g)).toHaveLength(3);
    expect(html).not.toContain("swirl");
  });

  it("falls back to the app's own word", () => {
    expect(renderToStaticMarkup(<Loading />)).toContain(de.app.loading);
  });
});
