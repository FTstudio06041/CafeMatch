import { Component } from 'react';

/**
 * 全域錯誤邊界。
 *
 * 沒有它的話，render 階段（含 lazy chunk 載入失敗）只要拋出一個未捕捉的例外，
 * React 會把整棵樹卸載 —— 畫面變成全白、只剩 body 底色，連 Suspense 的
 * 「載入頁面中...」都不會出現，也沒有任何線索可查。
 *
 * 常見觸發原因是 Vite dev 的模組 URL 過期：瀏覽器快取到舊的 ?v= hash 時，
 * 該模組會回 504（不是 404，瀏覽器不會自動重試），於是 lazy import 失敗。
 * 這種情況下清掉快取重新載入就會好，所以下面直接給使用者這個按鈕。
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary] 未捕捉的錯誤：', error, info?.componentStack);
  }

  handleHardReload = () => {
    // 帶上時間戳強制略過快取，順手清掉可能損毀的本機狀態
    try {
      sessionStorage.clear();
    } catch {
      // 隱私模式下可能不給存取，忽略
    }
    window.location.replace(`${window.location.pathname}?_r=${Date.now()}`);
  };

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div style={{
        padding: '2rem',
        maxWidth: 760,
        margin: '0 auto',
        fontFamily: 'system-ui, "Microsoft JhengHei", sans-serif',
        lineHeight: 1.7,
      }}>
        <h1 style={{ fontSize: 20, marginBottom: 8 }}>頁面載入失敗</h1>
        <p style={{ color: '#7d6c59', marginTop: 0 }}>
          先試「重新載入（清快取）」。若反覆出現，請把下面的訊息回報給開發者。
        </p>
        <button
          onClick={this.handleHardReload}
          style={{
            font: 'inherit', fontWeight: 700, cursor: 'pointer',
            border: '1px solid #432a00', background: '#432a00', color: '#fff',
            borderRadius: 999, padding: '10px 22px', margin: '8px 0 20px',
          }}
        >
          重新載入（清快取）
        </button>
        <pre style={{
          background: '#f6f1e8',
          border: '1px solid #e7ddcf',
          borderRadius: 8,
          padding: '12px 14px',
          overflowX: 'auto',
          fontSize: 13,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}>
          {error?.message || String(error)}
          {error?.stack ? `\n\n${error.stack}` : ''}
        </pre>
      </div>
    );
  }
}
