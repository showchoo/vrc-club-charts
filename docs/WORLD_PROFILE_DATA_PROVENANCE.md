# World profile data provenance and uncertainty

The public World profile describes only what is actually present in the
catalog. The `掲載情報と確認範囲` panel separates three different admission
reasons:

- **DJタグによる掲載**: the World is listed due to a DJ tag, not a verified
  operating DJ player.
- **運営者による確認申告**: a site owner reports past DJ playback experience.
  This is not a third-party or independent technical check.
- **検査記録あり**: the separately maintained playback verification registry
  has an accepted record. It does *not* imply acoustic quality, all features
  or live-streaming operation were independently tested.

Other catalog signals are handled conservatively:

- `author_tag_*` values can be shown as **creator labels**. `system_*`
  and malformed tags are omitted. These tags are not evidence that a named
  piece of equipment is present, working, or appropriate for use by a DJ.
- Maximum and recommended capacity appear only when they are actual positive
  integer data. Contradictory recommended capacity is hidden.
- The World updated date is shown only when it is a valid, nonfuture,
  timezone-bearing ISO-8601 timestamp; unknown fields remain `—`.
- Existing `source` URL buttons are limited to known HTTPS providers
  (VRChat, vrcw.net and vrcmap.com), no embedded credentials or unexpected
  ports. Independent official World links use the validated World ID.
- All user-supplied labels are HTML-escaped; text or links are not generated
  from AI model prose, speculation or private data.

This is a **static profile improvement only**: no VRChat client access,
camera/video inspection, autonomous entry, new World admission, ranking
promotions, third-party account collection, or client permissions.

## Validate

```bash
python -m unittest tests.test_world_public_facts
python -m unittest discover -s tests -p "test_*.py"
python scripts/build_vercel.py
```

Google Search Console ranking and indexing may be measured only *after*
Vercel has deployed the matching commit. Existing index links, canonical
URLs and sitemap must remain unchanged.
