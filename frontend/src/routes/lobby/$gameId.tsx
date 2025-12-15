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
    <div className="min-h-svh min-w-full bg-body dark:bg-darkbody dark:text-darktext overflow-hidden">
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
      <div className="flex justify-center items-center min-h-full max-h-full w-screen overflow-hidden">
        <div className="flex max-h-svh min-h-svh w-screen bg-inherit p-4">
          {/* Sidebar left*/}
          <div className=" max-h-svh overflow-hidden">
            <aside
              className={`absolute lg:relative min-h-full left-0 top-0 w-60 dark:bg-inherit bg-body flex lg:translate-x-0 ${menu ? "translate-x-0" : "-translate-x-60"} transition-all duration-300 h-full rounded z-50`}
            >
              <LeftSidebar />
            </aside>
          </div>
          <div className="flex flex-1 max-h-svh w-screen overflow-hidden">
            {/* Main content */}
            <div className="relative flex-1 max-h-svh overflow-y-auto">
              <Header title={`Lobbyy - ${gameId}`} />
              <main className="flex-1 p-6 dark:text-darktext flex flex-col items-center justify-center max-w-screen">
                <GameDetail id={gameId} />
              </main>
            </div>

            {/* Sidebar right */}

            <aside
              className={`absolute lg:relative right-0 top-0 w-60 dark:bg-inherit bg-body flex lg:translate-x-0 ${chat ? "translate-x-0" : "translate-x-60"} transition-all duration-300 h-full rounded z-50`}
            >
              <ChatSidebar />
            </aside>
          </div>
        </div>
      </div>
    </div>
  );
}
