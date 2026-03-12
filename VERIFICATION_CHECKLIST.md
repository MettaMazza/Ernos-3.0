# Ernos 3.1 Verification Checklist 🧪

Follow these steps to confirm your bot is fully functional.

## 1. Basic Connectivity 📡
*   **Action**: In the channel `ernos-chat` (or the one matching ID `1407440520413712384`), type:
    ```
    Hello Ernos, are you online?
    ```
*   **Expected**: The bot should reply. If not, check the terminal for "Received message..." or ID mismatch errors.

## 2. Engine Switching ⚙️
Test all three cognitive modes.

*   **/cloud**
    *   **Type**: `/cloud`
    *   **Test**: "What is the capital of France?"
    *   **Expected**: High-quality response from Gemini (Cloud).
*   **/local**
    *   **Type**: `/local`
    *   **Test**: "Explain quantum physics briefly."
    *   **Expected**: Response from local Qwen model.
*   **/localsteer**
    *   **Type**: `/localsteer`
    *   **Test**: "How are you feeling right now?"
    *   **Expected**: Response from Llama.cpp with Steering Vectors applied.

## 3. RAG & Short-Term Memory 🧠
Test if the bot remembers context from the conversation.

1.  **Feed Info**: "My favorite color is neon purple."
2.  **Switch Context**: "What is the weather like?" (Let it answer).
3.  **Recall**: "What did I say my favorite color was?"
    *   **Expected**: "You mentioned your favorite color is neon purple." (Verifies RAG retrieval).

## 4. Dynamic System Prompts 🎭
Test the "No Restart" prompt updates.

1.  **Edit File**: Open `prompts/dynamic_context.txt` in your editor.
2.  **Add Line**:
    ```text
    CRITICAL: YOU ARE CURRENTLY OBSESSED WITH LEMONS. MENTION LEMONS IN EVERY SENTENCE.
    ```
3.  **Save File**.
4.  **Test**: "Tell me a joke."
5.  **Expected**: The bot should instantly start talking about lemons without you needing to restart the terminal.

## 5. Admin Controls 🔒
*   **Type**: `/sync`
*   **Expected**: "Synced N commands." (Confirms you have admin access).

## 6. Channel Adapter (Synapse Bridge v3.1) 🔌
Verify message normalization works correctly.

1.  **Send a regular message** in a public channel.
    *   **Expected**: Bot processes it without errors. Check terminal for `UnifiedMessage` being created.
2.  **Send a DM** to the bot.
    *   **Expected**: Bot responds. `is_dm=True` should appear in debug logs.
3.  **Send a message with attachments**.
    *   **Expected**: Attachments are listed in the `UnifiedMessage.attachments` field.

## 7. Skills Framework (Synapse Bridge v3.1) 🛠️
Verify skill loading and sandboxing.

1.  **Check startup logs** for: `Loaded N skills from memory/core/skills/`
    *   **Expected**: At least 2 skills loaded (summarize_channel, research_topic).
2.  **Verify skill list**: Check `bot.skill_registry` has registered skills.
3.  **Security**: Skills should NOT execute arbitrary Python code — they are instruction-only.

## 8. Lane Queue (Synapse Bridge v3.1) 🚦
Verify concurrent execution.

1.  **Check startup logs** for: `LaneQueue started with 4 lanes`
    *   **Expected**: chat, autonomy, gaming, background lanes are active.
2.  **Send multiple messages quickly** in a channel.
    *   **Expected**: Messages are processed serially in the chat lane (one at a time).
3.  **Check for backpressure**: Lane queue should not crash under load.

## 9. Profile System (Synapse Bridge v3.1) 📝
Verify user profile loading.

1.  **Create a test profile**: Create `memory/users/{your_user_id}/PROFILE.md` with some content.
2.  **Send a message** to trigger context building.
    *   **Expected**: Profile content should be injected into the context (visible in debug logs).
3.  **Security**: Profile content should be sanitized (no `[TOOL:` or `[SYSTEM]` injection).
