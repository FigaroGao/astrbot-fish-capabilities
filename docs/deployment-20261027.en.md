# 2026-10-27: Combined tablet deployment and validation

[中文](deployment-20261027.md) · [0.8.0 capabilities](release-0.8.0.en.md)

## Current deployment

These previously offline changes are deployed to the AstrBot capability plugin on the MatePad; reading strategy is now v6. Only the capability plugin was reloaded, without restarting NapCat. Source/configuration were backed up, source hashes checked precisely, and deployment performed while idle. Only four capability settings were added/enabled:

- `bili_storyboard_enabled`
- `bili_gallery_scan_enabled`
- `bili_character_enabled`
- `codex_resets_enabled`

The final 74 local static source files match the device, and the capability plugin is active. Temporary diagnostic plugins were removed. QQ and OneBot were online before and after testing.

## Capabilities and evidence

| Capability | Validation completed | Actual limits |
| --- | --- | --- |
| Numbered overview, time windows/crops | Local selection, boundary, and unknown-ID tests; tablet visual calls work | Ordinary reading still primarily uses Bilibili previews, not the full video |
| Source-video image scan | Native Termux ffmpeg 9.0.2 installed; a real 65-second public video downloaded at about 1.49 MB, producing 130 sampled frames with a 0.5-second tail gap | The changing video reached the 48-page limit, so complete page reading is not claimed; no sound |
| Slide/chat page reading | Local and native ffmpeg tests; the final three-page text-bearing synthetic video conservatively retained 8 candidates, all 8 read with none unread | Compression variations can retain duplicates; flashes, blur, or long text may remain incompletely read |
| Visible scene but unclear text | Added partial status, separate page lists, and source limitations; partial recognition cannot count as complete | Unread/partial pages still need clearer evidence; no added OCR or full-transcription guarantee |
| Ad candidate filtering/refill | Synthetic regressions cover endpoints, confidence, valid IDs, refill, and refusing to summarize all-ad material | No real-ad accuracy benchmark; cannot guarantee removing every ad or zero false positives |
| AI character atlas | Three references load on tablet; DeepSeek/GPT/Claude reference samples match with account-identity flags false; a real Bilibili preview once matched GPT | Reference reuse is not an unseen-sample benchmark; a later full real-preview retest encountered HTTP 412 |
| Bilibili comment emote/image candidates | Real account returned 25 site emotes and 6 image candidates; 74 public images checked locally; root-comment candidate/selection-argument interception tests passed | No test image was uploaded or publicly posted; visible publication or autonomous selection is not guaranteed |
| Public Codex reset announcements | Tablet status/history/detail succeeded, source was fresh, and detail ID matched; owner query tool is active | Third-party announcements, not personal quota, fixed account windows, or confirmation of credit arrival |
| New-announcement notification | Exactly one unified `codex_resets` task, every 15 minutes; initial baseline suppresses old announcements | No fabricated new announcement or test QQ notification; a genuinely new announcement must arrive |

## Issues found and fixed on-device

1. The original short `Mozilla/5.0` user agent caused CDN HTTP 567. Downloads now use the existing SDK's normal playback user agent and Referer with a full-range request. HTTP 200 and 206 are validated separately; 206 must cover zero through the full total length, rather than treating a partial response as a complete file. No cookies or account credentials were sent to the media CDN, and signed URLs were not printed.
2. The SDK occasionally returns an initially disallowed media URL. Selection now considers only safe HTTPS primary/backup sources actually supplied by the SDK. It does not rewrite signed URLs or permit arbitrary domains/ports.
3. Equal timestamps could make cache reads choose an older strategy result. Descending rowid breaks the tie, covered by a frozen-time regression.
4. Page reading now has a partial state and sufficient structured output space. The v6 cache separates earlier unread results.

## HTTP 412 and logs

A later Bilibili public metadata request returned HTTP 412. Repeated probes stopped; there was no verification bypass, IP change, or extra test comment. Earlier successful streaming/scanning evidence remains valid, but does not prove that the entire subsequent real-site reading chain passed again. When an endpoint is unavailable, normal behavior reports the failure honestly or retains usable previews.

One temporary diagnostic plugin produced an ERROR because its uninstall name did not match. It was subsequently removed using the correct name. Historical errors are not presented as zero. The final temporary-probe list is empty, and the capability plugin remains active.

## Unchanged behavior

Nightly reflection remains at 05:00 Hong Kong time. Bilibili comments remain capped at 20 per rolling 24 hours with zero interval. Owner identity, core persona, private/group memory isolation, QQ recovery, and public-review policy were not changed.

## Local regression and backups

The final device-source regression passed 587 tests, including a real desktop ffmpeg synthetic test. The existing audioop deprecation notice is unrelated to this deployment. Private device evidence retains initial failures, CDN diagnostics, fixes, and final page-reading/source audits; overlapping test counts are not added together. Public-package regression is recorded separately in the validation log.

The tablet and computer retain private pre-deployment source/configuration backups and final source snapshots. Real configuration is marked PRIVATE and excluded from GitHub. This document records deployment; reusable source and documentation were published afterward, while the letter remains in the tablet's local mailbox.
