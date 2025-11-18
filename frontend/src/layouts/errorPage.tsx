import Sidebar from "../components/Sidebar";
import { useState } from "react";
import { Bars2Icon, XMarkIcon } from "@heroicons/react/24/solid";

const ErrorPage = ({
  errorMessage,
  errorCode,
}: {
  errorMessage: string;
  errorCode: number;
}) => {
  const [menu, setMenu] = useState(false);

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
            {errorCode.toString()} - {errorMessage}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ErrorPage;
