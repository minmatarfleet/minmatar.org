const LITE_YOUTUBE_OPEN_PATTERN = /<lite-youtube[^>]*videoid=["']([^"']+)["'][^>]*>/gi;
const LITE_YOUTUBE_BLOCK_PATTERN = /<lite-youtube[\s\S]*?<\/lite-youtube>/gi;
const LITE_YOUTUBE_SELF_PATTERN = /<lite-youtube[^>]*\/>/gi;
const HIDDEN_THUMB_DIV_PATTERN = /<div class="hidden">[\s\S]*?<\/div>/gi;

export function extractYoutubeVideoIds(content: string): string[] {
  const ids: string[] = [];
  let match: RegExpExecArray | null;
  const pattern = new RegExp(LITE_YOUTUBE_OPEN_PATTERN.source, LITE_YOUTUBE_OPEN_PATTERN.flags);

  while ((match = pattern.exec(content)) !== null) {
    ids.push(match[1]);
  }

  return ids;
}

export function isVideoPost(content: string): boolean {
  return extractYoutubeVideoIds(content).length > 0;
}

export function stripMediaEmbeds(content: string): string {
  return content
    .replace(HIDDEN_THUMB_DIV_PATTERN, '')
    .replace(LITE_YOUTUBE_BLOCK_PATTERN, '')
    .replace(LITE_YOUTUBE_SELF_PATTERN, '')
    .trim();
}

export function hasReadableMarkdownContent(content: string): boolean {
  return stripMediaEmbeds(content).length > 0;
}
