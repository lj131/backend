# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Run Commands

```bash
# Start the API server
uvicorn api.api:app --reload --host 0.0.0.0 --port 8000

# Quick syntax check on all source files
python -c "
import py_compile
for f in ['api/api.py', 'funcation/memory_center.py', 'funcation/prompt.py',
          'funcation/memory_agent.py', 'funcation/profile_agent.py',
          'funcation/relationship_agent.py', 'funcation/state_agent.py',
          'funcation/event_agent.py', 'funcation/story_agent.py',
          'funcation/memory.py', 'funcation/utils.py']:
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

No test framework, linter, or type checker is configured. The project has no `setup.py`, `pyproject.toml`, or build system.

## Architecture

This is a **character-based AI chat system** (AI girlfriend simulator). A FastAPI server receives chat messages, assembles a rich system prompt from multiple data sources, calls DeepSeek, and returns the AI character's reply.

### Core Data Flow

```
POST /chat
  → MemoryCenter.load_current_character()     # data/characters/{id}.json
  → MemoryCenter.load_memory(char_id)         # data/memories/{id}.json (all dynamic state)
  → MemoryCenter.load_current_world()         # data/worlds/{id}.json
  → event_agent.check_daily_event()           # Generate daily event if new day (DeepSeek)
  → story_agent.check_story()                 # Generate/advance multi-stage story (DeepSeek)
  → story_agent.sync_story_to_state()         # Copy current story stage → character_state
  → prompt.build_system_prompt()              # Assemble full system prompt from all data
  → profile_agent.extract_profile()           # AI extracts name/city/job/mood from user msg
  → relationship_agent.update_relationship()  # AI determines favorability delta (-10..+10)
  → state_agent.analyze_state()               # AI evaluates character mood/energy
  → DeepSeek API (deepseek-chat, temp=0.9)   # Generate reply
  → memory_agent.extract_memory()             # AI decides add/update/ignore long-term memory
  → memory.save_memory()                      # Save chat history to memories/{id}_memory.json
```

### Key Concept: Two "Memory" Systems

There are **two separate memory concepts** — don't confuse them:

| System | Location | Content | Manager |
|--------|----------|---------|---------|
| **Structured state** | `data/memories/{id}.json` | profile, favorability, long_memory, events, chat_summary, relationship, character_state, story, last_chat_time — all in one JSON | `MemoryCenter` class |
| **Chat history** | `memories/{id}_memory.json` | Raw message array `[{role, content}, ...]` | `memory.py` module |

### MemoryCenter — The Central Hub

`funcation/memory_center.py` is the single entry point for ALL dynamic per-character data. The `MemoryCenter` class manages:

- **Profile** (`profile`): User info extracted by AI — name, city, job, mood, recent_topics
- **Favorability** (`favorability`): 0–100 score, updated by `relationship_agent` (AI-analyzed delta)
- **Relationship** (`relationship`): level (陌生/普通/朋友/亲近/暧昧) + last_reason, auto-calculated from favorability thresholds
- **Long memory** (`long_memory`): List of facts about the user, extracted by `memory_agent`
- **Events** (`events`): Timestamped life events, auto-generated when relationship level changes
- **Character state** (`character_state`): mood, energy, current_event — managed by `state_agent`
- **Story** (`story`): Multi-stage narrative with UUID, stages list, progress tracking
- **Character/world selection**: Reads `current_character.json` and `current_world.json`

### Agent Modules (All Use DeepSeek)

Every `*_agent.py` module in `funcation/` follows the same pattern: imports OpenAI client, reads `DEEPSEEK_API_KEY` from env, and calls `deepseek-chat` model. Each handles one specific domain:

| Agent | Called in /chat | Purpose | Temperature |
|-------|----------------|---------|-------------|
| `event_agent` | Step 6 | Generate daily character event (`{title, description, impact}`) | 1 |
| `story_agent` | Step 7 | Generate/advance multi-stage story arcs (5+ stages) | 1 |
| `profile_agent` | Step 10 | Extract name/city/job/mood from user messages | 0.3 |
| `relationship_agent` | Step 11 | Analyze sentiment → favorability delta (-10..+10) + reason | 0 |
| `state_agent` | Step 12 | Determine character mood + energy (0–100) | 0 |
| `memory_agent` | Step 16 | Classify user msg as add/update/ignore for long-term memory | 0.9 |

### Prompt Assembly

`funcation/prompt.py` builds the full system prompt from ~10 data sources. The prompt sections (in order):
1. World context (name + background)
2. Character info (name, description, personality)
3. Relationship status (attitude based on favorability thresholds: <20/50/80)
4. Relationship level + last change reason
5. Current story (title, description, current stage)
6. Character state (mood, energy, current event)
7. User profile summary
8. Memory summary (recent chat, long-term memory, key events, chat summaries)
9. Story history (last 5 story items)
10. Mood-driven behavior instructions (开心/低落/疲惫/生气)
11. 18 rules (stay in character, 2-5 sentences per reply, etc.)

### Character Files

Character definitions in `data/characters/{id}.json` are static (read-only after creation). The character ID is the JSON field `"id"`, NOT the filename. Known characters:
- `linwan` (林婉): cold exterior, secretly caring
- `maid` (小羽): gentle maid, filename is `student.json`
- `xiaomei` (小梅): aloof, sometimes sarcastic, filename is `teacher.json`

### World Files

World definitions in `data/worlds/{id}.json` provide setting context. Known worlds:
- `campus` (校园): university daily life
- `cyberpunk` (赛博朋克): neon-lit corporate dystopia 2099

## Important Patterns

- **Lazy imports for agents**: `MemoryCenter` methods use `from funcation import X` inside method bodies (not at module top) to avoid circular imports.
- **File I/O per call**: Each `MemoryCenter` method does its own load-modify-save cycle. There's no in-memory caching or batching. For a single-user app this is fine.
- **No error handling**: The `/chat` endpoint has no try/except. Any agent failure, API error, or file I/O issue results in a 500.
- **`response_format={"type": "json_object"}`**: Used by `memory_agent` and `profile_agent` to force structured JSON from DeepSeek. `relationship_agent` and `story_agent` use plain text + manual JSON parsing with `json.loads()`.
- **Directory name**: The package is `funcation` (not `function`). This is intentional — all imports use this spelling.
- **No `__init__.py`**: The `funcation/` directory has no init file. Imports use `from funcation import module_name`.
- **Fallback paths**: `MemoryCenter.load_character_by_id()` and `load_world_by_id()` try `data/` first, then fall back to old root-level directories.
