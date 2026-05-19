// 팀 로고 파일명 매핑 — 사이드바와 시뮬레이션 탭 양쪽에서 사용
const LOGO_MAP: Record<string, string> = {
  '울산 HD FC': '울산 HD FC.png',
  '전북 현대 모터스': '전북 현대 모터스.png',
  '광주FC': '광주 FC.png',
  '인천 유나이티드': '인천 유나이티드.png',
  '강원FC': '강원 FC.png',
  '대구FC': '대구 FC.png',
  '수원FC': '수원 FC.png',
  '포항 스틸러스': '포항 스틸러스.png',
  '김천 상무 프로축구단': '김천상무프로축구단.png',
  '제주SK FC': '제주 SK FC.png',
  'FC서울': 'FC 서울.png',
  '대전 하나 시티즌': '대전 하나 시티즌.png',
};

export function teamLogo(teamName: string): string {
  for (const [key, value] of Object.entries(LOGO_MAP)) {
    const compactKey = key.replace(/\s/g, '');
    if (teamName.includes(compactKey) || teamName.replace(/\s/g, '').includes(compactKey)) {
      return `/logos/${value}`;
    }
  }
  return `/logos/${teamName}.png`;
}
