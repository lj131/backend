# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Run Commands

```bash
# Start the API server (from backend/ directory)
uvicorn api.api:app --reload --host 0.0.0.0 --port 8000

# Quick syntax check on all source files
python -c "
import py_compile
for f in ['api/api.py', 'api/websocket.py', 'funcation/memory_center.py',
          'funcation/prompt.py', 'funcation/memory_agent.py', 'funcation/profile_agent.py',
          'funcation/relationship_agent.py', 'funcation/state_agent.py',
          'funcation/event_agent.py', 'funcation/story_agent.py', 'funcation/memory.py',
          'funcation/utils.py', 'funcation/recall_agent.py', 'funcation/memory_rag.py',
          'funcation/embedding_manager.py', 'funcation/world_event_agent.py',
          'funcation/interaction_agent.py', 'funcation/query_classifier.py',
          'funcation/webrtc_agent.py', 'funcation/voice_service.py',
          'funcation/conversation_manager.py',
          'funcation/proactive/proactive_engine.py', 'funcation/proactive/proactive_trigger.py',
          'funcation/proactive/proactive_decision.py', 'funcation/proactive/proactive_message_agent.py',
          'funcation/proactive/proactive_cooldown.py']:
    py_compile.compile(f, doraise=True)
print('OK')
"

# Integration test via TestClient
python -c "
from fastapi.testclient import TestClient
from api.api import app
client = TestClient(app)
r = client.post('/chat', json={'message': '你好'})
print(r.json())
"
```

No test framework, linter, or type checker is configured. No `setup.py`, `pyproject.toml`, or build system.

## Architecture

This is a **character-based AI chat system** (AI companion simulator). A FastAPI server receives chat messages, assembles a rich system prompt from multiple data sources, calls DeepSeek, and returns the AI character's reply. It also supports **real-time voice calls** via WebRTC + WebSocket, a **proactive greeting** system, and a **world event** system with NPC interactions.

### Core Data Flow (POST /chat)

```
POST /chat
  → MemoryCenter.load_current_character()     # data/characters/{id}.json
  → memory.load_memory(char_id)               # memories/{id}_memory.json (chat history)
  → MemoryCenter.load_memory(char_id)         # data/memories/{id}.json (all dynamic state)
  → MemoryCenter.load_current_world()         # data/worlds/{id}.json
  → world_event_agent.tick()                  # Advance world events, auto-generate if needed
  → story_agent.check_story()                 # Generate/advance multi-stage story (DeepSeek)
  → story_agent.sync_story_to_state()         # Copy current story stage → character_state
  → _sync_story_to_rag()                      # Sync story to ChromaDB vector store
  → interaction_agent.build_social_prompt()   # Build NPC social context for prompt
  → recall_agent.detect_memory_scope()        # Determine which RAG collections to search
  → memory_rag.retrieve_memories()            # Semantic search across ChromaDB collections
  → prompt.build_system_prompt()              # Assemble full system prompt (~10 data sources + RAG results)
  → mc.update_profile()                       # AI extracts user profile fields (DeepSeek)
  → _sync_profile_to_rag()                    # Sync profile to ChromaDB
  → relationship_agent.update_relationship()  # AI determines favorability delta (-10..+10)
  → _sync_relationship_to_rag()               # Sync relationship to ChromaDB
  → state_agent.analyze_state()               # AI evaluates character mood/energy
  → DeepSeek API (deepseek-chat, temp=0.9)    # Generate reply
  → memory_agent.extract_memory()             # AI decides add/update/ignore long-term memory
  → mc.add_chat_summary()                     # Append to chat summary
  → memory.save_memory()                      # Save chat history to memories/{id}_memory.json
  → Return {reply, favorability}
```

### Key Concept: Two "Memory" Systems

There are **two separate memory concepts** — don't confuse them:

| System | Location | Content | Manager |
|--------|----------|---------|---------|
| **Structured state** | `data/memories/{id}.json` | profile, favorability, long_memory, events, chat_summary, relationship, character_state, story, last_chat_time — all in one JSON | `MemoryCenter` class |
| **Chat history** | `memories/{id}_memory.json` | Raw message array `[{role, content}, ...]` | `memory.py` module |

### Third Memory System: RAG Vector Store

`funcation/memory_rag.py` maintains a **ChromaDB** vector database at `data/chroma/` with 6 independent collections per character:

