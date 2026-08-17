import os
import sys
import time
from pathlib import Path

# Add project root to python path to import src modules
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.tools.mcp_manager import McpClient

def run_test():
    print("=== Testing stdio MCP Client Connection ===")
    mock_server_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "mock_mcp_server.py"))
    
    # We will invoke python to run the mock server
    command = sys.executable
    args = [mock_server_path]
    
    print(f"Creating client for: {command} {args}")
    client = McpClient(name="test-mock", command=command, args=args)
    
    print("Starting client...")
    success = client.start()
    if not success:
        print("[FAIL] Client start failed!")
        sys.exit(1)
        
    print(f"[OK] Client started successfully. Status: {client.status}")
    print(f"Discovered Tools catalog: {client.tools}")
    
    if len(client.tools) == 0:
        print("[FAIL] No tools discovered!")
        client.stop()
        sys.exit(1)
        
    print("Calling tool 'echo' with message 'Hello World!'...")
    res = client.call_tool("echo", {"message": "Hello World!"})
    print(f"Response: {res}")
    
    # Verify response
    content = res.get("content", [])
    if len(content) > 0 and content[0].get("text") == "Echo: Hello World!":
        print("[SUCCESS] Tool call response matches expected Echo string!")
    else:
        print("[FAIL] Unexpected tool call response!")
        client.stop()
        sys.exit(1)
        
    print("Logs generated during session:")
    for log in client.logs:
        print(f"  {log}")
        
    print("Stopping client...")
    client.stop()
    print("[OK] Client stopped cleanly.")
    print("=== All MCP Client Tests Passed ===")

if __name__ == "__main__":
    run_test()
