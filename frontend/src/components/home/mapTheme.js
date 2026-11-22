/**
 * 把 OpenFreeMap 的 positron 底圖換成站上的拿鐵色系，標籤只留中文。
 *
 * 直接改 style JSON 再交給 MapLibre（而不是載入後逐層 setPaintProperty），
 * 第一次畫出來就是對的顏色，不會先閃一下灰色底圖。
 */
export const MAP_STYLE_URL = 'https://tiles.openfreemap.org/styles/positron';

const LATTE = {
  background: '#efe5d8',
  water: '#bfd2d4',
  park: '#d9dcc0',
  wood: '#d3d8b6',
  residential: '#e9ddcc',
  building: '#e1d1bd',
  buildingOutline: '#d3c0a6',
  road: '#fbf7f0',
  roadCasing: '#d9c6ad',
  motorway: '#f2dec0',
  rail: '#cdbb9f',
  boundary: '#c3ad8e',
  label: '#5d4037',
  labelHalo: '#f7f0e6',
  waterLabel: '#557a80',
};

// 台灣的 OSM name 本來就是中文；有 zh-Hant 就優先用
const CHINESE_NAME = ['coalesce', ['get', 'name:zh-Hant'], ['get', 'name:zh'], ['get', 'name']];

// 對找咖啡廳沒有幫助、只會讓畫面變雜的圖層
const DROP_LAYER = (id) => id.includes('shield') || id.startsWith('label_country') || id.startsWith('aeroway');

export function applyLatteTheme(style) {
  const themed = structuredClone(style);
  themed.layers = themed.layers.filter((layer) => !DROP_LAYER(layer.id));

  for (const layer of themed.layers) {
    const { id, type } = layer;
    const paint = layer.paint || (layer.paint = {});

    if (type === 'background') {
      paint['background-color'] = LATTE.background;
    } else if (id === 'water') {
      paint['fill-color'] = LATTE.water;
    } else if (id === 'park') {
      paint['fill-color'] = LATTE.park;
    } else if (id === 'landcover_wood') {
      paint['fill-color'] = LATTE.wood;
    } else if (id === 'landuse_residential') {
      paint['fill-color'] = LATTE.residential;
    } else if (id === 'building') {
      paint['fill-color'] = LATTE.building;
      paint['fill-outline-color'] = LATTE.buildingOutline;
    } else if (id === 'waterway') {
      paint['line-color'] = LATTE.water;
    } else if (type === 'line' && id.includes('casing')) {
      paint['line-color'] = LATTE.roadCasing;
    } else if (type === 'line' && id.startsWith('highway_motorway')) {
      paint['line-color'] = LATTE.motorway;
    } else if (type === 'line' && (id.startsWith('highway') || id.startsWith('road') || id.startsWith('tunnel'))) {
      paint['line-color'] = LATTE.road;
    } else if (type === 'line' && id.startsWith('railway')) {
      paint['line-color'] = LATTE.rail;
    } else if (type === 'line' && id.startsWith('boundary')) {
      paint['line-color'] = LATTE.boundary;
    } else if (type === 'symbol' && layer.layout?.['text-field']) {
      layer.layout['text-field'] = CHINESE_NAME;
      paint['text-color'] = id.startsWith('water') ? LATTE.waterLabel : LATTE.label;
      paint['text-halo-color'] = LATTE.labelHalo;
    }
  }
  return themed;
}