| Collection | Content | Synced by |
|-----------|---------|-----------|
| `profile` | User profile fields (name, city, job, mood) | `_sync_profile_to_rag()` on each /chat |
| `long_memory` | Long-term memory facts | `memory_agent` extraction |
| `story` | Story overview + individual stages | `_sync_story_to_rag()` on each /chat |
| `events` | World/character events | Event creation/update |
| `relationship` | Relationship level + favorability + reason | `_sync_relationship_to_rag()` on each /chat |
| `chat_summary` | Chat summary entries | Chat summary updates |

Embeddings use **FastEmbed** (BGE-small-zh-v1.5, local ONNX, free) by default. Provider is configurable via `EMBEDDING_PROVIDER` env var. The `embedding_manager.py` module lazy-loads a singleton embedding function.

RAG retrieval flow: `recall_agent.detect_memory_scope()` (DeepSeek) determines which collections to query → `memory_rag.retrieve_memories()` performs semantic search → results are injected into the system prompt.

### MemoryCenter — The Central Hub

`funcation/memory_center.py` is the single entry point for ALL dynamic per-character data. The `MemoryCenter` class manages:

- **Profile** (`profile`): User info extracted by AI — name, city, job, mood, recent_topics
- **Favorability** (`favorability`): 0–100 score, updated by `relationship_agent` (AI-analyzed delta)
- **Relationship** (`relationship`): level (陌生/普通/朋友/亲近/暧昧) + last_reason, auto-calculated from favorability thresholds
- **Long memory** (`long_memory`): List of facts about the user, extracted by `memory_agent`
- **Events** (`events`): Timestamped life events, auto-generated when relationship level changes
- **Character state** (`character_state`): mood, energy, current_event — managed by `state_agent`
- **Story** (`story`): Multi-stage narrative with UUID, stages list, progress tracking
- **Chat summary** (`chat_summary`): Running summary of conversation turns
- **Proactive message cache** (`proactive_message`, `caring_message`): Cached greeting messages
- **Character/world selection**: Reads `current_character.json` and `current_world.json`

### Agent Modules (All Use DeepSeek)

Every `*_agent.py` module in `funcation/` follows the same pattern: imports OpenAI client, reads `DEEPSEEK_API_KEY` from env, and calls `deepseek-chat` model. Each handles one specific domain:

| Agent | Called in /chat | Purpose | Temperature |
|-------|----------------|---------|-------------|
| `world_event_agent` | Step 6 | Tick world events, auto-generate new events, apply character impact | 1 (for generation) |
| `story_agent` | Step 7 | Generate/advance multi-stage story arcs (5+ stages) | 1 |
| `interaction_agent` | Step 8 | Build NPC social context prompt from world state | N/A (prompt builder) |
| `recall_agent` | Step 9 | Determine which RAG collections to search based on user input | 0 |
| `profile_agent` | Step 11 | Extract name/city/job/mood from user messages | 0.3 |
| `relationship_agent` | Step 12 | Analyze sentiment → favorability delta (-10..+10) + reason | 0 |
| `state_agent` | Step 13 | Determine character mood + energy (0–100) | 0 |
| `memory_agent` | Step 16 | Classify user msg as add/update/ignore for long-term memory | 0.9 |
| `query_classifier` | (utility) | Classify user queries for routing | — |
| `proactive_decision` | (proactive) | Decide whether to send proactive greeting | — |
| `proactive_message_agent` | (proactive) | Generate proactive greeting message | — |
| `proactive_trigger` | (proactive) | Detect triggers for proactive messages | — |
| `proactive_cooldown` | (proactive) | Manage cooldown between proactive messages | — |

### WebSocket / WebRTC Voice Call System

`api/websocket.py` provides two WebSocket endpoints:

- **`/voice/call`**: Main voice call signaling channel. Handles WebRTC offer/answer exchange, ICE candidate relay, conversation start, audio data relay, text messages (from browser speech recognition), and call teardown. Uses `webrtc_agent` for signaling and `conversation_manager` for dialogue processing.
- **`/voice/status`**: Status monitoring endpoint that pushes connection count every second.

`funcation/webrtc_agent.py`: WebRTC signaling server using **aiortc**. Manages `CallSession` objects with `RTCPeerConnection` instances. Handles offer/answer/ICE candidate relay between frontend and server.

`funcation/conversation_manager.py`: Voice conversation orchestrator. Mirrors the `/chat` endpoint's agent flow but in an async context for real-time voice. Manages `ConversationContext` per call (state machine: IDLE → LISTENING → PROCESSING → SPEAKING), processes text from browser speech recognition, generates AI replies via DeepSeek, and queues TTS synthesis.

