"""Remove imported YouTube videos that are not public.

Videos are matched by SHA-256 of the video ID. Matching posts go back to
draft so the author can republish them.
"""

import hashlib
import re

from django.db import migrations

VIDEO_ID_RE = re.compile(r'videoid="([A-Za-z0-9_-]{11})"')

NON_PUBLIC_VIDEO_HASHES = frozenset(
    {
        "225cffef85b25432f553020b7bed66b4a7caaaa3c109f27e6d5585cc49aa4940",
        "6ccbac56e9de4907ce546c6b0a8d6656cfe5ee411c7622ae5ec214eaf8bd2af4",
        "f538a282a5329be478d4f71af8215dc5a0de4337aed351fb0f4df8120d36a153",
        "b40d743a073863da9cfa8ce0c6b08e9710e139161342b64912fdf8f88526c25f",
        "a5150b0f058cc8242e0bbbbddaf9435dc1c6857289b80b8468644b1cb3a91f77",
        "20d2984f9cf6b54610c34240f4fd01feda763d7fca6a45499327597ea09f9685",
        "6c4566cc95f091bdb9509118bd6229935089a984b7c02ed009a5d0cad7b25134",
        "f70736c5624165d0d74b7a828bf32e0032953b9e833ef9b7ef9d8fb88cfb4120",
        "0d0930db68e2b2f0e45f0b4d647d7ce4038400717996c7dcb637e3f69149774c",
        "ce97cfe623fea43fa18c996e248ba0ce5de914c1b5872749db9f7aa5921dbd1d",
        "6a8ebd643cdf977b2c0e9eeead426aa9018f01893fb5f8a40e3680c336e769c9",
        "407433631549e44d044130f7e017e6a659ff2b9feab29558f89658610d9eacd7",
        "f8e5421e9732723df149b3bce86f587985eff19521c40e6dab4649ebcf508e61",
        "5b2178fdccfbe34a8c5808a72612381ac6e8b569fab42724994d2d9681780b14",
        "199d804658197d0ad3c016af11b0d304c972e2dd2ce47f6d179e8dc0ddeec381",
        "3808cca4d59bc764e5d4a6c5308fd724d6493f0cdf42f000223a7bef2d74c502",
        "35d68e5b3244566bd043836454cd74bdc9b1bedecf3adfd5cae50feafabe8999",
        "6dbd589098965de0e21355f170a28deb92100eabcb84c0e0fcc7c5aeeaf96af2",
        "fcc49459960d4beb2cc599e1bbd2d4bdde6d6942b59aab81dff7ed66be191770",
        "a3bda86c08b85a74122b89f3b763057699e300c4efc1b02e58295dc535a13862",
        "b49c70e3717ee0e0facbb36af2250b241a72809833ecfc0daefb88428cca597a",
        "30e1662b1c6b93e5fd3418f74ea13b0f989f5bcfabe8d4cc9ccae06fd812380d",
        "0639320513b90ac0a87817173a1e27d2f5249522a2ae5e44ef413d1268832bb5",
        "443c37cf2220b8484d06a6fa358e91fbc6727e1e06caed289554a63570ab2b46",
        "384646dcaf6ca8cac78c22b0ec0d8b145d7c93c6542b9a2aea0c07fd8387dafe",
        "204c1d5022bf5362dbea0fce2bea38773ae965a6850b12f9a676a78dcd43dca0",
        "616f402ae32e0d8900e5fd8551d25f996a152d0013d12fc9454cf3e0ecf96eba",
        "07e0b837948f55fc034ea144f5102b56c20b4ec36f3e089d1f59d0f5975b7a49",
        "e221d40f9667d4c22ba69396c860e1f7d7cf2d416acb680ae65b53eb259bd5f9",
        "bcccb325b9b08bcacf368e40bc5d5488ae87243129dc9062406604674d72d4dd",
        "86cc0227095b295b33279c9b311a444c3a498fd07f1daeb1711bded8981e36db",
        "2b27f02704ff4cc5b9483b0c71c76a366453f910e6dbbf433ab0b130ea3c4c96",
        "28ad22f18172a9f4112227be2471ef26852accd796003dab8ff11b32333e393a",
        "84ebf0a5f7ce59609173ea0822e1a2d9074baa049bf6bb8798c3fe1cdd5889ea",
        "c2f5ca4a6e41795ad4c02b940e43abbc8b1e54ce0ffad48e99ad6f6d4fbdefcd",
        "4c21007dd708ead1086caa8601ce3207fe0e6ed37a69e01db5d4a2d0e8f8633f",
        "40435aa0ae03ba4afe6843473ca59fa7fee76240d19ef6e8257381230722d834",
        "4b486b813afb4746086ea0ca4ffa6a1b7f0d0b4ff62d958c531ba611c294644a",
        "17e709e77946794b4f7b49affbbd4916745260f53cee9685a471791aaaffdbe1",
        "3e74f616ad97755973c9301df16038a91ad8178658485703a64c28ef85efd708",
    }
)


def _is_non_public(video_id):
    digest = hashlib.sha256(video_id.encode()).hexdigest()
    return digest in NON_PUBLIC_VIDEO_HASHES


def hide_non_public_youtube(apps, schema_editor):
    CreatorItem = apps.get_model("creators", "CreatorItem")
    EvePost = apps.get_model("posts", "EvePost")

    item_ids = [
        pk
        for pk, external_id in CreatorItem.objects.filter(
            provider="youtube"
        ).values_list("id", "external_id")
        if _is_non_public(external_id)
    ]
    CreatorItem.objects.filter(id__in=item_ids).delete()

    post_ids = [
        pk
        for pk, content in EvePost.objects.filter(
            state="published", content__contains="videoid="
        ).values_list("id", "content")
        if any(_is_non_public(v) for v in VIDEO_ID_RE.findall(content or ""))
    ]
    EvePost.objects.filter(id__in=post_ids).update(state="draft")


class Migration(migrations.Migration):
    dependencies = [
        ("creators", "0001_initial"),
        ("posts", "0008_evepost_campaign"),
    ]

    operations = [
        migrations.RunPython(
            hide_non_public_youtube, migrations.RunPython.noop
        ),
    ]
