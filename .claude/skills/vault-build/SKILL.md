---
name: vault-build
description: "Build Obsidian vault infrastructure — dashboards, MOCs, canvases, templates, graph config, and bookmarks from any folder of markdown notes. Use when the user wants to turn a folder into a proper Obsidian vault or enhance an existing vault with Dataview dashboards, Maps of Content, canvas boards, and templates."
---

# `/vault-build` — Obsidian Vault Constructor

Takes a vault path, analyzes its content, and builds all 7 Obsidian infrastructure layers: config, Dataview plugin, dashboards, MOCs, canvases, templates, and graph/bookmarks. Adaptive to any vault — scans folders, tags, and frontmatter to generate tailored content.

## Usage

```
/vault-build <vault-path>                        # Build all 7 layers
/vault-build <vault-path> --phase 3              # Single phase only (dashboards)
/vault-build <vault-path> --phase 3,4,5          # Multiple phases
/vault-build <vault-path> --dry-run              # Preview without writing
/vault-build <vault-path> --source PRDs/my-prd.md  # Use source material to inform content
```

## Phases

| # | Phase | Creates | Depends On |
|---|-------|---------|------------|
| 1 | Config | `.obsidian/` (app.json, appearance.json, core-plugins, community-plugins) | nothing |
| 2 | Dataview | `.obsidian/plugins/dataview/` (plugin files + settings) | Phase 1 |
| 3 | Dashboards | `_dashboards/*.md` (Dataview-powered status tables) | Phase 2 |
| 4 | MOCs | `MOC-*.md` (Maps of Content with curated links + auto-discovery) | content notes exist |
| 5 | Canvases | `_canvas/*.canvas` (visual relationship maps) | content notes exist |
| 6 | Templates | `_templates/*.md` (note creation templates per category) | nothing |
| 7 | Graph & Bookmarks | `.obsidian/graph.json` + `.obsidian/bookmarks.json` | all above |

---

## Phase 1: `.obsidian/` Config

### Pre-check
```
IF <vault-path>/.obsidian/ EXISTS:
  → Read existing config files
  → MERGE new settings (never overwrite user prefs like theme, font size)
  → Skip files that already exist and look intentional
ELSE:
  → Create .obsidian/ from scratch
```

### Create these files

**app.json** — Editor & app settings:
```json
{
  "livePreview": true,
  "strictLineBreaks": false,
  "readableLineLength": true,
  "showLineNumber": true,
  "propertiesInDocument": "visible",
  "newFileLocation": "root",
  "newLinkFormat": "shortest",
  "useMarkdownLinks": false,
  "attachmentFolderPath": "./",
  "templateFolderPath": "_templates",
  "promptDelete": false
}
```

**appearance.json** — Theme:
```json
{
  "theme": "obsidian",
  "baseFontSize": 16
}
```

**core-plugins.json** — Enable essential core plugins:
```json
{
  "file-explorer": true, "global-search": true, "switcher": true,
  "graph": true, "backlink": true, "canvas": true, "outgoing-link": true,
  "tag-pane": true, "properties": true, "page-preview": true,
  "templates": true, "command-palette": true, "editor-status": true,
  "bookmarks": true, "outline": true, "word-count": true,
  "file-recovery": true,
  "footnotes": false, "daily-notes": false, "note-composer": false,
  "slash-command": false, "zk-prefixer": false, "random-note": false,
  "slides": false, "audio-recorder": false, "workspaces": false,
  "publish": false, "sync": false, "markdown-importer": false,
  "bases": false, "webviewer": false
}
```

**community-plugins.json**:
```json
["dataview"]
```

**workspace.json** — Default 3-pane layout:
- Left sidebar (300px): File explorer, Search, Bookmarks
- Main: Empty editor
- Right sidebar (300px, collapsed): Backlinks, Outgoing links, Tags, Outline

Refer to `references/obsidian-patterns.md` § Workspace JSON for the full template.

---

## Phase 2: Dataview Plugin

### Install Dataview from bundled files

Copy files from the skill's `references/dataview-plugin/` directory to `<vault-path>/.obsidian/plugins/dataview/`:

| Source | Destination | Size |
|--------|-------------|------|
| `references/dataview-plugin/manifest.json` | `.obsidian/plugins/dataview/manifest.json` | ~1KB |
| `references/dataview-plugin/main.js` | `.obsidian/plugins/dataview/main.js` | ~2.3MB |
| `references/dataview-plugin/styles.css` | `.obsidian/plugins/dataview/styles.css` | ~5KB |
| `references/dataview-plugin/data.json` | `.obsidian/plugins/dataview/data.json` | ~1KB |

