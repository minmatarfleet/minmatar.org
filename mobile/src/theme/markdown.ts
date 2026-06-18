import { StyleSheet } from 'react-native';
import type { MarkdownProps } from 'react-native-markdown-display';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';

export const markdownStyles: MarkdownProps['style'] = {
  body: {
    ...typography.body,
    color: colors.faded,
  },
  heading1: {
    ...typography.titleLg,
    color: colors.highlight,
    marginTop: spacing.xl,
    marginBottom: spacing.md,
  },
  heading2: {
    ...typography.title,
    color: colors.highlight,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  heading3: {
    ...typography.bodyStrong,
    color: colors.fleetYellow,
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  paragraph: {
    marginTop: 0,
    marginBottom: spacing.md,
  },
  strong: {
    color: colors.highlight,
    fontFamily: 'Montserrat_600SemiBold',
  },
  em: {
    color: colors.fleetYellow,
  },
  bullet_list: {
    marginBottom: spacing.md,
  },
  ordered_list: {
    marginBottom: spacing.md,
  },
  list_item: {
    marginBottom: spacing.sm,
  },
  hr: {
    backgroundColor: colors.border,
    height: 1,
    marginVertical: spacing.lg,
  },
  blockquote: {
    backgroundColor: colors.surfaceRaised,
    borderLeftWidth: 3,
    borderLeftColor: colors.fleetRed,
    paddingLeft: spacing.md,
    paddingVertical: spacing.sm,
    marginBottom: spacing.md,
  },
};
