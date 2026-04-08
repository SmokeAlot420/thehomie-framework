# Obsidian Patterns Reference

Comprehensive reference for all Obsidian file formats, query syntax, and configuration patterns used by `/vault-build`. Extracted from proven implementations in `C:\Users\YourUser\coding-vault\`.

---

## 1. Frontmatter Convention

### Standard Property Order

```yaml
---
aliases: ["Alias 1", "Alias 2"]
tags: [category, sub-tag]
status: current
priority: P1
date: 2026-03-08
completed: 2026-03-08
superseded_by: "[[new-note]]"
related:
  - "[[note-1]]"
  - "[[note-2]]"
summary: "One-line description for dashboard display."
---
```

### Valid Status Values

| Status | Meaning | Dashboard Color |
|--------|---------|----------------|
| `current` | Active work, primary focus | Blue |
| `in-progress` | Started but not complete | Yellow |
| `planned` | Queued, not started | Gray |
| `completed` | Done, all criteria met | Green |
| `archived` | Superseded or obsolete | Red |
| `researched` | Research gathered, not yet actioned | Orange |
| `decided` | Decision made, pending implementation | Purple |

### Priority Values

| Priority | Meaning |
|----------|---------|
| `P0` | Critical — blocking other work |
| `P1` | High — do this sprint |
| `P2` | Medium — do next sprint |
| `P3` | Low — backlog |

### Tag Conventions
- **Category tags**: `prd`, `research`, `decision`, `architecture`, `competitor`, `review`, `moc`, `dashboard`
- **Sub-tags**: Use flat (not nested). e.g., `[research, risk]` not `[research/risk]`
- **Special tags**: `hub` (aggregation docs), `rca` (root cause analysis)

---

## 2. Dataview DQL Reference

### TABLE Query

```dataview
TABLE
  status AS "Status",
  priority AS "Priority",
  date AS "Created",
  summary AS "Summary"
FROM "folder-name"
WHERE status = "current" OR status = "in-progress"
SORT priority ASC
```

### TABLE WITHOUT ID

Removes the automatic file link column — useful for aggregation queries:

```dataview
TABLE WITHOUT ID
  key AS "Status",
  length(rows) AS "Count"
FROM "folder-name"
GROUP BY status
SORT key ASC
```

### LIST Query

```dataview
LIST summary
FROM "folder-name"
WHERE contains(tags, "hub")
```

### GROUP BY

```dataview
TABLE summary AS "Summary"
FROM "folder-name"
GROUP BY priority
SORT key ASC
```

### Filtering Patterns

```
WHERE status = "current"                              -- exact match
WHERE status = "current" OR status = "in-progress"    -- OR
WHERE contains(tags, "research")                      -- array contains
WHERE !summary                                        -- missing property
WHERE date >= date(today) - dur(30 days)              -- date math
WHERE file.folder != "_dashboards"                    -- exclude folder
WHERE length(file.inlinks) = 0                        -- orphan detection
```

### Sorting Patterns

```
SORT priority ASC                                     -- alphabetical
SORT date DESC                                        -- newest first
SORT length(file.inlinks) + length(file.outlinks) DESC  -- most connected
SORT file.mtime DESC                                  -- recently modified
LIMIT 10                                              -- top N results
```

### Custom Sort with choice()

For custom status ordering (not alphabetical):

```dataview
SORT choice(status = "current", "1",
  choice(status = "in-progress", "2",
  choice(status = "planned", "3",
  choice(status = "completed", "4", "5")))) ASC
```

### Inline Dataview (Quick Stats)

```markdown
- **Total notes**: `$= dv.pages("").length`
- **PRDs**: `$= dv.pages('"prds"').length`
- **Completed**: `$= dv.pages('"prds"').where(p => p.status == "completed").length`
```

Note: Folder paths in inline JS use double-nested quotes: `'"folder"'`

### FROM Patterns

```
FROM ""                    -- all notes in vault
FROM "folder"              -- specific folder
FROM "folder1" OR "folder2"  -- multiple folders
FROM #tag                  -- notes with tag
FROM #tag1 OR #tag2        -- notes with either tag
FROM "folder" AND #tag     -- folder + tag intersection
```

### Excluding Utility Folders

Always exclude infrastructure folders from vault-wide queries:

```
FROM ""
WHERE file.folder != "_dashboards"
  AND file.folder != "_templates"
  AND file.folder != "_canvas"
