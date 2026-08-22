import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DiscoveredFile } from "../api/client";

/* ==========================================================================
   Model
   ========================================================================== */

export interface FolderNode {
  /** Unique across the whole forest — used as the expand/collapse key. */
  key: string;
  name: string;
  /** Absolute device path, shown dimmed next to root nodes. */
  path?: string;
  /** Extra tag rendered on the row (e.g. "excluded by default"). */
  badge?: string;
  folders: FolderNode[];
  files: DiscoveredFile[];
}

/** Row height in px. Must match --row-h in app.css: the virtualizer maps
 * scroll offset to row index arithmetically, so the two cannot drift. */
export const ROW_H = 26;

/** Rebuilds the on-device subfolder structure under a root directory from
 * each file's absolute path, so nested folders (e.g. Media/Images/Sent)
 * become real tree nodes instead of one flat list. */
export function buildFolderTree(
  rootKey: string,
  rootName: string,
  remoteDir: string,
  files: DiscoveredFile[],
  badge?: string
): FolderNode {
  const root: FolderNode = { key: rootKey, name: rootName, path: remoteDir, badge, folders: [], files: [] };
  const byKey = new Map<string, FolderNode>([[rootKey, root]]);
  const normRoot = remoteDir.replace(/\/+$/, "");

  for (const f of files) {
    let rel = f.path;
    if (rel.startsWith(normRoot + "/")) rel = rel.slice(normRoot.length + 1);
    else if (rel.startsWith(normRoot)) rel = rel.slice(normRoot.length).replace(/^\/+/, "");

    const parts = rel.split("/").filter(Boolean);
    parts.pop(); // the filename itself; the file is attached to its folder below

    let cur = root;
    let curKey = rootKey;
    for (const part of parts) {
      curKey = `${curKey}/${part}`;
      let next = byKey.get(curKey);
      if (!next) {
        next = { key: curKey, name: part, folders: [], files: [] };
        byKey.set(curKey, next);
        cur.folders.push(next);
      }
      cur = next;
    }
    cur.files.push(f);
  }

  const sortRec = (n: FolderNode) => {
    n.folders.sort((a, b) => a.name.localeCompare(b.name));
    n.files.sort((a, b) => a.filename.localeCompare(b.filename));
    n.folders.forEach(sortRec);
  };
  sortRec(root);
  return root;
}

export function collectFiles(node: FolderNode, out: DiscoveredFile[] = []): DiscoveredFile[] {
  out.push(...node.files);
  for (const f of node.folders) collectFiles(f, out);
  return out;
}

/** Pruned copy keeping only branches with a matching filename; null if none. */
export function filterTree(node: FolderNode, needle: string): FolderNode | null {
  const files = node.files.filter((f) => f.filename.toLowerCase().includes(needle));
  const folders = node.folders
    .map((f) => filterTree(f, needle))
    .filter((f): f is FolderNode => f !== null);
  if (!files.length && !folders.length) return null;
  return { ...node, files, folders };
}

export function allFolderKeys(roots: FolderNode[]): string[] {
  const keys: string[] = [];
  const walk = (n: FolderNode) => {
    keys.push(n.key);
    n.folders.forEach(walk);
  };
  roots.forEach(walk);
  return keys;
}

export type FileStateMap = Record<string, string>;

export interface FolderStat { included: number; total: number; includedSize: number; }

/** Bottom-up single pass: every folder's rolled-up selection counts. */
export function computeFolderStats(roots: FolderNode[], states: FileStateMap): Map<string, FolderStat> {
  const map = new Map<string, FolderStat>();
  const visit = (n: FolderNode): FolderStat => {
    let included = 0, total = 0, includedSize = 0;
    for (const f of n.files) {
      if (f.default_state === "INACCESSIBLE") continue;
      total++;
      if (states[f.path] === "INCLUDE") { included++; includedSize += f.size; }
    }
    for (const sub of n.folders) {
      const s = visit(sub);
      included += s.included; total += s.total; includedSize += s.includedSize;
    }
    const stat = { included, total, includedSize };
    map.set(n.key, stat);
    return stat;
  };
  roots.forEach(visit);
  return map;
}

