# Ordinary video: scene overview → model selection → source-frame details

October 31, 2026, strategy 10. This independently implemented Python service borrows the addressable-overview and local-detail workflow from [dsh-video-storyboard](https://github.com/SAOS-3624/dsh-video-storyboard). It does not require DSH or Node, does not port every upstream algorithm, and does not inherit the upstream 384-token accounting claim.

## Routing

Keep existing preview classification and character-reference matching. `chat`, `slides`, suspected static-image material and the existing image-reading fallback after preview failure still call the original `read_pages` and `GalleryScanner.scan`. The gallery implementation, page limits, missing-page reports and related settings are unchanged.

Ordinary videos use SceneReader. Obtain a source under normal playback permissions, limited to 96 MiB and ten minutes. Temporary files stay local and are removed after completion or cancellation. Single-threaded ffmpeg decodes two frames per second at 64×36. HSV differences and a local baseline identify candidate changes; overview times are distributed by change density and include both timeline endpoints. This is not frame-by-frame scene detection and may miss short flashes.

Overview images are extracted again from the source with a maximum dimension of 640 and include IDs, timestamps, time ranges and available subtitle samples. The model decides whether more detail is needed, selecting normalized crops by actual ID or up to two windows of at most thirty seconds. Windows are decoded again from the same source rather than selecting only old thumbnails. At most six detail images are included, with a maximum dimension of 1600 and no source upscaling. A 360p source is never presented as high-resolution footage.

Validate all IDs, crop coordinates, time ranges and finite numeric values. Explicit ads still require observed endpoints, confidence of at least 0.9 and commercial-promotion evidence; detail selection cannot restore excluded ranges. Uncertain material stays. Source/download/scan failures explicitly report `scene_fallback` and use the limited preview route rather than claiming a successful scene scan. A failed visual plan uses the overview without unbounded retries.

## Cost and receipts

The ordinary route uses at most three vision calls: existing classification/character references, new overview selection, and final interpretation with selected details. No additional resident model or ASR is introduced. Requests contain no private conversation or long-term memory and must not execute instructions found in the video. Existing reading caches are reused after version invalidation. Scene processing has a 210-second overall timeout; unavailable source detail is reported honestly.

Results include `visual_status=scene_overview_zoom`, `preview_selection_method=scene_density_then_model_zoom`, scan metadata, intervals, selected windows and actual image manifests. `full_video_watched=false` and `audio_heard=false`. Downloading a source is not equivalent to watching or hearing the entire video.

## Validation and deployment

Computer tests use real ffmpeg with synthetic video to verify scanning, source dimensions and selected-window extraction. The tablet's actual Ubuntu environment passed the complete synthetic pipeline: six overview frames, four detail images, correct crop dimensions and temporary-directory cleanup. Model responses were fixed test output. This test incurred no real model calls, posted no comments and sent no QQ test messages; it does not establish real Bilibili source availability or actual model selection accuracy.

Only `services/bili_storyboard.py` and the new `services/bili_scene.py` were deployed after comparing live-source hashes and creating a private backup. Failed reloads roll back. A runtime probe confirmed strategy 10, scanner/ffmpeg availability and healthy QQ/OneBot state. The temporary probe was removed. NapCat was not restarted, and courses, speech, comment permissions and scheduled tasks were not changed.

All 659 regression tests passed, with one existing audioop deprecation warning. Older mention fixtures were brought up to date with the current `status()` interface and `source_id`; production comment validation was not relaxed.