```

---

## 3. Canvas JSON Specification

### File Format

Canvas files are JSON with `.canvas` extension, stored in `_canvas/` directory.

```json
{
  "nodes": [],
  "edges": []
}
```

### Node Types

**File node** — references an existing vault note:
```json
{
  "id": "unique-kebab-id",
  "type": "file",
  "file": "relative/path/to/note.md",
  "x": 0,
  "y": 0,
  "width": 350,
  "height": 300,
  "color": "2"
}
```

**Text node** — standalone text (labels, headers):
```json
{
  "id": "label-name",
  "type": "text",
  "text": "# Section Header",
  "x": 0,
  "y": -100,
  "width": 260,
  "height": 60
}
```

### Edge Format

```json
{
  "id": "e-from-to",
  "fromNode": "source-node-id",
  "toNode": "target-node-id",
  "fromSide": "right",
  "toSide": "left",
  "label": "relationship description"
}
```

Side values: `"top"`, `"bottom"`, `"left"`, `"right"`

### Color Presets

| Preset | Color | Recommended Use |
|--------|-------|----------------|
| `"1"` | Red | Archived, deprecated |
| `"2"` | Orange | Research, investigation |
| `"3"` | Yellow | Planned, in-progress |
| `"4"` | Green | Completed, decided |
| `"5"` | Purple | Hub, active/important |
| `"6"` | Cyan | External, competitors |

No color = default gray.

### Layout Guidelines

```
Column spacing:  500-700px horizontal between groups
Row spacing:     300-350px vertical between nodes in same column
Node widths:     300-400px for file nodes, 260px for label nodes
Node heights:    250-400px for file nodes, 60px for label nodes
Start position:  Most important node near (0, 0)
Flow direction:  Left-to-right for process flows, top-to-bottom for hierarchies
```

### Canvas Design Patterns

**Status Board** (Kanban-style):
```
[Completed]     [Active]        [Planned]
  node            node            node
  node            node            node
  node
```

**Knowledge Map** (Flow):
```
[Research] → [Hub] → [Decisions] → [Output]
  node         node      node         node
  node                   node
  node
```

**Hierarchy** (Tree):
```
              [Root]
            /        \
     [Branch1]    [Branch2]
      /    \         /   \
   [Leaf] [Leaf]  [Leaf] [Leaf]
