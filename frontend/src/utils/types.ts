export type AuthResult = {
  user: null | {
    id: string;
    name: string;
  };
};

export type Message = {
  show: boolean;
  msg: string;
  type: "info" | "success" | "error" | "warning";
  onClose?: () => void;
};
