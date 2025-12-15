interface GameDetailProps {
  id: string;
}
export default function GameDetail({ id }: GameDetailProps) {
  return (
    <div className="flex flex-col items-center text-center text-main dark:text-darktext">
      <h2 className="mt-7 text-xl font-light text-muted transition-colors duration-300 md:text-2xl dark:text-darkmutedtext">
        {id}
      </h2>
      <p>
        Lorem ipsum dolor sit, amet consectetur adipisicing elit. Debitis
        possimus modi officiis est. Recusandae, ea! Ut iusto animi, eveniet
        facere maxime iste tempore voluptatum, id saepe soluta vel beatae
        consectetur.
      </p>
    </div>
  );
}