```

---

## 4. Graph Configuration

### graph.json Format

```json
{
  "collapse-filter": true,
  "search": "",
  "showTags": false,
  "showAttachments": false,
  "hideUnresolved": false,
  "showOrphans": true,
  "collapse-color-groups": true,
  "colorGroups": [
    {
      "query": "path:folder-name",
      "color": {"a": 1, "r": 100, "g": 200, "b": 255}
    },
    {
      "query": "file:MOC",
      "color": {"a": 1, "r": 200, "g": 100, "b": 255}
    }
  ],
  "collapse-display": true,
  "showArrow": false,
  "textFadeMultiplier": 0,
  "nodeSizeMultiplier": 1,
  "lineSizeMultiplier": 1,
  "collapse-forces": true,
  "centerStrength": 0.518713248970312,
  "repelStrength": 10,
  "linkStrength": 1,
  "linkDistance": 250,
  "scale": 0.7,
  "close": false
}
```

### Color Group Queries

```
"path:folder-name"      -- all notes in a folder
"file:MOC"              -- files with "MOC" in the name
"file:CLAUDE"           -- specific named files
"tag:#research"          -- notes with a specific tag
"path:_dashboards"       -- infrastructure folders
```

### RGBA Color Values

```json
{"a": 1, "r": 255, "g": 100, "b": 100}   // Red
{"a": 1, "r": 255, "g": 180, "b": 100}   // Orange
{"a": 1, "r": 255, "g": 255, "b": 100}   // Yellow
{"a": 1, "r": 100, "g": 255, "b": 150}   // Green
{"a": 1, "r": 200, "g": 100, "b": 255}   // Purple
{"a": 1, "r": 100, "g": 200, "b": 255}   // Blue/Cyan
{"a": 1, "r": 200, "g": 200, "b": 200}   // Gray (muted)
{"a": 1, "r": 255, "g": 150, "b": 200}   // Pink
```

### Recommended Color Assignments

| Content Type | Color | RGBA |
|-------------|-------|------|
| Research notes | Orange | `r:255, g:180, b:100` |
| PRDs / Projects | Purple | `r:200, g:100, b:255` |
| Decisions | Green | `r:100, g:255, b:150` |
| Architecture | Blue | `r:100, g:200, b:255` |
| Competitors | Cyan | `r:100, g:230, b:230` |
| MOC files | Pink | `r:255, g:150, b:200` |
| Dashboards | Green (muted) | `r:150, g:220, b:170` |
| Templates | Gray | `r:200, g:200, b:200` |

---

## 5. Bookmarks Configuration

### bookmarks.json Format

```json
{
  "items": [
    {
      "type": "file",
      "ctime": 1741398000000,
      "path": "CLAUDE.md",
      "title": "Vault Index"
    },
    {
      "type": "file",
      "ctime": 1741398001000,
      "path": "_dashboards/project-overview.md",
      "title": "Project Overview"
    }
  ]
}
```

### Fields
- `type`: Always `"file"` for note bookmarks
- `ctime`: Unix timestamp in milliseconds (use sequential values for ordering)
- `path`: Relative path from vault root
- `title`: Display name in bookmark sidebar (can differ from filename)

### Bookmark Groups (Folders)

```json
{
  "items": [
    {
      "type": "group",
      "ctime": 1741398000000,
      "title": "Navigation",
      "items": [
        {"type": "file", "ctime": 1741398001000, "path": "CLAUDE.md", "title": "Index"},
        {"type": "file", "ctime": 1741398002000, "path": "_dashboards/project-overview.md", "title": "Dashboard"}
      ]
    }
  ]
}
```

---

## 6. Template Placeholders

### Obsidian Built-in Variables

| Placeholder | Replaced With |
|-------------|---------------|
| `{{date}}` | Current date (format from settings) |
| `{{time}}` | Current time |
| `{{title}}` | New note's filename |
| `{{date:format}}` | Custom date format (e.g., `{{date:YYYY-MM-DD}}`) |

### Template Body Patterns

```markdown
---
{frontmatter matching the category's convention}
---

# {{title}}

## {First Section}

{Placeholder or guidance text}

## {Second Section}

{Placeholder or guidance text}

<!--
NOTES:
- Usage guidance invisible in reading mode
- Valid state transitions for this note type
- Tag recommendations
-->
```

---

## 7. Workspace JSON Template

### Full 3-Pane Layout

```json
{
  "main": {
    "id": "main-split",
    "type": "split",
    "children": [
      {
        "id": "main-tabs",
        "type": "tabs",
        "children": [
          {
            "id": "empty-leaf",
            "type": "leaf",
            "state": {
              "type": "empty",
              "state": {}
            }
          }
        ]
      }
    ],
    "direction": "vertical"
  },
  "left": {
    "id": "left-split",
    "type": "split",
    "children": [
      {
        "id": "left-tabs",
        "type": "tabs",
        "children": [
          {
            "id": "file-explorer-leaf",
            "type": "leaf",
            "state": {
              "type": "file-explorer",
              "state": {"sortOrder": "alphabetical"},
              "icon": "lucide-folder-closed",
              "title": "Files"
            }
          },
          {
            "id": "search-leaf",
            "type": "leaf",
            "state": {
              "type": "search",
              "state": {"query": "", "matchingCase": false},
              "icon": "lucide-search",
              "title": "Search"
            }
          },
          {
            "id": "bookmarks-leaf",
            "type": "leaf",
            "state": {
              "type": "bookmarks",
              "state": {},
              "icon": "lucide-bookmark",
              "title": "Bookmarks"
            }
          }
        ]
      }
    ],
    "direction": "horizontal",
    "width": 300
  },
  "right": {
    "id": "right-split",
    "type": "split",
    "children": [
      {
        "id": "right-tabs",
        "type": "tabs",
        "children": [
          {
            "id": "backlink-leaf",
            "type": "leaf",
            "state": {
              "type": "backlink",
              "state": {"collapseAll": false, "extraContext": false},
              "icon": "links-coming-in",
              "title": "Backlinks"
            }
          },
          {
            "id": "outgoing-leaf",
            "type": "leaf",
            "state": {
              "type": "outgoing-link",
              "state": {"linksCollapsed": false},
              "icon": "links-going-out",
              "title": "Outgoing links"
            }
          },
          {
            "id": "tag-leaf",
            "type": "leaf",
            "state": {
              "type": "tag",
              "state": {"sortOrder": "frequency", "useHierarchy": true},
              "icon": "lucide-tags",
              "title": "Tags"
            }
          },
          {
            "id": "outline-leaf",
            "type": "leaf",
            "state": {
              "type": "outline",
              "state": {},
              "icon": "lucide-list",
              "title": "Outline"
            }
          }
        ]
      }
    ],
    "direction": "horizontal",
    "width": 300,
    "collapsed": true
  },
  "left-ribbon": {
    "hiddenItems": {
      "switcher:Open quick switcher": false,
      "graph:Open graph view": false,
      "canvas:Create new canvas": false,
      "templates:Insert template": false,
      "command-palette:Open command palette": false
    }
  },
  "active": "empty-leaf",
  "lastOpenFiles": []
}
```

---

## 8. MOC (Map of Content) Pattern

### Structure

```markdown
---
aliases: ["Search Term 1", "Search Term 2"]
tags: [moc]
status: current
priority: P2
date: {today}
related:
  - "[[primary-hub-note]]"
summary: "Navigation hub for {topic} notes."
---

# {Topic Title}

{1-2 sentence overview of what this topic covers in the vault.}

## {Curated Section 1}

- [[note-a]] — {context from summary or key point}
- [[note-b]] — {context}

## {Curated Section 2}

- [[note-c]] — {context}
- [[note-d]] — {context}

## Related Dashboards

- [[project-overview]] — Active work and stats
- [[{relevant}-tracker]] — Status table

## Auto-Discovery

*Notes tagged with {tag} — catches new additions automatically.*

\```dataview
TABLE status, priority, summary
FROM #{topic-tag}
SORT priority ASC
\```
```

### Key Principles
1. **Curated links > automated queries** — The human-selected links with context are the primary value
2. **Auto-discovery supplements** — The Dataview query at the bottom catches notes added after the MOC was written
3. **Aliases for findability** — Include common search terms so Quick Switcher finds this MOC
4. **Cross-references** — Link to dashboards and other MOCs

---

## 9. Dashboard Patterns (5 Proven Types)

### Type 1: Project Overview (vault-wide)
- Active work table (status = current/in-progress)
- Recent activity (date-based)
- Note counts by folder (GROUP BY file.folder)
- Quick stats (inline JS)
- High-priority items (P0, not completed)

### Type 2: Folder Tracker (per-folder)
- Full table with all properties
- Filtered views by status or tag
- Grouped views by priority

### Type 3: Vault Health (diagnostics)
- Missing properties (summary, status, priority, tags)
- Orphan notes (no incoming links)
- Most connected notes (hub detection)
- Notes by status (distribution check)

### Type 4: Decision Log (chronological)
- All decisions sorted by date DESC
- Active vs completed split
- Links to related research

### Type 5: Weekly Review (periodic)
- Modified this week (file.mtime based)
- Status snapshot of active projects
- Decisions made this week
- Free-form reflection sections

---

## 10. Validation Rules

What makes a well-formed vault (based on coding-vault validator):

1. **Every note** (except dashboards/templates) should have:
   - `tags` (at minimum the category tag)
   - `summary` (for dashboard display)
   - `status` (for filtering/grouping)

2. **Every wikilink** `[[target]]` should resolve to an existing file

3. **Folders to exclude** from validation: `_dashboards`, `_templates`, `_canvas`, `.obsidian`

4. **Frontmatter must be valid YAML** — no tabs, proper quoting, array format for lists

5. **No duplicate aliases** across notes (causes ambiguous Quick Switcher results)

6. **Canvas file references** must point to existing notes (broken canvas links show as "File not found")