### Pre-check
```
IF .obsidian/plugins/dataview/ EXISTS:
  → Compare versions (manifest.json → version field)
  → If existing version >= bundled version → SKIP (don't downgrade)
  → If existing version < bundled version → warn user, skip unless --force
```

### data.json settings (optimized defaults)
```json
{
  "renderNullAs": "\\-",
  "warnOnEmptyResult": true,
  "refreshEnabled": true,
  "refreshInterval": 2500,
  "defaultDateFormat": "MMMM dd, yyyy",
  "showResultCount": true,
  "allowHtml": true,
  "enableInlineDataview": true,
  "enableDataviewJs": true,
  "enableInlineDataviewJs": true,
  "prettyRenderInlineFields": true,
  "prettyRenderInlineFieldsInLivePreview": true
}
```

---

## Phase 3: Dashboards

### Vault Analysis (CRITICAL — do this FIRST)

Before creating any dashboard, analyze the vault:

```
1. List all top-level folders (exclude _dashboards, _templates, _canvas, .obsidian)
2. Sample 5-10 .md files from each folder — read frontmatter
3. Detect frontmatter pattern:
   - Has YAML frontmatter? → property-based queries (FROM "folder" WHERE status = ...)
   - No frontmatter? → folder-based queries only (FROM "folder" TABLE file.name)
4. Catalog all unique:
   - Folders (become query sources)
   - Tags (become filter criteria)
   - Status values (become grouping criteria)
   - Priority values (become sort criteria)
   - Custom properties (become table columns)
5. Count total notes per folder
```

### Create `_dashboards/` directory

Generate dashboards adapted to the vault's actual content. Always create these 3 core dashboards:

#### 1. `project-overview.md` — Master dashboard
```
---
tags: [dashboard]
summary: "Combined project dashboard: active work, recent activity, vault stats."
---
```

Sections:
- **Active Work**: TABLE of notes where `status = "current" OR status = "in-progress"` (skip if vault has no status property)
- **Recent Activity**: TABLE of notes with recent `date` frontmatter (skip if no date property)
- **Note Counts by Folder**: TABLE WITHOUT ID grouped by `file.folder`
- **Quick Stats**: Inline JS (`$= dv.pages("folder").length`) for each folder

#### 2. `vault-health.md` — Diagnostic dashboard
```
---
tags: [dashboard]
summary: "Vault health checks: missing properties, orphan notes, link integrity."
---
```

Sections (adapt to detected properties):
- **Notes Missing `summary`**: LIST WHERE !summary (only if vault uses summary)
- **Notes Missing `status`**: LIST WHERE !status (only if vault uses status)
- **Orphan Notes**: LIST WHERE length(file.inlinks) = 0
- **Most Connected Notes**: TABLE sorted by inlinks + outlinks DESC LIMIT 10
- **Notes by Status**: TABLE WITHOUT ID GROUP BY status

#### 3. Folder-specific dashboard (1 per major folder with 5+ notes)

For each folder with 5+ notes, create a dashboard named `{folder-name}-tracker.md`:
```
TABLE status, priority, summary FROM "{folder}" SORT priority ASC
```

Add grouping/filtering sections based on detected tags and status values.

### Dashboard Query Rules
- Always exclude `_dashboards`, `_templates`, `_canvas` folders from vault-wide queries
- Use `SORT priority ASC` when priority exists
- Use `SORT date DESC` for chronological views
- Use `choice()` for custom sort ordering when status has a known progression
- Include both a full TABLE view and filtered LIST views per dashboard
- Every dashboard gets `tags: [dashboard]` and `summary:` in frontmatter

---

## Phase 4: Maps of Content (MOCs)

### Topic Detection

```
1. Analyze folder structure + tags to identify 3-7 topic clusters
2. A topic cluster = a folder with 5+ notes OR a tag used by 5+ notes across folders
3. For each cluster, identify:
   - Hub note (most linked-to note in the cluster)
   - Key notes (high priority or high connectivity)
   - Related decisions, research, or architecture notes
```

### Create MOC files

For each detected topic cluster, create `MOC-{topic}.md` in the vault root:

