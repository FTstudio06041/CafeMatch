import { useNavigate } from 'react-router-dom';

export default function WelcomeModal({ show, onClose }) {
  const navigate = useNavigate();

  return (
    <div className={`welcome-modal-overlay ${show ? 'active' : ''}`}>
       <div className="welcome-card">
          <h2 className="welcome-title">歡迎來到 啡你莫屬！</h2>
          <p className="welcome-text">這似乎是您第一次來訪。<br/>建議您先進行心理測驗，<br/>讓啡啡更了解您的喜好喔！</p>
          <div className="welcome-actions">
              <button className="btn-secondary" onClick={onClose}>先不用</button>
              <button className="btn-primary" onClick={() => navigate('/quiz')}>開始測驗</button>
          </div>
       </div>
    </div>
  );
}
