import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Matchday Scout | K리그 전술 분석",
  description: "K리그 이벤트 데이터 기반 AI 전술 분석 플랫폼",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
