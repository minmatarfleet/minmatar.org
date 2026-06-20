import { useEffect, type ReactNode } from 'react';
import { Dimensions, Modal, Pressable, StyleSheet, View, type ViewStyle } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';

import { colors } from '@/src/theme';

const SHEET_SLIDE_MS = 280;
const SHEET_SLIDE_OFFSET = Dimensions.get('window').height * 0.35;

interface BottomSheetProps {
  visible: boolean;
  onClose: () => void;
  children: ReactNode;
  sheetStyle?: ViewStyle;
  scrimAccessibilityLabel?: string;
}

export function BottomSheet({
  visible,
  onClose,
  children,
  sheetStyle,
  scrimAccessibilityLabel = 'Close',
}: BottomSheetProps) {
  const translateY = useSharedValue(SHEET_SLIDE_OFFSET);

  useEffect(() => {
    translateY.value = visible
      ? withTiming(0, { duration: SHEET_SLIDE_MS })
      : SHEET_SLIDE_OFFSET;
  }, [translateY, visible]);

  const sheetAnimatedStyle = useAnimatedStyle(() => ({
    transform: [{ translateY: translateY.value }],
  }));

  return (
    <Modal visible={visible} transparent animationType="none" onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <Pressable
          style={styles.scrim}
          onPress={onClose}
          accessibilityLabel={scrimAccessibilityLabel}
        />
        <Animated.View style={[styles.sheet, sheetStyle, sheetAnimatedStyle]}>{children}</Animated.View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    justifyContent: 'flex-end',
  },
  scrim: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: colors.scrim,
  },
  sheet: {
    backgroundColor: colors.surface,
  },
});
