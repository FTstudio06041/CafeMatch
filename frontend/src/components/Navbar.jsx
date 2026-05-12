import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

export default function Navbar() {
  const navigate = useNavigate();
  const location = useLocation();

  // 狀態新增了 isAnimating，用來控制是否要播放滑動動畫
  const [markerStyle, setMarkerStyle] = useState({ left: 0, width: 0, opacity: 0, isAnimating: false });
  const [hoveredIndex, setHoveredIndex] = useState(null); // 追蹤滑鼠目前懸停在哪個按鈕上
  const navRefs = useRef([]);

  const navItems = [
    { path: '/chat', label: '對話' },
    { path: '/explore', label: '探索' },
    { path: '/quiz', label: '測驗' }
  ];

  // 找出目前網址對應的是第幾個按鈕
  const activeIndex = navItems.findIndex(item => location.pathname.startsWith(item.path));

  // 更新滑塊位置的函式
  const updateMarker = (index, animate = true) => {
    if (index !== -1 && navRefs.current[index]) {
      const target = navRefs.current[index];
      setMarkerStyle({
        left: target.offsetLeft,
        width: target.offsetWidth,
        opacity: 1,
        isAnimating: animate // 決定這次移動要不要帶動畫
      });
    }
  };

  // 🚀 修復 Bug 1：處理換頁時的「瞬間移動」
  useEffect(() => {
    // 每次元件掛載或換頁時，先「無動畫」瞬間跳到正確位置
    updateMarker(activeIndex, false);

    // 等待 50 毫秒後，再把動畫開關打開，這樣之後的 hover 才會有滑動效果
    const timer = setTimeout(() => {
      setMarkerStyle(prev => ({ ...prev, isAnimating: true }));
    }, 50);

    return () => clearTimeout(timer);
  }, [location.pathname, activeIndex]);

  // 滑鼠互動處理
  const handleMouseEnter = (index) => {
    setHoveredIndex(index);
    updateMarker(index, true);
  };

  const handleMouseLeave = () => {
    setHoveredIndex(null);
    updateMarker(activeIndex, true); // 滑鼠離開導覽列，滑塊彈回當前頁面
  };

  return (
    <nav className="navbar" onMouseLeave={handleMouseLeave}>
      {/* 透過 isAnimating 來動態決定要不要加入 .animate 的 CSS class */}
      <div 
        className={`nav-marker ${markerStyle.isAnimating ? 'animate' : ''}`} 
        style={{
          left: `${markerStyle.left}px`,
          width: `${markerStyle.width}px`,
          opacity: markerStyle.opacity
        }}
      ></div>

      {navItems.map((item, index) => {
        const isActive = index === activeIndex;
        
        // 🚀 修復 Bug 2：判斷這個按鈕現在該不該變白色？
        // 如果滑鼠有懸停，反白的文字就跟著滑鼠走；如果沒有懸停，就反白當前頁面的文字
        const isHighlighted = hoveredIndex !== null ? index === hoveredIndex : isActive;

        return (
          <button
            key={item.path}
            ref={el => navRefs.current[index] = el}
            className={`nav-btn ${isActive ? 'active' : ''}`}
            // 用 inline-style 強制覆蓋 CSS：被選中的變白色，其他的退回淺咖啡色
            style={{ color: isHighlighted ? '#fff' : 'var(--text-light)' }} 
            onClick={() => navigate(item.path)}
            onMouseEnter={() => handleMouseEnter(index)}
          >
            {item.label}
          </button>
        );
      })}
    </nav>
  );
}