import React, { useMemo } from 'react';
import { Coffee, Bean, MapPin, Map, Store, MessageCircleMore } from 'lucide-react';
import InteractiveIcon from './InteractiveIcon';

const FloatingBackgroundIcons = () => {
    // 使用 useMemo 確保隨機位置在重新渲染時不會跳動
    const icons = useMemo(() => {
        // 定義想要出現的圖示種類
        const iconTypes = [Coffee, Bean, MapPin, Map, Store, MessageCircleMore];

        // 產生隨機分佈的圖示資料
        return Array.from({ length: 40 }).map((_, i) => ({
            id: i,
            Component: iconTypes[i % iconTypes.length],
            size: Math.floor(Math.random() * (40 - 20 + 1) + 20), // 20px ~ 40px
            top: `${Math.random() * 90}%`,
            left: `${Math.random() * 90}%`,
            delay: `${Math.random() * 5}s`, // 隨機延遲，讓動作錯開
            duration: `${5 + Math.random() * 5}s`, // 隨機速度 (5s ~ 10s)
        }));
    }, []);

    return (
        <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100vw',
            height: '100vh',
            pointerEvents: 'none',
            zIndex: 0,
            overflow: 'hidden',
            opacity: 0.15,
        }}>
            {icons.map(({ id, Component, size, top, left, delay, duration }) => (
                <InteractiveIcon
                    key={id}
                    Component={Component}
                    size={size}
                    top={top}
                    left={left}
                    delay={delay}
                    duration={duration}
                />
            ))}
        </div>
    );
};

export default FloatingBackgroundIcons;