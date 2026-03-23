"""Mysekai query plugin for LangBot."""

from langbot_plugin.api.definition.plugin import BasePlugin


class MysekaiQueryPlaceholder(BasePlugin):
    """Plugin entrypoint."""

    async def initialize(self):
        """Called by plugin runtime during async initialization."""
        return
