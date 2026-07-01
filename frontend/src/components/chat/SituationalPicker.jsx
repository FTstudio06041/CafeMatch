import { useState, useEffect, useLayoutEffect, useRef, useContext, useCallback } from 'react';
import { AuthContext } from '../../context/AuthContext';
import { X, ArrowLeft, Check } from 'lucide-react';
import { logger } from '../../utils/logger';
import { Flip } from '../../utils/gsap';
import './SituationalPicker.css';

/**
 * SituationalPicker — chat page 的情境式偏好收集元件。
 *
 * 與 quiz page 的人格測驗不同：此元件不算分、不產生人格結果，
 * 只把使用者「這次想要什麼」收集成結構化情境偏好，透過 onComplete
 * 交給外層送進推薦系統（/api/chat 帶 situational_context）。
 *
 * 產出的 answers 形狀範例：
 *   {
 *     time: 'afternoon',
 *     activity: 'work', companion: 'big_group',
 *     vibe: { score: 3, flavor: 'greenery' },
 *     taste: { score: 1 },
 *     budget: { value: 'cheap' } | { custom: 120 },
 *     special: ['outlet', 'quiet']
 *   }
 */
export default function SituationalPicker({ onComplete, onCancel, flipFromRef }) {
  const { API_BASE_URL } = useContext(AuthContext);

  const [state, setState] = useState('loading'); // 'loading' | 'question' | 'error'
  const [questions, setQuestions] = useState([]);
  const [stepIndex, setStepIndex] = useState(0);
  const [subPhase, setSubPhase] = useState(null); // null | 'followup' | 'flavor'
  const [activeFollowupKey, setActiveFollowupKey] = useState(null);
  const [customBudget, setCustomBudget] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  // answersRef 同步保存最新答案，讓 setTimeout 推進 / 完成時不受 setState 時序影響
  const answersRef = useRef({});
  const [, forceRerender] = useState(0);
  const advancingRef = useRef(false);
  const containerRef = useRef(null);
  const hasFlippedRef = useRef(false);

  useEffect(() => {
    let mounted = true;
    (async () => {
      setState('loading');
      setErrorMsg('');
      try {
        const res = await fetch(`${API_BASE_URL}/api/situational/questions`, { credentials: 'include' });
        if (!res.ok) throw new Error(`伺服器回應錯誤 (${res.status})`);
        const data = await res.json();
        if (!data.questions || data.questions.length === 0) throw new Error('未取得任何題目');
        if (mounted) {
          setQuestions(data.questions);
          setStepIndex(0);
          setSubPhase(null);
          answersRef.current = {};
          setState('question');
        }
      } catch (err) {
        logger.error('取得情境題目失敗：', err);
        if (mounted) {
          setErrorMsg(err.message || '無法取得題目，請稍後再試');
          setState('error');
        }
      }
    })();
    return () => { mounted = false; };
  }, [API_BASE_URL]);

  // 由邀請小卡的實際位置/尺寸「長成」完整題目卡（GSAP Flip），只在第一次進入
  // question 狀態（題目真正就緒）時執行一次；loading 骨架不參與這段幾何轉場。
  useLayoutEffect(() => {
    if (state !== 'question') return;
    if (hasFlippedRef.current) return;
    hasFlippedRef.current = true;
    const flipFrom = flipFromRef?.current;
    if (flipFrom && containerRef.current) {
      Flip.from(flipFrom, {
        targets: containerRef.current,
        duration: 0.45,
        ease: 'power2.out',
        absolute: true,
      });
    }
  }, [state, flipFromRef]);

  // 卡片產生（展開）後，自動把它捲進視野；若卡片太長，頁面會往下捲到底
  // 延遲略長於上面的 Flip 動畫（0.45s），避免捲動與幾何轉場同時發生互相干擾
  useEffect(() => {
    if (state !== 'question') return;
    const t = setTimeout(() => {
      containerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }, 480);
    return () => clearTimeout(t);
  }, [state]);

  const updateAnswers = useCallback((updater) => {
    const next = typeof updater === 'function' ? updater(answersRef.current) : updater;
    answersRef.current = next;
    forceRerender((n) => n + 1);
  }, []);

  const finish = useCallback(() => {
    const final = { ...answersRef.current };
    if (!final.special) final.special = [];
    if (onComplete) onComplete(final);
  }, [onComplete]);

  const goNext = useCallback(() => {
    setSubPhase(null);
    setActiveFollowupKey(null);
    setStepIndex((prev) => {
      if (prev + 1 < questions.length) return prev + 1;
      finish();
      return prev;
    });
  }, [questions.length, finish]);

  const advanceSoon = useCallback(() => {
    if (advancingRef.current) return;
    advancingRef.current = true;
    setTimeout(() => { advancingRef.current = false; goNext(); }, 220);
  }, [goNext]);

  const goBack = () => {
    if (subPhase) { setSubPhase(null); setActiveFollowupKey(null); return; }
    if (stepIndex > 0) { setSubPhase(null); setStepIndex((p) => p - 1); }
  };

  if (state === 'loading') {
    return (
      <div className="sp-container">
        {onCancel && <button className="sp-close-btn" onClick={onCancel}><X size={18} /></button>}
        <div className="sp-status">準備題目中...</div>
      </div>
    );
  }

  if (state === 'error') {
    return (
      <div className="sp-container">
        {onCancel && <button className="sp-close-btn" onClick={onCancel}><X size={18} /></button>}
        <div className="sp-status">
          <p className="sp-error-msg">{errorMsg}</p>
          <button className="sp-cancel-btn" onClick={onCancel}>關閉</button>
        </div>
      </div>
    );
  }

  const q = questions[stepIndex];
  if (!q) return null;
  const answers = answersRef.current;
  const isLast = stepIndex === questions.length - 1;

  const Option = ({ selected, onClick, children }) => (
    <div className={`sp-option ${selected ? 'selected' : ''}`} onClick={onClick}>
      <span className="sp-option-text">{children}</span>
      {selected && <Check size={16} />}
    </div>
  );

  // ---- 各題型的作答區 ----
  const renderBody = () => {
    // 單選（時間）
    if (q.type === 'single_select') {
      return (
        <div className="sp-options">
          {q.options.map((opt) => (
            <Option
              key={opt.value}
              selected={answers[q.id] === opt.value}
              onClick={() => { updateAnswers((a) => ({ ...a, [q.id]: opt.value })); advanceSoon(); }}
            >
              {opt.label}
            </Option>
          ))}
        </div>
      );
    }

    // 單選 + 追問（活動 + 同行）
    if (q.type === 'single_select_with_followup') {
      if (subPhase === 'followup') {
        const fu = (q.followups || {})[activeFollowupKey];
        return (
          <div className="sp-sub">
            <div className="sp-sub-prompt">{fu?.prompt}</div>
            <div className="sp-options">
              {(fu?.options || []).map((fopt) => (
                <Option
                  key={fopt.value}
                  selected={answers.companion === fopt.value}
                  onClick={() => { updateAnswers((a) => ({ ...a, companion: fopt.value })); advanceSoon(); }}
                >
                  {fopt.label}
                </Option>
              ))}
            </div>
          </div>
        );
      }
      return (
        <div className="sp-options">
          {q.options.map((opt) => (
            <Option
              key={opt.value}
              selected={answers[q.id] === opt.value}
              onClick={() => {
                updateAnswers((a) => ({ ...a, [q.id]: opt.value, companion: undefined }));
                if (opt.followup) { setActiveFollowupKey(opt.followup); setSubPhase('followup'); }
                else advanceSoon();
              }}
            >
              {opt.label}
            </Option>
          ))}
        </div>
      );
    }

    // 兩層：0-4 強度 + 風味（氛圍、餐飲）
    if (q.type === 'scale_with_flavor') {
      if (subPhase === 'flavor') {
        const cur = answers[q.id] || {};
        return (
          <div className="sp-sub">
            <div className="sp-sub-prompt">{q.flavor?.prompt}</div>
            <div className="sp-options">
              {(q.flavor?.options || []).map((fopt) => (
                <Option
                  key={fopt.value}
                  selected={cur.flavor === fopt.value}
                  onClick={() => {
                    updateAnswers((a) => ({ ...a, [q.id]: { ...(a[q.id] || {}), flavor: fopt.value } }));
                    advanceSoon();
                  }}
                >
                  {fopt.label}
                </Option>
              ))}
            </div>
          </div>
        );
      }
      const cur = answers[q.id] || {};
      const trigger = q.flavor_trigger_min ?? 2;
      return (
        <div className="sp-options">
          {q.scale.map((s) => (
            <Option
              key={s.value}
              selected={cur.score === s.value}
              onClick={() => {
                updateAnswers((a) => ({ ...a, [q.id]: { score: s.value } }));
                if (s.value >= trigger) setSubPhase('flavor');
                else advanceSoon();
              }}
            >
              {s.label}
            </Option>
          ))}
        </div>
      );
    }

    // 預算：價位帶 + 自訂數字
    if (q.type === 'budget') {
      const budget = answers.budget || {};
      return (
        <div className="sp-options">
          {q.options.map((opt) => (
            <Option
              key={opt.value}
              selected={budget.value === opt.value}
              onClick={() => { updateAnswers((a) => ({ ...a, budget: { value: opt.value } })); advanceSoon(); }}
            >
              {opt.label}
            </Option>
          ))}
          {q.custom_input?.enabled && (
            <div className="sp-custom">
              <span className="sp-custom-label">{q.custom_input.label}</span>
              <div className="sp-custom-row">
                <span className="sp-custom-unit">{q.custom_input.unit || 'NT$'}</span>
                <input
                  type="number"
                  min="1"
                  inputMode="numeric"
                  value={customBudget}
                  onChange={(e) => setCustomBudget(e.target.value)}
                  placeholder="每人預算"
                />
                <button
                  className="sp-custom-btn"
                  disabled={!customBudget || parseInt(customBudget, 10) <= 0}
                  onClick={() => {
                    const n = parseInt(customBudget, 10);
                    if (!n || n <= 0) return;
                    updateAnswers((a) => ({ ...a, budget: { custom: n } }));
                    advanceSoon();
                  }}
                >
                  確定
                </button>
              </div>
            </div>
          )}
        </div>
      );
    }

    // 多選（特殊需求）
    if (q.type === 'multi_select') {
      const picked = answers.special || [];
      const toggle = (value) => {
        updateAnswers((a) => {
          const cur = a.special || [];
          if (value === 'none') return { ...a, special: cur.includes('none') ? [] : ['none'] };
          let next = cur.filter((v) => v !== 'none');
          next = next.includes(value) ? next.filter((v) => v !== value) : [...next, value];
          return { ...a, special: next };
        });
      };
      return (
        <>
          <div className="sp-chips">
            {q.options.map((opt) => (
              <div
                key={opt.value}
                className={`sp-chip ${picked.includes(opt.value) ? 'selected' : ''}`}
                onClick={() => toggle(opt.value)}
              >
                {opt.label}
              </div>
            ))}
          </div>
          <button className="sp-confirm-btn" onClick={() => (isLast ? finish() : goNext())}>
            {isLast ? '完成，幫我推薦' : '下一步'}
          </button>
        </>
      );
    }

    return null;
  };

  const headerPrompt = subPhase === 'followup'
    ? q.prompt
    : (subPhase === 'flavor' ? q.prompt : q.prompt);

  return (
    <div className="sp-container" ref={containerRef}>
      {onCancel && <button className="sp-close-btn" onClick={onCancel}><X size={18} /></button>}

      <div className="sp-content">
        <div className="sp-progress">
          {(stepIndex > 0 || subPhase) && (
            <button className="sp-back-btn" onClick={goBack} aria-label="上一步">
              <ArrowLeft size={16} />
            </button>
          )}
          <span>步驟 {stepIndex + 1} <span className="sp-progress-total">/ {questions.length}</span></span>
        </div>

        {q.title && <div className="sp-title">{q.title}</div>}
        <div className="sp-prompt">{headerPrompt}</div>

        {renderBody()}
      </div>
    </div>
  );
}
