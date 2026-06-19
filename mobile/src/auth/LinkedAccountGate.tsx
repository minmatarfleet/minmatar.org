import type { ReactNode } from 'react';

import { useAuth } from '@/src/auth/AuthContext';
import { LinkAccountPrompt } from '@/src/components/LinkAccountPrompt';

interface LinkedAccountGateProps {
  children: ReactNode;
  fallback?: ReactNode;
}

export function LinkedAccountGate({ children, fallback }: LinkedAccountGateProps) {
  const { isLinked } = useAuth();

  if (!isLinked) {
    return fallback ?? <LinkAccountPrompt compact />;
  }

  return children;
}

export function useIsLinked(): boolean {
  return useAuth().isLinked;
}
