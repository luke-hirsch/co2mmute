import {
  Bars2Icon,
  ChatBubbleBottomCenterTextIcon,
  XMarkIcon,
} from "@heroicons/react/24/solid";

import { useState } from "react";
import LeftSidebar from "./LeftSidebar";
import Header from "../Header";
import GameDetail from "./GameDetail";
import ChatSidebar from "../ChatSidebar";
import PlayerDetailPanel from "./PlayerDetailPanel";
import { useParams } from "@tanstack/react-router";

import Loading from "../Loading";
import { useAuth } from "../../context/AuthContext";
import { useGameDetails } from "../../hooks/gameHooks";
import { type WSPlayer } from "../../types/wsTypes";

const Lobby = () => {
  const [menu, setMenu] = useState(false);
  const [chat, setChat] = useState(false);
  const [selectedPlayer, setSelectedPlayer] = useState<WSPlayer | null>(null);
  const { isLoading, isError, isHost, isPlayer, auth } = useAuth();
  const { gameId } = useParams({ from: "/lobby/$gameId" });
  const gameData = useGameDetails(gameId);
  return (
    <div className="min-h-svh min-w-full max-w-screen bg-body dark:bg-darkbody dark:text-darktext overflow-hidden">
      <div className="lg:hidden absolute top p-2 w-screen flex justify-between">
        <Bars2Icon
          className={`w-10 h-10 cursor-pointer dark:text-darktext text-main transition-all duration-300 ${menu || chat ? "z-0 opacity-0 translate-x-full" : "opacity-100 z-75"}`}
          onClick={() => setMenu(true)}
        />

        <XMarkIcon
          className={`w-10 h-10 cursor-pointer dark:text-darktext text-main transition-all duration-300 ${menu ? "opacity-100 z-85 " : "z-0 opacity-0 -translate-x-full"}`}
          onClick={() => setMenu(false)}
        />
      </div>
      <div className="lg:hidden absolute top p-2 w-screen flex justify-between">
        <XMarkIcon
          className={`w-10 h-10 cursor-pointer dark:text-darktext text-main transition-all duration-300 ${chat ? "opacity-100 z-85" : "z-0 opacity-0 translate-x-full"}`}
          onClick={() => setChat(false)}
        />
        <ChatBubbleBottomCenterTextIcon
          className={`w-10 h-10 cursor-pointer dark:text-darktext text-main transition-all duration-300 ${chat || menu ? "z-0 opacity-0 translate-x-full" : "opacity-100 z-75"}`}
          onClick={() => setChat(true)}
        />
      </div>

      {/* Centering container */}
      <div className="flex justify-center items-center min-h-full max-h-full w-full overflow-hidden">
        <div className="flex max-h-svh min-h-svh w-screen bg-inherit p-4">
          {/* Sidebar left*/}
          <div className=" max-h-svh overflow-hidden">
            {isHost || isPlayer ? (
              <aside
                className={`absolute lg:relative min-h-full left-0 top-0 w-60 dark:bg-inherit bg-body flex lg:translate-x-0 ${menu ? "translate-x-0" : "-translate-x-60"} transition-all duration-300 h-full rounded z-50`}
              >
                <LeftSidebar
                  gameId={gameId}
                  selectedPlayerId={selectedPlayer?.playerId}
                  onPlayerSelect={setSelectedPlayer}
                />
              </aside>
            ) : (
              <></>
            )}
          </div>
          <div className="flex flex-1 max-h-svh w-screen overflow-hidden">
            {/* Main content */}
            <div className="relative flex-1 max-h-svh overflow-y-auto">
              <Header title={`Lobbyy - ${gameId}`} />
              <main className="flex-1 p-6 dark:text-darktext flex flex-col items-center justify-center max-w-screen">
                {isLoading ? (
                  <Loading />
                ) : isError ? (
                  <div>Fehler</div>
                ) : isHost && selectedPlayer ? (
                  <PlayerDetailPanel
                    player={selectedPlayer}
                    gameId={gameId}
                    onClose={() => setSelectedPlayer(null)}
                    onPlayerUpdated={() => {
                      // Lobby socket will auto-update the player list
                    }}
                    onPlayerKicked={() => {
                      setSelectedPlayer(null);
                    }}
                  />
                ) : isPlayer ? (
                  <GameDetail
                    id={gameId}
                    role="player"
                    playerId={auth?.player?.playerId}
                  />
                ) : isHost ? (
                  <GameDetail id={gameId} role="host" />
                ) : (
                  <div>No access</div>
                )}
              </main>
            </div>

            {/* Sidebar right */}
            {isHost || isPlayer ? (
              <aside
                className={`absolute lg:relative right-0 top-0 w-60 dark:bg-inherit bg-body flex lg:translate-x-0 ${chat ? "translate-x-0" : "translate-x-60"} transition-all duration-300 h-full rounded z-50`}
              >
                <ChatSidebar
                  gameId={gameId}
                  chatEnabled={gameData?.data?.chat_enabled ?? true}
                />
              </aside>
            ) : (
              <></>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Lobby;
