export {};

declare global {
  namespace YT {
    type PlayerState = number;

    interface PlayerOptions {
      videoId?: string;
      playerVars?: Record<string, string | number>;
      events?: {
        onReady?: (event: OnReadyEvent) => void;
      };
    }

    interface Player {
      destroy(): void;
      playVideo(): void;
      pauseVideo(): void;
      seekTo(seconds: number, allowSeekAhead: boolean): void;
      getCurrentTime(): number;
    }

    interface PlayerConstructor {
      new (elementId: string | HTMLElement, options: PlayerOptions): Player;
    }

    interface OnReadyEvent {
      target: Player;
    }
  }

  interface Window {
    YT?: {
      Player: YT.PlayerConstructor;
    };
    onYouTubeIframeAPIReady?: () => void;
  }
}
