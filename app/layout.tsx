import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mismatch",
  description: "NHL moneyline discrepancy engine",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
