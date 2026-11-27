from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from creators.models import YouTubeAnnouncement
from creators.youtube_announce import announce_new_uploads, parse_feed

CHANNEL = "UCtestchannel"
DISCORD_CHANNEL = 555


def entry(video_id, title, *, short=False, age=timedelta(hours=1)):
    published = (timezone.now() - age).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    link = (
        f"https://www.youtube.com/shorts/{video_id}"
        if short
        else f"https://www.youtube.com/watch?v={video_id}"
    )
    return f"""
 <entry>
  <id>yt:video:{video_id}</id>
  <yt:videoId>{video_id}</yt:videoId>
  <yt:channelId>{CHANNEL}</yt:channelId>
  <title>{title}</title>
  <link rel="alternate" href="{link}"/>
  <published>{published}</published>
 </entry>"""


def feed(*entries):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" '
        'xmlns="http://www.w3.org/2005/Atom">\n'
        f' <link rel="alternate" href="https://www.youtube.com/channel/{CHANNEL}"/>'
        + "".join(entries)
        + "\n</feed>"
    ).encode()


def response(content, status=200):
    mock = MagicMock()
    mock.status_code = status
    mock.content = content
    return mock


@override_settings(
    YOUTUBE_ANNOUNCE_CHANNEL_ID=CHANNEL,
    DISCORD_YOUTUBE_ANNOUNCE_CHANNEL_ID=DISCORD_CHANNEL,
)
@patch("creators.youtube_announce.queue_channel_message")
@patch("creators.youtube_announce.requests.get")
class AnnounceYouTubeUploadsTestCase(TestCase):
    def seed(self, video_id="old"):
        YouTubeAnnouncement.objects.create(
            youtube_channel_id=CHANNEL,
            video_id=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}",
        )

    def test_parse_feed_tells_shorts_from_videos(self, get, queue):
        videos = parse_feed(
            feed(entry("s1", "A short", short=True), entry("v1", "A video"))
        )
        self.assertEqual(
            [(v.video_id, v.is_short, v.url) for v in videos],
            [
                ("s1", True, "https://www.youtube.com/shorts/s1"),
                ("v1", False, "https://www.youtube.com/watch?v=v1"),
            ],
        )
        get.assert_not_called()
        queue.assert_not_called()

    def test_first_poll_records_without_posting(self, get, queue):
        get.return_value = response(feed(entry("v1", "Backlog")))
        result = announce_new_uploads()
        self.assertTrue(result["first_poll"])
        self.assertEqual(result["recorded"], ["v1"])
        queue.assert_not_called()
        row = YouTubeAnnouncement.objects.get(video_id="v1")
        self.assertIsNone(row.announced_at)

    def test_posts_new_short_and_video_oldest_first(self, get, queue):
        self.seed()
        get.return_value = response(
            feed(
                entry("s1", "Newest short", short=True),
                entry("v1", "Earlier video", age=timedelta(hours=3)),
                entry("old", "Seen before"),
            )
        )
        result = announce_new_uploads()
        self.assertEqual(result["announced"], ["v1", "s1"])
        messages = [c.kwargs["message"] for c in queue.call_args_list]
        self.assertEqual(
            messages,
            [
                "New video from Minmatar Fleet: **Earlier video**\n"
                "https://www.youtube.com/watch?v=v1",
                "New short from Minmatar Fleet: **Newest short**\n"
                "https://www.youtube.com/shorts/s1",
            ],
        )
        for call in queue.call_args_list:
            self.assertEqual(call.args, (DISCORD_CHANNEL,))
        self.assertIsNotNone(
            YouTubeAnnouncement.objects.get(video_id="s1").announced_at
        )

    def test_second_run_posts_nothing(self, get, queue):
        self.seed()
        get.return_value = response(feed(entry("v1", "New")))
        announce_new_uploads()
        announce_new_uploads()
        self.assertEqual(queue.call_count, 1)

    def test_old_upload_is_recorded_not_posted(self, get, queue):
        self.seed()
        get.return_value = response(
            feed(entry("v1", "Old one", age=timedelta(days=5)))
        )
        result = announce_new_uploads()
        self.assertEqual(result["recorded"], ["v1"])
        queue.assert_not_called()

    def test_feed_error_changes_nothing(self, get, queue):
        get.return_value = response(b"", status=500)
        self.assertEqual(announce_new_uploads()["status"], "feed_unavailable")
        self.assertFalse(YouTubeAnnouncement.objects.exists())
        queue.assert_not_called()

    @override_settings(DISCORD_YOUTUBE_ANNOUNCE_CHANNEL_ID=0)
    def test_disabled_without_a_discord_channel(self, get, queue):
        self.assertEqual(announce_new_uploads()["status"], "disabled")
        get.assert_not_called()
        queue.assert_not_called()
