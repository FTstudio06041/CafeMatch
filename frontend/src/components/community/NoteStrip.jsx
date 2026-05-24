import React from 'react';
import NoteBubble from './NoteBubble';

/**
 * 便利貼橫向捲動列
 * 位於 Navbar 下方，無論是否有資料都顯示。最左側固定為當前使用者。
 */
export default function NoteStrip({ notes, currentUser, onNoteClick, onEditClick }) {
  // 找出當前使用者的便利貼
  const currentUserNote = currentUser ? notes.find(n => n.user_email === currentUser.email) : null;
  // 其他使用者的便利貼
  const otherNotes = currentUser ? notes.filter(n => n.user_email !== currentUser.email) : notes;

  return (
    <div className="note-strip">
      {/* 當前使用者的泡泡 */}
      {currentUser && (
        <div className="note-bubble current-user-bubble" onClick={() => onEditClick(currentUserNote)}>
          <div className="note-bubble-avatar">
            {currentUser.picture ? (
              <img src={currentUser.picture} alt="我的頭像" />
            ) : (
              <div className="note-bubble-avatar-placeholder">
                {(currentUser.name || 'U').charAt(0)}
              </div>
            )}
          </div>
          <div className={`note-bubble-text ${currentUserNote ? 'color-' + currentUserNote.color_index : 'empty'}`}>
            {currentUserNote ? (currentUserNote.content.length > 10 ? currentUserNote.content.slice(0, 10) + '...' : currentUserNote.content) : '+'}
          </div>
        </div>
      )}

      {/* 其他使用者的便利貼泡泡 */}
      {otherNotes.map((note) => (
        <NoteBubble
          key={note.id}
          note={note}
          onClick={onNoteClick}
        />
      ))}
    </div>
  );
}
