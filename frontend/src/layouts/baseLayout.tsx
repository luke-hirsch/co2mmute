const BaseLayout = ({ children }: { children: React.ReactNode }) => {
  return (
    <div className="flex min-h-dvh min-w-screen items-center justify-center">
      {children}
    </div>
  );
};

export default BaseLayout;
