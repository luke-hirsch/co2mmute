/**
 * The study pages' data: `api/studies/…`, staff only, reading too.
 *
 * Plain REST with refetch after a write — there is no socket on these screens,
 * so nothing here races with a second source of truth.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

export type Study = {
  id: number;
  name: string;
  description: string;
  created_at: string;
  /** Counts; the rows come from their own endpoints. */
  games: number;
  codes: number;
  notes: number;
};

export type StudyCode = {
  id: number;
  code: string;
  created_at: string;
  used: boolean;
};

export type StudyCard = { code: string; url: string; qr: string };

export type StudyGameRow = {
  game_id: string;
  name: string;
  map: string | null;
  started_at: string | null;
  ended_at: string | null;
};

export type MetaValue = string | number | boolean;

export type StudyNote = {
  id: number;
  author: string | null;
  games: string[];
  about_date: string | null;
  created_at: string;
  updated_at: string;
  text: string;
  meta: Record<string, MetaValue>;
};

export type NoteInput = {
  text: string;
  about_date: string | null;
  games: string[];
  meta: Record<string, MetaValue>;
};

export const studyKeys = {
  all: ["studies"] as const,
  list: () => ["studies", "list"] as const,
  one: (id: number) => ["studies", id] as const,
  codes: (id: number) => ["studies", id, "codes"] as const,
  cards: (id: number) => ["studies", id, "cards"] as const,
  games: (id: number) => ["studies", id, "games"] as const,
  notes: (id: number) => ["studies", id, "notes"] as const,
};

const json = (method: string, body: unknown): RequestInit => ({
  method,
  body: JSON.stringify(body),
});

export function useStudies() {
  return useQuery({
    queryKey: studyKeys.list(),
    queryFn: () => apiFetch<Study[]>("/api/studies/"),
  });
}

export function useStudy(id: number) {
  return useQuery({
    queryKey: studyKeys.one(id),
    queryFn: () => apiFetch<Study>(`/api/studies/${id}/`),
  });
}

export function useCreateStudy() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { name: string; description: string }) =>
      apiFetch<Study>("/api/studies/", json("POST", input)),
    onSuccess: () => client.invalidateQueries({ queryKey: studyKeys.all }),
  });
}

export function useUpdateStudy(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { name: string; description: string }) =>
      apiFetch<Study>(`/api/studies/${id}/`, json("PATCH", input)),
    onSuccess: () => client.invalidateQueries({ queryKey: studyKeys.all }),
  });
}

/** 409 when a game of the study started; the message is the server's sentence. */
export function useDeleteStudy(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<void>(`/api/studies/${id}/`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: studyKeys.all }),
  });
}

export function useStudyGames(id: number) {
  return useQuery({
    queryKey: studyKeys.games(id),
    queryFn: () => apiFetch<StudyGameRow[]>(`/api/studies/${id}/games/`),
  });
}

export function useLinkGame(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (gameId: string) =>
      apiFetch<StudyGameRow>(
        `/api/studies/${id}/games/`,
        json("POST", { game_id: gameId }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: studyKeys.all }),
  });
}

export function useUnlinkGame(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (gameId: string) =>
      apiFetch<void>(`/api/studies/${id}/games/${gameId}/`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: studyKeys.all }),
  });
}

export function useStudyCodes(id: number) {
  return useQuery({
    queryKey: studyKeys.codes(id),
    queryFn: () => apiFetch<StudyCode[]>(`/api/studies/${id}/codes/`),
  });
}

export function useMakeCodes(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (count: number) =>
      apiFetch<StudyCode[]>(`/api/studies/${id}/codes/`, json("POST", { count })),
    onSuccess: () => client.invalidateQueries({ queryKey: studyKeys.all }),
  });
}

export function useDeleteCode(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (codeId: number) =>
      apiFetch<void>(`/api/studies/${id}/codes/${codeId}/`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: studyKeys.all }),
  });
}

export function useStudyCards(id: number) {
  return useQuery({
    queryKey: studyKeys.cards(id),
    queryFn: () => apiFetch<StudyCard[]>(`/api/studies/${id}/cards/`),
  });
}

export function useStudyNotes(id: number) {
  return useQuery({
    queryKey: studyKeys.notes(id),
    queryFn: () => apiFetch<StudyNote[]>(`/api/studies/${id}/notes/`),
  });
}

export function useSaveNote(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ noteId, input }: { noteId: number | null; input: NoteInput }) =>
      noteId === null
        ? apiFetch<StudyNote>(`/api/studies/${id}/notes/`, json("POST", input))
        : apiFetch<StudyNote>(
            `/api/studies/${id}/notes/${noteId}/`,
            json("PATCH", input),
          ),
    onSuccess: () => client.invalidateQueries({ queryKey: studyKeys.all }),
  });
}

export function useDeleteNote(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (noteId: number) =>
      apiFetch<void>(`/api/studies/${id}/notes/${noteId}/`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: studyKeys.all }),
  });
}
