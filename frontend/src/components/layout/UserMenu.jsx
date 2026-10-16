import { useContext, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronDown, LayoutDashboard, LogOut, MessageSquareWarning, UserRound } from 'lucide-react';
import { AuthContext } from '../../context/AuthContext';
import { navigateWithTransition } from '../../utils/viewTransition';

export default function UserMenu({ user, onOpenAccount, onOpenBugReport }) {
  const { logout } = useContext(AuthContext);
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onPointer = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const choose = (action) => () => {
    setOpen(false);
    action();
  };

  const initial = (user.name || '?').trim().charAt(0).toUpperCase();

  return (
    <div className="user-menu" ref={rootRef}>
      <button
        type="button"
        className="user-menu-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`${user.name || '使用者'} 的帳號選單`}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="user-menu-avatar">
          {user.picture ? <img src={user.picture} alt="" /> : initial}
        </span>
        <ChevronDown size={16} aria-hidden="true" />
      </button>

      {open && (
        <div className="user-menu-pop" role="menu">
          <div className="user-menu-head">
            <div className="user-menu-name">{user.name}</div>
            <div className="user-menu-email">{user.email}</div>
          </div>
          <button type="button" role="menuitem" onClick={choose(onOpenAccount)}>
            <UserRound size={18} aria-hidden="true" /> 帳號設定
          </button>
          <button type="button" role="menuitem" onClick={choose(onOpenBugReport)}>
            <MessageSquareWarning size={18} aria-hidden="true" /> 回報問題 / 建議
          </button>
          {user.is_admin && (
            <button type="button" role="menuitem" onClick={choose(() => navigateWithTransition(navigate, '/admin', 'forward'))}>
              <LayoutDashboard size={18} aria-hidden="true" /> 管理後台
            </button>
          )}
          <button type="button" role="menuitem" className="danger" onClick={choose(logout)}>
            <LogOut size={18} aria-hidden="true" /> 登出
          </button>
        </div>
      )}
    </div>
  );
}
