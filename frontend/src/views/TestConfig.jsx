import React, { useState, useEffect } from 'react';
import useStore from '../store/useStore.js';

const API = '/api/v1/ref';

// ── tiny inline helpers ───────────────────────────────────────────────────────

function Badge({ children, color = 'gray' }) {
  return <span className={`badge badge-${color}`}>{children}</span>;
}

function IconBtn({ onClick, title, danger, children }) {
  return (
    <button
      className={`btn btn-sm ${danger ? 'btn-ghost' : 'btn-ghost'}`}
      style={danger ? { color: '#ef4444' } : {}}
      onClick={onClick}
      title={title}
    >
      {children}
    </button>
  );
}

function Input({ value, onChange, placeholder, style }) {
  return (
    <input
      className="form-input"
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      style={style}
    />
  );
}

// ── Category row ──────────────────────────────────────────────────────────────

function CategoryRow({ cat, onSaved, onDeleted }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(cat.name);
  const [critical, setCritical] = useState(cat.is_critical);
  const [saving, setSaving] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const save = async () => {
    setSaving(true);
    await fetch(`${API}/categories/${cat.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, is_critical: critical }),
    });
    setSaving(false);
    setEditing(false);
    onSaved();
  };

  const del = async () => {
    if (!confirm(`Delete category "${cat.name}" and all its test cases?`)) return;
    await fetch(`${API}/categories/${cat.id}`, { method: 'DELETE' });
    onDeleted();
  };

  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <div className="card-header" style={{ cursor: 'pointer' }} onClick={() => !editing && setExpanded(v => !v)}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1 }}>
          <span style={{ fontSize: 13, color: 'var(--text3)', userSelect: 'none' }}>
            {expanded ? '▾' : '▸'}
          </span>
          {editing ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1 }} onClick={e => e.stopPropagation()}>
              <Input value={name} onChange={setName} placeholder="Category name" style={{ flex: 1 }} />
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer', whiteSpace: 'nowrap' }}>
                <input type="checkbox" checked={critical} onChange={e => setCritical(e.target.checked)} />
                Critical
              </label>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
              <span className="card-title" style={{ margin: 0 }}>{cat.name}</span>
              {cat.is_critical && <Badge color="red">CRITICAL</Badge>}
              <Badge color="gray">{cat.test_cases?.length ?? 0} tests</Badge>
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: 4 }} onClick={e => e.stopPropagation()}>
          {editing ? (
            <>
              <button className="btn btn-sm btn-primary" onClick={save} disabled={saving}>
                {saving ? 'Saving…' : 'Save'}
              </button>
              <button className="btn btn-sm btn-ghost" onClick={() => { setEditing(false); setName(cat.name); setCritical(cat.is_critical); }}>
                Cancel
              </button>
            </>
          ) : (
            <>
              <IconBtn onClick={() => { setEditing(true); setExpanded(true); }} title="Edit category">✎</IconBtn>
              <IconBtn onClick={del} title="Delete category" danger>✕</IconBtn>
            </>
          )}
        </div>
      </div>

      {expanded && (
        <div className="card-body" style={{ paddingTop: 0 }}>
          <TestCaseList categoryId={cat.id} testCases={cat.test_cases ?? []} onChanged={onSaved} />
        </div>
      )}
    </div>
  );
}

// ── Test case list inside a category ─────────────────────────────────────────

function TestCaseList({ categoryId, testCases, onChanged }) {
  const [items, setItems] = useState(testCases);
  const [newName, setNewName] = useState('');
  const [adding, setAdding] = useState(false);

  useEffect(() => { setItems(testCases); }, [testCases]);

  const addTestCase = async () => {
    if (!newName.trim()) return;
    setAdding(true);
    const res = await fetch(`${API}/testcases`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newName.trim(), category_id: categoryId, display_order: items.length }),
    });
    const created = await res.json();
    setItems(prev => [...prev, created]);
    setNewName('');
    setAdding(false);
    onChanged();
  };

  const updateTestCase = async (tc, name) => {
    await fetch(`${API}/testcases/${tc.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    setItems(prev => prev.map(t => t.id === tc.id ? { ...t, name } : t));
    onChanged();
  };

  const deleteTestCase = async (tc) => {
    if (!confirm(`Delete test case "${tc.name}"?`)) return;
    await fetch(`${API}/testcases/${tc.id}`, { method: 'DELETE' });
    setItems(prev => prev.filter(t => t.id !== tc.id));
    onChanged();
  };

  return (
    <div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 10 }}>
        {items.map((tc, idx) => (
          <TestCaseRow key={tc.id} tc={tc} index={idx + 1} onUpdate={updateTestCase} onDelete={deleteTestCase} />
        ))}
        {items.length === 0 && (
          <div className="text-muted" style={{ fontSize: 13, padding: '8px 0' }}>No test cases yet.</div>
        )}
      </div>

      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <Input
          value={newName}
          onChange={setNewName}
          placeholder="New test case name…"
          style={{ flex: 1 }}
        />
        <button
          className="btn btn-sm btn-primary"
          onClick={addTestCase}
          disabled={adding || !newName.trim()}
        >
          {adding ? 'Adding…' : '+ Add'}
        </button>
      </div>
    </div>
  );
}

