import React, { useRef, useEffect } from 'react';
import { motion, useSpring } from 'framer-motion';

const InteractiveIcon = ({ Component, size, top, left }) => {
  const ref = useRef(null);

  // 使用 useSpring 讓移動更有彈性
  const offsetX = useSpring(0, { stiffness: 80, damping: 15 });
  const offsetY = useSpring(0, { stiffness: 80, damping: 15 });

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!ref.current) return;

      const rect = ref.current.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;

      // 計算鼠標與圖示中心的距離
      const distanceX = e.clientX - centerX;
      const distanceY = e.clientY - centerY;
      const distance = Math.sqrt(distanceX ** 2 + distanceY ** 2);

      // 設定排斥範圍（150px 內觸發）
      const radius = 150;

      if (distance < radius) {
        // 越近力道越大，往反方向推開
        const power = (radius - distance) / radius;
        const moveX = (distanceX / distance) * -60 * power;
        const moveY = (distanceY / distance) * -60 * power;

        offsetX.set(moveX);
        offsetY.set(moveY);
      } else {
        // 離開範圍後回到原點
        offsetX.set(0);
        offsetY.set(0);
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, [offsetX, offsetY]);

  return (
    // 外層：負責定位
    <div
      ref={ref}
      style={{
        position: 'absolute',
        top,
        left,
      }}
    >
      {/* 內層：負責 framer-motion 滑鼠排斥位移 */}
      <motion.div
        style={{
          x: offsetX,
          y: offsetY,
          color: '#432a00',
        }}
      >
        <Component size={size} strokeWidth={1.5} />
      </motion.div>
    </div>
  );
};

export default InteractiveIcon;