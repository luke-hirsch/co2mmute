import {
  Bars2Icon,
  ChatBubbleBottomCenterTextIcon,
  XMarkIcon,
} from "@heroicons/react/24/solid";
import { useState } from "react";
import { type Message } from "../utils/types";
import Header from "../components/Header";

const BaseLayout = ({
  children,
  title,
  msg,
  leftSidebar,
  leftSidebarIcon,
  rightSidebar,
  rightSidebarIcon,
}: {
  children: React.ReactNode;
  title?: string;
  msg?: Message;
  leftSidebar?: React.ReactNode;
  leftSidebarIcon?: React.ReactNode;
  rightSidebar?: React.ReactNode;
  rightSidebarIcon?: React.ReactNode;
}) => {
  const [menu, setMenu] = useState(false);
  const [chat, setChat] = useState(false);
  const baseStyles = "p-1 rounded-md text-white border text-sm";
  //
  //
  const typeStyles = {
    success: `${baseStyles}  dark:text-main dark:bg-sucess-100 bg-success-700`,
    error: `${baseStyles} dark:text-main dark:bg-error-100 bg-error-700`,
    warning: `${baseStyles} dark:text-main dark:bg-warning-100 bg-warning-700`,
    info: `${baseStyles} dark:text-main dark:bg-elevated bg-darkelevated`,
  };

  return (
    <div className="min-h-svh min-w-full bg-body dark:bg-darkbody dark:text-darkmain overflow-hidden">
      <div className="lg:hidden absolute top p-2 w-screen flex justify-between">
        {leftSidebar && (
          <>
            {leftSidebarIcon ? (
              leftSidebarIcon
            ) : (
              <Bars2Icon
                className={`w-10 h-10 cursor-pointer dark:text-darkmain text-main transition-all duration-300 ${menu ? "z-0 opacity-0 translate-x-full" : "opacity-100 z-50"}`}
                onClick={() => setMenu(true)}
              />
            )}
            <XMarkIcon
              className={`w-10 h-10 cursor-pointer dark:text-darkmain text-main transition-all duration-300 ${menu ? "opacity-100 z-50" : "z-0 opacity-0 -translate-x-full"}`}
              onClick={() => setMenu(false)}
            />
          </>
        )}

        {rightSidebar && (
          <>
            <XMarkIcon
              className={`w-10 h-10 cursor-pointer dark:text-darkmain text-main transition-all duration-300 ${menu ? "opacity-100 z-50" : "z-0 opacity-0 translate-x-full"}`}
              onClick={() => setChat(false)}
            />{" "}
            {rightSidebarIcon ? (
              rightSidebarIcon
            ) : (
              <ChatBubbleBottomCenterTextIcon
                className={`w-10 h-10 cursor-pointer dark:text-darkmain text-main transition-all duration-300 ${menu ? "z-0 opacity-0 translate-x-full" : "opacity-100 z-50"}`}
                onClick={() => setChat(true)}
              />
            )}
          </>
        )}
      </div>
      {/* Centering container */}
      <div className="flex justify-center items-center min-h-svh max-h-svh">
        <div className="flex max-h-svh w-screen bg-inherit">
          {/* Sidebar left*/}
          {leftSidebar && (
            <aside
              className={`absolute lg:relative left-0 top-0 w-60 dark:bg-inherit bg-body flex lg:translate-x-0 ${menu ? "translate-x-0" : "-translate-x-60"} transition-all duration-300 h-svh rounded z-50`}
            >
              {leftSidebar}
            </aside>
          )}

          <div className="flex flex-1 max-h-svh">
            {/* Main content */}
            <div className="relative flex-1 max-h-svh overflow-y-auto">
              {msg?.show && (
                <div className="absolute inset-0 flex items-center justify-center z-50">
                  <div className="relative lg:w-1/3 w-2/3 bg-body shadow-lg rounded-lg p-2">
                    <button
                      onClick={msg.onClose}
                      className="absolute top-2 right-2 text-muted hover:text-main"
                    >
                      &times;
                    </button>
                    <div className={`${typeStyles[msg.type]}`}>{msg.msg}</div>
                  </div>
                </div>
              )}
              {title && <Header title={title} />}
              <main className="flex-1 p-6 dark:text-darkmain flex flex-col items-center justify-center max-w-screen">
                {children}
              </main>
            </div>

            {/* Sidebar right */}
            {rightSidebar && (
              <aside
                className={`absolute lg:relative right-0 top-0 w-60 dark:bg-inherit bg-body flex lg:translate-x-0 ${chat ? "translate-x-0" : "translate-x-60"} transition-all duration-300 h-svh rounded z-50`}
              >
                {rightSidebar}
              </aside>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default BaseLayout;
