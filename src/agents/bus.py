"""
AgentBus — Publish-subscribe message bus for inter-agent communication.

Enables agents to communicate with each other through topics,
direct messaging, and request-response patterns.
"""
import asyncio
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, Optional

logger = logging.getLogger("Agents.Bus")


@dataclass
class AgentMessage:
    """A message on the agent bus."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    sender_id: str = ""
    topic: str = ""
    content: Any = None
    timestamp: float = field(default_factory=time.time)
    reply_to: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Subscription:
    """A subscription to a topic."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    topic: str = ""
    handler: Optional[Callable] = None
    agent_id: str = ""
    created_at: float = field(default_factory=time.time)


class AgentBus:
    """
    Central message bus for inter-agent communication.

    Patterns supported:
    - Publish/Subscribe: one-to-many broadcast
    - Direct: one-to-one messaging
    - Request/Response: ask and wait for answer
    - Fan-out: broadcast to all, collect responses
    """

    _instance = None
    _subscriptions: dict[str, list[Subscription]] = defaultdict(list)
    _direct_queues: dict[str, asyncio.Queue] = {}
    _pending_requests: dict[str, asyncio.Future] = {}
    _message_log: list[AgentMessage] = []
    _max_log_size: int = 10000

    @classmethod
    def get_instance(cls) -> "AgentBus":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def publish(self, topic: str, content: Any,
                      sender_id: str = "system") -> int:
        """
        Publish a message to a topic. All subscribers receive it.
        Returns the number of subscribers notified.
        """
        msg = AgentMessage(
            sender_id=sender_id,
            topic=topic,
            content=content
        )
        self._log_message(msg)

        subscribers = self._subscriptions.get(topic, [])
        notified = 0

        for sub in subscribers:
            if sub.handler:
                try:
                    if asyncio.iscoroutinefunction(sub.handler):
                        await sub.handler(msg)
                    else:
                        sub.handler(msg)
                    notified += 1
                except Exception as e:
                    logger.error(f"Subscriber {sub.id} handler error: {e}")

            if sub.agent_id and sub.agent_id in self._direct_queues:
                await self._direct_queues[sub.agent_id].put(msg)
                notified += 1

        logger.debug(f"Published to '{topic}': notified {notified} subscribers")
        return notified

    def subscribe(self, topic: str, handler: Optional[Callable] = None,
                  agent_id: str = "") -> str:
        """
        Subscribe to a topic. Returns subscription ID.
        Provide either a handler function or an agent_id for queue-based delivery.
        """
        sub = Subscription(
            topic=topic,
            handler=handler,
            agent_id=agent_id
        )
        self._subscriptions[topic].append(sub)

        if agent_id and agent_id not in self._direct_queues:
            self._direct_queues[agent_id] = asyncio.Queue(maxsize=1000)

        return sub.id

    def unsubscribe(self, subscription_id: str):
        """Remove a subscription."""
        for topic, subs in self._subscriptions.items():
            self._subscriptions[topic] = [s for s in subs if s.id != subscription_id]

    async def send_direct(self, target_agent_id: str, content: Any,
                          sender_id: str = "system") -> bool:
        """Send a direct message to a specific agent."""
        if target_agent_id not in self._direct_queues:
            self._direct_queues[target_agent_id] = asyncio.Queue(maxsize=1000)

        msg = AgentMessage(
            sender_id=sender_id,
            topic=f"direct:{target_agent_id}",
            content=content
        )
        self._log_message(msg)

        try:
            self._direct_queues[target_agent_id].put_nowait(msg)
            return True
        except asyncio.QueueFull:
            logger.warning(f"Direct queue full for agent {target_agent_id}")
            return False

    async def receive(self, agent_id: str, timeout: float = 30.0) -> Optional[AgentMessage]:
        """Receive the next message for an agent (blocking with timeout)."""
        if agent_id not in self._direct_queues:
            self._direct_queues[agent_id] = asyncio.Queue(maxsize=1000)

        try:
            return await asyncio.wait_for(
                self._direct_queues[agent_id].get(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            return None

    async def request(self, target_agent_id: str, query: Any,
                      sender_id: str = "system",
                      timeout: float = 60.0) -> Optional[Any]:
        """
        Send a request to an agent and wait for its response.
        Request-response pattern.
        """
        request_id = uuid.uuid4().hex[:12]
        future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future

        msg = AgentMessage(
            sender_id=sender_id,
            topic=f"request:{target_agent_id}",
            content=query,
            metadata={"request_id": request_id}
        )

        await self.send_direct(target_agent_id, msg)

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            return None

    async def respond(self, request_id: str, response: Any):
        """Respond to a pending request."""
        future = self._pending_requests.pop(request_id, None)
        if future and not future.done():
            future.set_result(response)

    async def fan_out(self, topic: str, content: Any,
                      sender_id: str = "system",
                      timeout: float = 30.0) -> list[Any]:
        """
        Broadcast to all subscribers and collect their responses.
        Each subscriber should call respond() with their result.
        """
        request_ids = []
        subscribers = self._subscriptions.get(topic, [])

        for sub in subscribers:
            if sub.agent_id:
                req_id = uuid.uuid4().hex[:12]
                future = asyncio.get_event_loop().create_future()
                self._pending_requests[req_id] = future
                request_ids.append(req_id)

                msg = AgentMessage(
                    sender_id=sender_id,
                    topic=topic,
                    content=content,
                    metadata={"request_id": req_id}
                )
                await self.send_direct(sub.agent_id, msg)

        if not request_ids:
            return []

        results = []
        for req_id in request_ids:
            future = self._pending_requests.get(req_id)
            if future:
                try:
                    result = await asyncio.wait_for(future, timeout=timeout)
                    results.append(result)
                except asyncio.TimeoutError:
                    self._pending_requests.pop(req_id, None)

        return results

    def get_topics(self) -> dict[str, int]:
        """Get all active topics and subscriber counts."""
        return {topic: len(subs) for topic, subs in self._subscriptions.items() if subs}

    def get_queue_depth(self, agent_id: str) -> int:
        """Get the number of pending messages for an agent."""
        q = self._direct_queues.get(agent_id)
        return q.qsize() if q else 0

    def get_recent_messages(self, topic: Optional[str] = None, limit: int = 50) -> list[dict]:
        """Get recent messages, optionally filtered by topic."""
        msgs = self._message_log
        if topic:
            msgs = [m for m in msgs if m.topic == topic]
        return [
            {
                "id": m.id,
                "sender": m.sender_id,
                "topic": m.topic,
                "content": str(m.content)[:200],
                "timestamp": m.timestamp
            }
            for m in msgs[-limit:]
        ]

    def cleanup_agent(self, agent_id: str):
        """Clean up all subscriptions and queues for an agent."""
        for topic in list(self._subscriptions.keys()):
            self._subscriptions[topic] = [
                s for s in self._subscriptions[topic] if s.agent_id != agent_id
            ]
        self._direct_queues.pop(agent_id, None)

    def _log_message(self, msg: AgentMessage):
        self._message_log.append(msg)
        if len(self._message_log) > self._max_log_size:
            self._message_log = self._message_log[-self._max_log_size // 2:]
