# Developer Resources Index

> Curated resources for AI-assisted development. Drop into any project root or reference from your IDE/agent instructions.

---

## Quick Lookup by Need

| I need to... | Go to |
|--------------|-------|
| Build accurate RAG | [Trustworthy RAG](#trustworthy-rag), [Corrective RAG](#corrective-rag), [ColBERT RAG](#colbert-rag) |
| Add memory/state | [Zep Memory](#zep-memory) |
| Route between tools/DBs | [RAG SQL Router](#rag-sql-router) |
| Build agents | [Claude Code Patterns](#claude-code-patterns), [OpenAI Agents Guide](#openai-agents-guide) |
| Design guided learning UX | [DeepTutor](#deeptutor) |
| Create devotional/meditation UX | [Hallow Patterns](#hallow-app-patterns) |
| Understand context engineering | [Context Engineering Survey](#context-engineering-survey) |
| Build beautiful frontends | [Frontend Design Patterns](#frontend-design-patterns) |

---

## RAG & Retrieval

### Trustworthy RAG
`#rag` `#citations` `#accuracy` `#production`

**Repo:** `github.com/patchy631/ai-engineering-hub/Trustworthy-RAG`

**What it solves:** LLMs hallucinating citations, wrong attributions, unverifiable claims

**Key patterns:**
- Citation verification pipeline
- Source confidence scoring
- Retrieval-grounded generation
- Fact-checking layer

**Use when:** Any app where accuracy matters (legal, medical, theological, educational)

---

### Corrective RAG
`#rag` `#self-correction` `#quality`

**Repo:** `github.com/patchy631/ai-engineering-hub/Corrective-RAG`

**What it solves:** Retrieved content that contradicts known facts or other sources

**Key patterns:**
- Cross-reference validation
- Contradiction detection
- Confidence thresholding
- Retrieval quality scoring

**Use when:** Domain-specific apps where bad retrieval = bad outcomes

---

### ColBERT RAG
`#rag` `#retrieval` `#performance`

**Repo:** `github.com/patchy631/ai-engineering-hub/ColBERT-RAG`

**What it solves:** Slow or imprecise retrieval at scale

**Key patterns:**
- Late interaction for better matching
- Token-level similarity
- Efficient indexing

**Use when:** Large corpora, need speed + accuracy balance

---

### RAG SQL Router
`#rag` `#routing` `#multi-source`

**Repo:** `github.com/patchy631/ai-engineering-hub/RAG-SQL-Router`

**What it solves:** Queries that need different backends (vector DB vs SQL vs API)

**Key patterns:**
- Intent classification
- Dynamic source selection
- Query transformation per backend

**Use when:** Apps with multiple data sources (structured + unstructured)

---

## Memory & State

### Zep Memory
`#memory` `#personalization` `#state`

**Repo:** `github.com/patchy631/ai-engineering-hub/Zep-Memory`

**What it solves:** Stateless AI that forgets everything between sessions

**Key patterns:**
- Long-term user memory
- Session state management
- Memory summarization
- Retrieval from memory

**Use when:** Personalized apps, progress tracking, user journeys, learning systems

---

## Agents & Orchestration

### Claude Code Patterns
`#agents` `#tools` `#workflows` `#claude`

**Repo:** `github.com/anthropics/claude-code`

**What it solves:** Building effective agentic workflows with Claude

**Key patterns:**
- Custom slash commands
- Agent hooks and middleware
- Multi-step task orchestration
- Tool use patterns

**Related:** `anthropics/claude-cookbooks`, `anthropics/quickstarts`

**Use when:** Any Claude-powered agent, automation, or agentic coding setup

---

### OpenAI Agents Guide
`#agents` `#orchestration` `#tools`

**Source:** `github.com/AniruddhaChattopadhyay/Books` (OpenAI Agents PDF)

**What it solves:** Understanding agent architecture patterns

**Key patterns:**
- Tool selection strategies
- Multi-agent coordination
- Error handling in agents
- State management

**Use when:** Designing any agentic system, regardless of model provider

---

### Context Engineering Survey
`#context` `#rag` `#memory` `#architecture`

**Source:** `github.com/AniruddhaChattopadhyay/Books` (Context Engineering Survey)

**What it solves:** Understanding how to structure context for LLMs

**Key patterns:**
- Context window optimization
- RAG vs fine-tuning decisions
- Memory architecture patterns
- Prompt structuring

**Use when:** Designing any LLM-powered system, optimizing existing apps

---

## UX Patterns

### DeepTutor
`#education` `#guided-learning` `#citations` `#questions`

**Repo:** `github.com/HKUDS/DeepTutor`

**What it solves:** Building effective AI tutoring/learning experiences

**Key patterns:**
- Citation system (maps to Trustworthy RAG)
- Question generation from content
- Guided learning flows
- Dual-loop problem solving

**Use when:** Educational apps, onboarding flows, documentation assistants

---

### Hallow App Patterns
`#meditation` `#devotional` `#engagement` `#spiritual`

**Reference:** Hallow iOS/Android app

**What it solves:** Bridging study + devotion, sustained engagement

**Key patterns:**
- Lectio Divina flow (Read → Reflect → Respond → Rest)
- Session length options (5/10/15/20 min)
- Ambient audio layers
- Journaling prompts
- Streak tracking
- Gentle notifications

**Use when:** Contemplative apps, habit-forming products, wellness/spiritual tech

---

### Frontend Design Patterns
`#ui` `#design` `#frontend`

**Location:** `/mnt/skills/public/frontend-design/SKILL.md`

**What it solves:** Avoiding generic AI-generated UI, building distinctive interfaces

**Key patterns:**
- Design system foundations
- Component composition
- Animation and interaction
- Accessibility patterns

**Use when:** Any user-facing app where design quality matters

---

## Data & APIs

### Bible & Theological Data
`#bible` `#theology` `#data`

| Resource | Type | What it provides |
|----------|------|------------------|
| `scrollmapper/bible_databases` | SQLite | Verse mappings, cross-refs, Strong's |
| `wldeh/bible-api` | API | Multiple translations |
| `rkeplin/bible-api` | API | NIV text |
| `BradyStephenson/bible-data` | JSON | Structured metadata |
| `CCEL/church-fathers` | Text | Patristic writings |
| `HistoricalChristianFaith` | Text | Church fathers encyclopedia |
| `OpenBible Geocoding` | JSON | Biblical location coordinates |
| `Creeds.json` | JSON | Historical creeds |

---

## Project Templates

### Vibe Coding Setup Checklist

For any new project with AI agents:

```markdown
## Project Setup

- [ ] Create CLAUDE.md or PROJECT_CONTEXT.md with:
  - [ ] Project mission (one sentence)
  - [ ] Tech stack
  - [ ] Key architectural decisions
  - [ ] Data sources and how to access
  - [ ] Coding conventions
  - [ ] Common tasks with examples

- [ ] Add relevant skill references:
  - [ ] RAG patterns (if AI-powered)
  - [ ] Memory patterns (if stateful)
  - [ ] UX patterns (if user-facing)

- [ ] Set up agent instructions in IDE (Antigravity/Cursor/etc.)
```

### Standard Project Context Template

```markdown
# [Project Name]

## Mission
[One sentence: what does this do and for whom?]

## Stack
- Framework:
- Language:
- AI:
- Database:
- Deployment:

## Architecture
[Simple diagram or description]

## Key Patterns
[What patterns from the resources index apply?]

## Data Sources
[What data does this use? How is it accessed?]

## Agent Tasks
[Common things an AI agent might do in this codebase]
```

---

## Tagging Reference

| Tag | Meaning |
|-----|---------|
| `#rag` | Retrieval-Augmented Generation |
| `#memory` | State persistence, user memory |
| `#agents` | Autonomous AI agents |
| `#tools` | Tool use, function calling |
| `#citations` | Source attribution, accuracy |
| `#education` | Learning, tutoring UX |
| `#routing` | Query/intent routing |
| `#frontend` | UI/UX patterns |

---

## How to Use This Index

### In Claude.ai / Claude Code
Reference this file in your conversation or CLAUDE.md:
```
See DEVELOPER_RESOURCES_INDEX.md for patterns on [topic]
```

### In Antigravity
Add to project context or reference in instructions:
```
When implementing [feature], consult the [section] in DEVELOPER_RESOURCES_INDEX.md
```

### Starting a New Project
1. Copy this file to project root
2. Delete irrelevant sections
3. Add project-specific resources
4. Reference in your agent instructions

---

*Last updated: January 2026*