`funcation/voice_service.py`: TTS service with pluggable providers (Edge TTS default, Coqui optional). Uses `edge-tts` package for free Chinese speech synthesis. Configurable voice, rate, pitch, volume.

### Prompt Assembly

`funcation/prompt.py` builds the full system prompt from ~12 data sources. The prompt sections (in order):
1. World context (name + background)
2. Character info (name, description, personality)
3. Relationship status (attitude based on favorability thresholds: <20/50/80)
4. Relationship level + last change reason
5. Current story (title, description, current stage)
6. Character state (mood, energy, current event)
7. User profile summary
8. Memory summary (recent chat, long-term memory, key events, chat summaries)
9. Story history (last 5 story items)
10. **RAG retrieved memories** (semantically relevant context from ChromaDB)
11. **NPC social context** (other characters' states and recent interactions)
12. **World events** (active world events affecting the scene)
13. Mood-driven behavior instructions (开心/低落/疲惫/生气)
14. 18 rules (stay in character, 2-5 sentences per reply, etc.)

### World Event System

`funcation/world_event_agent.py`: Manages a world-level event timeline. Events have title, description, importance, progress (0-100), status (running/finished/paused), and character impacts. The `tick()` function advances world time, progresses events, auto-generates new events via DeepSeek, applies impacts to characters, and can trigger story generation from completed events.

`funcation/interaction_agent.py`: Manages NPC-to-NPC relationships and interactions within a world. Tracks relationship scores between all character pairs, records interaction history, generates gossip, and can simulate multi-character interactions driven by world events.

### Proactive Greeting System

`funcation/proactive/`: Sub-package for character-initiated messages:
- `proactive_trigger.py`: Detects conditions (idle time, favorability changes, time of day, events)
- `proactive_decision.py`: Decides whether to send a message (DeepSeek, with cooldown)
- `proactive_message_agent.py`: Generates the greeting text (DeepSeek)
- `proactive_cooldown.py`: Prevents message spam
- `proactive_engine.py`: Orchestrates the full flow

Called via `GET /proactive` endpoint. Results are cached in MemoryCenter and also exposed via `GET /proactive-message` and `GET /caring-message`.

### Character Files

Character definitions in `data/characters/{id}.json` are static (read-only after creation). The character ID is the JSON field `"id"`, NOT the filename. Known characters:
- `linwan` (林婉): cold exterior, secretly caring
- `maid` (小羽): gentle maid, filename is `student.json`
- `xiaomei` (小梅): aloof, sometimes sarcastic, filename is `teacher.json`

### World Files

World definitions in `data/worlds/{id}.json` provide setting context. Known worlds:
- `campus` (校园): university daily life
- `cyberpunk` (赛博朋克): neon-lit corporate dystopia 2099

Worlds now have dynamic runtime state (`data/worlds/{id}_state.json`) tracking current events, history events, and environmental state.

## Important Patterns

- **Lazy imports for agents**: `MemoryCenter` methods use `from funcation import X` inside method bodies (not at module top) to avoid circular imports.
- **File I/O per call**: Each `MemoryCenter` method does its own load-modify-save cycle. There's no in-memory caching or batching. For a single-user app this is fine.
- **No error handling**: The `/chat` endpoint has no try/except. Any agent failure, API error, or file I/O issue results in a 500. WebSocket handlers do have per-message try/except.
- **`response_format={"type": "json_object"}`**: Used by `memory_agent` and `profile_agent` to force structured JSON from DeepSeek. `relationship_agent` and `story_agent` use plain text + manual JSON parsing with `json.loads()`.
- **Directory name**: The package is `funcation` (not `function`). This is intentional — all imports use this spelling.
- **No `__init__.py`**: The `funcation/` directory has no init file. Imports use `from funcation import module_name`. Exception: `funcation/proactive/` has an `__init__.py`.
- **Fallback paths**: `MemoryCenter.load_character_by_id()` and `load_world_by_id()` try `data/` first, then fall back to old root-level directories.
- **RAG sync is eager**: Every `/chat` call syncs profile, story, and relationship to ChromaDB via `_sync_*_to_rag()` helper functions. This keeps vectors fresh but adds latency.
- **WebSocket singleton pattern**: `conversation_manager` and `webrtc_agent` are module-level singletons imported directly by `api/websocket.py`.
- **TTS is async-queued**: `conversation_manager` puts TTS requests on an `asyncio.Queue` processed by a background coroutine. The actual audio push to frontend is stubbed (TODO).
- **Environment**: `.env` file must contain `DEEPSEEK_API_KEY`. Optional: `TAVILY_API_KEY`, `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`.
