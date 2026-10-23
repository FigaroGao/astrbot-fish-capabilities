# Intent-based replies and the GCP bridge

An existing Group Chat Plus (GCP) installation is required. `patches/group-chat-plus-intent.patch` contains the minimal before/after difference used on the original device. That device already had customizations; this is not a patch for arbitrary official versions. Baseline hashes are in `patches/baseline.json`.

Back up GCP main.py, inspect the source, and compare manually or first run `git apply --check`. Stop on a mismatch rather than overwriting GCP. The patch excludes the full original installation and retains upstream AGPL-3.0 obligations.

The bridge observes incoming group messages, wraps the original `_process_message` async generator through `route_group`, and skips old probability/AI gates for `fish_intent_approved` batches. Original generation, memory, and segmentation remain. Recheck entry points after upstream upgrades.

Ordinary messages wait for 20 seconds of quiet, with at most 60 seconds of continuous activity, using the latest 20 bounded group messages. Intent decisions time out after 12 seconds and fail silently, at least 30 seconds apart. They receive no private memory, image URLs, or tools. The original main model generates approved replies.

Spontaneous replies default to 180 seconds after the last reply, 6 rounds/hour and 20/day, with Hong Kong day boundaries. Direct mentions, replies to the bot, and recognized explicit meme requests take the direct path. Busy-time ordinary messages merge; direct requests retain only the latest entry point while older messages remain in the bounded snapshot. Bubbles do not count as new rounds.

Disable AstrBot built-in spontaneous replies and GCP independent proactive topics to avoid multiple controllers. When intent_enabled is true, original 5%/8% fallback probabilities do not participate. Set intent_provider_id to an available compatible provider.

Rollback: disable intent_enabled and reload to use original _process_message, or restore the GCP backup. Reload success does not verify the QQ chain.