```markdown
---
aliases: ["Topic Alias 1", "Topic Alias 2"]
tags: [moc]
status: current
priority: P2
date: {today}
related:
  - "[[hub-note]]"
summary: "Navigation hub for {topic} notes."
---

# {Topic Title}

{1-2 sentence description of what this topic area covers.}

## {Section 1 — e.g., "Strategy & Planning"}

- [[note-1]] — {one-line context from note's summary}
- [[note-2]] — {one-line context}

## {Section 2 — e.g., "Research"}

- [[note-3]] — {one-line context}
- [[note-4]] — {one-line context}

## Related Dashboards

- [[project-overview]] — Active work and vault-wide stats
- [[{folder}-tracker]] — {folder} status table

## Auto-Discovery

*Notes tagged with {topic-tag} — auto-updates when new notes are added.*

\```dataview
TABLE status, priority, summary
FROM #{topic-tag}
SORT priority ASC
\```
```

### MOC Rules
- **Curated links first** — hand-pick the most important 10-20 notes with `[[wikilinks]]` and context
- **Auto-discovery last** — Dataview query at the bottom catches new notes the MOC hasn't been updated for
- **Never just a Dataview query** — MOCs add human curation value on top of automated discovery
- Group links by sub-topic (2-4 sections of 3-8 links each)
- Every MOC links to at least 1 dashboard
- Include `aliases` for common search terms

---

## Phase 5: Canvases

### Canvas Generation

Create 1-2 `.canvas` files in `_canvas/` directory. Canvas JSON format:

```json
{
  "nodes": [
    {"id": "unique-id", "type": "file", "file": "path/to/note.md", "x": 0, "y": 0, "width": 350, "height": 300, "color": "2"},
    {"id": "label-id", "type": "text", "text": "# Section Label", "x": 0, "y": -100, "width": 260, "height": 60}
  ],
  "edges": [
    {"id": "edge-id", "fromNode": "node-a", "toNode": "node-b", "fromSide": "right", "toSide": "left", "label": "relationship"}
  ]
}
```

### Canvas Layout Strategy

1. **Project Status Canvas** — Always create this:
   - Columns: Completed | Active | Planned/Archived
   - Each node = a PRD, project, or major deliverable
   - Edges show evolution (v1 → v2 → v3)
   - Use color coding: 4=completed (green), 5=active (purple), 1=archived (red), 3=planned (yellow)

2. **Knowledge Map Canvas** — Create if vault has research/decisions/architecture:
   - Left-to-right flow: Research → Hub → Decisions → Output
   - Label nodes for each column section
   - Edges from research to hub to decisions to PRDs
   - Color coding: 2=research (orange), 5=hub (purple), 4=decisions (green), 6=competitors (cyan)

### Canvas Layout Rules
- **Spacing**: 350px between columns, 350px between rows
- **Node sizes**: File nodes 300-400w × 250-400h, text labels 260w × 60h
- **Starting position**: Center of canvas (x=0, y=0) for the most important node
- **Color presets**: 1=red, 2=orange, 3=yellow, 4=green, 5=purple, 6=cyan
- **Edge sides**: Use `fromSide`/`toSide` with values: "top", "bottom", "left", "right"
- **IDs**: Use descriptive kebab-case (e.g., "risk1", "label-research", "e-risk1-hub")

---

## Phase 6: Templates

### Template Detection

```
1. Identify note categories from folders and tags:
   - Each folder with 3+ notes likely needs a template
   - Each tag used by 3+ notes that share a common frontmatter pattern needs a template
2. For each category, extract the common frontmatter pattern:
   - Which properties appear in most notes? (status, priority, date, tags, summary, related)
   - What are the valid values? (status: current|in-progress|completed|archived)
   - What body sections repeat?
```

### Create `_templates/` directory

For each detected category, create `{category}-template.md`:

```markdown
---
aliases: [""]
tags: [{category}]
status: {default-status}
priority: P1
date: {{date}}
related:
  - "[[]]"
summary: ""
---

# {{title}}

## {Section 1 from common pattern}

{Guidance comment or placeholder}

## {Section 2 from common pattern}

{Guidance comment or placeholder}

<!--
NOTES:
- {Usage guidance specific to this template}
- {Valid status transitions}
- {Tag conventions}
-->
```

### Template Rules
- Use `{{date}}` and `{{title}}` Obsidian template placeholders (these get replaced on insertion)
- Include all common frontmatter properties with sensible defaults
- Include HTML comments (`<!-- -->`) with usage guidance — invisible in reading mode
- Always include `related: ["[[]]"]` for wiki-link connections
- Always include `summary: ""` — dashboards depend on it
- Default `status` should be the most common starting state for that category
- Match the body section structure from the best examples in that category