// ── Single test case row ──────────────────────────────────────────────────────

function TestCaseRow({ tc, index, onUpdate, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(tc.name);

  const save = async () => {
    if (!name.trim() || name === tc.name) { setEditing(false); return; }
    await onUpdate(tc, name.trim());
    setEditing(false);
  };

  const cancel = () => { setName(tc.name); setEditing(false); };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 8px', borderRadius: 6, background: 'var(--surface2)' }}>
      <span style={{ fontSize: 11, color: 'var(--text3)', minWidth: 22, textAlign: 'right' }}>{index}.</span>
      {editing ? (
        <>
          <Input value={name} onChange={setName} placeholder="Test case name" style={{ flex: 1, fontSize: 13 }} />
          <button className="btn btn-sm btn-primary" onClick={save}>Save</button>
          <button className="btn btn-sm btn-ghost" onClick={cancel}>Cancel</button>
        </>
      ) : (
        <>
          <span style={{ flex: 1, fontSize: 13 }}>{tc.name}</span>
          <IconBtn onClick={() => setEditing(true)} title="Edit">✎</IconBtn>
          <IconBtn onClick={() => onDelete(tc)} title="Delete" danger>✕</IconBtn>
        </>
      )}
    </div>
  );
}

// ── Add category modal (inline form) ─────────────────────────────────────────

