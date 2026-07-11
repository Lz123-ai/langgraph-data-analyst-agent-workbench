# Model Providers

The Agent uses a validated model only for structured question understanding. Planning and execution remain schema-grounded application code.

## OpenAI

```env
USE_LLM=true
LLM_PROVIDER=openai
LLM_MODEL=gpt-4.1-mini
LLM_API_KEY=...
```

## OpenAI-compatible APIs

DeepSeek, Alibaba Cloud Model Studio/Qwen, Moonshot, Zhipu and other services can be used when their endpoint implements the OpenAI chat-completions protocol:

```env
USE_LLM=true
LLM_PROVIDER=openai_compatible
LLM_MODEL=provider-model-name
LLM_API_KEY=provider-api-key
LLM_BASE_URL=https://provider.example.com/v1
```

Model names and base URLs come from the provider. Never commit a real key.

## Ollama

```env
USE_LLM=true
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:8b
LLM_BASE_URL=http://127.0.0.1:11434/v1
```

Ollama does not require a cloud API key. The selected model must support reliable JSON/structured output for best results.
