from __future__ import annotations

import queue
from collections import defaultdict
from collections.abc import Callable

from .events import Event, EventType

Handler = Callable[[Event], None]


class EventEngine:
    def __init__(self) -> None:
        self.events: queue.Queue[Event] = queue.Queue()
        self.handlers: dict[EventType, list[Handler]] = defaultdict(list)

    def register(self, event_type: EventType, handler: Handler) -> None:
        self.handlers[event_type].append(handler)

    def put(self, event: Event) -> None:
        self.events.put(event)

    def drain(self) -> None:
        while not self.events.empty():
            event = self.events.get()
            for handler in self.handlers.get(event.type, []):
                handler(event)

