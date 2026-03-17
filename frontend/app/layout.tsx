import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "./lib/auth-context";

export const metadata: Metadata = {
  title: "Docs Research Copilot",
  description: "문서를 붙여넣고 AI로 요약합니다",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
