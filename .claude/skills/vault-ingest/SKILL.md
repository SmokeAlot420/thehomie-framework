---
name: vault-ingest
description: "Ingest a document into an Obsidian vault with full red carpet treatment — auto-detect target vault, place in the right folder, generate YAML frontmatter, wire into MOCs, update dashboards, add to canvas, and update MEMORY.md. Use PROACTIVELY whenever the user says: 'add this to the vault', 'ingest this', 'put this in obsidian', 'file this', 'add this doc', 'vault this', 'save this to the vault', 'make this a vault note', or hands you a document/file and wants it properly organized. Also triggers on: 'red carpet this', 'full treatment', 'ingest these files'. Works with single files or batch mode."
---

# `/vault-ingest` — Red Carpet Document Ingestion

Takes one or more documents and makes them first-class citizens in the appropriate Obsidian vault. Handles everything: placement, frontmatter, MOC wiring, canvas nodes, dashboard visibility, and memory updates.

## Usage

```
/vault-ingest path/to/document.md                    # Single file
/vault-ingest path/to/doc1.md path/to/doc2.md        # Multiple files
/vault-ingest "paste or description"                  # From conversation context
/vault-ingest path/to/file.md --vault coding          # Force target vault
/vault-ingest path/to/file.md --vault thehomie    # Force target vault
/vault-ingest path/to/file.md --dry-run               # Preview without writing
```

## Vaults

Two Obsidian vaults are available. The skill auto-detects which one a document belongs in, but the user can override with `--vault`.

| Vault | Path | Purpose | Folders |
|-------|------|---------|---------|
| **coding-vault** | `C:\Users\YourUser\coding-vault\` | Technical knowledge — PRDs, research, decisions, architecture, patterns | By topic (research/, decisions/, PRDs/, etc.) |
| **thehomie** | `C:\Users\YourUser\thehomie\TheHomie\Memory\` | Operational — daily logs, system docs, deep-dives, goals, drafts | docs/, daily/, weekly/, drafts/ |

### Auto-Detection Rules

Read the document content and classify it:

| Content Signals | Target Vault | Target Folder |
|----------------|-------------|---------------|
| Deployment-specific app architecture, API docs, backend/frontend deep-dives | thehomie | `docs/` |
| SEO research, competitor analysis, algorithm updates | coding-vault | `research/` |
| PRDs, feature specs, implementation plans | coding-vault | `PRDs/` |
| Architecture decisions, tech choices (ADR-style) | coding-vault | `decisions/` |
| Personal operations, finance, accounts, life admin | thehomie | `docs/` |
| System overviews, unified docs, thehomie docs | thehomie | `docs/` |
| Email/message drafts | thehomie | `drafts/active/` |
| Weekly summaries/reviews | thehomie | `weekly/` |

If ambiguous, ask the user. Don't guess on edge cases.

---

## The Red Carpet (9 Steps)

### Step 1: Read & Classify

Read the source document(s). For each file, determine:
- **Target vault** (coding-vault or thehomie)
- **Target folder** within that vault
- **Topic cluster** — which MOC(s) this relates to
- **Content summary** — 1-2 sentence description for frontmatter
- **Related notes** — scan for names, topics, or concepts that match existing vault notes

For classification, scan existing vault notes to understand the neighborhood. Read the MOC files to see what topics are already organized.

### Step 2: Generate Frontmatter

Every ingested document gets YAML frontmatter. Generate it based on content analysis:

```yaml
---
aliases: ["Short Name", "Alternate Name"]
tags: [detected-tag-1, detected-tag-2]
status: current
date: YYYY-MM-DD
related:
  - "[[Related-Note-1]]"
  - "[[Related-Note-2]]"
