import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Text } from 'react-native-paper';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { BottomSheet } from '@/src/components/BottomSheet';
import type { ActivityItem } from '@/src/types/activity';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';
import { formatEveTimeShort, formatTimelineTime } from '@/src/utils/eveTime';
import { kindLabel, getActivityAccent, mapActivityToDetail } from '@/src/utils/activityDisplay';

interface ActivityDetailModalProps {
  item: ActivityItem | null;
  onClose: () => void;
}

export function ActivityDetailModal({ item, onClose }: ActivityDetailModalProps) {
  const insets = useSafeAreaInsets();

  if (!item) return null;

  const detail = mapActivityToDetail(item);
  const { accent } = getActivityAccent(item);

  return (
    <BottomSheet
      visible
      onClose={onClose}
      sheetStyle={{
        maxHeight: '78%',
        borderTopWidth: 3,
        borderTopColor: accent,
        paddingBottom: Math.max(insets.bottom, spacing.lg),
      }}
    >
      <View style={styles.sheetHeader}>
        <View style={styles.sheetHeaderText}>
          <Text style={[styles.sheetLabel, { color: accent }]}>{kindLabel(item)}</Text>
          <Text style={styles.sheetTime}>
            {formatTimelineTime(item.timestamp)} · {formatEveTimeShort(item.timestamp)} EVE
          </Text>
        </View>
        <Pressable onPress={onClose} hitSlop={12} style={styles.closeBtn}>
          <MaterialCommunityIcons name="close" size={22} color={colors.faded} />
        </Pressable>
      </View>

      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
        <Text style={styles.title}>{detail.title}</Text>
        <Text style={styles.subheader}>{detail.subheader}</Text>

        {detail.body ? <Text style={[styles.body, { borderLeftColor: accent }]}>{detail.body}</Text> : null}

        <View style={styles.sections}>
          {detail.sections.map((section) => (
            <View key={section.label} style={styles.sectionRow}>
              <Text style={styles.sectionLabel}>{section.label}</Text>
              <Text style={styles.sectionValue}>{section.value}</Text>
            </View>
          ))}
        </View>
      </ScrollView>
    </BottomSheet>
  );
}

const styles = StyleSheet.create({
  sheetHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  sheetHeaderText: {
    flex: 1,
    gap: spacing.xs,
  },
  sheetLabel: {
    ...typography.overline,
    fontSize: 9,
  },
  sheetTime: {
    ...typography.caption,
    color: colors.faded,
    fontSize: 11,
  },
  closeBtn: {
    padding: spacing.xs,
    marginLeft: spacing.md,
  },
  scroll: {
    flexGrow: 0,
  },
  scrollContent: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.xxxl,
    gap: spacing.sm,
  },
  title: {
    ...typography.bodyStrong,
    color: colors.highlight,
    fontSize: 16,
    lineHeight: 22,
  },
  subheader: {
    ...typography.caption,
    color: colors.faded,
    fontSize: 13,
    lineHeight: 18,
  },
  body: {
    ...typography.body,
    color: colors.faded,
    fontSize: 14,
    lineHeight: 21,
    marginTop: spacing.sm,
    paddingLeft: spacing.md,
    borderLeftWidth: 2,
  },
  sections: {
    marginTop: spacing.lg,
    gap: spacing.md,
    paddingTop: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  sectionRow: {
    gap: 2,
  },
  sectionLabel: {
    ...typography.overline,
    color: colors.muted,
    fontSize: 9,
  },
  sectionValue: {
    ...typography.caption,
    color: colors.highlight,
    fontSize: 13,
    lineHeight: 18,
  },
});
