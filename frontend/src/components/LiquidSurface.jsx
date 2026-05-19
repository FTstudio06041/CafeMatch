import React, { useEffect, useRef } from 'react';

const MAX_RIPPLES = 42;

export default function LiquidSurface() {
  const canvasRef = useRef(null);
  const ripplesRef = useRef([]);
  const pointerRef = useRef({ x: 0, y: 0, lastX: 0, lastY: 0, active: false });
  const frameRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d', { alpha: true });
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (reduceMotion) return undefined;

    const resize = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(window.innerWidth * ratio);
      canvas.height = Math.floor(window.innerHeight * ratio);
      canvas.style.width = `${window.innerWidth}px`;
      canvas.style.height = `${window.innerHeight}px`;
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    };

    const addRipple = (x, y, strength = 1) => {
      ripplesRef.current.push({
        x,
        y,
        age: 0,
        life: 54 + Math.random() * 18,
        radius: 8,
        strength,
        wobble: Math.random() * Math.PI * 2
      });

      if (ripplesRef.current.length > MAX_RIPPLES) {
        ripplesRef.current.splice(0, ripplesRef.current.length - MAX_RIPPLES);
      }
    };

    const handlePointerMove = (event) => {
      const pointer = pointerRef.current;
      const dx = event.clientX - pointer.lastX;
      const dy = event.clientY - pointer.lastY;
      const distance = Math.hypot(dx, dy);

      pointer.x = event.clientX;
      pointer.y = event.clientY;
      pointer.active = true;

      if (distance > 12) {
        addRipple(event.clientX, event.clientY, Math.min(distance / 28, 1.8));
        pointer.lastX = event.clientX;
        pointer.lastY = event.clientY;
      }
    };

    const handlePointerLeave = () => {
      pointerRef.current.active = false;
    };

    const drawRipple = (ripple) => {
      const progress = ripple.age / ripple.life;
      const alpha = Math.max(0, 1 - progress);
      const radius = ripple.radius + progress * 110 * ripple.strength;
      const wobble = Math.sin(progress * Math.PI * 5 + ripple.wobble) * 4;

      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      ctx.lineWidth = 1.8 + ripple.strength;
      ctx.strokeStyle = `rgba(255, 255, 255, ${0.22 * alpha})`;
      ctx.beginPath();
      ctx.ellipse(ripple.x, ripple.y, radius + wobble, radius * 0.58, 0, 0, Math.PI * 2);
      ctx.stroke();

      ctx.globalCompositeOperation = 'multiply';
      ctx.lineWidth = 1;
      ctx.strokeStyle = `rgba(67, 42, 0, ${0.11 * alpha})`;
      ctx.beginPath();
      ctx.ellipse(ripple.x + 5, ripple.y + 7, radius * 0.82, radius * 0.43, 0, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    };

    const drawPointerWake = () => {
      const pointer = pointerRef.current;
      if (!pointer.active) return;

      const gradient = ctx.createRadialGradient(pointer.x, pointer.y, 8, pointer.x, pointer.y, 130);
      gradient.addColorStop(0, 'rgba(255, 255, 255, 0.3)');
      gradient.addColorStop(0.42, 'rgba(255, 255, 255, 0.08)');
      gradient.addColorStop(1, 'rgba(255, 255, 255, 0)');

      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(pointer.x, pointer.y, 130, 0, Math.PI * 2);
      ctx.fill();

      ctx.globalCompositeOperation = 'multiply';
      ctx.strokeStyle = 'rgba(67, 42, 0, 0.08)';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.ellipse(pointer.x, pointer.y + 8, 64, 24, 0, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    };

    const render = () => {
      ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
      drawPointerWake();

      ripplesRef.current = ripplesRef.current.filter((ripple) => {
        ripple.age += 1;
        drawRipple(ripple);
        return ripple.age < ripple.life;
      });

      frameRef.current = window.requestAnimationFrame(render);
    };

    resize();
    window.addEventListener('resize', resize);
    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerleave', handlePointerLeave);
    frameRef.current = window.requestAnimationFrame(render);

    return () => {
      window.removeEventListener('resize', resize);
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerleave', handlePointerLeave);
      if (frameRef.current) window.cancelAnimationFrame(frameRef.current);
    };
  }, []);

  return <canvas ref={canvasRef} className="liquid-surface" aria-hidden="true" />;
}
