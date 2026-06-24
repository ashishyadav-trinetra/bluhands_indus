import { ReactNode } from "react";

interface TabContainerProps {
  children: ReactNode;
}

export function TabContainer({ children }: TabContainerProps) {
  return (
    <div className="bg-[#1a1c22] border border-[#2a2d37] rounded-xl flex flex-col h-full w-full">
      {children}
    </div>
  );
}