/* ==========================================================================
   Flattening — the tree is rendered as a flat list so it can be virtualized
   and navigated with the arrow keys.
   ========================================================================== */

interface FlatRow {
  kind: "folder" | "file";
  key: string;
  /** One entry per ancestor level; true when that ancestor has siblings
   * below it, i.e. the vertical connector continues past this row. The
   * last entry describes this row itself and drives its elbow. */
  lineage: boolean[];
  node?: FolderNode;
  file?: DiscoveredFile;
}

function flatten(
  roots: FolderNode[],
  isExpanded: (key: string) => boolean
): FlatRow[] {
  const rows: FlatRow[] = [];
  const walk = (node: FolderNode, lineage: boolean[]) => {
    rows.push({ kind: "folder", key: node.key, lineage, node });
    if (!isExpanded(node.key)) return;
    const childCount = node.folders.length + node.files.length;
    node.folders.forEach((sub, i) => walk(sub, [...lineage, i < childCount - 1]));
    node.files.forEach((file, i) => {
      rows.push({
        kind: "file",
        key: file.path,
        lineage: [...lineage, node.folders.length + i < childCount - 1],
        file,
      });
    });
  };
  // Roots carry an empty lineage: no connector lines at the outermost level.
  roots.forEach((r) => walk(r, []));
  return rows;
}

/* ==========================================================================
   Icons — small, flat, generic; deliberately uniform across file types,
   matching a classic Explorer/installer tree.
   ========================================================================== */

function FolderIcon({ open }: { open: boolean }) {
  return open ? (
    <svg width="14" height="12" viewBox="0 0 15 13" className="tree-icon" aria-hidden="true">
      <path d="M1 1.6C1 .9 1.55.3 2.3.3H5.6l1.2 1.4h5.4c.72 0 1.3.58 1.3 1.3v.7H2.4L1 12.2V1.6z" fill="#dfa22f" />
      <path d="M2.1 4.1H14l-1.5 7c-.1.46-.5.8-.98.8H2.9c-.47 0-.87-.32-.97-.78L.5 5.3c-.2-.7.32-1.2 1-1.2z" fill="#f6ca62" />
    </svg>
  ) : (
    <svg width="14" height="12" viewBox="0 0 15 13" className="tree-icon" aria-hidden="true">
      <path d="M1 1.8c0-.7.55-1.3 1.25-1.3H5.9L7.1 2h5.6c.72 0 1.3.58 1.3 1.3v7.4c0 .72-.58 1.3-1.3 1.3H2.3c-.72 0-1.3-.58-1.3-1.3V1.8z" fill="#f6ca62" />
      <path d="M1 3.6h13v-.3c0-.72-.58-1.3-1.3-1.3H7.1L5.9.5H2.25C1.55.5 1 1.1 1 1.8v1.8z" fill="#e3b04b" />
    </svg>
  );
}

function FileIcon() {
  return (
    <svg width="11" height="12" viewBox="0 0 11 13" className="tree-icon" aria-hidden="true">
      <path d="M1 .5h5l3.5 3.5V12a.5.5 0 0 1-.5.5h-8A.5.5 0 0 1 .5 12V1a.5.5 0 0 1 .5-.5z" fill="#fff" stroke="#8a8f95" />
      <path d="M6 .5v3a.5.5 0 0 0 .5.5H9.5" fill="none" stroke="#8a8f95" />
    </svg>
  );
}

/* ==========================================================================
   Component
   ========================================================================== */

