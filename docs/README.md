# Foobara Universe

Multi-repo ecosystem manager for the [Foobara](https://github.com/foobara/foobara) Ruby framework.

## Structure

```
foobara-universe/
├── foobara-ecosystem-ruby/     # 63 Ruby repositories organized by category
│   ├── core/                   # Foundation libraries (5 repos)
│   ├── connectors/             # Command connectors (9 repos)
│   ├── drivers/                # CRUD drivers (4 repos)
│   ├── generators/             # Code generators (16 repos)
│   ├── apis/                   # External API integrations (6 repos)
│   ├── ai/                     # AI/Agent components (6 repos)
│   ├── web/                    # Web applications (4 repos)
│   ├── tools/                  # Development tools (5 repos)
│   ├── types/                  # Type extensions (2 repos)
│   ├── auth/                   # Authentication (2 repos)
│   ├── integrations/           # Framework integrations (3 repos)
│   └── typescript/             # TypeScript generators (1 repo)
│
├── foobara-ecosystem-python/   # Future Python implementation
│
├── eureka/                     # Quick research notes
├── eureka-vault/               # Strategic research hub
│   ├── breakthroughs/          # Major discoveries
│   ├── research/               # Active research
│   ├── milestones/             # FM1, FM2, FM3 tracking
│   ├── templates/              # Task templates
│   └── schedules/              # Daily/weekly routines
│
├── scripts/                    # Automation scripts
│   ├── config/repos.yml        # Repository configuration
│   ├── clone-all.sh            # Clone all repositories
│   ├── sync-check.rb           # Detect upstream changes
│   ├── eureka-trigger.rb       # Generate research tasks
│   └── create-wedo-tasks.rb    # Generate WeDo tasks
│
└── .foobara-universe/          # State and configuration
    ├── state/                  # Sync state tracking
    └── pending-tasks/          # WeDo task queue
```

## Quick Start

### Clone All Repositories

```bash
./scripts/clone-all.sh
```

Options:
- `--dry-run` - Preview what would be cloned
- `--category NAME` - Clone only specific category

### Check for Upstream Changes

```bash
./scripts/sync-check.rb --verbose --fetch
```

Options:
- `--json` - Output as JSON
- `--fetch` - Fetch from remotes first
- `--category NAME` - Check specific category only

### Create WeDo Tasks

```bash
./scripts/create-wedo-tasks.rb
```

Options:
- `--dry-run` - Preview tasks without creating
- `--sync-check-output FILE` - Use pre-generated sync output

## Categories

| Category | Repos | Description |
|----------|-------|-------------|
| core | 5 | Foundation libraries: foobara, util, lru-cache, inheritable-thread-vars, spec-helpers |
| connectors | 9 | Protocol connectors: rack, rails, sh-cli, mcp, resque |
| drivers | 4 | CRUD drivers: postgresql, redis, local-files |
| generators | 16 | Code generators for domains, commands, types |
| apis | 6 | External APIs: anthropic, openai, ollama, rubygems |
| ai | 6 | AI components: agent, agent-cli, llm-backed-command |
| web | 4 | Web apps: foobara-www, examples, foobarticles |
| tools | 5 | Dev tools: foob CLI, rubocop-rules, extract-repo |
| types | 2 | Type extensions: active-record-type, json-schema |
| auth | 2 | Authentication: auth, auth-http |
| integrations | 3 | Framework integrations: rails, heroku, typescript-react |
| typescript | 1 | TypeScript code generation |

## WeDo Integration

Changes are tracked and converted to WeDo tasks:

| Change Type | Priority | Dependency |
|-------------|----------|------------|
| Upstream commits | normal/high | AGENT_CAPABLE |
| Version bump (major) | urgent | USER_REQUIRED |
| Version bump (minor) | high | USER_REQUIRED |
| Dependency added | normal | AGENT_CAPABLE |
| Dependency removed | high | USER_REQUIRED |

Task format: `FOOBARA-XXX: Description`

## Eureka Research

Strategic research system that monitors the ecosystem and drives product planning.

### Research Milestones

| Milestone | Focus | Status |
|-----------|-------|--------|
| FM1 | Ecosystem Intelligence | Active |
| FM2 | FlukeBase Integration | Planned |
| FM3 | Product Pipeline | Planned |

### Research Triggers

Changes automatically create research tasks:

| Trigger | Condition | Task Prefix |
|---------|-----------|-------------|
| Upstream Burst | >10 commits behind | EUREKA-SYNC |
| Breaking Change | Major version bump | EUREKA-BREAK |
| MCP Updates | mcp-connector changes | EUREKA-MCP |
| AI Components | ai/ category updates | EUREKA-AI |

### Task Cascade

```
EUREKA-* (Research) → PROD-* (Planning) → FOOBARA-* (Implementation)
```

## Daily Workflow

```bash
# 1. Check for upstream changes
./scripts/sync-check.rb --fetch --verbose

# 2. Generate research tasks from significant changes
./scripts/eureka-trigger.rb --verbose

# 3. Create implementation tasks from completed research
./scripts/create-wedo-tasks.rb

# 4. View all pending tasks
cat .foobara-universe/pending-tasks/*.jsonl | jq .
cat eureka-vault/pending/*.jsonl | jq .
```

## FlukeBase Project

This ecosystem is registered as FlukeBase project ID: 27 (`foobara-universe`)

Sync with: `fb_sync --project_id 27`
