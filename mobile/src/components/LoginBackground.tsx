import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';

import { colors } from '@/src/theme';
import { getLoginCover } from '@/src/utils/eveImage';

const FALLBACK_GRADIENT = ['#1a0808', colors.background, '#0a0a14'] as const;

export function LoginBackground() {
  const [imageFailed, setImageFailed] = useState(false);

  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none">
      {!imageFailed ? (
        <Image
          source={{ uri: getLoginCover() }}
          style={StyleSheet.absoluteFill}
          contentFit="cover"
          contentPosition="top center"
          transition={400}
          onError={() => setImageFailed(true)}
        />
      ) : null}
      <LinearGradient
        colors={
          imageFailed
            ? [...FALLBACK_GRADIENT]
            : ['rgba(0,0,0,0.25)', 'rgba(0,0,0,0.55)', 'rgba(0,0,0,0.94)']
        }
        locations={imageFailed ? [0, 0.55, 1] : [0, 0.4, 1]}
        style={StyleSheet.absoluteFill}
      />
    </View>
  );
}
