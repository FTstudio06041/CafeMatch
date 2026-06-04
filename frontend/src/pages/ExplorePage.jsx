import { useState, useEffect, useContext, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import '../ExplorePage.css';

import { toast } from '../utils/toast';
import { logger } from '../utils/logger';
export default function ExplorePage() {
  const { user, API_BASE_URL } = useContext(AuthContext);
  const [searchParams, setSearchParams] = useSearchParams();

  // 狀態管理
  
  // 探索頁專用狀態
  const [shops, setShops] = useState([]);
  const [currentFilter, setCurrentFilter] = useState('all'); // 'all', 'fav', 'visited'
  const openShopId = searchParams.get('open_shop_id');
  const selectedShop = openShopId ? shops.find(item => String(item.id) === openShopId) || null : null;

  const fetchCafes = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/cafes`, { credentials: 'include' });
      const data = await response.json();
      setShops(data);
    } catch (error) {
      logger.error('Failed to fetch cafes:', error);
    }
  }, [API_BASE_URL]);

  // 1. 初始化：讀取側欄對話紀錄與抓取咖啡廳資料
  useEffect(() => {
    Promise.resolve().then(fetchCafes);
  }, [fetchCafes]);

  // 2. 篩選邏輯 (根據 currentFilter 狀態自動過濾)
  const filteredShops = shops.filter(shop => {
    if (currentFilter === 'fav') return shop.is_fav;
    if (currentFilter === 'visited') return shop.is_visited;
    return true;
  });

  const openShop = (shop) => {
    setSearchParams({ open_shop_id: String(shop.id) });
  };

  const closeShop = () => {
    setSearchParams({});
  };

  const getShopImage = (shop) => shop?.image_url || shop?.image || '';
  const getImageAttribution = (shop) => {
    if (shop?.image_source !== 'google') return '';
    return shop.image_attribution ? `圖片：${shop.image_attribution}` : '圖片：Google Maps';
  };

  // 3. 點擊收藏/去過的 API 呼叫
  const toggleAction = async (type) => {
    if (!selectedShop) return;
    if (user?.isGuest) {
      toast.info("請先登入才能使用此功能！");
      return;
    }

    // 提前鎖定當前操作的店家 ID，避免狀態在非同步過程中錯亂
    const targetId = selectedShop.id;

    try {
      const response = await fetch(`${API_BASE_URL}/api/user/shop_state`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ cafe_id: targetId, type: type })
      });
      const result = await response.json();

      if (result.success) {
        // 修正 1：乾淨地更新所有的 shops 列表 (純函數)
        setShops(prevShops => prevShops.map(shop => {
          if (shop.id === targetId) {
            return {
              ...shop,
              is_fav: type === 'fav' ? result.fav : shop.is_fav,
              is_visited: type === 'visited' ? result.visited : shop.is_visited
            };
          }
          return shop;
        }));

      } else {
        toast.info("請先登入才能使用此功能！");
      }
    } catch (error) {
      logger.error("Error updating state:", error);
    }
  };

  return (
    <>
        <div className={`explore-content ${selectedShop ? 'detail-mode' : ''}`}>
          {selectedShop ? (
            <section className="shop-detail-page">
              <div className="detail-topbar">
                <button className="detail-back-btn" onClick={closeShop}>
                  <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 12H5"></path><path d="M12 19l-7-7 7-7"></path></svg>
                  返回探索
                </button>
                <div className="detail-status">
                  {selectedShop.is_fav && <span className="detail-status-pill fav">已收藏</span>}
                  {selectedShop.is_visited && <span className="detail-status-pill visited">已去過</span>}
                </div>
              </div>

              <div className="detail-hero">
                <div className="detail-hero-info">
                  <div>
                    <div className="detail-tags">{selectedShop.tags}</div>
                    <h1 className="detail-title">{selectedShop.name}</h1>
                    <div className="detail-meta">
                      <span>{selectedShop.rating} ★</span>
                      <span>{selectedShop.hours}</span>
                    </div>

                    <div className="detail-info-panel">
                      <div className="detail-section-title">店家資訊</div>
                      <p className="detail-desc">{selectedShop.desc}</p>

                      <div className="detail-info-list">
                        <div className="detail-info-row">
                          <svg className="info-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg>
                          <span>{selectedShop.phone}</span>
                        </div>
                        <div className="detail-info-row">
                          <svg className="info-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
                          <span>{selectedShop.address}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="detail-actions">
                    <button className={`detail-action-btn btn-fav ${selectedShop.is_fav ? 'active' : ''}`} onClick={() => toggleAction('fav')}>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill={selectedShop.is_fav ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
                      收藏
                    </button>
                    <button className={`detail-action-btn btn-visited ${selectedShop.is_visited ? 'active' : ''}`} onClick={() => toggleAction('visited')}>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                      已去過
                    </button>
                  </div>
                </div>

                <div className="detail-hero-img" style={{ backgroundColor: selectedShop.color }}>
                  {getShopImage(selectedShop) && (
                    <>
                      <img src={getShopImage(selectedShop)} alt={selectedShop.name} onError={(e) => { e.currentTarget.style.display = 'none'; }} />
                      {getImageAttribution(selectedShop) && <div className="image-attribution detail">{getImageAttribution(selectedShop)}</div>}
                    </>
                  )}
                </div>
              </div>

              <div className="detail-body">
                <div className="detail-map-panel">
                  {selectedShop.address && selectedShop.address !== "地址未知" ? (
                    <iframe title={`${selectedShop.name} 地圖`} width="100%" height="100%" frameBorder="0" src={`https://maps.google.com/maps?q=${encodeURIComponent(selectedShop.address)}&t=&z=15&ie=UTF8&iwloc=&output=embed`} allowFullScreen></iframe>
                  ) : selectedShop.map_url ? (
                    <button className="detail-map-link" onClick={() => window.open(selectedShop.map_url, '_blank')}>開啟地圖</button>
                  ) : '尚無地圖資料'}
                </div>
              </div>
            </section>
          ) : (
            <>
              {/* 篩選標籤 */}
              <div className="filter-bar">
                <div className={`filter-chip ${currentFilter === 'all' ? 'active' : ''}`} onClick={() => setCurrentFilter('all')}>全部</div>
                <div className={`filter-chip ${currentFilter === 'fav' ? 'active' : ''}`} onClick={() => setCurrentFilter('fav')}>已收藏</div>
                <div className={`filter-chip ${currentFilter === 'visited' ? 'active' : ''}`} onClick={() => setCurrentFilter('visited')}>已去過</div>
              </div>

              {/* 咖啡廳網格 */}
              <div className="shop-grid">
                {filteredShops.length === 0 ? (
                  <div style={{ gridColumn: '1/-1', textAlign: 'center', marginTop: '50px' }}>沒有符合條件的咖啡廳</div>
                ) : (
                  filteredShops.map(shop => (
                    <div key={shop.id} className={`shop-card ${shop.is_fav ? 'is-fav' : ''} ${shop.is_visited ? 'is-visited' : ''}`} onClick={() => openShop(shop)}>
                      <div className="card-img" style={{ backgroundColor: shop.color }}>
                        {getShopImage(shop) && (
                          <>
                            <img src={getShopImage(shop)} alt={shop.name} onError={(e) => { e.currentTarget.style.display = 'none'; }} />
                            {getImageAttribution(shop) && <div className="image-attribution">{getImageAttribution(shop)}</div>}
                          </>
                        )}
                      </div>
                      <div className="card-status-icons">
                        {shop.is_fav && (
                          <div className="status-dot fav">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="#795548" stroke="#795548" strokeWidth="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
                          </div>
                        )}
                        {shop.is_visited && (
                          <div className="status-dot visited">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#432a00" strokeWidth="3"><polyline points="20 6 9 17 4 12"></polyline></svg>
                          </div>
                        )}
                      </div>
                      <div className="card-info">
                        <div className="shop-name">{shop.name}</div>
                        <div className="shop-tags">{shop.tags}</div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </>
          )}
        </div>
    </>
  );
}
