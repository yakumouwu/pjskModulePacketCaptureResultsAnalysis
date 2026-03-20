from __future__ import annotations

from typing import AsyncGenerator

from langbot_plugin.api.definition.components.command.command import Command
from langbot_plugin.api.entities.builtin.command.context import CommandReturn, ExecuteContext


class Mysk(Command):
    """Placeholder command for group-side smoke tests."""

    async def initialize(self):
        await super().initialize()

        @self.subcommand(
            name="",
            help="Mysekai placeholder command",
            usage="mysk ping",
            examples=["mysk ping", "mysk help"],
        )
        async def root(context: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            if not context.crt_params:
                yield CommandReturn(text="mysk is ready. Try: !mysk ping")
                return

            action = context.crt_params[0].strip().lower()
            if action in {"ping", "p"}:
                yield CommandReturn(text="mysk pong: plugin link is healthy")
                return

            if action in {"help", "h"}:
                yield CommandReturn(text="available subcommands: ping, help")
                return

            yield CommandReturn(text=f"unknown subcommand: {action}. available: ping, help")
