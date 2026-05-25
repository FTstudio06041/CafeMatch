import React from 'react';
import { useNavigate } from 'react-router-dom';
import { encodeId } from '../../utils/hashId';
import { formatTime } from '../../utils/formatters';

export default function OriginalPostQuote({ orig }) {
  const navigate = useNavigate();
  if (!orig) return null;

  return (
    <div 
      onClick={(e) => { 
        e.stopPropagation(); 
        navigate(`/post/${encodeId(orig.id)}`); 
      }}
      style={{
        marginTop: '8px',
        marginBottom: '12px',
        marginLeft: '24px',
        maxWidth: '85%',
        padding: '12px',
        border: '1px solid rgba(139, 90, 43, 0.15)',
        borderRadius: '12px',
        backgroundColor: 'rgba(255, 255, 255, 0.45)',
        boxShadow: 'inset 0 1px 3px rgba(139, 90, 43, 0.05)',
        backdropFilter: 'blur(2px)',
        transition: 'all 0.2s ease',
        display: 'flex',
        gap: '12px',
        alignItems: 'center',
        cursor: 'pointer'
    }}>
      {/* 左半部：文字與標題 */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '6px' }}>
          <div style={{ 
            width: '20px', 
            height: '20px', 
            borderRadius: '50%', 
            overflow: 'hidden', 
            marginRight: '6px', 
            backgroundColor: '#e2d5c8', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center', 
            fontSize: '0.65rem',
            border: '1px solid rgba(139, 90, 43, 0.1)'
          }}>
            {orig.user_picture ? <img src={orig.user_picture} alt="avatar" style={{ width: '100%', height: '100%', objectFit: 'cover' }}/> : (orig.user_name || 'U').charAt(0)}
          </div>
          <span style={{ fontWeight: 'bold', fontSize: '0.85rem', color: '#4a3b32', marginRight: '8px' }}>{orig.user_name}</span>
          <span style={{ fontSize: '0.75rem', color: 'rgba(139, 90, 43, 0.6)' }}>{formatTime(orig.created_at)}</span>
        </div>
        <div style={{ 
          fontSize: '0.9rem', 
          color: '#5c4b3f', 
          lineHeight: '1.4',
          display: '-webkit-box',
          WebkitLineClamp: 3,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
          textOverflow: 'ellipsis'
        }}>
          {orig.content}
        </div>
      </div>

      {/* 右半部：縮略圖 */}
      {orig.image && (
        <div style={{ 
          width: '80px', 
          height: '80px', 
          borderRadius: '8px', 
          overflow: 'hidden', 
          border: '1px solid rgba(139, 90, 43, 0.1)',
          flexShrink: 0
        }}>
          <img src={orig.image} alt="original" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        </div>
      )}
    </div>
  );
}
