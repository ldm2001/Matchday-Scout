import { Pattern, SetPieceRoutine, Hub } from '@/types';
import { TeamAnalysis } from '@/lib/api';

type ScoredItem = {
  category: string;
  title: string;
  description: string;
  score: number;
};

const mean = (values: number[]) => {
  if (!values.length) return 0;
  const total = values.reduce((sum, value) => sum + (Number.isFinite(value) ? value : 0), 0);
  return total / values.length;
};

const scoreClamp = (value: number, min: number, max: number) => {
  return Math.min(max, Math.max(min, Math.floor(value)));
};

const generateSummary = (strengths: ScoredItem[], weaknesses: ScoredItem[]) => {
  if (!strengths.length && !weaknesses.length) return '분석할 데이터가 부족합니다.';

  const parts: string[] = [];
  if (strengths.length) {
    const categories = Array.from(new Set(strengths.map((s) => s.category)));
    parts.push(`${categories.join(', ')} 분야에서 강점을 보입니다`);
  }
  if (weaknesses.length) {
    const categories = Array.from(new Set(weaknesses.map((w) => w.category)));
    parts.push(`${categories.join(', ')} 분야는 개선이 필요합니다`);
  }

  return `${parts.join('. ')}.`;
};

export function buildTeamAnalysis(
  teamId: number,
  patterns: Pattern[],
  setpieces: SetPieceRoutine[],
  hubs: Hub[],
): TeamAnalysis {
  const strengths: ScoredItem[] = [];
  const weaknesses: ScoredItem[] = [];
  const insights: string[] = [];

  if (patterns.length) {
    const shotRates = patterns.map((p) => Number(p.shot_conversion_rate) || 0);
    const maxShotRate = Math.max(...shotRates);
    const totalFrequency = patterns.reduce((sum, p) => sum + (Number(p.frequency) || 0), 0);

    if (maxShotRate > 0.25) {
      strengths.push({
        category: '공격',
        title: '높은 슈팅 전환율',
        description: `최고 ${(maxShotRate * 100).toFixed(0)}% 전환율의 위험한 공격 패턴 보유`,
        score: scoreClamp(maxShotRate * 300, 0, 100),
      });
    } else if (maxShotRate < 0.1) {
      weaknesses.push({
        category: '공격',
        title: '낮은 결정력',
        description: `공격 패턴의 슈팅 전환율이 ${(maxShotRate * 100).toFixed(0)}%로 저조`,
        score: scoreClamp(maxShotRate * 300, 20, 100),
      });
    }

    if (totalFrequency > 500) {
      strengths.push({
        category: '공격',
        title: '다양한 공격 루트',
        description: `${totalFrequency}회의 다채로운 공격 시도`,
        score: scoreClamp(totalFrequency / 8, 0, 100),
      });
    }

    if (patterns.length < 4) {
      weaknesses.push({
        category: '공격',
        title: '패턴 다양성 부족',
        description: `${patterns.length}개의 한정된 공격 루트만 보유`,
        score: 50,
      });
    }

    const avgDuration = mean(patterns.map((p) => Number(p.avg_duration) || 0));
    if (avgDuration > 40) {
      weaknesses.push({
        category: '공격',
        title: '느린 빌드업 템포',
        description: `평균 ${avgDuration.toFixed(0)}초의 긴 빌드업, 역습에 취약 가능`,
        score: 55,
      });
    }
  }

  if (setpieces.length) {
    const corners = setpieces.filter((s) => String(s.type).includes('Corner'));
    const freekicks = setpieces.filter((s) => String(s.type).includes('Freekick'));

    if (corners.length) {
      const avgCornerRate = mean(corners.map((c) => Number(c.shot_rate) || 0));
      if (avgCornerRate > 0.3) {
        strengths.push({
          category: '세트피스',
          title: '코너킥 위협',
          description: `코너킥에서 ${(avgCornerRate * 100).toFixed(0)}% 슈팅 전환`,
          score: scoreClamp(avgCornerRate * 200, 0, 100),
        });
      } else if (avgCornerRate < 0.15) {
        weaknesses.push({
          category: '세트피스',
          title: '코너킥 효율 저조',
          description: `코너킥 슈팅 전환율 ${(avgCornerRate * 100).toFixed(0)}%로 개선 필요`,
          score: scoreClamp(avgCornerRate * 200, 20, 100),
        });
      }
    }

    if (freekicks.length) {
      const avgFkRate = mean(freekicks.map((f) => Number(f.shot_rate) || 0));
      if (avgFkRate > 0.25) {
        strengths.push({
          category: '세트피스',
          title: '프리킥 전문가',
          description: `프리킥에서 ${(avgFkRate * 100).toFixed(0)}% 슈팅 전환`,
          score: scoreClamp(avgFkRate * 200, 0, 100),
        });
      }

      if (avgFkRate < 0.2) {
        weaknesses.push({
          category: '세트피스',
          title: '프리킥 활용 저조',
          description: `프리킥 슈팅 전환율 ${(avgFkRate * 100).toFixed(0)}%`,
          score: 40,
        });
      }
    }
  }

  if (hubs.length) {
    const topHub = hubs[0];
    const hubScore = Number(topHub.hub_score) || 0;
    const passesMade = Number(topHub.passes_made) || 0;

    if (hubScore > 0.8) {
      strengths.push({
        category: '빌드업',
        title: '핵심 플레이메이커',
        description: `${topHub.player_name || '선수'}가 공격 조율의 핵심`,
        score: scoreClamp(hubScore * 100, 0, 100),
      });
    }

    if (passesMade > 400) {
      strengths.push({
        category: '빌드업',
        title: '안정적 볼 순환',
        description: `핵심 허브가 ${passesMade}회 패스로 경기 지배`,
        score: scoreClamp(passesMade / 5, 0, 100),
      });
    }

    if (hubs.length >= 2) {
      const hubScores = hubs.slice(0, 3).map((h) => Number(h.hub_score) || 0);
      if (hubScores[0] > hubScores[1] * 1.5) {
        weaknesses.push({
          category: '빌드업',
          title: '허브 의존도 높음',
          description: `1번 허브 ${hubs[0].player_name || ''}에 과도하게 의존`,
          score: 45,
        });
      }
    }

    if (hubs.length >= 2) {
      const receives = hubs.slice(0, 2).map((h) => Number(h.passes_received) || 0);
      const ratio = receives[0] / Math.max(receives[1], 1);
      if (ratio > 1.8) {
        weaknesses.push({
          category: '빌드업',
          title: '패스 루트 예측 가능',
          description: '특정 선수로의 패스 집중, 상대 압박에 취약',
          score: 50,
        });
      }
    }
  }

  if (strengths.length) {
    const topStrength = strengths.reduce((best, item) => (item.score > best.score ? item : best));
    insights.push(`💪 가장 큰 강점: ${topStrength.title}`);
  }
  if (weaknesses.length) {
    const topWeakness = weaknesses.reduce((worst, item) => (item.score < worst.score ? item : worst));
    insights.push(`⚠️ 개선 필요: ${topWeakness.title}`);
  }
  if (patterns.length >= 3) {
    insights.push(`📊 ${patterns.length}개의 주요 공격 패턴 보유`);
  }
  if (setpieces.length) {
    insights.push(`⚽ ${setpieces.length}개의 세트피스 루틴 분석됨`);
  }

  const allScores = [...strengths, ...weaknesses].map((item) => item.score);
  const overallScore = allScores.length ? Math.floor(mean(allScores)) : 50;

  return {
    team_id: teamId,
    overall_score: overallScore,
    strengths: strengths.sort((a, b) => b.score - a.score).slice(0, 3),
    weaknesses: weaknesses.sort((a, b) => a.score - b.score).slice(0, 3),
    insights: insights.slice(0, 4),
    summary: generateSummary(strengths, weaknesses),
  };
}
