import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DataAnalyst AI",
  description: "FastAPI, Next.js, and MongoDB Atlas starter",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
