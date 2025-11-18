import viteLogo from "../../assets/vite.svg";

interface HeaderProps {
  title: string;
  icon?: string;
  margin?: string;
  padding?: string;
  iconColor?: string;
}
export default function Header({
  title,

  margin = "my-7",
  padding = "p-0",
}: HeaderProps) {
  return (
    <div
      className={`${margin} ${padding} text-center items-center flex flex-col`}
    >
      <a href="https://vite.dev" target="_blank">
        <img src={viteLogo} className="logo" alt="Vite logo" />
      </a>
      <h2 className="md:text-2xl text-xl mt-7 font-light">{title}</h2>
    </div>
  );
}
