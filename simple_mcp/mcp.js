// Ref: https://mcp.holt.courses/lessons/lets-build-mcp/my-first-mcp-server
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({
  name: "add-server",
  version: "1.0.0",
});

// You could get info about the registered tools by the following command
// echo '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"name": "add", "arguments": {}}}' | node mcp.js
//
// You could call the tool using the following command
// echo '{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "add", "arguments": {"a": 3, "b": 4}}}' | node mcp.js
server.registerTool(
  "add",
  {
    title: "Add two numbers",
    description: "Add two numbers and return the result",
    inputSchema: {
      a: z.number(),
      b: z.number(),
    },
  },
  async ({ a, b }) => {
    return { content: [{ type: "text", text: String(a + b) }] };
  },
);

const transport = new StdioServerTransport();
await server.connect(transport);
