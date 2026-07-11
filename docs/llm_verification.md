# LLM Verification

The Agent is rule-first by default. Enabling an LLM changes only structured
question understanding; execution remains schema-grounded fixed tools.

1. Revoke any key accidentally pasted into chat, a terminal transcript, issue,
   or commit, then create a replacement in the provider console.
2. Copy `.env.example` to the ignored `.env` file.
3. Configure a provider. For DeepSeek:

   ```env
   USE_LLM=true
   LLM_PROVIDER=openai_compatible
   LLM_MODEL=deepseek-chat
   LLM_API_KEY=replace-with-a-new-key
   LLM_BASE_URL=https://api.deepseek.com/v1
   ```

4. Start the backend, then run:

   ```powershell
   .\scripts\verify-llm.ps1
   ```

For a protected deployment, provide `-AccessToken` to the script. The script
never prints, writes, or transmits a key outside the configured provider call.
The backend also exposes a safe `GET /api/ops/model-status` endpoint and an
explicit `POST /api/ops/model-smoke-test` endpoint for deployment probes.

Record the provider, model, date, latency, and result in the release notes
after a live verification. Never commit the resulting `.env` file.
