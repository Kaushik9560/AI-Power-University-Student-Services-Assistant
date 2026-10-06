"""OWNER: student-data. TODO step 2: test lookup results and ToolError cases."""

from app.graph.nodes.tools import tools_node


def test_tools_node_preserves_contract() -> None:
    result = tools_node({"question": "What is my status?"})
    assert result["tool_results"] == {"facts": []}
    assert result["tools_used"] == []
    assert result["student"] == {}
