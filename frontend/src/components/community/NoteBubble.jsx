
/**
 * 單個便利貼泡泡
 * 顯示使用者頭像 + 截斷至 10 字的文字泡泡
 */
export default function NoteBubble({ note, onClick }) {
  // 截斷至 20 字
  const truncated = note.content.length > 20
    ? note.content.slice(0, 20) + '...'
    : note.content;

  return (
    <div className="note-bubble" onClick={() => onClick(note)}>
      {/* 頭像 */}
      <div className="note-bubble-avatar">
        {note.user_picture ? (
          <img src={note.user_picture} alt={note.user_name} />
        ) : (
          <div className="note-bubble-avatar-placeholder">
            {(note.user_name || 'U').charAt(0)}
          </div>
        )}
      </div>

      {/* 文字泡泡 */}
      <div className={`note-bubble-text color-${note.color_index ?? 0}`}>
        {truncated}
      </div>
    </div>
  );
}
