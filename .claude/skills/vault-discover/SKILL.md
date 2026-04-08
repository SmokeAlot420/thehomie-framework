---
name: vault-discover
description: "AI-powered knowledge graph discovery: analyzes all 3 Obsidian vaults to surface hidden connections, cross-domain analogies, structural gaps, and 'aha moments' between notes that should be connected but aren't. The compounding interest engine for your knowledge system."
---

# `/vault-discover` — Knowledge Graph Discovery Engine

Autonomously browses your vault graph, reads note content, and surfaces non-obvious connections,
cross-domain analogies, structural gaps, and genuine "aha moments" you'd never find manually.
This is the compound interest engine — it makes your knowledge system smarter every time it runs.

## Usage

```
/vault-discover                          # Full discovery across all 3 vaults
/vault-discover --vault coding-vault     # Focus on one vault
/vault-discover --topic "SEO fleet"      # Focus discoveries around a topic
/vault-discover --quick                  # Structural analysis only (no deep read)
/vault-discover --apply                  # Auto-apply discovered connections after review
```

## Vaults

| Vault | Path | Domain |
|-------|------|--------|
| coding-vault | `C:\Users\YourUser\coding-vault\` | YourBusiness: SEO/GEO, architecture, 27 brand sites, competitors, decisions |
| thehomie | `C:\Users\YourUser\thehomie\TheHomie\Memory\` | AI agent: heartbeat, memory, cognition, operations, daily logs |
| unified-vault | `C:\Users\YourUser\unified-vault\` | Personal: cross-project, crypto, workflows, tools, daily logs |

**Skip directories:** `_templates/`, `_dashboards/`, `_canvas/`, `_ops/`, `.obsidian/`

## Philosophy

Most vault tools maintain — this one discovers. The difference:

- **Maintain** asks: "Is this note healthy?" (frontmatter, links, staleness)
- **Discover** asks: "What does this note MEAN, and what else in your brain connects to it?"

The value is in **cross-domain pattern recognition**. You're working on an AI agent framework
AND managing 27 brand websites AND tracking personal workflows. Patterns from one domain
almost certainly apply to another — but you'd never look because they live in different vaults
with different tags. That's exactly where the gold is.

### Discovery Types (what we're looking for)

| Type | Example | Value |
|------|---------|-------|
| **Cross-domain analogy** | "Managing 27 brand sites is the same pattern as managing multiple AI agents — both need fleet ops, health monitoring, and standardized templates" | Reuse solutions across domains |
| **Structural gap** | Two note clusters about related topics with zero links between them | Bridge ideas that should talk to each other |
| **Contradiction** | Decision note says "always use Supabase" but another says "SQLite is the intentional default" | Surface unresolved tensions |
| **Reinforcement** | Multiple independent notes arriving at the same conclusion from different angles | Strengthen conviction |
| **Missing bridge** | Notes A→B and C→D exist, but B and C are about the same concept under different names | Connect disconnected islands |
| **Temporal pattern** | Same topic appears in daily logs 4x in 3 weeks but has no dedicated note | Signal to promote to permanent knowledge |
| **Undervalued node** | A note with rich content but zero incoming links | Reconnect buried treasure |

---

## Pipeline (6 Phases)

### Phase 1: BUILD GRAPH — Map the territory

Parse all 3 vaults into a link graph. Nodes = notes, edges = wiki-links (both `related:` frontmatter and body `[[links]]`).

```bash
# For each vault, extract the graph structure
VAULT_PATH="..."
SKIP="-not -path '*/_templates/*' -not -path '*/_ops/*' -not -path '*/.obsidian/*' -not -path '*/_dashboards/*' -not -path '*/_canvas/*'"

# 1. List all notes (nodes)
find "$VAULT_PATH" -name "*.md" $SKIP | sort > /tmp/vault_nodes.txt

# 2. Extract all outgoing wiki-links per note (edges)
for f in $(cat /tmp/vault_nodes.txt); do
  stem=$(basename "$f" .md)
  # Get links from frontmatter related: field
  awk '/^---/{n++; if(n==2) exit} n==1' "$f" | grep -oP '\[\[([^\]|]+)' | sed 's/\[\[//' | while read link; do
    echo "$stem -> $link"
  done
  # Get links from body text
  awk '/^---/{n++; next} n>=2' "$f" | grep -oP '\[\[([^\]|]+)' | sed 's/\[\[//' | while read link; do
    echo "$stem -> $link"
  done
