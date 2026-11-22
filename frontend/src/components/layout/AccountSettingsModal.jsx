import { useContext, useRef, useState } from 'react';
import Cropper from 'react-cropper';
import { X } from 'lucide-react';
import { AuthContext } from '../../context/AuthContext';
import { apiClient } from '../../utils/apiClient';
import { toast } from '../../utils/toast';
import { logger } from '../../utils/logger';

const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;

/** 帳號設定：改名、換頭像、刪除帳號（原本在個人頁） */
export default function AccountSettingsModal({ onClose }) {
  const { user, updateUser } = useContext(AuthContext);
  const [name, setName] = useState(user?.name || '');
  const [picture, setPicture] = useState(user?.picture || '');
  const [imageToCrop, setImageToCrop] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [busy, setBusy] = useState(false);
  const cropperRef = useRef(null);
  const fileRef = useRef(null);

  const pickFile = (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    if (file.size > MAX_UPLOAD_BYTES) {
      toast.info('圖片太大囉！請上傳 5MB 以下的圖片。');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setImageToCrop(reader.result);
    reader.readAsDataURL(file);
  };

  const cropNow = () => {
    const cropper = cropperRef.current?.cropper;
    if (!cropper) return picture;
    const result = cropper.getCroppedCanvas({ width: 300, height: 300, fillColor: '#fff' })
      .toDataURL('image/jpeg', 0.9);
    setPicture(result);
    setImageToCrop('');
    return result;
  };

  const save = async () => {
    if (!name.trim()) {
      toast.info('請輸入顯示名稱');
      return;
    }
    // 還在裁切就直接用目前的裁切框
    const finalPicture = imageToCrop ? cropNow() : picture;
    setBusy(true);
    try {
      const result = await apiClient('/api/user/update', {
        method: 'POST',
        body: JSON.stringify({ name: name.trim(), picture: finalPicture }),
      });
      if (result?.success) {
        updateUser({ name: result.name, picture: result.picture });
        toast.success('已更新帳號資料');
        onClose();
      }
    } catch (err) {
      logger.error('更新帳號失敗:', err);
    } finally {
      setBusy(false);
    }
  };

  const deleteAccount = async () => {
    setBusy(true);
    try {
      const result = await apiClient('/api/user/delete', { method: 'POST' });
      if (result?.success) {
        toast.info('帳號已刪除，後會有期！');
        window.location.href = '/';
      }
    } catch (err) {
      logger.error('刪除帳號失敗:', err);
      setBusy(false);
    }
  };

  return (
    <div className="account-overlay" onClick={onClose}>
      <div
        className="account-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="account-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="account-modal-head">
          <h2 id="account-modal-title">帳號設定</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="關閉">
            <X size={20} />
          </button>
        </div>

        {confirmDelete ? (
          <div className="account-danger">
            <p>
              刪除帳號<strong>無法復原</strong>，會永久刪除你的收藏、評論、對話與測驗紀錄。
            </p>
            <div className="account-actions">
              <button type="button" className="btn-secondary" onClick={() => setConfirmDelete(false)} disabled={busy}>取消</button>
              <button type="button" className="btn-danger" onClick={deleteAccount} disabled={busy}>確認刪除帳號</button>
            </div>
          </div>
        ) : (
          <>
            <label className="account-field">
              <span>顯示名稱</span>
              <input type="text" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
            </label>

            <div className="account-field">
              <span>頭像</span>
              <div className="account-avatar-row">
                <span className="account-avatar">
                  {picture ? <img src={picture} alt="目前的頭像" /> : (name || '?').charAt(0)}
                </span>
                <input ref={fileRef} type="file" accept="image/*" hidden onChange={pickFile} />
                <button type="button" className="btn-secondary" onClick={() => fileRef.current?.click()}>選擇圖片</button>
              </div>
              {imageToCrop && (
                <div className="account-cropper">
                  <Cropper
                    src={imageToCrop}
                    style={{ height: 260, width: '100%' }}
                    aspectRatio={1}
                    guides={false}
                    ref={cropperRef}
                    viewMode={1}
                    autoCropArea={0.8}
                    background={false}
                  />
                  <div className="account-actions">
                    <button type="button" className="btn-secondary" onClick={() => setImageToCrop('')}>取消裁切</button>
                    <button type="button" className="btn-primary" onClick={cropNow}>確認裁切</button>
                  </div>
                </div>
              )}
            </div>

            <div className="account-actions">
              <button type="button" className="link-danger" onClick={() => setConfirmDelete(true)}>刪除帳號</button>
              <span className="grow" />
              <button type="button" className="btn-secondary" onClick={onClose}>取消</button>
              <button type="button" className="btn-primary" onClick={save} disabled={busy}>儲存</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
