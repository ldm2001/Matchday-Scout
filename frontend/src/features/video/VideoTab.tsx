'use client';

import VideoAnalysis from '@/components/VideoAnalysis';
import styles from '@/app/page.module.css';

// 비디오 분석 탭 - 업로드/추적 UI 래퍼
export default function VideoTab() {
  return (
    <div className={styles.videoSection}>
      <VideoAnalysis />
    </div>
  );
}