summary: "One-line summary of what this document covers."
---
```

**Frontmatter rules:**
- `aliases` — short name + any acronyms or alternate names mentioned in the doc
- `tags` — derived from content (max 5). Use existing vault tags when possible — scan MOCs and other notes for tag conventions before inventing new ones
- `status` — `current` for active docs, `reference` for static reference material, `archived` for historical
- `date` — today's date (YYYY-MM-DD)
- `related` — wiki-links to 2-5 notes that are topically connected. Find these by scanning the vault for notes that mention similar concepts
- `summary` — one sentence, plain English, useful for Dataview table columns

**If the document already has frontmatter:** Merge, don't overwrite. Add missing fields, preserve existing values. If `related` exists, append new links rather than replacing.

**If the document has no frontmatter:** Insert the full block at the top of the file, before the first heading.

### Step 2.5: Preserve Raw Source

Copy the original, unmodified source document into the vault's `raw/` directory. This creates an immutable archive that enables "recompile from source" if entity extraction or compilation needs to be re-run. This is the Karpathy LLM Wiki `raw/` pattern — **never modify files in `raw/`**.

Invoke the canonical CLI — it handles directory creation, collision → date-prefix, and metadata preservation in one call:

```bash
cd .claude/scripts && uv run python entity_extractor.py preserve-raw "path/to/original-source.md" --vault-dir "path/to/vault"
```

The command prints the destination path on stdout (e.g., `path/to/vault/raw/original-source.md`, or on collision `path/to/vault/raw/2026-04-11-original-source.md`). Capture that path if you need to reference the archived copy later.

**Semantics:**
- Target: `{vault_root}/raw/{original-filename}`
- If a file with the same name already exists in `raw/`, the CLI falls back to `{YYYY-MM-DD}-{original-filename}` automatically
- File metadata (mtime, permissions) is preserved via `shutil.copy2`
- The source file is **never modified**
- This step is quick — just a file copy, no analysis

### Step 3: Place the File

Copy (not move) the document to its target location in the vault:
- If a file with the same name already exists, STOP and ask the user
- Use UPPER-KEBAB-CASE for filenames in both vaults to match conventions (e.g., `SEO-DEEP-DIVE.md`, `VOICE-AI-ARCHITECTURE.md`)
- The placed file includes the new frontmatter from Step 2

### Step 3.5: Compile Entities (The Cascade)

**This is the compilation step** — ported from Karpathy's LLM Wiki pattern. After placing the source note, extract entities/concepts and cascade updates through concept pages. This turns the vault from a filing system into a deeply interlinked knowledge graph.

**How it works:**

1. Read the placed source note
2. Run heuristic entity extraction as a starting point:
   ```bash
   cd .claude/scripts && uv run python entity_extractor.py extract "path/to/placed-source.md"
   ```
3. Review the extracted entities (printed as JSON). **Enhance with your own understanding** — the heuristic catches headings, bold text, and wiki-links, but you can identify deeper concepts the heuristics miss. Add/remove/adjust entities as needed.
4. Save your final entity list to a temp JSON file and compile:
   ```bash
   cd .claude/scripts && uv run python entity_extractor.py compile "path/to/placed-source.md" --entities /tmp/entities.json --vault-dir "path/to/vault" --memory-dir "path/to/memory"
   ```
   Or just run compilation directly from the source (uses heuristic extraction):
   ```bash
   cd .claude/scripts && uv run python entity_extractor.py compile "path/to/placed-source.md" --vault-dir "path/to/vault" --memory-dir "path/to/memory"
   ```
5. The compilation:
   - Creates new concept pages in `concepts/` for entities not yet in the vault
   - Updates existing concept pages with new claims from this source
   - Adds cross-references between source and concept pages
   - Regenerates `concepts/INDEX.md` (grouped by entity type)
   - Reindexes all modified files for search

**Concept pages** live in `{vault_root}/concepts/` as flat UPPER-KEBAB-CASE files with `tags: [concept, auto-compiled]`. They accumulate claims from multiple sources over time, building a dense knowledge graph. Heading numbers (e.g., `1. System Architecture`) are automatically stripped from slugs.

**Confidence threshold:** Only entities with confidence >= 0.6 get concept pages. This filters noise (generic terms, incidental mentions) while keeping meaningful concepts.

### Step 3.5b: Lint Health Check (Optional)

After compilation, optionally run the vault linter to catch structural issues:

```bash
cd .claude/scripts && uv run python vault_lint.py --vault-dir "path/to/vault"
```

8 checks: orphan pages, broken wikilinks, frontmatter validation, tag audit (against SCHEMA.md), stale content, page size, index completeness, contradiction scan. Zero LLM cost.

### Step 3.6: Flag Contradictions

After compilation, check updated concept pages for conflicting claims from different sources:

```bash
cd .claude/scripts && uv run python entity_extractor.py contradictions "path/to/concept-page.md"
```

If contradictions are found, they're automatically inserted as Obsidian callout blocks:

```markdown
> [!warning] Contradiction (direct)
> **[[Source-A]]** says: "SQLite is the default database"
> **[[Source-B]]** says: "The system does not use SQLite as the default"
> *Flagged during compilation on 2026-04-06*
```

Report any contradictions found to the user — these are valuable signals, not errors.

### Step 4: Wire into MOCs

Find the relevant MOC(s) and add the new document as a curated wiki-link.

**For coding-vault:** Read existing MOCs (glob for `MOC-*.md` or `*-hub.md`). Find the one whose topic matches the document. Add under the appropriate subsection with a context line:
```markdown
- [[NEW-DOCUMENT]] — One-line context about what this adds
```

**For thehomie:** inspect the existing `MOC-*.md` files first and use the closest fit. Default to the system MOC for framework/runtime docs and the operations MOC for operational material.

Add the new note under the right section. If no section fits, add a new subsection before the Auto-Discovery query.

**If no MOC fits:** Create a new `MOC-{topic}.md` following the vault's MOC pattern (curated links + auto-discovery Dataview query at bottom).

### Step 5: Update Canvas

Find the relevant canvas board and add the new document as a file node.

**For thehomie canvases:**
- `_canvas/thehomie-architecture.canvas` — system/identity docs
- the closest deployment/system canvas already present in the vault for deployment-specific technical docs

**For coding-vault canvases:** Glob for `_canvas/*.canvas` or `*.canvas` files.

**Canvas update process:**
1. Read the canvas JSON
2. Find the right cluster of nodes (by analyzing existing node positions and labels)
3. Calculate position: place the new node near related nodes, offset by 350px to avoid overlap
4. Add the node with `"type": "file"`, appropriate dimensions (300w x 250h default)
5. Add an edge from the most related existing node to the new node
6. Write the updated JSON back

**If the canvas would get too crowded (>20 nodes):** Skip the canvas update and note it in the report. Canvases lose value when they're cluttered.

### Step 6: Update Memory

**For thehomie vault:** Edit `MEMORY.md` in the vault root. Add the new document to the relevant section under "Important Facts" or "Active Projects".

**For coding-vault:** Edit `CLAUDE.md` in the vault root. Add the document reference to the appropriate section.

---

## Batch Mode

When given multiple files, process them in sequence but optimize:
1. Scan all vaults ONCE at the start (read all MOCs, canvases, existing notes)
2. Classify all files before placing any
3. Present the classification plan to the user for confirmation
4. Execute placements, MOC updates, and canvas updates
5. Single consolidated report at the end

---

## Report

After processing, output a summary:

```
## Ingested: {filename}

| Step | Result |
|------|--------|
| Vault | coding-vault |
| Folder | research/ |
| Frontmatter | 3 tags, 4 related links, summary generated |
| MOC | Added to MOC-seo-research.md (Research section) |
| Canvas | Added to research-map.canvas (node + 1 edge) |
| Memory | Added to MEMORY.md line 47 |
```

For batch mode, show a summary table of all files processed.

---

## Rules

1. **Read before write** — always scan the vault's existing structure before placing anything
2. **Never overwrite** — if a file exists at the target path, ask the user
3. **Copy, don't move** — the original file stays where it is
4. **Match conventions** — use the naming style, tag style, and structure of existing vault notes
5. **Merge frontmatter** — if the doc already has YAML frontmatter, add to it rather than replacing
6. **Validate links** — every `[[wikilink]]` added to an MOC must point to a real file
7. **Canvas sanity** — don't add to canvases with >20 nodes (diminishing returns)
8. **Ask on ambiguity** — if vault/folder classification isn't clear, ask rather than guess
9. **Preserve content** — never modify the body of the document (only add/merge frontmatter at the top)
10. **Report everything** — the user should know exactly what changed and where
