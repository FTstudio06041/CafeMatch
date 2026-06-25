import { useState, useContext } from 'react';
import { AuthContext } from '../context/AuthContext';
import { CHAT_WINDOW_UI_TEXTS } from '../utils/constants';
import './ChatWindow.css';

export default function ChatWindow() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([{ sender: 'ai', text: CHAT_WINDOW_UI_TEXTS.welcomeMessage }]);
  const [inputMsg, setInputMsg] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const { API_BASE_URL } = useContext(AuthContext);

  const sendMessage = async () => {
    if (!inputMsg.trim()) return;
    
    const newMessages = [...messages, { sender: 'user', text: inputMsg }];
    setMessages(newMessages);
    setInputMsg('');
    setIsTyping(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ message: inputMsg }),
      });
      const data = await response.json();
      
      setMessages([...newMessages, { sender: 'ai', text: data.reply || data.error }]);
    } catch (e) { // eslint-disable-line no-unused-vars
      setMessages([...newMessages, { sender: 'ai', text: CHAT_WINDOW_UI_TEXTS.networkError }]);
    } finally {
      setIsTyping(false);
    }
  };

  if (!isOpen) {
    return (
      <button onClick={() => setIsOpen(true)} className="chat-floating-btn">
        {CHAT_WINDOW_UI_TEXTS.chatButton}
      </button>
    );
  }

  return (
    <div className="chat-window">
      <div className="chat-window-header">
        <h4>{CHAT_WINDOW_UI_TEXTS.chatHeader}</h4>
        <button onClick={() => setIsOpen(false)} className="chat-window-close-btn">X</button>
      </div>
      <div className="chat-window-messages">
        {messages.map((msg, i) => (
          <div key={i} className={msg.sender === 'user' ? 'chat-window-user-msg' : 'chat-window-ai-msg'}>
            {msg.text}
          </div>
        ))}
        {isTyping && <div className="chat-window-ai-msg">{CHAT_WINDOW_UI_TEXTS.typing}</div>}
      </div>
      <div className="chat-window-input-area">
        <input 
          value={inputMsg} 
          onChange={(e) => setInputMsg(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
          className="chat-window-input"
          placeholder={CHAT_WINDOW_UI_TEXTS.inputPlaceholder}
        />
        <button onClick={sendMessage} className="chat-window-send-btn">{CHAT_WINDOW_UI_TEXTS.send}</button>
      </div>
    </div>
  );
}