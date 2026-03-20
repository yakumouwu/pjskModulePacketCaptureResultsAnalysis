from __future__ import annotations

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import context, events
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class DefaultEventListener(EventListener):
    """Minimal event listener matching LangBotPluginBox layout."""

    async def initialize(self):
        await super().initialize()

        @self.handler(events.PersonMessageReceived)
        async def handle_private_message(event_context: context.EventContext):
            await self._handle_message(event_context)

        @self.handler(events.GroupMessageReceived)
        async def handle_group_message(event_context: context.EventContext):
            await self._handle_message(event_context)

    async def _handle_message(self, event_context: context.EventContext):
        message = "".join(
            element.text
            for element in event_context.event.message_chain
            if isinstance(element, platform_message.Plain)
        ).strip()
        lower = message.lower()

        if lower in {"mysk ping", "!mysk ping"}:
            await event_context.reply(
                platform_message.MessageChain(
                    [platform_message.Plain(text="mysk pong: plugin link is healthy")]
                )
            )
            event_context.prevent_default()
            return

        if lower in {"mysk help", "!mysk help", "mysk", "!mysk"}:
            await event_context.reply(
                platform_message.MessageChain(
                    [platform_message.Plain(text="usage: mysk ping | mysk help")]
                )
            )
            event_context.prevent_default()
