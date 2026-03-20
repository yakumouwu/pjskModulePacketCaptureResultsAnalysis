"""Placeholder plugin for LangBot upload smoke test."""

from langbot_plugin.api.definition.plugin import BasePlugin


class MysekaiQueryPlaceholder(BasePlugin):
    """Minimal plugin class for runtime mount/initialize validation."""

    async def initialize(self):
        """Called by plugin runtime during async initialization."""
        return
