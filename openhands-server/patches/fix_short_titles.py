"""Make conversation titles 2-3 words instead of the SDK's 50-char sentences.

The SDK asks the LLM for "a concise, descriptive title" up to `max_length`
characters with a leading emoji, which produces things like
"💄 Create a modern landing page with a hero section and...". In the BluHands
sidebar that reads as the raw prompt repeated back, because it very nearly is.

BluHands users are non-developers browsing a list of their apps, so the title
wants to be a NAME ("Bakery Landing Page"), not a summary of the request.

Patched rather than forked because title generation lives in the SDK
(`openhands.sdk.conversation.title_utils`) and runs inside the agent-server
subprocess. Only the prompt changes — the LLM call, truncation, failure
handling and fallback all stay the SDK's.

Loaded via sitecustomize.py at interpreter startup.
"""

_SYSTEM_PROMPT = (
    'You name projects. Given the user\'s first message, reply with a SHORT '
    'NAME for what they are building — 2 to 3 words, Title Case. '
    'Name the THING, not the request: "Bakery Landing Page", not "Create a '
    'landing page for a bakery". No emoji, no quotes, no punctuation, no '
    'explanation. Reply with the name and nothing else.'
)


def _apply_short_title_patch():
    try:
        from openhands.sdk.conversation import title_utils
        from openhands.sdk.llm import Message, TextContent

        def _short_title(message: str, llm, max_length: int = 50):
            truncated = message[:1000] + '...(truncated)' if len(message) > 1000 else message
            try:
                response = llm.completion(
                    [
                        Message(
                            role='system',
                            content=[TextContent(text=_SYSTEM_PROMPT)],
                        ),
                        Message(
                            role='user',
                            content=[
                                TextContent(
                                    text=(
                                        'Name the project described by this '
                                        f'message:\n\n{truncated}'
                                    )
                                )
                            ],
                        ),
                    ]
                )
                content = response.message.content
                if not content or not isinstance(content[0], TextContent):
                    return None

                title = content[0].text.strip().strip('"\'').rstrip('.')
                # A small model will sometimes ignore "no explanation" and add a
                # second line — keep only the first.
                title = title.splitlines()[0].strip()
                if not title:
                    return None
                # Hard-trim runaway output to 3 words, then to max_length.
                words = title.split()
                if len(words) > 3:
                    title = ' '.join(words[:3])
                if len(title) > max_length:
                    title = title[: max_length - 3] + '...'
                return title
            except Exception:
                # Same contract as the SDK: None -> caller uses the fallback.
                return None

        # generate_title_from_message looks this up as a module global at call
        # time (same module), so rebinding the attribute is enough — unlike the
        # git patch, where the callers had imported the name into other modules.
        title_utils.generate_title_with_llm = _short_title
    except Exception:
        pass


_apply_short_title_patch()
