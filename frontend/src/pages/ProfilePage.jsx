import React, { useState, useEffect, useContext, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import Cropper from 'react-cropper';
import '../ProfilePage.css';
import Navbar from '../components/Navbar';

export default function ProfilePage() {
  const { user, API_BASE_URL, logout } = useContext(AuthContext);
  const navigate = useNavigate();

  // --- 側欄與導覽狀態 ---
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [chats, setChats] = useState([]);

  // --- 資料網格狀態 ---
  const [favShops, setFavShops] = useState([]);
  const [visitedShops, setVisitedShops] = useState([]);
  const [quizHistory, setQuizHistory] = useState([]);

  // --- Modal 狀態 ---
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);

  // --- 編輯表單與裁切狀態 ---
  const [newName, setNewName] = useState('');
  const [imageToCrop, setImageToCrop] = useState('');
  const [croppedImageBase64, setCroppedImageBase64] = useState('');
  const [fileName, setFileName] = useState('尚未選擇檔案');
  const cropperRef = useRef(null);

  // ==========================================
  // 初始化與資料抓取
  // ==========================================
  useEffect(() => {
    // 1. 讀取側欄對話紀錄
    const savedChats = JSON.parse(localStorage.getItem('allChats')) || [];
    setChats(savedChats);

    // 2. 初始化使用者編輯資料
    if (user) {
      setNewName(user.name || '');
      setCroppedImageBase64(user.picture || '');
      if (user.picture) setFileName('使用目前的頭像');
    }

    // 3. 抓取 API 資料 (並行處理)
    const fetchProfileData = async () => {
      try {
        const [cafesRes, quizRes] = await Promise.all([
          fetch(`${API_BASE_URL}/api/cafes`, { credentials: 'include' }).catch(() => null),
          // 修正為正確的歷史紀錄端點
          fetch(`${API_BASE_URL}/api/quiz/history`, { credentials: 'include' }).catch(() => null)
        ]);

        if (cafesRes && cafesRes.ok) {
          const cafesData = await cafesRes.json();
          setFavShops(cafesData.filter(s => s.is_fav));
          setVisitedShops(cafesData.filter(s => s.is_visited));
        }

        if (quizRes && quizRes.ok) {
          const quizData = await quizRes.json();
          // 將後端資料映射為前端顯示格式
          if (quizData?.history) {
            const formattedHistory = quizData.history.map(hist => ({
              id: hist.id,
              date: new Date(hist.created_at).toLocaleDateString('zh-TW', { 
                year: 'numeric', month: '2-digit', day: '2-digit' 
              }),
              resultName: hist.title,
              resultDesc: `咖啡人格類型：${hist.type_key}`,
              rawHist: hist // 保留原始資料以供諮詢 AI 使用
            }));
            setQuizHistory(formattedHistory);
          }
        }
      } catch (err) {
        console.error('Failed to fetch profile data:', err);
      }
    };

    fetchProfileData();
  }, [user, API_BASE_URL]);

  // ==========================================
  // 行為處理
  // ==========================================

  // 以此結果諮詢 AI
  const handleConsultAI = (histItem) => {
    // 將歷史測驗結果轉為 JSON 字串存入 targetQuizContext，供 ChatPage 解析
    const quizData = {
      title: histItem.resultName,
      scores: histItem.rawHist.scores || {}
    };
    localStorage.setItem('targetQuizContext', JSON.stringify(quizData));
    navigate('/chat');
  };

  // 側欄新建對話
  const handleNewChat = () => {
    localStorage.setItem('targetChatId', 'new');
    navigate('/chat');
  };

  // 側欄選擇對話
  const handleSelectChat = (chatId) => {
    localStorage.setItem('targetChatId', chatId);
    navigate('/chat');
  };

  // ==========================================
  // 裁切圖片邏輯
  // ==========================================
  const handleFileSelect = (e) => {
    e.preventDefault();
    let files = e.target.files;
    if (files && files.length > 0) {
      if (files[0].size > 5 * 1024 * 1024) {
        alert("圖片太大囉！請上傳 5MB 以下的圖片。");
        return;
      }
      setFileName(files[0].name);
      const reader = new FileReader();
      reader.onload = () => {
        setImageToCrop(reader.result);
        setCroppedImageBase64(''); // 清除之前的最終預覽
      };
      reader.readAsDataURL(files[0]);
    }
  };

  const performCrop = () => {
    if (typeof cropperRef.current?.cropper !== "undefined") {
      setCroppedImageBase64(
        cropperRef.current?.cropper.getCroppedCanvas({ width: 300, height: 300, fillColor: '#fff' }).toDataURL('image/jpeg', 0.9)
      );
      setImageToCrop(''); // 隱藏裁切器
    }
  };

  const cancelCrop = () => {
    setImageToCrop('');
    if (user?.picture) {
      setCroppedImageBase64(user.picture);
      setFileName('使用目前的頭像');
    } else {
      setCroppedImageBase64('');
      setFileName('尚未選擇檔案');
    }
  };

  // ==========================================
  // API 呼叫：儲存與刪除
  // ==========================================
  const saveProfile = async () => {
    if (!newName.trim()) {
      alert('請輸入顯示名稱');
      return;
    }
    
    // 如果還在裁切狀態，自動幫他切下去
    if (imageToCrop) performCrop();

    try {
      const response = await fetch(`${API_BASE_URL}/api/user/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ name: newName, picture: croppedImageBase64 })
      });
      const result = await response.json();
      if (result.success) {
        alert('更新成功！');
        window.location.reload(); // 強制刷新讓 Context 抓到新資料
      } else {
        alert(result.error || '更新失敗');
      }
    } catch (err) {
      console.error(err);
      alert('連線錯誤，請稍後再試');
    }
  };

  const confirmDeleteAccount = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/user/delete`, {
        method: 'POST',
        credentials: 'include'
      });
      const data = await response.json();
      if (data.success) {
        localStorage.removeItem('allChats');
        alert("帳號已成功刪除，後會有期！");
        window.location.href = '/';
      } else {
        alert(data.error || '刪除失敗');
      }
    } catch (error) {
      console.error("Delete failed", error);
      alert('連線錯誤，無法刪除帳號');
    }
  };

  // ==========================================
  // 渲染
  // ==========================================
  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', width: '100%' }}>
      {/* --- 左側欄 --- */}
      <aside className={`sidebar ${isSidebarCollapsed ? 'collapsed' : ''}`}>
        <button className="toggle-sidebar-btn" onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="9" y1="3" x2="9" y2="21"></line></svg>
        </button>
        <button className="user-profile-btn" style={{ borderColor: 'var(--accent-color)', borderWidth: '2px', borderStyle: 'solid' }}>
          <div className="user-avatar" style={{ backgroundColor: user?.picture ? 'transparent' : 'var(--accent-color)' }}>
            {user?.picture ? <img src={user.picture} alt="avatar" style={{width: '100%', borderRadius: '50%'}} /> : 'U'}
          </div>
          <span className="user-name text-label">{user?.name}</span>
        </button>
        <button className="new-chat-btn" onClick={handleNewChat}>
           <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
           <span className="text-label">新增對話</span>
        </button>
        <div className="history-label text-label">對話紀錄</div>
        <div className="chat-list">
           {chats.length === 0 ? <div className="empty-sidebar-msg">尚無對話紀錄</div> : 
             chats.map(chat => (
               <div key={chat.id} className="chat-item" onClick={() => handleSelectChat(chat.id)}>
                 <div className="chat-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg></div>
                 <span className="chat-title text-label">{chat.title}</span>
               </div>
           ))}
        </div>
      </aside>

      {/* --- 主內容區 --- */}
      <main className="main-container">
        <nav className="navbar">
          <Navbar />
        </nav>

        <div className="profile-content">
          {/* 使用者資訊卡片 */}
          <div className="profile-header-card">
            <div className="header-avatar">
               {user?.picture ? <img src={user.picture} alt="Avatar" /> : <div style={{width:'100%', height:'100%', backgroundColor:'var(--accent-color)'}}></div>}
            </div>
            <div className="header-info">
              <div className="header-name">{user?.name}</div>
              <div className="header-email">{user?.email || '未綁定 Email'}</div>
              <div className="profile-actions">
                <button className="btn-edit-profile" onClick={() => setShowEditModal(true)}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg> 編輯個人資料
                </button>
                <button className="btn-logout" onClick={logout}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg> 登出
                </button>
                {user?.is_admin && (
                  <button className="btn-edit-profile" onClick={() => navigate('/admin')} style={{ backgroundColor: 'var(--accent-color)', color: '#fff' }}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"></path><circle cx="12" cy="12" r="3"></circle></svg> 管理後台
                  </button>
                )}
              </div>
              <div style={{ marginTop: '10px' }}>
                <a href="#" onClick={(e) => { e.preventDefault(); setShowDeleteModal(true); }} style={{ color: '#bbb', fontSize: '0.8rem', textDecoration: 'none' }}>註銷帳號 (刪除所有資料)</a>
              </div>
            </div>
          </div>

          {/* 收藏網格 */}
          <div className="section-header">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
            <div className="section-title">我的收藏</div>
          </div>
          <div className="cards-grid">
            {favShops.length === 0 ? <div className="empty-state">尚無紀錄</div> : 
              favShops.map(shop => (
                <div key={shop.id} className="mini-shop-card" onClick={() => navigate(`/explore?open_shop_id=${shop.id}`)}>
                  <div className="mini-img" style={{ backgroundColor: shop.color }}></div>
                  <div className="mini-info">
                    <div className="mini-name">{shop.name}</div><div className="mini-tag">{shop.tags}</div>
                  </div>
                  <span className="mini-badge badge-fav">已收藏</span>
                </div>
              ))}
          </div>

          {/* 已去過網格 */}
          <div className="section-header">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
            <div className="section-title">已去過的店</div>
          </div>
          <div className="cards-grid">
            {visitedShops.length === 0 ? <div className="empty-state">尚無紀錄</div> : 
              visitedShops.map(shop => (
                <div key={shop.id} className="mini-shop-card" onClick={() => navigate(`/explore?open_shop_id=${shop.id}`)}>
                  <div className="mini-img" style={{ backgroundColor: shop.color }}></div>
                  <div className="mini-info">
                    <div className="mini-name">{shop.name}</div><div className="mini-tag">{shop.tags}</div>
                  </div>
                  <span className="mini-badge badge-visited">已去過</span>
                </div>
              ))}
          </div>

          {/* 測驗紀錄 */}
          <div className="section-header">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            <div className="section-title">測驗紀錄</div>
          </div>
          <div className="cards-grid">
             {quizHistory.length === 0 ? <div className="empty-state">尚無測驗紀錄</div> : 
               quizHistory.map((item, i) => (
                 <div key={i} className="result-card">
                   <div className="card-header"><span className="card-date">{item.date}</span></div>
                   <div className="card-coffee-name">{item.resultName}</div>
                   <div className="card-desc">{item.resultDesc}</div>
                   <button className="use-context-btn" onClick={() => handleConsultAI(item)}>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                      以此結果諮詢 AI
                   </button>
                 </div>
               ))
             }
          </div>
        </div>

        {/* --- 編輯資料 Modal --- */}
        <div className={`modal-overlay ${showEditModal ? 'active' : ''}`} onClick={() => setShowEditModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-title">編輯個人資料</div>
            <div className="form-group">
              <label className="form-label">顯示名稱</label>
              <input type="text" className="form-input" value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="請輸入您的暱稱" />
            </div>
            <div className="form-group">
              <label className="form-label">上傳頭像</label>
              <input type="file" id="uploadInput" accept="image/*" style={{ display: 'none' }} onChange={handleFileSelect} />
              
              <div style={{ display: 'flex', alignItems: 'center', gap: '15px', marginBottom: '10px' }}>
                <button type="button" className="btn-upload" onClick={() => document.getElementById('uploadInput').click()}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg> 選擇圖片
                </button>
                <span style={{ fontSize: '0.9rem', color: '#888' }}>{fileName}</span>
              </div>

              {/* 裁切區塊 */}
              {imageToCrop && (
                <>
                  <div style={{ width: '100%', height: '300px', background: '#333', marginBottom: '10px', borderRadius: '8px', overflow: 'hidden' }}>
                    <Cropper
                      src={imageToCrop}
                      style={{ height: 400, width: "100%" }}
                      aspectRatio={1}
                      guides={false}
                      ref={cropperRef}
                      viewMode={1}
                      autoCropArea={0.8}
                      background={false}
                    />
                  </div>
                  <div style={{ display: 'flex', gap: '10px', marginBottom: '15px' }}>
                    <button type="button" className="btn-cancel" style={{ flex: 1 }} onClick={cancelCrop}>取消裁切</button>
                    <button type="button" className="btn-save" style={{ flex: 1, backgroundColor: '#555' }} onClick={performCrop}>確認裁切</button>
                  </div>
                </>
              )}

              {/* 預覽區塊 */}
              {!imageToCrop && croppedImageBase64 && (
                <div style={{ textAlign: 'center' }}>
                  <p style={{ fontSize: '0.8rem', color: '#666', marginBottom: '5px' }}>最終預覽：</p>
                  <img src={croppedImageBase64} style={{ width: '100px', height: '100px', borderRadius: '50%', objectFit: 'cover', border: '2px solid #eee' }} alt="Preview" />
                </div>
              )}
            </div>
            <div className="modal-actions">
              <button className="btn-cancel" onClick={() => setShowEditModal(false)}>取消</button>
              <button className="btn-save" onClick={saveProfile}>儲存變更</button>
            </div>
          </div>
        </div>

        {/* --- 刪除帳號 Modal --- */}
        <div className={`modal-overlay ${showDeleteModal ? 'active' : ''}`} onClick={() => setShowDeleteModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-title" style={{ color: '#d32f2f' }}>確認註銷帳號？</div>
            <p style={{ color: 'var(--text-main)', lineHeight: 1.6, marginBottom: '20px' }}>
              此動作<span style={{ color: '#d32f2f', fontWeight: 'bold' }}>無法復原</span>。<br />將永久刪除您的所有資料，包括收藏店家與測驗紀錄。
            </p>
            <div className="modal-actions">
              <button className="btn-cancel" onClick={() => setShowDeleteModal(false)}>取消</button>
              <button className="btn-save" style={{ backgroundColor: '#d32f2f' }} onClick={confirmDeleteAccount}>確認刪除</button>
            </div>
          </div>
        </div>

      </main>
    </div>
  );
}