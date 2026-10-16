import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { MAP_STYLE_URL, applyLatteTheme } from './mapTheme';
import './CafeMap.css';

// 花蓮市區；拿不到任何座標時的預設視角
const HUALIEN_CENTER = [121.6045, 23.9785];
const ESPRESSO = '#4e342e';
const MUTED = '#a1887f';
const FONT_BOLD = ['Noto Sans Bold'];

// lucide「coffee」圖示（和站上其他地方同一套），marker 是原生 DOM，不能直接放 React 元件
const COFFEE_ICON = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 2v2"/><path d="M14 2v2"/><path d="M16 8a1 1 0 0 1 1 1v8a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V9a1 1 0 0 1 1-1h14a4 4 0 1 1 0 8h-1"/><path d="M6 2v2"/></svg>';

// 跨次掛載保留：切到測驗頁再回來時，地圖不必重新下載樣式，也停在離開前的位置
let themedStyleCache = null;
let lastCamera = null;

const hasCoords = (c) => Number.isFinite(c?.lat) && Number.isFinite(c?.lng);

function toGeoJSON(cafes) {
  return {
    type: 'FeatureCollection',
    features: cafes.filter(hasCoords).map((c) => ({
      type: 'Feature',
      id: c.id,
      geometry: { type: 'Point', coordinates: [c.lng, c.lat] },
      properties: { id: c.id, name: c.name, open: c.is_open_now === true },
    })),
  };
}

function boundsOf(cafes) {
  const pts = cafes.filter(hasCoords);
  if (pts.length === 0) return null;
  const bounds = new maplibregl.LngLatBounds();
  pts.forEach((c) => bounds.extend([c.lng, c.lat]));
  return bounds;
}

// MapLibre 用 inline transform 定位 marker 的根元素，放大效果要做在裡面那層，兩者才不會互相蓋掉
/**
 * 首次進來的視角：店家主要集中在花蓮市區，少數幾家在新城、壽豐。
 * 全部框進去會縮到整片花蓮、市區擠成一顆聚合圈，所以兩個方向各去掉最外側約 5%。
 */
function coreBoundsOf(cafes) {
  const pts = cafes.filter(hasCoords);
  if (pts.length < 8) return boundsOf(pts);
  const trim = Math.floor(pts.length * 0.05);
  const lats = pts.map((c) => c.lat).sort((a, b) => a - b).slice(trim, pts.length - trim);
  const lngs = pts.map((c) => c.lng).sort((a, b) => a - b).slice(trim, pts.length - trim);
  return new maplibregl.LngLatBounds([lngs[0], lats[0]], [lngs[lngs.length - 1], lats[lats.length - 1]]);
}

function pinElement(rank, cafe, handlersRef) {
  const wrap = document.createElement('div');
  wrap.className = 'map-pin-wrap';
  const btn = document.createElement('button');
  btn.type = 'button';
  // rank 為 null：不是推薦、只是目前開著詳情的那家（從聚合裡拉出來單獨標示）
  btn.className = rank == null ? 'map-pin focus active' : 'map-pin';
  btn.setAttribute('aria-label', rank == null ? `${cafe.name}（店家詳情）` : `AI 推薦第 ${rank} 家：${cafe.name}`);
  btn.innerHTML = `<span class="map-pin-head"><span class="map-pin-num">${rank ?? COFFEE_ICON}</span></span>`;
  btn.addEventListener('click', (e) => { e.stopPropagation(); handlersRef.current.onSelect(cafe.id); });
  btn.addEventListener('mouseenter', () => handlersRef.current.onHover(cafe.id));
  btn.addEventListener('mouseleave', () => handlersRef.current.onHover(null));
  wrap.appendChild(btn);
  return wrap;
}

/**
 * 首頁地圖。
 *   cafes           要顯示的店（已套用篩選）
 *   recommendedIds  AI 推薦的店，依名次畫成大頭針（不參與聚合）
 *   selectedId      店家詳情開著的那家：飛過去
 *   hoveredId       店家卡 hover 的那家：放大圖釘
 *   padding         詳情面板蓋住地圖的部分（桌機右側面板），飛過去時避開
 */
