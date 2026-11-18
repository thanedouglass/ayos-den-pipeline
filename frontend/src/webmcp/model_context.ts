/**
 * Browser-Native WebMCP Model Context Protocol Polyfill and Registry.
 * Implements navigator.modelContext imperative API previewed for W3C / Chrome WebMCP standard.
 */

export interface WebMcpTool {
  name: string;
  description: string;
  inputSchema: {
    type: string;
    properties: Record<string, any>;
    required?: string[];
  };
  execute: (input: any) => Promise<any>;
}

export interface ModelContextInterface {
  tools: Map<string, WebMcpTool>;
  registerTool: (tool: WebMcpTool) => void;
  unregisterTool: (name: string) => void;
  getTools: () => WebMcpTool[];
  executeTool: (name: string, input: any) => Promise<any>;
}

declare global {
  interface Navigator {
    modelContext?: ModelContextInterface;
  }
}

export function initModelContext(): ModelContextInterface {
  if (typeof window !== "undefined" && !navigator.modelContext) {
    const toolRegistry = new Map<string, WebMcpTool>();

    const modelContext: ModelContextInterface = {
      tools: toolRegistry,
      registerTool(tool: WebMcpTool) {
        toolRegistry.set(tool.name, tool);
        console.log(`[WebMCP Imperative] Registered tool: ${tool.name}`, tool);
        window.dispatchEvent(new CustomEvent("webmcp:toolRegistered", { detail: tool }));
      },
      unregisterTool(name: string) {
        toolRegistry.delete(name);
        console.log(`[WebMCP Imperative] Unregistered tool: ${name}`);
        window.dispatchEvent(new CustomEvent("webmcp:toolUnregistered", { detail: { name } }));
      },
      getTools() {
        return Array.from(toolRegistry.values());
      },
      async executeTool(name: string, input: any) {
        const tool = toolRegistry.get(name);
        if (!tool) {
          throw new Error(`WebMCP Tool '${name}' is not registered on navigator.modelContext.`);
        }
        return await tool.execute(input);
      },
    };

    navigator.modelContext = modelContext;
  }

  return navigator.modelContext!;
}
