# Connecting TeamBoard to AI clients

The steps below apply once the official TeamBoard HTTPS address is published. Verify the exact redirect URI in the platform before adding it to TeamBoard's OAuth callback policy. The local TeamBoard tests exercise OAuth, PKCE, scopes and revocation. Hosted compatibility is pending access to the official endpoint and eligible accounts.

| Client surface | Documented availability | Connection path | Current verification |
| --- | --- | --- | --- |
| ChatGPT web | Business and Enterprise/Edu for full custom MCP with workspace permission. Pro can use read and fetch tools. Apply the provider's account and region rules. | Custom MCP server with OAuth and an approved callback. | Official documentation reviewed. Hosted test pending. |
| Claude web and desktop | Custom remote connectors across free and paid plans with account and organization limits. | Custom connector with automatic registration or registered OAuth credentials as supported. | Official documentation reviewed. Hosted test pending. |
| Gemini Apps | Custom apps for eligible US adults, personal Google accounts, enabled History and English on supported surfaces. | Custom app URL. Use automatic registration where supported or enter approved client credentials when offered. | Official documentation reviewed. Hosted test pending. |
| Gemini API and CLI | Developer products with their own availability and authentication. | Follow the configuration for the specific developer client. | Separate from verification of the consumer app. |

## ChatGPT

1. In the web app, open Plugins and select **Add custom MCP server**. In a managed workspace, enable custom MCP access according to the administrator policy first.
2. Enter the official TeamBoard MCP URL and select OAuth. Check the exact redirect URL shown for the connection. ChatGPT documents both a stable callback and callbacks unique to the connection.
3. Start the connection and review the scopes on TeamBoard. Confirm that `teamboard_whoami` returns your own account and that a workspace outside your membership is unavailable.
4. On an eligible write connection, create one disposable task and retry with the same key to verify that it exists only once. Revoke the connection in TeamBoard and verify that another request requires authorization.

[ChatGPT connection settings](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt) · [ChatGPT OAuth integration](https://developers.openai.com/plugins/build/auth)

## Claude

1. In Customize → Connectors, choose **Add custom connector**. Managed accounts may require a workspace owner to add it first.
2. Enter the official TeamBoard MCP URL. Choose automatic registration if the connection supports it, or use a client registered for Claude's exact callback on TeamBoard.
3. Sign in on TeamBoard, review the permissions and enable the connector in your conversation. Check it with **“List my workspaces”** and **«فضاهای کاری من را نمایش بده»**.
4. In a workspace you administer, test authorized and denied operations on disposable records. Remove the connector and verify the TeamBoard connection is revoked or revoke it from Security → AI connections.

[Claude remote connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp) · [Claude authentication](https://claude.com/docs/connectors/building/authentication)

## Gemini Apps

1. Check that your account can use custom connected apps. Enter the official TeamBoard HTTPS endpoint in **Custom apps** or **Gemini Apps Developer Mode**, depending on the surface available to your account.
2. Use Gemini's automatic OAuth registration where supported, or the approved client ID and secret if the UI asks for preregistration. Operator policy must contain the exact callback for the selected installation.
3. Sign in on TeamBoard, review access and use the connected app. In Developer Mode, check the tool name, input, output and OAuth result for your account.
4. Verify a timezone-sensitive reminder using an explicit offset or `Asia/Tehran`, if the client requests and supports write permissions. Test revocation and reconnect before relying on the integration.

[Gemini Apps availability](https://support.google.com/gemini/answer/17209137) · [Gemini Apps Developer Mode](https://developers.google.com/connected-apps/mcp/dev-mode/usage) · [Gemini OAuth setup](https://developers.google.com/connected-apps/mcp/oauth)

### Gemini API and CLI

The Gemini API and Gemini CLI have separate configuration and OAuth flows. A successful developer-client connection provides a result for that client. [Gemini API function calling](https://aistudio.google.com/docs/function-calling#mcp) · [Gemini CLI MCP setup](https://geminicli.com/docs/tools/mcp-server/)

## Troubleshooting

- Check the full endpoint path, authorization metadata and exact registered callback. A loopback development address is reachable only from the local environment.
- If login works but an operation is refused, check the connection's granted scope and the account's current workspace role. Use TeamBoard's approval page for sensitive operations.
- In Security → AI connections, revoke an old authorization before reconnecting with a different account or set of scopes. Manage any copies already received by the AI provider in that provider's data settings.
