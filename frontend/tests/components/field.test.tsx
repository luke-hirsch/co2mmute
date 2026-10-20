import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Field } from "@/components/layout/field";

describe("Field", () => {
  it("shows a refusal as an amber rule beside ink text, like the notes", () => {
    const html = renderToStaticMarkup(
      <Field id="x" label="X" errors={["Zu klein."]}>
        <input id="x" />
      </Field>,
    );

    expect(html).toContain('role="alert"');
    expect(html).toContain("border-l-2 border-brandaccent pl-3");
    expect(html).toContain("text-foreground");
    expect(html).not.toMatch(/text-(brandaccent|destructive)/);
  });

  it("shows no alert without errors", () => {
    const html = renderToStaticMarkup(
      <Field id="x" label="X" errors={[]}>
        <input id="x" />
      </Field>,
    );
    expect(html).not.toContain('role="alert"');
  });
});