function AddCategoryForm({ onAdded, onCancel, nextOrder }) {
  const [slug, setSlug] = useState('');
  const [name, setName] = useState('');
  const [critical, setCritical] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const slugify = (v) => v.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');

  const handleNameChange = (v) => {
    setName(v);
    setSlug(slugify(v));
  };

  const save = async () => {
    if (!name.trim() || !slug.trim()) { setError('Name and slug are required.'); return; }
    setSaving(true);
    setError('');
    const res = await fetch(`${API}/categories`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug, name: name.trim(), is_critical: critical, display_order: nextOrder }),
    });
    if (!res.ok) {
      const d = await res.json();
      setError(d.detail ?? 'Failed to create category.');
      setSaving(false);
      return;
    }
    setSaving(false);
    onAdded();
  };

  return (
    <div className="card" style={{ marginBottom: 16, border: '2px solid var(--accent)' }}>
      <div className="card-header">
        <div className="card-title">New Category</div>
      </div>
      <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div className="form-group">
            <label className="form-label">Name</label>
            <Input value={name} onChange={handleNameChange} placeholder="e.g. Performance" />
          </div>
          <div className="form-group">
            <label className="form-label">Slug (auto)</label>
            <Input value={slug} onChange={setSlug} placeholder="e.g. performance" />
          </div>
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
          <input type="checkbox" checked={critical} onChange={e => setCritical(e.target.checked)} />
          Mark as Critical
        </label>
        {error && <div style={{ color: '#ef4444', fontSize: 13 }}>{error}</div>}
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-primary btn-sm" onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Create Category'}</button>
          <button className="btn btn-ghost btn-sm" onClick={onCancel}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

// ── Main view ─────────────────────────────────────────────────────────────────

export default function TestConfig() {
  const { loadRefData } = useStore();
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddCat, setShowAddCat] = useState(false);
  const [search, setSearch] = useState('');
  const [filterCritical, setFilterCritical] = useState('all');

  const fetchCategories = async () => {
    setLoading(true);
    const res = await fetch(`${API}/categories`);
    const cats = await res.json();
    // fetch test cases for each category
    const tcRes = await fetch(`${API}/testcases`);
    const allTc = await tcRes.json();
    const enriched = cats.map(cat => ({
      ...cat,
      test_cases: allTc.filter(tc => tc.category_id === cat.id).sort((a, b) => a.display_order - b.display_order),
    }));
    setCategories(enriched);
    setLoading(false);
    // keep store in sync so Execute/Dashboard reflect changes immediately
    loadRefData();
  };

  useEffect(() => { fetchCategories(); }, []);

  const filtered = categories.filter(cat => {
    const matchSearch = cat.name.toLowerCase().includes(search.toLowerCase()) ||
      cat.slug.toLowerCase().includes(search.toLowerCase());
    const matchCritical = filterCritical === 'all' ||
      (filterCritical === 'critical' && cat.is_critical) ||
      (filterCritical === 'non-critical' && !cat.is_critical);
    return matchSearch && matchCritical;
  });

  const totalTests = categories.reduce((s, c) => s + (c.test_cases?.length ?? 0), 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Header KPIs */}
      <div className="kpi-row" style={{ gridTemplateColumns: 'repeat(3,1fr)' }}>
        <div className="kpi-card" style={{ '--kpi-color': 'var(--accent)' }}>
          <div className="kpi-icon">📂</div>
          <div className="kpi-label">Categories</div>
          <div className="kpi-value">{categories.length}</div>
        </div>
        <div className="kpi-card" style={{ '--kpi-color': '#ef4444' }}>
          <div className="kpi-icon">⚠</div>
          <div className="kpi-label">Critical</div>
          <div className="kpi-value">{categories.filter(c => c.is_critical).length}</div>
        </div>
        <div className="kpi-card" style={{ '--kpi-color': '#22c55e' }}>
          <div className="kpi-icon">🧪</div>
          <div className="kpi-label">Total Test Cases</div>
          <div className="kpi-value">{totalTests}</div>
        </div>
      </div>

      {/* Toolbar */}
      <div className="card">
        <div className="card-body" style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            className="form-input"
            style={{ flex: 1, minWidth: 200 }}
            placeholder="Search categories…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <select
            className="form-select"
            style={{ width: 160 }}
            value={filterCritical}
            onChange={e => setFilterCritical(e.target.value)}
          >
            <option value="all">All</option>
            <option value="critical">Critical only</option>
            <option value="non-critical">Non-critical only</option>
          </select>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => setShowAddCat(v => !v)}
          >
            {showAddCat ? 'Cancel' : '+ New Category'}
          </button>
        </div>
      </div>

      {/* Add category form */}
      {showAddCat && (
        <AddCategoryForm
          nextOrder={categories.length}
          onAdded={() => { setShowAddCat(false); fetchCategories(); }}
          onCancel={() => setShowAddCat(false)}
        />
      )}

      {/* Category list */}
      {loading ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, flexDirection: 'column', gap: 12 }}>
          <div className="spinner" />
          <span className="text-muted">Loading from database…</span>
        </div>
      ) : filtered.length === 0 ? (
        <div className="card">
          <div className="card-body">
            <div className="empty-state">
              <div className="empty-state-icon">📂</div>
              <div className="empty-state-title">No categories found</div>
              <div className="empty-state-text">{search ? 'Try a different search term' : 'Click "+ New Category" to add one'}</div>
            </div>
          </div>
        </div>
      ) : (
        filtered.map(cat => (
          <CategoryRow
            key={cat.id}
            cat={cat}
            onSaved={fetchCategories}
            onDeleted={fetchCategories}
          />
        ))
      )}
    </div>
  );
}
