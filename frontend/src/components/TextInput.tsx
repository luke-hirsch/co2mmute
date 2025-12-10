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
  const baseBorder = "border border-subtle dark:border-darksubtle";
  const errorStyles =
    "border border-danger-500 bg-danger-100 text-danger-700 dark:border-danger-500 dark:bg-darkelevated dark:text-danger-500";

  if (disabled)
    return (
      <div className="flex justify-between items-center">
        <input
          placeholder={placeholder}
          onFocus={() => setError && setError(false)}
          name={name}
          type={type}
          value={value}
          className={`${margin} ${padding} rounded w-full bg-subtle text-muted ${additionalClasses} ${baseBorder} dark:bg-darkelevated dark:text-darkmutedtext`}
          disabled
        />
        {label && (
          <label
            htmlFor={name}
            className="text-sm"
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
        className={`${margin} ${padding} rounded w-full bg-surface text-main placeholder:text-muted transition ease-in-out duration-300 focus:outline-none focus:border-primary-500 focus:ring-0 ${additionalClasses} ${
          error ? errorStyles : baseBorder
        } dark:bg-darkelevated dark:text-darktext dark:placeholder:text-darkmutedtext`}
      />
      {label && (
        <label
          htmlFor={name}
          className="text-sm"
        >
          {label}
        </label>
      )}
    </div>
  );
}
