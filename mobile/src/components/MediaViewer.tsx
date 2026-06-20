import { useCallback, useState } from 'react';
import { StyleSheet, View, useWindowDimensions } from 'react-native';
import YoutubePlayer from 'react-native-youtube-iframe';

import { colors } from '@/src/theme';
import { spacing } from '@/src/theme/spacing';

interface MediaViewerProps {
  videoIds: string[];
}

export function MediaViewer({ videoIds }: MediaViewerProps) {
  const { width } = useWindowDimensions();
  const playerHeight = Math.round((width * 9) / 16);
  const [playingId, setPlayingId] = useState<string | null>(null);

  const onStateChange = useCallback((videoId: string) => {
    return (state: string) => {
      if (state === 'playing') {
        setPlayingId(videoId);
      } else if (state === 'paused' || state === 'ended') {
        setPlayingId((current) => (current === videoId ? null : current));
      }
    };
  }, []);

  if (videoIds.length === 0) {
    return null;
  }

  return (
    <View style={styles.container}>
      {videoIds.map((videoId) => (
        <View key={videoId} style={[styles.playerWrap, { height: playerHeight }]}>
          <YoutubePlayer
            height={playerHeight}
            width={width}
            play={playingId === videoId}
            videoId={videoId}
            onChangeState={onStateChange(videoId)}
            webViewProps={{
              androidLayerType: 'hardware',
            }}
          />
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: spacing.md,
  },
  playerWrap: {
    width: '100%',
    backgroundColor: '#000',
  },
});
