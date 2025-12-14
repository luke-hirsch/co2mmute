import { useEffect } from "react";

const RedirectToJoin = () => {
  useEffect(() => {
    window.location.replace("/join");
  }, []);

  return null;
};

export default RedirectToJoin;
