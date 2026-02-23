"""Feature flags with deterministic rollout buckets."""

import hashlib


def parse_rollout_percentage(value, default=100):
    """Parse rollout percentage from env/config with safe bounds."""
    try:
        percent = int(str(value).strip())
    except (TypeError, ValueError):
        return default

    if percent < 0:
        return 0
    if percent > 100:
        return 100
    return percent


def get_rollout_bucket(flag_name, seed):
    """Return a deterministic bucket in [0, 99] for a flag and seed."""
    raw = f"{flag_name}:{seed}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return int(digest[:8], 16) % 100


def is_feature_enabled(flag_name, seed, percentage, enabled=True):
    """Decide whether a feature is enabled for a seed at a rollout percentage."""
    if not enabled:
        return False
    if percentage >= 100:
        return True
    if percentage <= 0:
        return False

    bucket = get_rollout_bucket(flag_name, seed)
    return bucket < percentage
