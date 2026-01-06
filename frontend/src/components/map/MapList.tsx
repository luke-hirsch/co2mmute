import { useGameMaps } from "../../hooks/mapHooks";
import Loading from "../Loading";
import { Link } from "@tanstack/react-router";

const MapList = () => {
  const { data: maps, isLoading, error } = useGameMaps();

  if (isLoading) {
    return <Loading />;
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg text-red-600 dark:text-red-400">
          Error loading maps:{" "}
          {error instanceof Error ? error.message : "Unknown error"}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-linear-to-b from-body to-surface dark:from-darkbody dark:to-darksurface">
      <div className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-main dark:text-darktext mb-2">
            Game Maps
          </h1>
          <p className="text-muted dark:text-darkmutedtext">
            Select a map to view or edit
          </p>
        </div>

        {!maps || maps.length === 0 ? (
          <div className="bg-subtle dark:bg-darksubtle rounded-lg p-12 border border-subtle dark:border-darksubtle text-center">
            <p className="text-muted dark:text-darkmutedtext mb-4">
              No maps available yet
            </p>
            <a
              href="/map/upload"
              className="inline-block px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg transition-colors"
            >
              Upload a Map
            </a>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {maps.map((map) => (
              <Link
                key={map.id}
                to="/maps/$mapId"
                params={{ mapId: map.id.toString() }}
                className="block"
              >
                <div className="bg-surface dark:bg-darksurface rounded-lg shadow-lg border border-subtle dark:border-darksubtle hover:shadow-xl hover:border-indigo-500 dark:hover:border-indigo-400 transition-all overflow-hidden cursor-pointer h-full">
                  <div className="p-6">
                    <h2 className="text-xl font-bold text-main dark:text-darktext mb-2">
                      {map.name}
                    </h2>
                    {map.description && (
                      <p className="text-muted dark:text-darkmutedtext text-sm mb-4 line-clamp-2">
                        {map.description}
                      </p>
                    )}
                    <div className="space-y-2 text-sm text-muted dark:text-darkmutedtext mb-4">
                      <p>
                        <span className="font-semibold">Players:</span>{" "}
                        {map.max_player}
                      </p>
                      <p>
                        <span className="font-semibold">Size:</span> {map.x_dim}{" "}
                        × {map.y_dim}
                      </p>
                      <p>
                        <span className="font-semibold">Author:</span>{" "}
                        {map.author.username}
                      </p>
                    </div>
                    <div className="pt-4 border-t border-subtle dark:border-darksubtle">
                      <span className="inline-block px-3 py-1 bg-indigo-600/20 text-indigo-600 dark:text-indigo-400 text-xs font-medium rounded">
                        View Map →
                      </span>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default MapList;
