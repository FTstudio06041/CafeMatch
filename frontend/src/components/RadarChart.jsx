import React from 'react';

// =============================================
// 五維雷達圖元件（純 SVG，無外部套件）
// =============================================

// 雷達圖的五個維度定義
const DIMENSIONS = [
  { key: 'work', label: '工作讀書' },
  { key: 'env', label: '空間氛圍' },
  { key: 'social', label: '社交舒適' },
  { key: 'taste', label: '餐飲口味' },
  { key: 'cp', label: 'CP值' },
];

// 佈局常數
const CX = 160;               // 中心 X
const CY = 160;               // 中心 Y
const MAX_RADIUS = 110;        // 最大半徑
const LABEL_RADIUS = MAX_RADIUS + 45; // 標籤距離
const GRID_LEVELS = 4;         // 背景網格層數

/**
 * 計算五角形頂點座標（從頂部 -90° 開始順時針）
 */
function getPoint(index, radius) {
  const angle = ((2 * Math.PI) / DIMENSIONS.length) * index - Math.PI / 2;
  return {
    x: CX + radius * Math.cos(angle),
    y: CY + radius * Math.sin(angle),
  };
}

/**
 * 生成多角形頂點字串
 * @param {function} radiusFn - 接收維度索引，回傳該點的半徑
 */
function getPolygonPoints(radiusFn) {
  return DIMENSIONS.map((_, i) => {
    const p = getPoint(i, radiusFn(i));
    return `${p.x},${p.y}`;
  }).join(' ');
}

/**
 * 五維雷達圖
 * @param {Object} props.scores - 五維分數物件 { work, env, social, taste, cp }
 */
export default function RadarChart({ scores }) {
  const maxScore = Math.max(...Object.values(scores), 1);

  // 背景同心五角形
  const gridPolygons = Array.from({ length: GRID_LEVELS }, (_, level) => {
    const r = (MAX_RADIUS / GRID_LEVELS) * (level + 1);
    return getPolygonPoints(() => r);
  });

  // 資料多角形
  const dataPoints = getPolygonPoints((i) => {
    const score = scores[DIMENSIONS[i].key] || 0;
    return (score / maxScore) * MAX_RADIUS;
  });

  return (
    <div className="radar-container">
      <div className="radar-title">五維度側寫</div>
      <svg className="radar-svg" viewBox="-40 -40 400 400">
        {/* 背景網格 */}
        {gridPolygons.map((points, i) => (
          <polygon key={`grid-${i}`} points={points} className="radar-grid-polygon" />
        ))}

        {/* 軸線 */}
        {DIMENSIONS.map((_, i) => {
          const p = getPoint(i, MAX_RADIUS);
          return (
            <line
              key={`axis-${i}`}
              x1={CX} y1={CY} x2={p.x} y2={p.y}
              className="radar-axis-line"
            />
          );
        })}

        {/* 資料多角形 */}
        <polygon points={dataPoints} className="radar-data-polygon" />

        {/* 資料頂點圓點 */}
        {DIMENSIONS.map((dim, i) => {
          const score = scores[dim.key] || 0;
          const r = (score / maxScore) * MAX_RADIUS;
          const p = getPoint(i, r);
          return <circle key={`dot-${i}`} cx={p.x} cy={p.y} className="radar-dot" />;
        })}

        {/* 軸標籤 */}
        {DIMENSIONS.map((dim, i) => {
          const p = getPoint(i, LABEL_RADIUS);
          return (
            <text key={`label-${i}`} x={p.x} y={p.y} className="radar-label">
              {dim.label}
            </text>
          );
        })}

        {/* 分數標籤 */}
        {DIMENSIONS.map((dim, i) => {
          const score = scores[dim.key] || 0;
          const r = (score / maxScore) * MAX_RADIUS;
          const p = getPoint(i, Math.max(r + 20, 25));
          return (
            <text key={`score-${i}`} x={p.x} y={p.y + 14} className="radar-score">
              {score}
            </text>
          );
        })}
      </svg>
    </div>
  );
}
