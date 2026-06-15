import asyncio

from aidog_sdk import AiDog, DevPcWebSocketHost
from aidog_sdk.dev_pc_ws import _AckRoutingWebSocket


def test_ws_host_attaches_control_when_dog_is_provided() -> None:
    dog = AiDog(auto_edu=False)
    host = DevPcWebSocketHost(dog=dog)

    assert dog._ws_control is host

    dog.shutdown()


def test_ws_connected_callback_enters_edu_over_attached_ws() -> None:
    dog = AiDog()
    host = DevPcWebSocketHost(dog=dog)
    sent = []

    def send_edu_session(action, *, lease_ms=8000, command_id=None, timeout_s=3.0):
        sent.append((action, lease_ms, command_id, timeout_s))

    host.send_edu_session = send_edu_session
    host.wait_ack = lambda command_id, *, timeout_s=1.0: {"type": "ack", "id": command_id, "result": "accepted"}

    dog._on_ws_robot_connected()

    assert sent
    assert sent[0][0] == "enter"
    assert sent[0][2].startswith("dog-edu-")

    dog.exit_edu_mode()
    dog.shutdown()


def test_ack_routing_websocket_keeps_ack_from_custom_handler() -> None:
    async def run_case() -> None:
        messages = iter([
            '{"type":"ack","id":"cmd-1","result":"accepted"}',
            '{"imu":{"yaw_deg":1}}',
        ])
        recorded = []

        class FakeWebSocket:
            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return next(messages)
                except StopIteration:
                    raise StopAsyncIteration

            async def send(self, message):
                return None

        def record_ack(message: str) -> bool:
            if '"type":"ack"' not in message:
                return False
            recorded.append(message)
            return True

        wrapped = _AckRoutingWebSocket(FakeWebSocket(), record_ack)

        assert await wrapped.__anext__() == '{"imu":{"yaw_deg":1}}'
        assert recorded == ['{"type":"ack","id":"cmd-1","result":"accepted"}']

    asyncio.run(run_case())
