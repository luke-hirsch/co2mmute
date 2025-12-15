import { createFileRoute } from "@tanstack/react-router";
import {
  Bars2Icon,
  ChatBubbleBottomCenterTextIcon,
  XMarkIcon,
} from "@heroicons/react/24/solid";

import { useState } from "react";
import LeftSidebar from "../../components/lobby/LeftSidebar";
import Header from "../../components/Header";
import GameDetail from "../../components/lobby/GameDetail";
import ChatSidebar from "../../components/ChatSidebar";

export const Route = createFileRoute("/lobby/$gameId")({
  component: LobbyRoute,
});

function LobbyRoute() {
  const [menu, setMenu] = useState(false);
  const [chat, setChat] = useState(false);

  const { gameId } = Route.useParams();

  return (
    <div className="min-h-svh min-w-full bg-body dark:bg-darkbody dark:text-darkmain overflow-hidden">
      <div className="lg:hidden absolute top p-2 w-screen flex justify-between">
        <Bars2Icon
          className={`w-10 h-10 cursor-pointer dark:text-darkmain text-main transition-all duration-300 ${menu ? "z-0 opacity-0 translate-x-full" : "opacity-100 z-50"}`}
          onClick={() => setMenu(true)}
        />

        <XMarkIcon
          className={`w-10 h-10 cursor-pointer dark:text-darkmain text-main transition-all duration-300 ${menu ? "opacity-100 z-50" : "z-0 opacity-0 -translate-x-full"}`}
          onClick={() => setMenu(false)}
        />

        <XMarkIcon
          className={`w-10 h-10 cursor-pointer dark:text-darkmain text-main transition-all duration-300 ${menu ? "opacity-100 z-50" : "z-0 opacity-0 translate-x-full"}`}
          onClick={() => setChat(false)}
        />
        <ChatBubbleBottomCenterTextIcon
          className={`w-10 h-10 cursor-pointer dark:text-darkmain text-main transition-all duration-300 ${menu ? "z-0 opacity-0 translate-x-full" : "opacity-100 z-50"}`}
          onClick={() => setChat(true)}
        />
      </div>
      {/* Centering container */}
      <div className="flex justify-center items-center min-h-svh max-h-svh">
        <div className="flex max-h-svh w-screen bg-inherit">
          {/* Sidebar left*/}

          <aside
            className={`absolute lg:relative left-0 top-0 w-60 dark:bg-inherit bg-body flex lg:translate-x-0 ${menu ? "translate-x-0" : "-translate-x-60"} transition-all duration-300 h-svh rounded z-50`}
          >
            <LeftSidebar />
          </aside>

          <div className="flex flex-1 max-h-svh">
            {/* Main content */}
            <div className="relative flex-1 max-h-svh overflow-y-auto">
              <Header title={`Lobbyy - ${gameId}`} />
              <main className="flex-1 p-6 dark:text-darkmain flex flex-col items-center justify-center max-w-screen">
                <GameDetail id={gameId} />
              </main>
            </div>

            {/* Sidebar right */}

            <aside
              className={`absolute lg:relative right-0 top-0 w-60 dark:bg-inherit bg-body flex lg:translate-x-0 ${chat ? "translate-x-0" : "translate-x-60"} transition-all duration-300 h-svh rounded z-50`}
            >
              <ChatSidebar />
            </aside>
          </div>
        </div>
      </div>
    </div>
  );
}
