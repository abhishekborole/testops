export async function llm(messages, model, onChunk, sys) {
  const body = {
    model,
    max_tokens: 1000,
    stream: true,
    messages,
    system: sys || "You are a senior OpenShift/Kubernetes SRE. Be concise, specific, and actionable."
  };

  const apiKey = window.__testops_api_key || '';
  if (!apiKey) {
    if (onChunk) onChunk('[No API key set. Please enter your Anthropic API key in the header.]');
    return '[No API key set]';
  }

  try {
    const r = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
        "anthropic-dangerous-direct-browser-access": "true"
      },
      body: JSON.stringify(body)
    });

    if (!r.ok) {
      const errText = await r.text();
      let msg = `API Error ${r.status}: ${errText}`;
      if (onChunk) onChunk(msg);
      return msg;
    }

    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let full = '';
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6).trim();
        if (data === '[DONE]') continue;
        try {
          const obj = JSON.parse(data);
          if (obj.type === 'content_block_delta' && obj.delta?.type === 'text_delta') {
            const chunk = obj.delta.text;
            full += chunk;
            if (onChunk) onChunk(chunk);
          }
        } catch (e) {
          // ignore parse errors
        }
      }
    }
    return full;
  } catch (err) {
    const msg = `Error: ${err.message}`;
    if (onChunk) onChunk(msg);
    return msg;
  }
}
