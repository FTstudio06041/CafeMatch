import React, { useState, useContext } from 'react';
import { AuthContext } from '../context/AuthContext';

export default function ChatWindow() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([{ sender: 'ai', text: '你好！我是咖啡廳推薦助手，想找什麼樣的店呢？' }]);
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
    } catch (error) {
      setMessages([...newMessages, { sender: 'ai', text: '連線發生錯誤，請稍後再試。' }]);
    } finally {
      setIsTyping(false);
    }
  };

  if (!isOpen) {
    return (
      <button onClick={() => setIsOpen(true)} style={styles.floatingBtn}>
        💬 聊聊
      </button>
    );
  }

  return (
    <div style={styles.chatWindow}>
      <div style={styles.header}>
        <h4>咖啡助手</h4>
        <button onClick={() => setIsOpen(false)} style={styles.closeBtn}>X</button>
      </div>
      <div style={styles.messages}>
        {messages.map((msg, i) => (
          <div key={i} style={msg.sender === 'user' ? styles.userMsg : styles.aiMsg}>
            {msg.text}
          </div>
        ))}
        {isTyping && <div style={styles.aiMsg}>思考中...</div>}
      </div>
      <div style={styles.inputArea}>
        <input 
          value={inputMsg} 
          onChange={(e) => setInputMsg(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
          style={styles.input}
          placeholder="輸入訊息..."
        />
        <button onClick={sendMessage} style={styles.sendBtn}>送出</button>
      </div>
    </div>
  );
}

const styles = {
  floatingBtn: { position: 'fixed', bottom: '20px', right: '20px', padding: '15px 20px', borderRadius: '30px', backgroundColor: '#4E342E', color: 'white', border: 'none', cursor: 'pointer', boxShadow: '0 4px 8px rgba(0,0,0,0.2)' },
  chatWindow: { position: 'fixed', bottom: '20px', right: '20px', width: '300px', height: '400px', backgroundColor: 'white', border: '1px solid #ddd', borderRadius: '10px', display: 'flex', flexDirection: 'column', boxShadow: '0 5px 15px rgba(0,0,0,0.2)', zIndex: 1000 },
  header: { backgroundColor: '#4E342E', color: 'white', padding: '10px', display: 'flex', justifyContent: 'space-between', borderTopLeftRadius: '10px', borderTopRightRadius: '10px' },
  closeBtn: { background: 'none', border: 'none', color: 'white', cursor: 'pointer', fontWeight: 'bold' },
  messages: { flex: 1, padding: '10px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '10px', backgroundColor: '#fafafa' },
  userMsg: { alignSelf: 'flex-end', backgroundColor: '#DCF8C6', padding: '8px 12px', borderRadius: '15px' },
  aiMsg: { alignSelf: 'flex-start', backgroundColor: '#E0E0E0', padding: '8px 12px', borderRadius: '15px' },
  inputArea: { display: 'flex', padding: '10px', borderTop: '1px solid #ddd' },
  input: { flex: 1, padding: '8px', borderRadius: '4px', border: '1px solid #ccc' },
  sendBtn: { marginLeft: '5px', padding: '8px 15px', backgroundColor: '#4E342E', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }
};