done > /tmp/vault_edges.txt
```

Record per vault:
- **Node count** — total notes
- **Edge count** — total links
- **Density** — edges / (nodes * (nodes-1))
- **Average degree** — avg links per note

### Phase 2: STRUCTURAL ANALYSIS — Find where discoveries hide

Using the graph from Phase 1, compute:

#### 2a. Cluster Detection
Group notes by connectivity. Two approaches (use both):

1. **Tag-based clusters** — group by primary tag (seo, architecture, operations, daily, etc.)
2. **Link-based clusters** — connected components via BFS from MOC roots

For each cluster, record:
- Member notes
- Internal edge count (links within cluster)
- External edge count (links to other clusters)
- **Insularity score** = internal / (internal + external) — high = isolated cluster

#### 2b. Bridge Nodes
Notes that connect two otherwise separate clusters. Remove the note — does the graph split?

```bash
# Approximation: notes with incoming links from 2+ different tag groups
# These are the connectors between knowledge domains
```

#### 2c. Hub Nodes
Most-connected notes (highest degree). These are your knowledge anchors.
Separate into:
- **In-hubs** (most linked TO) — authoritative reference notes
- **Out-hubs** (most links FROM) — usually MOCs and dashboards

#### 2d. Orphan Analysis
Notes with < 2 total connections (incoming + outgoing) despite having > 200 chars of content.
These are undervalued — rich content nobody finds.

#### 2e. Cross-Vault Edges
Links that cross vault boundaries (e.g., coding-vault note links to a concept that exists
in thehomie). These are rare and extremely valuable — they represent conscious
cross-domain thinking you've already done.

#### 2f. Structural Gaps (InfraNodus-style)
Find pairs of clusters that:
- Have high semantic similarity (shared keywords, related topics)
- But low or zero link density between them

This is where the biggest discoveries hide — topics that SHOULD be talking to each other.

### Phase 3: STRATEGIC SAMPLING — Pick notes to deep-read

Don't read random notes. Select strategically from Phase 2 findings:

| Source | Count | Why |
|--------|-------|-----|
| Bridge nodes | 3-4 | They already connect domains — read to understand WHY |
| Orphans with rich content | 3-4 | Buried treasure — find where they belong |
| Cluster boundary notes | 4-5 | Notes at the edge of a cluster, closest to another cluster |
| Cross-vault edge endpoints | 2-3 | Existing cross-domain connections to extend |
| Hub notes (non-MOC) | 2-3 | Understand what the graph considers important |
| **Total** | **15-20** | Enough for pattern recognition, not so many we lose focus |

If `--topic` is specified, weight selection toward notes related to that topic.

For each selected note:
1. Read full content via the Read tool
2. Extract the **core concept** (1-2 sentences: what is this note really about?)
3. Extract **domain keywords** (what field/context does this belong to?)
4. Note the **insight density** — does this note contain decisions, patterns, or just logs?

### Phase 4: CROSS-REFERENCE & DISCOVER — The magic

This is the core value. With 15-20 deeply read notes from strategic positions in the graph,
perform cross-referencing:

#### 4a. Cross-Domain Analogies
For every pair of notes from DIFFERENT vaults or DIFFERENT clusters:
- Do they describe the same pattern in different domains?
- Could a solution from one apply to a problem in the other?
- Are they using different words for the same concept?

**Examples of what to look for:**
- "Fleet management" patterns (brand sites, agent instances, server deployments)
- "Health monitoring" patterns (vault health, heartbeat, site monitoring)
- "Pipeline" patterns (build pipelines, content pipelines, data pipelines)
- "Template/stamp" patterns (brand templates, note templates, prompt templates)

#### 4b. Contradictions & Tensions
Do any two notes assert opposing things?
- Different architectural decisions that conflict
- Goals that pull in opposite directions
- Assumptions in one note that another note disproves

#### 4c. Reinforcements
Multiple notes independently arriving at the same conclusion.
These strengthen conviction — note when 3+ sources agree.

#### 4d. Missing Bridges
Note A links to B. Note C links to D. But B and C are about the same concept
(different names, different vaults). The A→B→C→D path should exist but doesn't.

#### 4e. Temporal Patterns
From daily logs: topics that keep appearing without a dedicated note.
If something shows up 3+ times in recent logs, it deserves promotion to permanent knowledge.

#### 4f. Actionable Gaps
Based on what exists, what SHOULD exist but doesn't?
- A decision that was discussed but never recorded
- A pattern that appears everywhere but has no name
- A comparison that would clarify a choice

### Phase 5: SURFACE — Present discoveries

Generate a discovery report. Save to `unified-vault/_ops/discoveries/`:

**File:** `unified-vault/_ops/discoveries/discover-{YYYY-MM-DD}.md`

```markdown
---
tags: [discovery, vault-ops]
status: current
date: {today}
summary: "Knowledge graph discovery: {N} aha moments, {M} new connections suggested"
related: ["{most relevant notes}"]
priority: P2
---

# Vault Discovery — {date}

## Graph Snapshot

