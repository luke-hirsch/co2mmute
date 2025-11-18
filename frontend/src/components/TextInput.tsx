interface TextInputProps {
  name: string;
  placeholder?: string;
  type?: "text" | "email" | "password" | "number" | "date" | "file" | "time";
  value?: string | number | readonly string[] | undefined;
  padding?: string;
  margin?: string;
  error?: boolean;
  setError?: (value: boolean) => void;
  additionalClasses?: string;
  disabled?: boolean;
  label?: string | false;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  onFocus?: (e: React.FocusEvent<HTMLInputElement>) => void;
}
export default function TextInput({
  placeholder,
  name,
  type = "text",
  value = undefined,
  padding = "p-2",
  margin = "mb-4",
  error = false,
  setError,
  additionalClasses,
  disabled = false,
  label,
  onChange,
  onKeyDown,
}: TextInputProps) {
  const border = error
    ? " border-2 border-error-500"
    : " border border-zinc-500";

  if (disabled)
    return (
      <div className="flex justify-between items-center">
        <input
          placeholder={placeholder}
          onFocus={() => setError && setError(false)}
          name={name}
          type={type}
          value={value}
          className={`${margin} ${padding} placeholder:text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 text-zinc-700 rounded w-full ${additionalClasses} border border-zinc-500`}
          disabled
        />
        {label && (
          <label
            htmlFor={name}
            className="text-zinc-500 dark:text-zinc-400 text-sm "
          >
            {label}
          </label>
        )}
      </div>
    );
  return (
    <div className="flex justify-between items-center">
      <input
        onChange={onChange}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        onFocus={() => setError && setError(false)}
        name={name}
        type={type}
        value={value}
        className={`${margin} ${padding} focus:outline-none dark:focus:bg-white dark:focus:text-black focus:border-resi-500 transition ease-in-out duration-500 focus:ring-0 placeholder:text-zinc-700 text-zinc-700 rounded w-full dark:bg-zinc-900 dark:text-zinc-300 ${additionalClasses} ${border}`}
      />
      {label && (
        <label
          htmlFor={name}
          className="text-zinc-500 dark:text-zinc-400 text-sm "
        >
          {label}
        </label>
      )}
    </div>
  );
}
