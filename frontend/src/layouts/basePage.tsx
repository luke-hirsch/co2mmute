interface DashboardLayoutProps {
  children: React.ReactNode;
  title?: string;
  msg?: Message;
}

import Header from "../components/Header";
import Sidebar from "../components/Sidebar";
import type { Message } from "../utils/types";
import { useState } from "react";
import { Bars2Icon, XMarkIcon } from "@heroicons/react/24/solid";

const BaseLayout = ({ children, title, msg }: DashboardLayoutProps) => {
  const [menu, setMenu] = useState(false);

  const baseStyles = "p-1 rounded-md text-white border text-sm";
  //
  //
  const typeStyles = {
    success: `${baseStyles} dark:bg-white dark:text-black bg-black`,
    error: `${baseStyles} bg-error-200 border-error-500`,
    warning: `${baseStyles} dark:bg-white dark:text-black bg-black`,
    info: `${baseStyles} dark:bg-white dark:text-black bg-black`,
  };
  return (
    <div className="min-h-svh min-w-full bg-white dark:bg-black dark:text-white overflow-hidden">
      <div className="lg:hidden absolute top p-2 w-screen flex justify-between">
        <Bars2Icon
          className={`w-10 h-10 cursor-pointer dark:text-white text-black transition-all duration-300 ${menu ? "z-0 opacity-0 translate-x-full" : "opacity-100 z-50"}`}
          onClick={() => setMenu(true)}
        />
        <XMarkIcon
          className={`w-10 h-10 cursor-pointer dark:text-white text-black transition-all duration-300 ${menu ? "opacity-100 z-50" : "z-0 opacity-0 -translate-x-full"}`}
          onClick={() => setMenu(false)}
        />
      </div>
      {/* Centering container */}
      <div className="flex justify-center items-center min-h-svh max-h-svh">
        <div className="flex max-h-svh w-screen bg-inherit">
          {/* Sidebar */}
          <aside
            className={`absolute lg:relative left-0 top-0 w-60 dark:bg-inherit bg-white flex lg:translate-x-0 ${menu ? "translate-x-0" : "-translate-x-60"} transition-all duration-300 h-svh rounded z-50`}
          >
            <Sidebar />
          </aside>

          {/* Main content */}
          <div className="relative max-h-svh overflow-y-auto w-full ">
            {msg?.show && (
              <div className="absolute inset-0 flex items-center justify-center z-50">
                <div className="relative lg:w-1/3 w-2/3 bg-white shadow-lg rounded-lg p-2">
                  <button
                    onClick={msg.onClose}
                    className="absolute top-2 right-2 text-zinc-500 hover:text-zinc-700"
                  >
                    &times;
                  </button>
                  <div className={`${typeStyles[msg.type]}`}>{msg.msg}</div>
                </div>
              </div>
            )}
            {title && <Header title={title} />}
            <main className="flex-1 p-6 dark:text-white flex flex-col items-center justify-center max-w-screen">
              {children}
            </main>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BaseLayout;
