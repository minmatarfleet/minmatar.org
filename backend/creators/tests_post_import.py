"""Tests for Reddit/YouTube → EvePost import helpers."""

from datetime import datetime, timezone as dt_timezone
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User

from app.test import TestCase
from creators.models import CreatorProvider
from creators.post_import import (
    ImportCandidate,
    apply_imports,
    candidate_from_reddit,
    classify_reddit,
    fetch_youtube_window,
    partition_candidates,
    reddit_image_url,
    reddit_post_content,
    rewrite_reddit_inline_images,
    youtube_post_content,
)
from posts.models import EvePost, EveTag


def _published():
    return datetime(2026, 8, 20, 12, 0, tzinfo=dt_timezone.utc)


class CreatorPostImportTestCase(TestCase):
    def test_reddit_image_url_unescapes_preview(self):
        url = reddit_image_url(
            {
                "url": "https://www.reddit.com/r/Eve/comments/abc/",
                "preview": {
                    "images": [
                        {
                            "source": {
                                "url": "https://preview.redd.it/x.png?width=100&amp;s=1"
                            }
                        }
                    ]
                },
            }
        )
        self.assertEqual(url, "https://preview.redd.it/x.png?width=100&s=1")

    def test_reddit_image_url_prefers_i_reddit(self):
        url = reddit_image_url({"url": "https://i.redd.it/poster.png"})
        self.assertEqual(url, "https://i.redd.it/poster.png")

    def test_classify_youtube_link_on_reddit_is_videos(self):
        tag, skip = classify_reddit(
            {
                "subreddit": "eve",
                "title": "AT XXII SUPER FEEDERS",
                "post_hint": "rich:video",
                "is_self": False,
                "link_url": "https://www.youtube.com/watch?v=09-PtM6K3Xs",
            }
        )
        self.assertEqual(tag, "Videos")
        self.assertIsNone(skip)

    def test_reddit_youtube_link_uses_lite_youtube_content(self):
        candidate = candidate_from_reddit(
            {
                "id": "1w56c27",
                "title": "AT XXII SUPER FEEDERS",
                "permalink": (
                    "https://www.reddit.com/r/Eve/comments/"
                    "1w56c27/at_xxii_super_feeders/"
                ),
                "link_url": "https://www.youtube.com/watch?v=09-PtM6K3Xs",
                "subreddit": "eve",
                "is_self": False,
                "post_hint": "rich:video",
                "removed": False,
                "selftext": "",
                "image_url": "https://external-preview.redd.it/x.jpeg",
                "published_at": _published(),
            },
            self.user.username,
        )
        self.assertEqual(candidate.suggested_tag, "Videos")
        self.assertIn('videoid="09-PtM6K3Xs"', candidate.content)
        self.assertIn(
            "i.ytimg.com/vi/09-PtM6K3Xs/maxresdefault.jpg", candidate.content
        )
        self.assertNotIn("external-preview.redd.it", candidate.content)

    def test_classify_image_on_eve_is_propaganda(self):
        tag, skip = classify_reddit(
            {
                "subreddit": "eve",
                "title": "Green numbers go brrr",
                "post_hint": "image",
                "is_self": False,
                "image_url": "https://i.redd.it/x.png",
            }
        )
        self.assertEqual(tag, "Propaganda")
        self.assertIsNone(skip)

    def test_classify_aar_is_dispatches(self):
        tag, skip = classify_reddit(
            {
                "subreddit": "eve",
                "title": "AAR: 350B DOWN IN KAMELA",
                "post_hint": "",
                "is_self": True,
            }
        )
        self.assertEqual(tag, "Dispatches")
        self.assertIsNone(skip)

    def test_classify_self_post_is_dispatches(self):
        tag, skip = classify_reddit(
            {
                "subreddit": "eve",
                "title": "The problem with loyalty points",
                "post_hint": "",
                "is_self": True,
            }
        )
        self.assertEqual(tag, "Dispatches")
        self.assertIsNone(skip)

    def test_rewrite_reddit_preview_urls_to_markdown_images(self):
        bare = rewrite_reddit_inline_images(
            "Hello\n\nhttps://preview.redd.it/abc.png?width=100&s=1\n\nBye"
        )
        self.assertIn(
            "![image](https://preview.redd.it/abc.png?width=100&s=1)", bare
        )
        linked = rewrite_reddit_inline_images(
            "[Source: Warlock](https://preview.redd.it/xyz.png?width=10)"
        )
        self.assertEqual(
            linked,
            "![Source: Warlock](https://preview.redd.it/xyz.png?width=10)",
        )
        external = rewrite_reddit_inline_images(
            "https://external-preview.redd.it/abc.jpg?width=10"
        )
        self.assertEqual(
            external,
            "![image](https://external-preview.redd.it/abc.jpg?width=10)",
        )

    def test_classify_skips_other_subreddits(self):
        tag, skip = classify_reddit(
            {
                "subreddit": "funny",
                "title": "meme",
                "is_self": False,
                "post_hint": "image",
            }
        )
        self.assertEqual(skip, "subreddit:funny")
        self.assertEqual(tag, "Propaganda")

    def test_reddit_and_youtube_content_shapes(self):
        reddit = reddit_post_content(
            permalink="https://www.reddit.com/r/Eve/comments/abc/title/",
            image_url="https://i.redd.it/x.png",
            selftext="",
        )
        self.assertIn("![image](https://i.redd.it/x.png)", reddit)
        self.assertIn("comments/abc/", reddit)
        youtube = youtube_post_content("SK0jimasEuc")
        self.assertIn('videoid="SK0jimasEuc"', youtube)
        self.assertIn("i.ytimg.com/vi/SK0jimasEuc/maxresdefault.jpg", youtube)

    def test_partition_skips_existing_youtube_and_title(self):
        EvePost.objects.create(
            title="Existing video",
            state="published",
            seo_description="x",
            slug="existing-video",
            content=youtube_post_content("SK0jimasEuc"),
            user=self.user,
        )
        EvePost.objects.create(
            title="Green numbers go brrr",
            state="published",
            seo_description="x",
            slug="green",
            content="body",
            user=self.user,
        )
        youtube = ImportCandidate(
            provider=CreatorProvider.YOUTUBE,
            external_id="SK0jimasEuc",
            title="AT XXII Ad",
            url="https://www.youtube.com/watch?v=SK0jimasEuc",
            published_at=_published(),
            suggested_tag="Videos",
            content=youtube_post_content("SK0jimasEuc"),
            seo_description="AT",
            author_username=self.user.username,
        )
        reddit = ImportCandidate(
            provider=CreatorProvider.REDDIT,
            external_id="1vlhgk0",
            title="Green numbers go brrr",
            url="https://www.reddit.com/r/Eve/comments/1vlhgk0/green_numbers_go_brrr/",
            published_at=_published(),
            suggested_tag="Propaganda",
            content="![image](https://i.redd.it/x.png)",
            seo_description="Green",
            author_username=self.user.username,
        )
        fresh = ImportCandidate(
            provider=CreatorProvider.REDDIT,
            external_id="1vyvwvo",
            title="Supply and Trade",
            url="https://www.reddit.com/r/Eve/comments/1vyvwvo/supply/",
            published_at=_published(),
            suggested_tag="Propaganda",
            content="![image](https://i.redd.it/y.png)\n",
            seo_description="Supply",
            author_username=self.user.username,
        )
        to_import, skipped = partition_candidates(
            [youtube, reddit, fresh],
            posts=EvePost.objects.all(),
        )
        self.assertEqual([c.title for c in to_import], ["Supply and Trade"])
        reasons = {c.skip_reason for c in skipped}
        self.assertEqual(reasons, {"existing_youtube", "existing_title"})

    def test_apply_imports_writes_tagged_post_with_source_date(self):
        EveTag.objects.create(tag="Propaganda")
        published = _published()
        candidate = candidate_from_reddit(
            {
                "id": "1vlhgk0",
                "title": "Green numbers go brrr",
                "url": "https://www.reddit.com/r/Eve/comments/1vlhgk0/x/",
                "subreddit": "eve",
                "is_self": False,
                "post_hint": "image",
                "removed": False,
                "selftext": "",
                "image_url": "https://i.redd.it/poster.png",
                "published_at": published,
            },
            self.user.username,
        )
        created = apply_imports([candidate], state="published")
        self.assertEqual(len(created), 1)
        post = EvePost.objects.get(pk=created[0].pk)
        self.assertEqual(post.state, "published")
        self.assertEqual(post.date_posted, published)
        self.assertEqual(
            list(post.tags.values_list("tag", flat=True)), ["Propaganda"]
        )
        self.assertIn("i.redd.it/poster.png", post.content)

    @patch("creators.post_import.User.objects.create")
    def test_apply_imports_reuses_existing_username(self, create_user):
        other = User.objects.create_user("orionsasolo")
        candidate = ImportCandidate(
            provider=CreatorProvider.YOUTUBE,
            external_id="abcABCabcAB",
            title="Shameless Minmatar Fleet Plug",
            url="https://www.youtube.com/watch?v=abcABCabcAB",
            published_at=_published(),
            suggested_tag="Videos",
            content=youtube_post_content("abcABCabcAB"),
            seo_description="plug",
            author_username="orionsasolo",
        )
        created = apply_imports([candidate])
        self.assertEqual(created[0].user_id, other.id)
        create_user.assert_not_called()

    def test_apply_imports_skips_missing_username(self):
        candidate = ImportCandidate(
            provider=CreatorProvider.YOUTUBE,
            external_id="abcABCabcAB",
            title="Missing author video",
            url="https://www.youtube.com/watch?v=abcABCabcAB",
            published_at=_published(),
            suggested_tag="Videos",
            content=youtube_post_content("abcABCabcAB"),
            seo_description="plug",
            author_username="does-not-exist",
        )
        created = apply_imports([candidate])
        self.assertEqual(created, [])
        self.assertFalse(
            EvePost.objects.filter(title="Missing author video").exists()
        )

    @patch("creators.post_import._youtube_rss_window")
    @patch("creators.post_import._youtube_playlist_window")
    @patch("creators.post_import._youtube_access_token")
    def test_youtube_empty_playlist_falls_back_to_rss(
        self, access_token, playlist_window, rss_window
    ):
        access_token.return_value = "tok"
        playlist_window.return_value = []
        rss_window.return_value = [{"id": "SK0jimasEuc"}]
        account = MagicMock(platform_user_id="UCexample", token_invalid=False)
        result = fetch_youtube_window(account, cutoff=_published())
        rss_window.assert_called_once_with("UCexample", _published())
        self.assertEqual(result, [{"id": "SK0jimasEuc"}])
