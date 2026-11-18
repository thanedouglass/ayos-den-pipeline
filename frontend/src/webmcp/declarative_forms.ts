/**
 * Declarative WebMCP Form Integration.
 * Automatically scans and binds standard HTML forms with [toolname] attributes
 * and exposes SubmitEvent.agentInvoked detection.
 */

import { sendRpcRequest } from "./client";

export function bindDeclarativeWebMcpForms(
  onFormSubmitted?: (toolname: string, data: any, agentInvoked: boolean, result: any) => void
) {
  if (typeof document === "undefined") return;

  const forms = document.querySelectorAll<HTMLFormElement>("form[toolname]");
  forms.forEach((form) => {
    // Avoid double binding
    if (form.dataset.webmcpBound === "true") return;
    form.dataset.webmcpBound = "true";

    const toolname = form.getAttribute("toolname")!;
    console.log(`[WebMCP Declarative] Binding tool form: <form toolname="${toolname}">`);

    form.addEventListener("submit", async (event: SubmitEvent) => {
      event.preventDefault();

      // Check the WebMCP agentInvoked flag
      // If triggered programmatically by an AI agent, agentInvoked is true; otherwise false for human click
      const agentInvoked = (event as any).agentInvoked === true;

      const formData = new FormData(form);
      const data: Record<string, any> = {};
      formData.forEach((value, key) => {
        data[key] = value;
      });

      console.log(`[WebMCP SubmitEvent] toolname=${toolname} agentInvoked=${agentInvoked}`, data);

      // Notify live inspector
      window.dispatchEvent(
        new CustomEvent("webmcp:agentInvoked", {
          detail: {
            toolname,
            data,
            agentInvoked,
            timestamp: new Date().toISOString(),
          },
        })
      );

      try {
        const result = await sendRpcRequest("forms/submit", {
          toolname,
          data,
          agentInvoked,
        });

        if (onFormSubmitted) {
          onFormSubmitted(toolname, data, agentInvoked, result);
        }
      } catch (err) {
        console.error(`[WebMCP] Form submission failed:`, err);
      }
    });
  });
}
