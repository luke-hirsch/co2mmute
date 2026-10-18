import { MutationObserver, QueryClient, QueryObserver } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import { deleteStudyMutation, studyKeys } from "@/lib/queries/studies";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("deleting a study", () => {
  it("does not refetch the study it deleted, and marks the list stale", async () => {
    // The study page is still mounted while the delete lands. Refetching its
    // own study there answers 404, the page swaps to "gibt es nicht", and the
    // navigation to the list never happens (CI, 2026-10-18).
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(() => Promise.resolve(new Response(null, { status: 204 }))),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const study = vi.fn(() => Promise.resolve({ id: 4, name: "Dienstag" }));
    const page = new QueryObserver(client, { queryKey: studyKeys.one(4), queryFn: study });
    const unsubscribe = page.subscribe(() => {});
    await vi.waitFor(() => expect(study).toHaveBeenCalledTimes(1));
    client.setQueryData(studyKeys.list(), []);

    await new MutationObserver(client, deleteStudyMutation(client, 4)).mutate();

    expect(study).toHaveBeenCalledTimes(1);
    expect(client.getQueryState(studyKeys.list())?.isInvalidated).toBe(true);
    unsubscribe();
  });
});
