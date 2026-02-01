// Next.js 루트 레이아웃 컴포넌트 - 전역 스타일 및 메타데이터 설정
import type { Metadata } from "next";
import "./globals.css";

// SEO 메타데이터 정의
export const metadata: Metadata = {
  title: "Matchday Scout | K리그 전술 분석",
  description: "K리그 이벤트 데이터 기반 AI 전술 분석 플랫폼",
};

// 루트 레이아웃 - 모든 페이지에 공통 적용
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
