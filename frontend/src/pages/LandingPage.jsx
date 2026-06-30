import { useContext } from 'react';
import { AuthContext } from '../context/AuthContext';
import '../LandingPage.css'; // 引入剛才建立的 CSS
import FloatingBackgroundIcons from '../components/FloatingBackgroundIcon';
import CoffeeAskBar from '../components/AskBar';
import LiquidSurface from '../components/LiquidSurface';

export default function LandingPage() {
  const { login, loginAsGuest } = useContext(AuthContext);

  return (
    <div className="landing-body">
      <FloatingBackgroundIcons />
      <LiquidSurface />
      <header className="landing-header">
        <div className="brand-logo" onClick={() => window.location.reload()}>
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 8h1a4 4 0 0 1 0 8h-1"></path>
            <path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z"></path>
            <line x1="6" y1="1" x2="6" y2="4"></line>
            <line x1="10" y1="1" x2="10" y2="4"></line>
            <line x1="14" y1="1" x2="14" y2="4"></line>
          </svg>
          啡你莫屬 DEV
        </div>

        <div className="header-actions">
          <button className="btn-text" onClick={loginAsGuest}>以訪客繼續</button>
          <button className="btn-text" onClick={login}>註冊</button>
          <button className="btn-text" onClick={login}>登入</button>
          <button className="btn-primary-sm" onClick={login}>開始使用</button>
        </div>
      </header>

      <div className="landing-container">
        <div className="intro-section">
          <h1 className="main-title">找到你的<br />夢中情店</h1>
          <CoffeeAskBar />
          <div className="glow-wrapper">
            <button className="btn-google-login" onClick={login}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
              </svg>
              使用 Google 帳號登入
            </button>
          </div>
          <div style={{ marginTop: '20px', textAlign: 'center' }}>
            <button 
              onClick={loginAsGuest} 
              style={{ background: 'none', border: 'none', color: '#888', textDecoration: 'none', fontWeight: 600, cursor: 'pointer', fontSize: '0.9rem', padding: 0 }}
            >
              以訪客身分繼續
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
