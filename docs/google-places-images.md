# Google Places 店家圖片設定

探索頁現在會優先顯示店家手動上傳的 `cafes.image`，如果沒有手動圖片，後端會透過 Google Places API 取得店家照片。

## 需要的環境變數

在專案根目錄的 `.env` 加入：

```env
GOOGLE_MAPS_API_KEY=你的 Google Maps Platform API key
```

## Google Cloud 需要啟用

- Maps JavaScript API 不需要給這個功能使用
- 需要啟用 Places API
- API key 建議限制可用 API 為 Places API
- 若部署到正式環境，也建議限制後端伺服器來源

## 行為說明

- `/api/cafes` 會回傳 `image_url`、`image_source`、`image_attribution`
- 沒有手動圖片時，`image_url` 會指向 `/api/cafes/<id>/photo`
- 第一次開圖時，後端會用店名和地址找 Google place id，並存入 `cafes.google_place_id`
- 若管理員修改店名或地址，後端會清掉舊的 `google_place_id`，下次會重新配對
- 如果沒有設定 `GOOGLE_MAPS_API_KEY`，頁面會維持原本色塊 fallback