export default function CafeMap({ cafes, recommendedIds = [], selectedId, hoveredId, onSelect, onHover, padding }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef([]);
  const activeRef = useRef(null);
  const fittedRef = useRef(false);
  const handlersRef = useRef({ onSelect, onHover });
  const latestRef = useRef({ cafes, recommendedIds });
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    handlersRef.current = { onSelect, onHover };
    latestRef.current = { cafes, recommendedIds };
  });

  // ---- 建立地圖（只做一次）----
  useEffect(() => {
    let cancelled = false;
    let map = null;
    let resizeObserver = null;

    (async () => {
      let style = themedStyleCache;
      if (!style) {
        try {
          const res = await fetch(MAP_STYLE_URL);
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          style = applyLatteTheme(await res.json());
          themedStyleCache = style;
        } catch {
          if (!cancelled) setFailed(true);
          return;
        }
      }
      if (cancelled || !containerRef.current) return;

      const isTouch = window.matchMedia('(pointer: coarse)').matches;
      map = new maplibregl.Map({
        container: containerRef.current,
        style,
        center: lastCamera?.center || HUALIEN_CENTER,
        zoom: lastCamera?.zoom ?? 13,
        attributionControl: { compact: true },
        // 中文字形用裝置本身的字型畫，不必從圖磚伺服器下載
        localIdeographFontFamily: '"Noto Sans TC", "Microsoft JhengHei", "PingFang TC", sans-serif',
        // 觸控裝置上單指留給頁面捲動，雙指才移動地圖
        cooperativeGestures: isTouch,
      });
      mapRef.current = map;
      // 回來時停在離開前的位置，不再重新框一次全部店家
      if (lastCamera) fittedRef.current = true;
      map.on('moveend', () => {
        lastCamera = { center: map.getCenter().toArray(), zoom: map.getZoom() };
      });
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
      map.addControl(new maplibregl.GeolocateControl({ positionOptions: { enableHighAccuracy: true } }), 'top-right');

      const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12, className: 'map-tip' });

      // 樣式一就緒就加上店家圖層，不等 'load'：'load' 要等底圖圖磚全部載完、
      // 畫完第一個完整畫面才觸發，網路慢時圖釘會晚好幾秒才出現
      const setup = () => {
        if (cancelled || map.getSource('cafes')) return;
        map.addSource('cafes', {
          type: 'geojson',
          data: toGeoJSON([]),
          cluster: true,
          clusterRadius: 42,
          clusterMaxZoom: 15,
        });
        map.addLayer({
          id: 'cafe-clusters', type: 'circle', source: 'cafes', filter: ['has', 'point_count'],
          paint: {
            'circle-color': ESPRESSO,
            'circle-opacity': 0.88,
            'circle-radius': ['step', ['get', 'point_count'], 16, 6, 20, 15, 25],
            'circle-stroke-width': 3,
            'circle-stroke-color': '#fffaf3',
          },
        });
        map.addLayer({
          id: 'cafe-cluster-count', type: 'symbol', source: 'cafes', filter: ['has', 'point_count'],
          layout: { 'text-field': ['get', 'point_count_abbreviated'], 'text-font': FONT_BOLD, 'text-size': 13 },
          paint: { 'text-color': '#fffaf3' },
        });
        map.addLayer({
          id: 'cafe-points', type: 'circle', source: 'cafes', filter: ['!', ['has', 'point_count']],
          paint: {
            'circle-color': ['case', ['get', 'open'], ESPRESSO, MUTED],
            'circle-radius': ['case', ['boolean', ['feature-state', 'active'], false], 11, 7],
            'circle-stroke-width': 2.5,
            'circle-stroke-color': '#fffaf3',
          },
        });

        map.on('click', 'cafe-points', (e) => {
          const id = e.features?.[0]?.properties?.id;
          if (id != null) handlersRef.current.onSelect(Number(id));
        });
        map.on('click', 'cafe-clusters', async (e) => {
          const feature = e.features?.[0];
          if (!feature) return;
          const zoom = await map.getSource('cafes').getClusterExpansionZoom(feature.properties.cluster_id);
          map.easeTo({ center: feature.geometry.coordinates, zoom });
        });
        map.on('mouseenter', 'cafe-points', (e) => {
          map.getCanvas().style.cursor = 'pointer';
          const f = e.features?.[0];
          if (!f) return;
          popup.setLngLat(f.geometry.coordinates).setText(f.properties.name).addTo(map);
          handlersRef.current.onHover(Number(f.properties.id));
        });
        map.on('mouseleave', 'cafe-points', () => {
          map.getCanvas().style.cursor = '';
          popup.remove();
          handlersRef.current.onHover(null);
        });
        map.on('mouseenter', 'cafe-clusters', () => { map.getCanvas().style.cursor = 'pointer'; });
        map.on('mouseleave', 'cafe-clusters', () => { map.getCanvas().style.cursor = ''; });

        setReady(true);
      };
      if (map.isStyleLoaded()) setup();
      else map.once('style.load', setup);

      // 容器大小改變（對話框展開、視窗縮放）時重新計算畫布
      resizeObserver = new ResizeObserver(() => map.resize());
      resizeObserver.observe(containerRef.current);
    })();

    return () => {
      cancelled = true;
      resizeObserver?.disconnect();
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      map?.remove();
      mapRef.current = null;
    };
  }, []);

  // ---- 圖釘資料：推薦的店另外畫大頭針，不放進聚合 ----
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const recommended = new Set(recommendedIds);
    // 開著詳情的那家不能被聚合吃掉：從聚合資料拿出來，另外畫一根圖釘
    const focusId = selectedId != null && !recommended.has(selectedId) ? selectedId : null;
    map.getSource('cafes')?.setData(toGeoJSON(cafes.filter((c) => !recommended.has(c.id) && c.id !== focusId)));

    // 店家資料通常比地圖晚到：第一次拿到座標時才決定初始視角
    if (!fittedRef.current && cafes.some(hasCoords)) {
      fittedRef.current = true;
      const bounds = coreBoundsOf(cafes);
      if (bounds) map.fitBounds(bounds, { padding: { top: 110, bottom: 30, left: 30, right: 60 }, maxZoom: 15, duration: 0 });
    }

    markersRef.current.forEach((m) => m.remove());
    const byId = new Map(cafes.map((c) => [c.id, c]));
    const pins = recommendedIds.map((id, i) => [byId.get(id), i + 1]);
    if (focusId != null) pins.push([byId.get(focusId) || latestRef.current.cafes.find((c) => c.id === focusId), null]);
    markersRef.current = pins
      .filter(([cafe]) => hasCoords(cafe))
      .map(([cafe, rank]) => {
        const marker = new maplibregl.Marker({ element: pinElement(rank, cafe, handlersRef), anchor: 'bottom' })
          .setLngLat([cafe.lng, cafe.lat])
          .addTo(map);
        marker.cafeId = cafe.id;
        return marker;
      });
  }, [ready, cafes, recommendedIds, selectedId]);

  // ---- 有新的推薦時，把鏡頭拉到看得見全部推薦 ----
  const recommendedKey = recommendedIds.join(',');
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !recommendedKey) return;
    const ids = new Set(recommendedKey.split(',').map(Number));
    const bounds = boundsOf(latestRef.current.cafes.filter((c) => ids.has(c.id)));
    if (bounds) map.fitBounds(bounds, { padding: { top: 70, bottom: 40, left: 60, right: 60 }, maxZoom: 15, duration: 900 });
  }, [ready, recommendedKey]);

  // ---- hover / 選取的那家放大 ----
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const active = hoveredId ?? selectedId ?? null;
    if (activeRef.current != null) map.setFeatureState({ source: 'cafes', id: activeRef.current }, { active: false });
    if (active != null) map.setFeatureState({ source: 'cafes', id: active }, { active: true });
    activeRef.current = active;
    markersRef.current.forEach((m) => {
      const on = m.cafeId === active || m.cafeId === selectedId;
      m.getElement().firstChild?.classList.toggle('active', on);
      m.getElement().style.zIndex = on ? '2' : '';
    });
  }, [ready, hoveredId, selectedId, cafes, recommendedIds]);

  // ---- 開啟店家詳情時飛過去 ----
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    if (selectedId == null) {
      // flyTo 帶的 padding 會一直留在地圖上；詳情關掉就還原，之後的鏡頭才不會偏一邊
      const p = map.getPadding();
      if (p.top || p.right || p.bottom || p.left) map.easeTo({ padding: { top: 0, right: 0, bottom: 0, left: 0 }, duration: 300 });
      return;
    }
    const cafe = latestRef.current.cafes.find((c) => c.id === selectedId);
    if (!hasCoords(cafe)) return;
    const options = { center: [cafe.lng, cafe.lat], zoom: Math.max(map.getZoom(), 15), duration: 800 };
    // 只有真的要讓位時才帶 padding：MapLibre 看到 padding: undefined 這個 key 會去讀 .top 而當掉
    if (padding) options.padding = padding;
    map.flyTo(options);
  }, [ready, selectedId, padding]);

  return (
    <div className="cafe-map">
      <div ref={containerRef} className="cafe-map-canvas" />
      {failed && (
        <div className="cafe-map-fallback" role="status">
          地圖暫時載入失敗，店家資訊仍可從下方瀏覽
        </div>
      )}
    </div>
  );
}