export function FileTree({
  roots,
  states,
  onSetFiles,
  expanded,
  onToggleExpand,
  fmtSize,
  height,
  emptyLabel = "No items.",
}: {
  roots: FolderNode[];
  states: FileStateMap;
  onSetFiles: (files: DiscoveredFile[], value: string) => void;
  expanded: Record<string, boolean>;
  onToggleExpand: (key: string) => void;
  fmtSize: (n: number) => string;
  height?: number;
  emptyLabel?: string;
}) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportH, setViewportH] = useState(height ?? 420);
  const [cursor, setCursor] = useState(0);

  const isExpanded = useCallback((key: string) => !!expanded[key], [expanded]);
  const rows = useMemo(() => flatten(roots, isExpanded), [roots, isExpanded]);
  const stats = useMemo(() => computeFolderStats(roots, states), [roots, states]);

  // Keep the cursor in range as rows appear/disappear (filtering, collapsing).
  useEffect(() => {
    if (cursor > rows.length - 1) setCursor(Math.max(0, rows.length - 1));
  }, [rows.length, cursor]);

  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    const measure = () => setViewportH(el.clientHeight);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const scrollRowIntoView = useCallback((index: number) => {
    const el = viewportRef.current;
    if (!el) return;
    const top = index * ROW_H;
    if (top < el.scrollTop) el.scrollTop = top;
    else if (top + ROW_H > el.scrollTop + el.clientHeight) el.scrollTop = top + ROW_H - el.clientHeight;
  }, []);

  const moveCursor = useCallback((next: number) => {
    const clamped = Math.max(0, Math.min(rows.length - 1, next));
    setCursor(clamped);
    scrollRowIntoView(clamped);
  }, [rows.length, scrollRowIntoView]);

  const toggleRow = useCallback((row: FlatRow) => {
    if (row.kind === "folder" && row.node) {
      const stat = stats.get(row.node.key);
      const allOn = !!stat && stat.total > 0 && stat.included === stat.total;
      onSetFiles(collectFiles(row.node), allOn ? "EXCLUDE" : "INCLUDE");
    } else if (row.file && row.file.default_state !== "INACCESSIBLE") {
      onSetFiles([row.file], states[row.file.path] === "INCLUDE" ? "EXCLUDE" : "INCLUDE");
    }
  }, [onSetFiles, states, stats]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    const row = rows[cursor];
    if (!row) return;
    switch (e.key) {
      case "ArrowDown": e.preventDefault(); moveCursor(cursor + 1); break;
      case "ArrowUp": e.preventDefault(); moveCursor(cursor - 1); break;
      case "Home": e.preventDefault(); moveCursor(0); break;
      case "End": e.preventDefault(); moveCursor(rows.length - 1); break;
      case "PageDown": e.preventDefault(); moveCursor(cursor + Math.floor(viewportH / ROW_H)); break;
      case "PageUp": e.preventDefault(); moveCursor(cursor - Math.floor(viewportH / ROW_H)); break;
      case "ArrowRight":
        e.preventDefault();
        if (row.kind === "folder" && row.node) {
          if (!isExpanded(row.node.key)) onToggleExpand(row.node.key);
          else moveCursor(cursor + 1);
        }
        break;
      case "ArrowLeft":
        e.preventDefault();
        if (row.kind === "folder" && row.node && isExpanded(row.node.key)) {
          onToggleExpand(row.node.key);
        } else {
          // jump to the parent row (the nearest row that is one level shallower)
          const target = row.lineage.length - 1;
          for (let i = cursor - 1; i >= 0; i--) {
            if (rows[i].lineage.length === target) { moveCursor(i); break; }
          }
        }
        break;
      case " ": e.preventDefault(); toggleRow(row); break;
      case "Enter":
        e.preventDefault();
        if (row.kind === "folder" && row.node) onToggleExpand(row.node.key);
        else toggleRow(row);
        break;
    }
  };

  // Virtualization: only rows near the viewport are in the DOM, so a
  // 9,000-file discovery stays responsive.
  const OVERSCAN = 8;
  const first = Math.max(0, Math.floor(scrollTop / ROW_H) - OVERSCAN);
  const visibleCount = Math.ceil(viewportH / ROW_H) + OVERSCAN * 2;
  const last = Math.min(rows.length, first + visibleCount);
  const slice = rows.slice(first, last);

  return (
    <div
      className="tree-viewport"
      ref={viewportRef}
      style={height ? { height } : undefined}
      tabIndex={0}
      role="tree"
      aria-label="Discovered files"
      onScroll={(e) => setScrollTop((e.target as HTMLDivElement).scrollTop)}
      onKeyDown={onKeyDown}
    >
      {rows.length === 0 ? (
        <div className="placeholder inline">{emptyLabel}</div>
      ) : (
        <div style={{ height: rows.length * ROW_H, position: "relative" }}>
          <div style={{ position: "absolute", top: first * ROW_H, left: 0, right: 0 }}>
            {slice.map((row, i) => {
              const index = first + i;
              const depth = row.lineage.length;
              const guides = row.lineage.slice(0, -1);
              const continues = row.lineage[depth - 1];
              const selected = index === cursor;

              const isFolder = row.kind === "folder";
              const node = row.node;
              const file = row.file;
              const stat = isFolder && node ? stats.get(node.key) : undefined;

              const checked = isFolder
                ? !!stat && stat.total > 0 && stat.included === stat.total
                : !!file && states[file.path] === "INCLUDE";
              const indeterminate = isFolder && !!stat && stat.included > 0 && stat.included < stat.total;
              const disabled = isFolder
                ? !stat || stat.total === 0
                : file?.default_state === "INACCESSIBLE";
              const open = isFolder && node ? isExpanded(node.key) : false;

              return (
                <div
                  key={row.key}
                  className={
                    "tree-row" + (selected ? " selected" : "") + (disabled ? " disabled" : "")
                  }
                  role="treeitem"
                  aria-level={depth + 1}
                  aria-selected={selected}
                  aria-expanded={isFolder ? open : undefined}
                  onMouseDown={() => setCursor(index)}
                >
                  {guides.map((line, g) => (
                    <span key={g} className={"tree-guide" + (line ? " line" : "")} />
                  ))}
                  {depth > 0 && <span className={"tree-elbow" + (continues ? " continues" : "")} />}

                  {isFolder && node ? (
                    <button
                      type="button"
                      className={"tree-toggle" + (open ? " open" : "")}
                      tabIndex={-1}
                      aria-label={open ? `Collapse ${node.name}` : `Expand ${node.name}`}
                      onClick={() => onToggleExpand(node.key)}
                    >
                      <span>▶</span>
                    </button>
                  ) : (
                    <span className="tree-spacer" />
                  )}

                  <input
                    type="checkbox"
                    className="tree-check"
                    checked={checked}
                    disabled={disabled}
                    tabIndex={-1}
                    ref={(el) => { if (el) el.indeterminate = indeterminate; }}
                    aria-label={isFolder ? node?.name : file?.filename}
                    onChange={() => toggleRow(row)}
                  />

                  {isFolder ? <FolderIcon open={open} /> : <FileIcon />}

                  <span
                    className={"tree-label" + (isFolder && depth === 0 ? " tree-root-label" : "")}
                    onClick={() => {
                      setCursor(index);
                      if (isFolder && node) onToggleExpand(node.key);
                    }}
                  >
                    {isFolder ? node?.name : file?.filename}
                  </span>

                  {isFolder && depth === 0 && node?.path && (
                    <span className="tree-path">{node.path}</span>
                  )}
                  {isFolder && node?.badge && <span className="badge skipped">{node.badge}</span>}
                  {file?.is_trashed && <span className="badge skipped">trashed</span>}
                  {file?.crypt14_kind === "current" && <span className="badge protected">current DB</span>}
                  {file?.crypt14_kind === "historical" && <span className="badge info">historical DB</span>}

                  <span className="tree-meta">
                    {isFolder && stat
                      ? `${stat.included}/${stat.total} · ${fmtSize(stat.includedSize)}`
                      : file
                      ? fmtSize(file.size)
                      : ""}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