| Vault | Notes | Links | Density | Clusters | Bridges | Orphans |
|-------|-------|-------|---------|----------|---------|---------|
| coding-vault | N | N | 0.XX | N | N | N |
| thehomie | N | N | 0.XX | N | N | N |
| unified-vault | N | N | 0.XX | N | N | N |

## Aha Moments

### 1. {Title — the insight in one sentence}

**Type:** {cross-domain analogy | structural gap | contradiction | reinforcement | missing bridge | temporal pattern}
**Confidence:** {HIGH | MEDIUM | LOW}
**Notes involved:**
- [[note-a]] ({vault}) — {what it says}
- [[note-b]] ({vault}) — {what it says}

**The insight:** {2-3 sentences explaining WHY this connection matters and what it means}

**Suggested action:**
- [ ] Add `[[note-b]]` to `note-a`'s related field
- [ ] Create a bridging note: `{suggested-stem}.md`
- [ ] Explore this further with `/vault-thinking-partner "{question}"`

---

{Repeat for each discovery — aim for 3-7 discoveries}

## Structural Observations

### Cluster Health
{Which clusters are too insular? Which are well-connected?}

### Bridge Nodes Worth Protecting
{Notes that hold the graph together — if you deleted them, knowledge islands form}

### Undervalued Notes
{Notes with rich content but no incoming links — buried treasure}

## Suggested New Links

| Source | Target | Reason |
|--------|--------|--------|
| note-a | note-b | {why} |
| ... | ... | ... |

## Questions Worth Exploring

Based on gaps in the graph, these questions don't have answers in your vault yet:

1. {Question — derived from a structural gap or contradiction}
2. {Question}
3. {Question}
```

### Phase 6: WIRE (if `--apply` flag)

After user reviews the discoveries, apply the connections:

1. Update `related:` frontmatter on notes with new connections
2. Add wiki-links in body text where appropriate
3. Create any suggested bridging notes
4. Update MOCs if new cross-domain sections are needed
5. Log to ops history

---

## Discovery Strategies (per run type)

### Full Discovery (`/vault-discover`)
- All 6 phases
- 15-20 notes deep-read
- Cross-vault analysis
- ~5-10 min

### Quick Discovery (`/vault-discover --quick`)
- Phase 1-2 only (structural)
- No deep reading
- Reports: graph stats, orphans, bridges, cluster insularity
- ~1-2 min

### Topic-Focused (`/vault-discover --topic "SEO"`)
- Full pipeline but sampling biased toward topic
- Finds connections between the topic and OTHER domains
- Great for "how does X connect to everything else?"

### Single Vault (`/vault-discover --vault coding-vault`)
- Full pipeline within one vault
- Finds intra-vault gaps and underconnected notes
- Faster but misses cross-vault insights

---

## Rules

1. **Read before connecting** — always read both notes before claiming they're related
2. **Quality over quantity** — 3 genuine aha moments beats 10 obvious ones
3. **Cross-domain is king** — prioritize connections between different knowledge domains
4. **Explain WHY** — every discovery must include reasoning, not just "these two notes exist"
5. **No AI slop** — write in direct, specific language. "These two notes both discuss fleet management patterns" not "There are fascinating synergies between these knowledge artifacts"
6. **Confidence ratings are honest** — HIGH means you're sure. MEDIUM means it's plausible. LOW means it's a stretch worth exploring.
7. **Don't double-link** — check existing `related:` before suggesting a connection
8. **Preserve note content** — discovery is read-heavy, write-light. Only modify `related:` fields and MOC links.
9. **Save discoveries** — always write the discovery note to `unified-vault/_ops/discoveries/`
10. **Actionable outputs** — every aha moment includes a suggested next step

## Scheduling

Best results when run:
- **Weekly** (after `/vault-weekly-synthesis`) — synthesis identifies what changed, discovery finds what connects
- **After major ingests** — new notes create new connection potential
- **After vault health fixes** — freshly populated `related:` fields create a richer graph to analyze
- **On demand** — whenever you feel stuck or want fresh perspective

## What Makes This Different

| Tool | What it does | What it misses |
|------|-------------|---------------|
| Obsidian Graph View | Shows link structure visually | No semantic analysis, no reasoning about connections |
| Smart Connections plugin | Embedding-based similar notes | Single vault only, no cross-domain analogies |
| InfraNodus | Topic modeling + gap detection | External tool, doesn't understand your vault's context |
| `/vault-autolink` | Finds text mentions of note names | Mechanical — matches names, not concepts |
| `/vault-weekly-synthesis` | Identifies weekly patterns | Time-bounded, not graph-structural |
| **`/vault-discover`** | AI reads content + analyzes graph structure + reasons about cross-domain connections | Nothing — this is the full picture |

The compound effect: every time you run this, discovered connections get wired in,
making the NEXT discovery run find deeper, second-order connections. Knowledge compounds.