### Always-Create Templates
Even if the vault has no clear categories, always create:

1. **General note template** — minimal frontmatter + empty body
2. **Weekly review template** — Dataview queries for last 7 days + reflection sections

---

## Phase 7: Graph Config & Bookmarks

### Graph Color Groups

Analyze the vault's folder structure and create color groups in `graph.json`:

```json
{
  "colorGroups": [
    {"query": "path:folder1", "color": {"a": 1, "r": 100, "g": 200, "b": 255}},
    {"query": "path:folder2", "color": {"a": 1, "r": 255, "g": 150, "b": 100}},
    {"query": "file:MOC", "color": {"a": 1, "r": 200, "g": 100, "b": 255}},
    {"query": "path:_dashboards", "color": {"a": 1, "r": 100, "g": 255, "b": 150}}
  ]
}
```

### Color Assignment Strategy
1. Each major folder gets a unique color
2. MOC files get a distinctive color (purple recommended)
3. Dashboard files get a distinctive color (green recommended)
4. Template files get a muted color (gray)
5. Maximum 8-10 color groups (more becomes visual noise)

### Graph Settings (merge with existing)
```json
{
  "showTags": false,
  "showAttachments": false,
  "showOrphans": true,
  "showArrow": false,
  "textFadeMultiplier": 0,
  "nodeSizeMultiplier": 1,
  "lineSizeMultiplier": 1,
  "centerStrength": 0.5,
  "repelStrength": 10,
  "linkStrength": 1,
  "linkDistance": 250
}
```

### Bookmarks

Create `bookmarks.json` with the vault's most important navigation points:

```json
{
  "items": [
    {"type": "file", "ctime": {timestamp}, "path": "path/to/index.md", "title": "Vault Index"},
    {"type": "file", "ctime": {timestamp+1}, "path": "_dashboards/project-overview.md", "title": "Project Overview"},
    {"type": "file", "ctime": {timestamp+2}, "path": "_dashboards/vault-health.md", "title": "Vault Health"}
  ]
}
```

### Bookmark Selection Strategy
1. Vault index/readme (if exists) — always first
2. Project overview dashboard — always second
3. Most important hub note (highest connectivity)
4. Active project or PRD (if exists)
5. Vault health dashboard — always last
6. Maximum 5-7 bookmarks (more defeats the purpose)

---

## Execution Rules

1. **Read before write** — Always read existing files before creating. Never overwrite user content.
2. **Scan the vault first** — Phase 3-7 all depend on understanding what's in the vault. Always do a full scan of folders, files, frontmatter patterns, and tags before generating anything.
3. **Adapt, don't template** — Dashboard queries must reference REAL folders and properties from THIS vault. Never use generic placeholder queries that won't work.
4. **Non-destructive merging** — If `.obsidian/` exists, merge settings. If a dashboard exists, skip it. If a template exists, skip it. Only add what's missing.
5. **Validate links** — Every `[[wikilink]]` in an MOC or template must point to a real file in the vault. Never create broken links.
6. **Frontmatter consistency** — If the vault already has a frontmatter convention, match it exactly. Don't introduce new properties the vault doesn't use.
7. **Report what was created** — After each phase, list exactly which files were created, skipped (already existed), or merged.

## Dry Run Mode

When `--dry-run` is specified:
1. Run all analysis steps (folder scan, frontmatter detection, topic clustering)
2. Print a summary of what WOULD be created:
   - Files to create (with path and purpose)
   - Files to skip (already exist)
   - Config to merge (existing + new settings)
3. Show sample dashboard queries (so user can verify they reference real folders)
4. Do NOT write any files

## Error Handling

| Situation | Action |
|-----------|--------|
| Vault path doesn't exist | Error: "Path not found: {path}" |
| No .md files in vault | Error: "No markdown files found. Is this an Obsidian vault?" |
| .obsidian/ exists with unknown plugins | Preserve everything, only add/merge what's needed |
| Notes have no frontmatter | Use folder-based queries only, suggest adding frontmatter |
| Mixed frontmatter patterns | Use the most common pattern, note the inconsistency |
| Dataview already installed (newer version) | Skip plugin install, note version |
| Dashboard file already exists | Skip it, report "already exists" |

## References

- `references/obsidian-patterns.md` — Dataview DQL syntax, canvas JSON spec, frontmatter conventions, graph config format, workspace JSON template
- `references/dataview-plugin/` — Bundled Dataview v0.5.68 plugin files (manifest, main.js, styles, settings)
