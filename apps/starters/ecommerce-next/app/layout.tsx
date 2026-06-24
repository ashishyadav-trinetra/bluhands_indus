import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  // The agent personalizes title/description from the merchant's brand kit.
  title: "Storefront",
  description: "Built with BluHands.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
