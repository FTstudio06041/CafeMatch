import { useMemo } from 'react';
import { Coffee, Bean, MapPin, Map, Store, MessageCircleMore } from 'lucide-react';
import InteractiveIcon from './InteractiveIcon';

const FloatingBackgroundIcons = () => {
    const icons = useMemo(() => {
        // 6 種圖標排成 3×2 的基礎圖案 (tile)
        // 這個圖案會重複鋪滿畫面，動畫移動恰好一個圖案的距離後重置
        // 因為前後畫面圖案完全一致 → 無縫循環
        const iconTypes = [Coffee, Bean, MapPin, Map, Store, MessageCircleMore];

        // 基礎圖案尺寸
        const tileCols = 3;
        const tileRows = 2;

        // 畫面上需要多少個基礎圖案才能填滿（向上取整）
        const tilesX = 4; // 4 × 3 = 12 列，足以覆蓋畫面
        const tilesY = 4; // 4 × 2 = 8 排，足以覆蓋畫面

        // 總格數（多 1 個圖案的寬高，用來填補動畫移動時露出的空白）
        const totalCols = tilesX * tileCols + tileCols; // 12 + 3 = 15
        const totalRows = tilesY * tileRows + tileRows; // 8 + 2 = 10

        // 每格尺寸（以畫面填滿區域為基準）
        const gridW = tilesX * tileCols; // 12 列填滿 100vw
        const gridH = tilesY * tileRows; // 8 排填滿 100vh
        const cellW = 100 / gridW;       // 每格寬 (vw)
        const cellH = 100 / gridH;       // 每格高 (vh)

        // 簡單的決定性偽隨機函數
        const seededRandom = (seed) => {
            const x = Math.sin(seed) * 10000;
            return x - Math.floor(x);
        };

        // 為基礎圖案的每個位置產生固定的隨機偏移
        const tileOffsets = [];
        for (let r = 0; r < tileRows; r++) {
            for (let c = 0; c < tileCols; c++) {
                tileOffsets.push({
                    ox: (seededRandom(r * 10 + c) - 0.5) * cellW * 0.35,
                    oy: (seededRandom(r * 10 + c + 100) - 0.5) * cellH * 0.35,
                });
            }
        }

        const result = [];
        let index = 0;

        for (let row = 0; row < totalRows; row++) {
            for (let col = 0; col < totalCols; col++) {
                const tileR = row % tileRows;
                const tileC = col % tileCols;
                const tileIdx = tileR * tileCols + tileC;
                const { ox, oy } = tileOffsets[tileIdx];

                result.push({
                    id: index,
                    Component: iconTypes[tileIdx % iconTypes.length],
                    size: 28,
                    top: `${row * cellH + cellH / 2 + oy}vh`,
                    left: `${col * cellW + cellW / 2 + ox}vw`,
                });
                index++;
            }
        }

        return result;
    }, []);

    // 一個 tile 的寬高（用於 CSS 動畫位移量）
    const tileW = 100 / 4; // 25vw (= tileCols * cellW = 3 * 100/12)
    const tileH = 100 / 4; // 25vh (= tileRows * cellH = 2 * 100/8)

    return (
        <div className="grid-bg-container">
            <div
                className="grid-bg-inner"
                style={{
                    '--tile-w': `${tileW}vw`,
                    '--tile-h': `${tileH}vh`,
                }}
            >
                {icons.map(({ id, Component, size, top, left }) => (
                    <InteractiveIcon
                        key={id}
                        Component={Component}
                        size={size}
                        top={top}
                        left={left}
                    />
                ))}
            </div>
        </div>
    );
};

export default FloatingBackgroundIcons;