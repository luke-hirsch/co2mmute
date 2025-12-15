import logo from "../assets/logo.svg";

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
      className={`${margin} ${padding} flex flex-col items-center text-center text-main dark:text-darktext`}
    >
      <a
        href="#"
        target="_blank"
        className="transition-opacity duration-200 hover:opacity-80"
      >
        <img src={logo} className="logo h-16 w-auto" alt="Logo" />
      </a>
      <h2 className="mt-7 text-xl font-light text-muted transition-colors duration-300 md:text-2xl dark:text-darkmutedtext">
        {title}
      </h2>
    </div>
  );
}
