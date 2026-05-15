# ANNA_AI — Autonomous Agent Core

## Table of Contents

- [Project Description](#project-description)
- [Features](#features)
- [How It Works](#how-it-works)
  - [The Cognitive Loop](#the-cognitive-loop)
  - [User Input Path](#user-input-path)
  - [Configuration and Personality](#configuration-and-personality)
  - [Tool Execution](#tool-execution)
  - [Internal Tools and Services](#internal-tools-and-services)
  - [Chat Pipeline](#chat-pipeline)
  - [Content Filtering](#content-filtering)
  - [Memory System](#memory-system)
- [Required Installs](#required-installs)
  - [Ollama](#ollama)
  - [Python Core Dependencies](#python-core-dependencies)
  - [Discord Integration (Optional)](#discord-integration-optional)
  - [Live Chat Integrations (Optional)](#live-chat-integrations-optional)
  - [TTS (Optional)](#tts-optional)
- [Getting Started](#getting-started)
- [Using the System](#using-the-system)
  - [GUI](#gui)
  - [Controls Reference](#controls-reference)
  - [Adding Regular Tools](#adding-regular-tools)
  - [Adding Internal Tools](#adding-internal-tools)
  - [Memory](#memory)
  - [Logs](#logs)

---

## Project Description

ANNA_AI is a modular, continuously running AI agent system built around a self-directing cognitive loop. Rather than waiting passively for user input, ANNA_AI maintains its own internal stream of thought and autonomously decides when to speak, act, or reflect. The agent runs entirely on local hardware via Ollama and is designed for sustained, always-on operation with a persistent personality, memory, and toolset.

The core of the system is a prompting loop that separates cognition from response. On each cycle, a dedicated reasoning model processes the agent's current thought state and context, decides what mode of thinking to engage in next, and either generates an internal thought or triggers an audible spoken response. A secondary AI judge vets all speech decisions before text-to-speech fires, preventing repetitive or low-value output.

The system is built for Windows with CUDA-capable Nvidia hardware and a custom Python environment. All LLM inference is handled locally through Ollama; no external AI APIs are required for the core loop.

---

## Features

- **Continuous Cognitive Loop** — The agent thinks in a background async loop without waiting for input. Each cycle is classified as reactive, proactive, reflective, or action-oriented.
- **Agent-Driven Mode Routing** — The reasoning model outputs a `<next_mode>` tag in each response, directing the loop to the appropriate next cognitive mode. A timer-based fallback handles cases where the tag is absent.
- **Speak Judge** — A secondary LLM pass vetoes `<speak>YES</speak>` decisions before TTS fires. This prevents the agent from narrating its own internal state or repeating itself.
- **Cognitive Filter** — A third LLM validation layer discards responses that are completely off-context, written in an unsupported language, or near-identical duplicates of the previous response. The filter is fail-open; infrastructure errors do not silence the agent.
- **ThoughtBuffer** — A rolling in-memory window of the agent's thoughts, user inputs, tool outputs, and system events. This forms the context for every prompt.
- **Response Decider** — Parses agent `<next_mode>` tags and falls back to time-based routing (reactive if input present, proactive within 6 minutes of input, reflective beyond 6 minutes).
- **Four Cognitive Modes** — Reactive (responding to user input), Proactive (initiating conversation while context is warm), Reflective (deep self-directed thinking and memory retrieval during idle periods), and Action (tool execution).
- **Hot Reload** — Both core modules and tool modules can be reloaded at runtime without restarting the process. Two separate hot reload managers handle core logic and tools independently.
- **Modular Tool System** — Tools are discovered and loaded dynamically. Each tool registers its own controls, which are injected into the controls module at startup via the dynamic control initializer.
- **Crash Recovery** — The cognitive loop catches all unhandled exceptions and can auto-restart up to a configurable number of times with exponential backoff. A manual restart path is always available regardless of crash state.
- **Platform Integrations** — Optional live integrations for Discord (text and voice), Twitch chat, and YouTube live chat. Each routes incoming messages into the thought buffer as raw events.
- **Four-Tier Memory System** — Conversation history is stored across four tiers: a hot short-term window always in context, an embedded searchable record of today's older messages, embedded daily diary summaries for past days, and a read-only base knowledge store for personality and reference documents. Tiers 1–3 are encrypted at rest with AES-256-GCM and written atomically to prevent corruption on crash.
- **Memory-Aware Prompt Integration** — Before building a response prompt, `MemoryAwarePromptBuilder` analyzes the agent's recent thoughts for trigger keywords and determines which memory tiers to query. High-urgency situations skip deep retrieval for speed; lower-urgency turns can pull from all four tiers.
- **Session File Manager** — Files uploaded by the user during a session are held in memory (not persisted) and searched by keyword against the current query. Relevant excerpts are injected into prompts as session context. Supports code, markdown, PDF, and plain text up to 1 MB per file.
- **Document and Personality Embedding** — Two offline scripts (`embed_document.py`, `embed_personality.py`) pre-process external files into chunked vector embeddings stored as JSON under `personality/base_memory/`. `embed_document.py` handles general reference documents and game guides in two separate directory trees. `embed_personality.py` processes personality training data into thought examples and response examples used to shape cognitive style.
- **Streaming Responses** — User-triggered responses support streaming output, with full memory storage of both complete and interrupted responses.
- **GUI** — A tkinter-based interface with a tabbed left panel (Config, Controls, Files, Tools, Info) and a persistent chat pane on the right. All log output is color-coded by message type.
- **TTS** — Text-to-speech output is an optional internal tool. The agent marks its own outputs with `<speak>YES/NO</speak>` and the cognitive loop routes accordingly.
- **Configurable via JSON and .env** — All settings are loaded from `personality/config.json` with optional environment variable overrides using the `AGENT_<SECTION>_<KEY>` pattern.
- **Regular Tool System** — Agent-callable tools live under `ANNA_AI/BASE/tools/installed/`. Each tool is a `BaseTool` subclass with a standardized `execute()` interface and an `information.json` descriptor. Tools can optionally run background context loops that inject periodic state updates directly into the thought buffer.
- **Internal Tool System** — Service-layer tools (TTS, voice input, audio effects) live under `ANNA_AI/BASE/tools/internal/` and are managed separately by `InternalToolManager`. Service categories enforce mutual exclusivity — only one TTS backend and one voice input backend can be active at a time. Switching backends is handled automatically when a control variable changes.
- **Tool Instruction Builder** — Assembles two distinct prompt sections from tool metadata: a minimal tool list injected into every cognitive mode prompt, and a full documentation block with commands, argument signatures, examples, and usage guidance injected only during action mode.
- **Chat Engagement Layer** — Incoming messages from all live platforms are stored in `ChatEngagement` (pure storage, no thought creation). `ChatEventConverter` polls this store on a 2-second interval and converts unengaged messages into typed raw data events (`chat_direct_mention`, `chat_question`, `chat_message`) for the thought buffer. Urgency classification (mention → 9, question → 7, accumulation → 6) influences the agent's speak decisions.
- **Content Filter** — All incoming text (chat, voice, user input) passes through `ContentFilter` before reaching the thought buffer. Profanity and hate speech are replaced with `[filtered]` rather than dropped. An optional secondary AI pass using Ollama handles semantic edge cases not caught by regex. LRU caching on both the fingerprint hash and the AI result prevents redundant inference calls. Outgoing responses receive a lighter filter pass covering only hate speech and controversial content.
- **TTS Interface** — All TTS backends implement `TTSInterface`, which defines `speak()`, `stop()`, and `get_voice_info()`. The `speak()` method supports both streaming (sentence-by-sentence) and complete-audio modes and accepts a `stop_event` for mid-speech interruption. The active TTS tool is resolved through `InternalToolManager.get_active_tts_tool()` at call time.

---

## How It Works

### The Cognitive Loop

The loop runs as an asyncio task inside a background thread. On each cycle:

1. **Context is built.** `ThinkingModes.build_thought_context()` assembles tool state, session file context, user context, ongoing focus, and current goals into a list of context strings.
2. **Mode is determined.** If the previous cycle produced a `<next_mode>` tag, `ResponseDecider.parse_agent_next_mode()` routes directly to that mode. Otherwise the timer-based fallback in `ResponseDecider.decide_prompt_type()` takes over.
3. **A prompt is constructed.** One of four constructor classes (`ReactiveConstructor`, `ProactiveConstructor`, `ReflectiveConstructor`, `ActionConstructor`) assembles the full prompt from the thought buffer, context parts, personality, tool list, and mode-specific framing.
4. **The reasoning model runs.** `ThoughtProcessor` calls Ollama with the constructed prompt. The output is a thought, an action plan, or a response candidate — always including `<speak>YES/NO</speak>` and `<next_mode>...</next_mode>` tags.
5. **Speak decision is evaluated.** If the agent tagged `<speak>YES</speak>`, the loop checks the minimum response interval and then passes the decision to `SpeakJudge.should_speak()`. The judge runs a second Ollama inference to approve or deny.
6. **Response is filtered.** Approved responses pass through `CognitiveFilter.check_response()`, which runs a third Ollama call to reject off-context, wrong-language, or duplicate outputs.
7. **Output is delivered.** Passing responses are sent to TTS and logged. The thought is added to the `ThoughtBuffer`. The next mode tag is stored for the following cycle.
8. **Crash recovery.** Any unhandled exception is caught by `CognitiveLoopRecovery.on_crash()`, which decides whether to auto-restart with backoff or halt and wait for manual intervention.

### User Input Path

User input arrives through the GUI chat pane, Discord, Twitch, or YouTube. All paths funnel into `ProcessingDelegator`, which constructs a responsive prompt via `ResponsiveConstructor` and generates a reply using the response model. The reply is optionally streamed token-by-token. Completed responses are stored to memory.

### Configuration and Personality

All agent identity, model assignments, and feature flags live in `personality/config.json`. The `Config` singleton loads this file at startup, applies environment variable overrides, and exposes all settings as typed attributes. `personality/bot_info.py` and `personality/controls.py` are thin shims that read from this singleton.

### Tool Execution

Tools are Python modules dropped into `ANNA_AI/BASE/tools/installed/`. Each tool is a `BaseTool` subclass paired with an `information.json` descriptor. At startup, `ToolLifecycleManager` scans this directory with lazy loading — only critical fields are parsed during discovery, with full metadata deferred until a tool is actually needed. JSON files are cached by file modification time to avoid repeated parsing across hot reloads.

`ToolManager` maintains a mapping from each tool's `control_variable_name` (e.g. `USE_WIKI_SEARCH`) to its tool name (`wiki_search`). When a control variable changes at runtime, `ToolManager` uses this map to start or stop the corresponding tool without requiring a restart. Each `BaseTool` instance has a `start()` / `end()` lifecycle. If a tool declares `has_context_loop() = True`, a background asyncio task is created that runs `context_loop()` continuously, injecting periodic state updates directly into the thought buffer.

Tool calls from the agent arrive as JSON in `<actions>` tags. `ActionStateManager` records each pending call, tracks its age, and injects stale-action notifications back into the thought buffer when a tool has not responded within 60 seconds. Failed tool calls are summarized and surfaced to the agent on the next cognitive cycle.

`ToolInstructionBuilder` assembles two prompt sections from tool metadata. A minimal list (tool name, one-line description, invocation format) is included in every cognitive mode prompt so the agent always knows what is available. A full documentation block (all commands with argument signatures, examples, usage guidance, timeouts, cooldowns) is injected only during action mode when the agent has already decided to call a specific tool.

### Internal Tools and Services

Internal tools under `ANNA_AI/BASE/tools/internal/` are managed by a separate `InternalToolManager`. Unlike regular tools they are not called by the agent via JSON — they run as always-on background services when their control variable is enabled.

Each internal tool declares a `service_type` (`tts`, `voice_input`, or `audio_effects`). `InternalToolManager` enforces one-active-per-category: when a new TTS tool is enabled, the currently active TTS tool is unloaded before the new one initializes. This handles backend switching (e.g. switching between pyttsx3 and Kokoro) without manual teardown.

When a `voice_input` tool comes online, `InternalToolManager` automatically injects its Whisper model into the active Discord tool (if running) via `set_whisper_model()`, enabling voice call transcription without requiring a restart.

### Chat Pipeline

Messages from Discord, Twitch, and YouTube enter through platform-specific tool context loops and are passed to `ChatEngagement.ingest_chat_message()`. `ChatEngagement` stores messages in a capped deque and does no further processing — it is pure storage.

On each cognitive loop cycle, `ChatEventConverter.convert_unengaged_chat_to_events()` polls unengaged messages and converts them into typed raw data events ingested by the thought buffer. Each message is classified as `chat_direct_mention`, `chat_question`, or `chat_message` based on whether the bot was mentioned or the message contains a question mark. A 2-second conversion interval prevents duplicate event creation. Converted message IDs are tracked in a rolling set (capped at 100) to guarantee each message is ingested exactly once.

`ChatEngagement` also exposes urgency scoring for the speak decision path: direct mentions score 9, questions score 7, and accumulation of 3 or more unengaged messages scores 6.

### Content Filtering

All incoming text passes through `ContentFilter.filter_incoming()` before entering the thought buffer. The filter runs two passes: a fast regex pass that replaces matched profanity, hate speech, and controversial phrases with `[filtered]` inline (not dropped), followed by an optional AI semantic pass using Ollama for content that evades keyword patterns. Both the fuzzy text fingerprint and the AI result are cached via `lru_cache` (1000 entries each) to avoid redundant inference on repeated messages.

Outgoing agent responses pass through `filter_outgoing()`, which applies only the hate speech and controversial patterns — profanity in agent output is not filtered. Both passes are fail-open; filter errors pass the text through unchanged.

### Memory System

The memory system is a four-tier hierarchy managed by `MemoryManager` and queried through `MemorySearch`.

**Tier 1 — Short Memory** holds the most recent 25 messages in a plain list. It is not embedded; it is always included in context verbatim. This tier is what the agent reads as "the current conversation."

**Tier 2 — Medium Memory** holds today's older messages once they age out of the short window. Entries are embedded with `nomic-embed-text` via Ollama and stored in a searchable JSON file. `MemorySearch.search_medium_memory()` performs cosine similarity lookup against this store when the agent's thoughts contain recall or history triggers.

**Tier 3 — Long Memory** holds daily diary summaries generated by the `Summarizer`. On GUI startup, `summarize_previous_day()` checks whether the previous calendar date has a summary. If not, it pulls all Tier 1 and Tier 2 entries for that date, formats them into a conversation transcript, and calls the thought model to write a first-person reflective diary entry (capped at 2000 characters). The summary is archived and the original entries are removed. Long memory is searched the same way as medium memory but returns date-stamped summaries rather than individual messages.

**Tier 4 — Base Knowledge** is read-only. It is pre-processed offline by the two embedding scripts and stored under `personality/base_memory/`. `MemorySearch` loads all embedding JSON files from this directory at startup and queries them by cosine similarity. Results are classified as personality knowledge (conversation examples, system prompts, category summaries) or reference documents, and injected into prompts under separate headers.

Tiers 1–3 are persisted to disk with AES-256-GCM encryption via `memory_encryption.py`. The file format prefixes each encrypted blob with a 4-byte magic marker (`AMEM`), a version byte, a 16-byte Scrypt salt, and a 12-byte GCM nonce, followed by the ciphertext and 16-byte authentication tag. Writes are atomic: the new file is written to a temp path and renamed over the existing file using `os.replace()`. A `.bak` copy is kept before each write for one-deep rollback. On startup, `recover_pending_writes()` checks for and completes any interrupted writes from a previous crash.

If `USE_MEMORY_ENCRYPTION` is disabled in controls, the system derives a stable machine-local key from a randomly generated secret stored as a hex file at `personality/memory/.machine_secret`. The AES-GCM file format is used regardless, so the storage layer is always tamper-evident and crash-safe even without a user password.

**Memory-Aware Retrieval** is handled by `MemoryAwarePromptBuilder`. Before building any response prompt, it scans the agent's recent thoughts for trigger keyword groups: recall triggers (`remember`, `you said`, `last time`, etc.) activate Tiers 2 and 3; reference triggers (`how to`, `explain`, `what is`) activate Tier 4; yesterday triggers activate a targeted yesterday context pull. Urgency level gates how deep retrieval goes — at urgency 9 or above only Tier 1 is included; at urgency 7–8 Tiers 3 and 4 are skipped. This prevents slow embedding lookups from adding latency to time-critical responses.

**Session File Manager** (`session_file_manager.py`) is separate from the four-tier system. Files added during a session are stored in a plain dict in memory and discarded when the process exits. `get_context_for_query()` does keyword-based matching (no embedding) and returns relevant excerpts sized by `MAX_TOOL_RESULT_CHARS / MAX_TOOL_RESULTS` from config. Supported types include code files, markdown, PDF, and plain text up to 1 MB each.

**Embedding Scripts** (run offline, not at agent startup):

`embed_document.py` processes reference documents and game guides into chunked embeddings. The default mode reads from `personality/base_memory/base_files/` and writes to the `embeddings/` subdirectory. The `--game-guides` flag switches to `personality/base_memory/game_guides/`. The `--all` flag runs both. Chunking preserves newlines and paragraph breaks; boundaries prefer double newlines, then single newlines, then sentence ends, then word ends, with a 200-character overlap between chunks. Embeddings are skipped if the output file already exists, making reruns cheap.

`embed_personality.py` processes personality training data from `personality/base_memory/base_personality/` into two separate embedding sets: thought examples (used to shape how the agent interprets events and forms thoughts) and response examples (used to shape response style and vocabulary). Both sets are stored under `personality/base_memory/base_personality/embeddings/`.

---

## Required Installs

All packages require Python 3.11 or 3.12. A dedicated virtual environment is strongly recommended.

### Ollama

The inference backend for all LLM calls. Install from the official site and start the server before launching ANNA_AI. Pull at least one model to assign to `thought_model` and `text_model` in the config.

- Download the installer from `ollama.com/download` and run it. On Windows, Ollama runs as a background service automatically.
- Pull a model with `ollama pull <model-name>` from a terminal.
- The memory and embedding systems require `nomic-embed-text`: `ollama pull nomic-embed-text`

### Python Core Dependencies

Install all of the following in a single step by running `pip install -r requirements.txt` from your activated virtual environment. Individual package details are listed below for reference.

**requests** — HTTP client used for all Ollama API calls and tool network requests.

**python-dotenv** — Loads `.env` overrides into the environment at startup.

**torch** — Required for any tool or subsystem that uses GPU inference directly (Stable Diffusion, Whisper, etc.). For the RTX 5060 Ti (sm_120 / Blackwell), use a custom wheel built for that architecture rather than the PyPI package. Contact your wheel source or build from source with CUDA 12.x targeting sm_120.

**transformers** — HuggingFace model loading used by memory and optional inference tools. Same sm_120 wheel requirement applies if GPU acceleration is needed. After running `requirements.txt`, immediately run `pip install transformers==4.38.2` to lock to the required version.

**diffusers** — Required only if the Stable Diffusion image generation tool is enabled. `pip install diffusers`

**peft** — Parameter-efficient fine-tuning adapters, dependency of diffusers. `pip install peft`

**accelerate** — HuggingFace accelerate for model loading. `pip install accelerate`

**cryptography** — Required for AES-256-GCM encrypted memory storage. Included in `requirements.txt`.

**numpy** — Numerical operations and cosine similarity for memory search. Install a version compatible with your torch wheel; NumPy 1.x is required for some older diffusers versions. `pip install "numpy<2.0"` if you encounter compatibility errors.

**tkinter** — GUI framework. Included with most Python distributions on Windows. If missing, reinstall Python and ensure the tcl/tk option is checked in the installer.

### Discord Integration (Optional)

**discord.py** — Discord bot and voice client. `pip install discord.py`

**PyNaCl** — Required for Discord voice channel audio. `pip install PyNaCl`

**openai-whisper** — Speech-to-text for Discord voice input. `pip install openai-whisper`

### Live Chat Integrations (Optional)

**twitchio** — Twitch IRC chat client. `pip install twitchio`

**pytchat** or **yt-dlp** — YouTube live chat monitoring depending on which tool module is used. `pip install pytchat` or `pip install yt-dlp`

### TTS (Optional)

The TTS tool module determines which package is needed. Common options used with ANNA_AI include Kokoro, Coqui TTS, or pyttsx3. Install whichever matches your configured TTS tool. Example for pyttsx3: `pip install pyttsx3`

---

## Getting Started

1. **Clone or copy the project** into your working directory. The expected structure has a `ANNA_AI/BASE/` package at the root alongside a `personality/` directory.

2. **Create and activate a virtual environment.** From the project root: `python -m venv venv` then `venv\Scripts\activate` on Windows.

3. **Install dependencies.** With your virtual environment active, run `pip install -r requirements.txt`. This installs all core dependencies in one step. Immediately after, lock the transformers version: `pip install transformers==4.38.2`. Newer transformers versions break XTTS and must not be used. For RTX 50-series GPU support, follow the GPU package copy step in SETUP.md after the base install completes. Optional integration packages are documented in the Required Installs section above but are not included in `requirements.txt`; install only what you need.

4. **Install Ollama and pull your models.** Start the Ollama server. Pull the model you intend to use for thinking and for response generation. These can be the same model or different ones.

5. **Create `personality/config.json`.** At minimum, set the `bot` section (`name`, `username`) and the `ollama` section with your `endpoint` and model assignments for `thought_model`, `response_model`, and `action_model`. See the Config class docstring for all available keys. `personality/bot_info.py` and `personality/controls.py` are read-only shims that load from this file — do not edit them directly.

6. **Create a `.env` file at the project root** for any secrets (Discord bot token, Twitch OAuth token, YouTube video ID). Use the `AGENT_<SECTION>_<KEY>` naming convention to override any config.json value.

7. **Launch the system.** Run the entry point (typically a `main.py` or `app.py` at the project root that instantiates `AICore`). The GUI will open and the cognitive loop will start automatically.

---

## Using the System

### GUI

The left panel contains five tabs:

- **Config** — Live view of loaded configuration values.
- **Controls** — Toggle control flags (enable/disable tools, limit speaking rate, toggle auto-restart, etc.).
- **Files** — Session file manager for injecting document context into the agent's prompts.
- **Tools** — Status of loaded tool modules and their individual enable flags.
- **Info** — System stats, cognitive loop cycle counts, crash recovery status.

The right panel is the chat pane. Type a message and press Enter or click Send to inject input into the agent as a user message. The agent's responses appear here as well as in the console log.

### Controls Reference

Key runtime control flags (toggleable from the GUI Controls tab or via Discord slash commands):

- `AUTO_RESTART` — Whether the cognitive loop auto-restarts after a crash.
- `LIMIT_PROCESSING` — Caps the loop to one cycle per `PROCESSING_DELAY` seconds, reducing CPU/GPU load.
- `LIMIT_SPEAKING` — Enforces a minimum interval between spoken responses.
- `COGNITIVE_FILTER` — Enables or disables the response validation filter.
- `IN_DISCORD_CHAT`, `IN_TWITCH_CHAT`, `IN_YOUTUBE_CHAT` — Enable live platform chat routing.

All control flags are defined in `config.json` under the `controls` section. Changes made via the GUI are live for the current session; to persist them across restarts, update `config.json` directly.

### Adding Regular Tools

Create a subdirectory under `ANNA_AI/BASE/tools/installed/` containing two files: a `tool.py` with a class that inherits from `BaseTool`, and an `information.json` descriptor.

The `BaseTool` subclass must implement five members: the `name` property (must match `information.json`), `initialize()` for setup, `cleanup()` for teardown, `is_available()` for availability checks, and `execute(command, args)` for handling agent calls. Use the `_success_result()` and `_error_result()` helpers to return standardized result dicts. If the tool needs to push periodic data into the thought buffer (e.g. a monitoring tool), override `has_context_loop()` to return `True` and implement `context_loop(thought_buffer)`.

The `information.json` descriptor must include at minimum `tool_name`, `control_variable_name`, `tool_description`, and `available_commands` (an array of objects with `command`, `args`, `description`, and `format` fields). Optional keys include `tool_usage_examples`, `tool_usage_guidance`, `proactive_triggers`, `timeout_seconds`, `cooldown_seconds`, and `max_retries`. `ToolInstructionBuilder` reads all of these fields when constructing action mode prompts.

The `DynamicControlInitializer` will inject the tool's control variable into the controls module at startup. `ToolLifecycleManager` will discover the tool on next startup or hot reload. No registration function is needed.

### Adding Internal Tools

Create a subdirectory under `ANNA_AI/BASE/tools/internal/` containing a `tool.py` and an `information.json`. The tool class must inherit from `InternalToolInterface` and implement `tool_name`, `service_type`, `initialize()`, `cleanup()`, and `is_available()`. The `information.json` must include `tool_name`, `service_type`, `control_variable_name`, and `control_logic` (`enabled_when_true` or `enabled_when_false`). An optional `priority` field (integer) controls load order when multiple tools in the same service category are discovered.

### Memory

The agent's memory is organized across four tiers. Tiers 1–3 are written automatically after each interaction and encrypted at rest with AES-256-GCM using the `cryptography` package. Tier 4 (base knowledge) is read-only and must be pre-processed offline before the agent starts.

To add reference documents to Tier 4, place `.txt`, `.md`, or other supported text files in `personality/base_memory/base_files/` and run `python BASE/recall/embed_document.py`. For game guides, use the `--game-guides` flag. For personality training data, place JSON training files in `personality/base_memory/base_personality/` and run `python BASE/recall/embed_personality.py`. Both scripts require Ollama to be running with `nomic-embed-text` pulled.

To clear Tiers 1–3, delete the files in `personality/memory/`. The agent will start with a blank conversation history on next launch. Do not delete `personality/memory/.machine_secret` unless you also delete the encrypted memory files, or the files will be permanently unreadable.

### Logs

All log output is color-coded by message type in the GUI. Console output follows the same format with timestamps. Log verbosity per category is controlled by the `LOG_*` flags in `config.json` under the `logging` section.