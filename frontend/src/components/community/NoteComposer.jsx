import React, { useState } from 'react';

import { logger } from '../../utils/logger';
const NOTE_COLORS = [
  { key: 0, bg: '#FFF3E0' },
  { key: 1, bg: '#FCE4EC' },
  { key: 2, bg: '#FFFDE7' },
  { key: 3, bg: '#E8F5E9' },
  { key: 4, bg: '#E3F2FD' },
  { key: 5, bg: '#F3E5F5' },
];

/**
 * 便利貼快速輸入框（Modal 形式）
 * 支援新增與更新，文字上限 100 字 + 6 色選擇
 */
export default function NoteComposer({ initialNote, onSubmit, onClose, onDelete }) {
  const [content, setContent] = useState(initialNote ? initialNote.content : '');
  const [colorIndex, setColorIndex] = useState(initialNote ? initialNote.color_index : 0);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const charCount = content.length;
  const isOverLimit = charCount > 100;
  // 必須要有輸入文字才能提交
  const canSubmit = content.trim().length > 0 && !isOverLimit && !isSubmitting;
  
  const isUpdate = !!initialNote;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setIsSubmitting(true);
    try {
      await onSubmit({ content: content.trim(), color_index: colorIndex });
      onClose();
    } catch (err) {
      logger.error('發布便利貼失敗:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = () => {
    if (initialNote && onDelete) {
      onDelete(initialNote.id);
      onClose();
    }
  };

  return (
    <div className="note-composer-overlay" onClick={onClose}>
      <div className="note-composer-card" onClick={(e) => e.stopPropagation()}>
        <div className="note-composer-title">
          {isUpdate ? '📝 更新便利貼' : '✏️ 貼一張便利貼'}
        </div>

        <textarea
          className="note-composer-textarea"
          style={{ backgroundColor: NOTE_COLORS[colorIndex].bg }}
          placeholder="輸入簡單的文字分享你的狀態（100 字以內）..."
          value={content}
          onChange={(e) => setContent(e.target.value)}
          maxLength={110}
          autoFocus
        />

        <div className="note-composer-footer">
          {/* 字數計數 */}
          <span className={`note-composer-char-count ${isOverLimit ? 'over-limit' : ''}`}>
            {charCount}/100
          </span>

          {/* 顏色選擇 */}
          <div className="note-composer-colors">
            {NOTE_COLORS.map((c) => (
              <div
                key={c.key}
                className={`note-color-dot c${c.key} ${colorIndex === c.key ? 'selected' : ''}`}
                onClick={() => setColorIndex(c.key)}
              />
            ))}
          </div>
        </div>

        <div className="note-composer-actions">
          {isUpdate && (
            <button className="note-composer-cancel" onClick={handleDelete} style={{ color: '#dc3545', borderColor: '#f8d7da', marginRight: 'auto' }}>
              刪除
            </button>
          )}
          <button className="note-composer-cancel" onClick={onClose} style={isUpdate ? {flex: 'none', padding: '12px 20px'} : {}}>
            取消
          </button>
          <button
            className="note-composer-submit"
            onClick={handleSubmit}
            disabled={!canSubmit}
            style={isUpdate ? {flex: 'none', padding: '12px 30px'} : {}}
          >
            {isSubmitting ? '處理中...' : (isUpdate ? '更新' : '發布')}
          </button>
        </div>
      </div>
    </div>
  );
}
