import { useId, useMemo, useState } from 'react';
import { Search, X } from 'lucide-react';

const FILTERS = [
  { key: 'all', label: '全部' },
  { key: 'open', label: '營業中' },
  { key: 'top', label: '4.6★ 以上' },
  { key: 'fav', label: '已收藏', loginOnly: true },
];

function matches(cafe, q) {
  return cafe.name.toLowerCase().includes(q)
    || (cafe.address || '').includes(q)
    || (cafe.tag_list || []).some((t) => t.toLowerCase().includes(q));
}

/** 地圖左上角：找店（名稱、地址、特色標籤）＋篩選 */
export default function MapToolbar({ cafes, filter, onFilter, onPick, user }) {
  const [query, setQuery] = useState('');
  const [focused, setFocused] = useState(false);
  const listId = useId();
  const q = query.trim().toLowerCase();
  const results = useMemo(() => (q ? cafes.filter((c) => matches(c, q)).slice(0, 8) : []), [cafes, q]);
  const showResults = focused && q.length > 0;

  const pick = (cafe) => {
    onPick(cafe.id);
    setQuery('');
    setFocused(false);
  };

  return (
    <div className="map-toolbar">
      <div className="map-search">
        <Search size={18} aria-hidden="true" />
        <label htmlFor={`${listId}-input`} className="sr-only">搜尋咖啡廳</label>
        <input
          id={`${listId}-input`}
          type="search"
          placeholder="找店名、地址或特色，例如：插座"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setFocused(true)}
          // 延後關閉，讓點擊結果的事件先觸發
          onBlur={() => setTimeout(() => setFocused(false), 150)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && results[0]) pick(results[0]);
            if (e.key === 'Escape') setQuery('');
          }}
          role="combobox"
          aria-expanded={showResults}
          aria-controls={listId}
          aria-autocomplete="list"
          autoComplete="off"
        />
        {query && (
          <button type="button" className="map-search-clear" onClick={() => setQuery('')} aria-label="清除搜尋">
            <X size={16} />
          </button>
        )}
        {showResults && (
          <ul id={listId} className="map-search-results" role="listbox">
            {results.length === 0 ? (
              <li className="map-search-empty">找不到符合「{query.trim()}」的店</li>
            ) : results.map((cafe) => (
              <li key={cafe.id} role="option" aria-selected="false">
                <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => pick(cafe)}>
                  <span className="map-search-name">{cafe.name}</span>
                  <span className="map-search-sub">{cafe.address}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="map-filters" role="group" aria-label="篩選地圖上的店">
        {FILTERS.filter((f) => !f.loginOnly || user).map((f) => (
          <button
            key={f.key}
            type="button"
            className={`map-filter ${filter === f.key ? 'active' : ''}`}
            aria-pressed={filter === f.key}
            onClick={() => onFilter(f.key)}
          >
            {f.label}
          </button>
        ))}
      </div>
    </div>
  );
}
