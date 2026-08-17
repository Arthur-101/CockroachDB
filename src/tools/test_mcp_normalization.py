import os
import sys
from pathlib import Path

# Add project root to python path to import src modules
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.tools.basic_tools import ToolManager
from src.tools.mcp_manager import mcp_manager, McpClient

def run_test():
    print("=== Testing MCP Tool Response Normalization ===")
    
    # We will simulate a client response for a tool call
    mock_client = McpClient(name="test-notion", command=sys.executable, args=[])
    mock_client.status = "Active"
    
    # Inject mock client into the manager
    mcp_manager.clients["test-notion"] = mock_client
    
    # Stub client.call_tool to return a standard MCP response payload
    def mock_call_tool(name, arguments):
        return {
            "content": [
                {
                    "type": "text",
                    "text": '{"object": "list", "results": [{"id": "page-123"}]}'
                }
            ]
        }
    mock_client.call_tool = mock_call_tool
    
    manager = ToolManager()
    
    print("Executing 'mcp_test-notion_search' through ToolManager...")
    result = manager.execute_tool("mcp_test-notion_search", {"query": "test"})
    
    print(f"Normalized Result: {result}")
    
    # Assert normalized values
    assert result.get("success") is True, "Success should be True"
    assert "result" in result, "Result key should exist"
    assert result.get("message") == '{"object": "list", "results": [{"id": "page-123"}]}', "Message should match text content"
    print("[SUCCESS] MCP Tool response normalization successfully verified!")

if __name__ == "__main__":
    run_test()
