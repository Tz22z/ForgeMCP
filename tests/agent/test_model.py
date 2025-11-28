import json
from types import SimpleNamespace

from forgemcp.agent.model import ModelTurn, OpenAIResponsesModel
from forgemcp.core.models import ToolResult


class FakeResponses:
    def __init__(self) -> None:
        self.requests = []
        self.response = SimpleNamespace(
            id="resp_1",
            output=[
                SimpleNamespace(
                    type="function_call",
                    call_id="call_1",
                    name="read_file",
                    arguments=json.dumps({"path": "app.py"}),
                )
            ],
            output_text="",
            usage=SimpleNamespace(input_tokens=12, output_tokens=4),
        )

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.response


def test_openai_adapter_normalizes_function_calls() -> None:
    responses = FakeResponses()
    backend = OpenAIResponsesModel("test-model", SimpleNamespace(responses=responses))
    result = backend.decide(ModelTurn("fix it", []))
    assert result.decision.tool_calls[0].name == "read_file"
    assert result.decision.tool_calls[0].arguments == {"path": "app.py"}
    assert result.input_tokens == 12
    assert backend.previous_response_id == "resp_1"


def test_openai_adapter_sends_tool_output_against_previous_response() -> None:
    responses = FakeResponses()
    backend = OpenAIResponsesModel("test-model", SimpleNamespace(responses=responses))
    backend.previous_response_id = "resp_previous"
    backend.decide(
        ModelTurn(
            "continue",
            [],
            [ToolResult(call_id="call_1", tool_name="read_file", ok=True, output="content")],
        )
    )
    request = responses.requests[0]
    assert request["previous_response_id"] == "resp_previous"
    assert request["input"][0]["type"] == "function_call_output"
