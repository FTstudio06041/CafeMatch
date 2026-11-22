import { useContext } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { Coffee } from 'lucide-react';
import { AuthContext } from '../../context/AuthContext';
import UserMenu from './UserMenu';
import { navigateWithTransition } from '../../utils/viewTransition';

const PAGES = [
  { path: '/', label: '首頁' },
  { path: '/quiz', label: '心理測驗' },
];

/**
 * 頁面切換：只有兩頁，所以整個切換鈕任何地方點一下就換到另一頁，
 * 不必瞄準「另一邊」那半顆。不在這兩頁時（例如後台）才退回兩個各自的連結。
 */
function PageSwitch() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const activeIndex = PAGES.findIndex((p) => (p.path === '/' ? pathname === '/' : pathname.startsWith(p.path)));

  if (activeIndex === -1) {
    return (
      <nav className="topnav-seg" aria-label="主要頁面">
        {PAGES.map((page) => (
          <NavLink key={page.path} to={page.path} end={page.path === '/'} className="topnav-seg-btn">
            {page.label}
          </NavLink>
        ))}
      </nav>
    );
  }

  const current = PAGES[activeIndex];
  const other = PAGES[1 - activeIndex];
  return (
    <nav aria-label="主要頁面">
      <button
        type="button"
        className="topnav-seg switch"
        // 往右邊那頁（測驗）內容往左滑，回首頁往右滑，跟切換鈕的方向一致
        onClick={() => navigateWithTransition(navigate, other.path, activeIndex === 0 ? 'forward' : 'back')}
        aria-label={`目前在${current.label}，切換到${other.label}`}
      >
        <span
          className="topnav-seg-marker"
          aria-hidden="true"
          style={{ transform: `translateX(${activeIndex * 100}%)` }}
        />
        {PAGES.map((page, i) => (
          <span key={page.path} className={`topnav-seg-btn ${i === activeIndex ? 'active' : ''}`} aria-hidden="true">
            {page.label}
          </span>
        ))}
      </button>
    </nav>
  );
}

export default function TopNav({ onOpenAccount, onOpenBugReport }) {
  const { user, login } = useContext(AuthContext);
  const navigate = useNavigate();
  const goHome = (e) => {
    e.preventDefault();
    navigateWithTransition(navigate, '/', 'back');
  };

  return (
    <header className="topnav">
      <Link to="/" className="topnav-brand" aria-label="CafeMatch 首頁" onClick={goHome}>
        <Coffee size={24} strokeWidth={2.4} aria-hidden="true" />
        <span>CafeMatch</span>
      </Link>

      <div className="topnav-right">
        <PageSwitch />
        {user ? (
          <UserMenu user={user} onOpenAccount={onOpenAccount} onOpenBugReport={onOpenBugReport} />
        ) : (
          <button type="button" className="topnav-login" onClick={login}>登入</button>
        )}
      </div>
    </header>
  );
}
