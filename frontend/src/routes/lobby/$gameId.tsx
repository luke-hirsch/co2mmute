import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/lobby/$gameId")({
  component: LobbyRoute,
});

function LobbyRoute() {
  const { gameId } = Route.useParams();

  return (
    <div className="flex flex-col items-center gap-4 rounded-lg border border-slate-200 bg-white p-6 shadow">
      <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
        Lobby
      </h1>
      <p className="text-sm text-slate-600">
        Connected to game session <span className="font-mono">{gameId}</span>.
      </p>
    </div>
  );
}
