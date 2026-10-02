import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import {
  ShieldCheck, RefreshCw, Gavel, PlayCircle, AlertTriangle,
  CheckCircle2, EyeOff, XCircle, Clock, Zap
} from 'lucide-react';

interface CommitteeDecision {
  id: number;
  trade_date: string;
  stage: string;
  bond_code: string;
  bond_name: string;
  decision: string;
  reason: string;
  created_at: string;
}

interface CommitteePlan {
  id: number;
  bond_code: string;
  bond_name: string;
  action: string;
  buy_limit_price: number | null;
  sell_limit_price: number | null;
  prev_close: number | null;
  current_price: number | null;
  ai_priced: boolean;
  status: string;
  reason: string;
  stage: string;
  updated_at: string;
}

interface CommitteeState {
  bound_strategy: string;
  auto_execute: boolean;
  enabled: boolean;
  last_gate_date: string;
  last_midday_date: string;
  last_refresh_at: string;
  last_execute_date: string;
}

const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-slate-100 text-slate-600',
  executable: 'bg-emerald-100 text-emerald-700',
  missed: 'bg-amber-100 text-amber-700',
  alert: 'bg-red-100 text-red-700',
  expired: 'bg-slate-100 text-slate-400',
};

const STATUS_LABELS: Record<string, string> = {
  pending: '待触发',
  executable: '可成交',
  missed: '已错过',
  alert: '警示',
  expired: '已收盘',
};

const DECISION_BADGES: Record<string, { icon: any; cls: string; label: string }> = {
  approve: { icon: CheckCircle2, cls: 'bg-emerald-100 text-emerald-700', label: '准入' },
  watch: { icon: EyeOff, cls: 'bg-amber-100 text-amber-700', label: '观察(禁新买)' },
  reject: { icon: XCircle, cls: 'bg-red-100 text-red-700', label: '否决' },
};

export function TradingCommittee() {
  const [state, setState] = useState<CommitteeState | null>(null);
  const [schedulerRunning, setSchedulerRunning] = useState(false);
  const [decisions, setDecisions] = useState<CommitteeDecision[]>([]);
  const [plans, setPlans] = useState<CommitteePlan[]>([]);
  const [tradeDate, setTradeDate] = useState('');
  const [busy, setBusy] = useState<string>('');
  const [message, setMessage] = useState<{ type: 'ok' | 'warn' | 'err'; text: string } | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.getCommitteeToday();
      setState(data.state);
      setSchedulerRunning(data.scheduler_running);
      setDecisions(data.decisions || []);
      setPlans(data.plans || []);
      setTradeDate(data.trade_date);
    } catch (err: any) {
      setMessage({ type: 'err', text: err.message || '加载失败' });
    }
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 60000); // 每60秒轻量刷新
    return () => clearInterval(timer);
  }, [load]);

  const runAction = async (key: string, fn: () => Promise<any>, okText: (r: any) => string) => {
    setBusy(key);
    setMessage(null);
    try {
      const r = await fn();
      if (r.success === false) {
        setMessage({ type: 'warn', text: r.message || '执行未成功' });
      } else {
        setMessage({ type: 'ok', text: okText(r) });
      }
      await load();
    } catch (err: any) {
      setMessage({ type: 'err', text: err.message || '请求失败 (LLM 调用可能超时, 可重试)' });
    } finally {
      setBusy('');
    }
  };

  const toggleAuto = async () => {
    if (!state) return;
    const next = !state.auto_execute;
    if (next) {
      const confirmed = window.confirm(
        '【全自动执行】开启后:\n委员会审查+定价完成将直接触发调仓, 交易程序严格按 AI 限价执行, 无需人工确认。\n确定开启?'
      );
      if (!confirmed) return;
    }
    const s = await api.updateCommitteeSettings({ auto_execute: next });
    setState({ ...state, ...s });
  };

  const approvedCount = decisions.filter((d) => d.decision === 'approve').length;
  const watchCount = decisions.filter((d) => d.decision === 'watch').length;
  const rejectedCount = decisions.filter((d) => d.decision === 'reject').length;
  const alerts = plans.filter((p) => p.status === 'alert');

  return (
    <div className="space-y-4">
      {/* 顶部控制台 */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-600 flex items-center justify-center">
              <Gavel className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-800">AI 交易委员会</h2>
              <p className="text-xs text-slate-500">
                {tradeDate || '—'} · 盘前准入 → 约束式定价 → 盘中刷新 → 按限价执行
                {schedulerRunning && <span className="ml-2 text-emerald-600">● 调度运行中</span>}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => runAction('gate', () => api.runCommitteePremarket(),
                (r) => `盘前准入完成: 准入${r.approved?.length || 0} / 观察${r.watch?.length || 0} / 否决${r.rejected?.length || 0}`)}
              disabled={!!busy}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 disabled:opacity-50 cursor-pointer"
            >
              <ShieldCheck className={`w-4 h-4 ${busy === 'gate' ? 'animate-spin' : ''}`} />
              盘前准入
            </button>
            <button
              onClick={() => runAction('midday', () => api.runCommitteeMidday(),
                (r) => `午间复检完成${r.holding_alerts?.length ? `, ${r.holding_alerts.length} 条持仓警示` : ''}`)}
              disabled={!!busy}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-slate-700 text-white text-xs font-semibold hover:bg-slate-800 disabled:opacity-50 cursor-pointer"
            >
              <RefreshCw className={`w-4 h-4 ${busy === 'midday' ? 'animate-spin' : ''}`} />
              午间复检
            </button>
            <button
              onClick={() => runAction('refresh', () => api.refreshCommitteePrices(),
                (r) => `价格刷新完成: 更新 ${r.updated} 条计划`)}
              disabled={!!busy}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-700 text-xs font-semibold hover:bg-slate-50 disabled:opacity-50 cursor-pointer"
            >
              <Clock className={`w-4 h-4 ${busy === 'refresh' ? 'animate-spin' : ''}`} />
              刷新价格
            </button>
            <button
              onClick={() => runAction('exec', () => api.executeCommitteeNow(),
                (r) => `已按计划执行调仓 ${r.count} 个账号`)}
              disabled={!!busy}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-emerald-600 text-white text-xs font-semibold hover:bg-emerald-700 disabled:opacity-50 cursor-pointer"
            >
              <PlayCircle className={`w-4 h-4 ${busy === 'exec' ? 'animate-spin' : ''}`} />
              立即执行
            </button>
            <button
              onClick={toggleAuto}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold cursor-pointer border transition-all ${
                state?.auto_execute
                  ? 'bg-emerald-50 border-emerald-300 text-emerald-700'
                  : 'bg-white border-slate-300 text-slate-500 hover:bg-slate-50'
              }`}
            >
              <Zap className="w-4 h-4" />
              全自动执行: {state?.auto_execute ? '开' : '关'}
            </button>
          </div>
        </div>

        {/* 运行水位 */}
        {state && (
          <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-500 border-t border-slate-100 pt-3">
            <span>最近准入: <b className="text-slate-700">{state.last_gate_date || '未运行'}</b></span>
            <span>最近复检: <b className="text-slate-700">{state.last_midday_date || '未运行'}</b></span>
            <span>最近刷新: <b className="text-slate-700">{state.last_refresh_at || '未运行'}</b></span>
            <span>绑定策略: <b className="text-slate-700">{state.bound_strategy || '默认双低轮动'}</b></span>
            <span className="text-slate-400">约束: 买入≤昨收×1.02 · 卖出≥昨收×0.98 · 每30分钟刷新</span>
          </div>
        )}

        {message && (
          <div className={`mt-3 text-xs px-3 py-2 rounded-lg ${
            message.type === 'ok' ? 'bg-emerald-50 text-emerald-700'
            : message.type === 'warn' ? 'bg-amber-50 text-amber-700'
            : 'bg-red-50 text-red-700'}`}>
            {message.text}
          </div>
        )}
      </div>

      {/* 持仓警示横幅 */}
      {alerts.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-3 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-red-600 mt-0.5 shrink-0" />
          <div className="text-xs text-red-700 space-y-0.5">
            <div className="font-bold">持仓警示 ({alerts.length})</div>
            {alerts.map((a) => (
              <div key={a.id}>{a.bond_name}({a.bond_code}) 现价 {a.current_price?.toFixed(2)} — {a.reason}</div>
            ))}
          </div>
        </div>
      )}

      {/* 统计条 */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: '准入交易池', value: approvedCount, cls: 'text-emerald-600' },
          { label: '观察(禁新买)', value: watchCount, cls: 'text-amber-600' },
          { label: '否决出局', value: rejectedCount, cls: 'text-red-600' },
          { label: '限价计划', value: plans.length, cls: 'text-blue-600' },
        ].map((s) => (
          <div key={s.label} className="bg-white rounded-xl border border-slate-200 shadow-xs p-3">
            <div className={`text-2xl font-bold ${s.cls}`}>{s.value}</div>
            <div className="text-xs text-slate-500">{s.label}</div>
          </div>
        ))}
      </div>

      {/* 价格计划表 */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-800">今日限价交易计划</h3>
          <span className="text-xs text-slate-400">交易程序严格按 AI 限价撮合, 越界挂单等待不追价</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-slate-500 bg-slate-50 text-left">
                <th className="px-3 py-2 font-semibold">标的</th>
                <th className="px-3 py-2 font-semibold">动作</th>
                <th className="px-3 py-2 font-semibold">买入限价</th>
                <th className="px-3 py-2 font-semibold">卖出限价</th>
                <th className="px-3 py-2 font-semibold">昨收</th>
                <th className="px-3 py-2 font-semibold">现价</th>
                <th className="px-3 py-2 font-semibold">状态</th>
                <th className="px-3 py-2 font-semibold">定价理由</th>
                <th className="px-3 py-2 font-semibold">更新</th>
              </tr>
            </thead>
            <tbody>
              {plans.length === 0 && (
                <tr><td colSpan={9} className="px-3 py-8 text-center text-slate-400">暂无计划 — 点击「盘前准入」生成</td></tr>
              )}
              {plans.map((p) => {
                const dec = DECISION_BADGES[decisions.find((d) => d.bond_code === p.bond_code)?.decision || ''];
                return (
                  <tr key={p.id} className="border-t border-slate-50 hover:bg-slate-50/60">
                    <td className="px-3 py-2">
                      <div className="font-semibold text-slate-800">{p.bond_name}</div>
                      <div className="text-slate-400">{p.bond_code}</div>
                    </td>
                    <td className="px-3 py-2">
                      <span className={`px-2 py-0.5 rounded font-semibold ${
                        p.action === 'BUY' ? 'bg-red-100 text-red-700'
                        : p.action === 'SELL' ? 'bg-emerald-100 text-emerald-700'
                        : 'bg-slate-100 text-slate-600'}`}>
                        {p.action === 'BUY' ? '买入' : p.action === 'SELL' ? '卖出' : '持有'}
                      </span>
                      {dec && <span className={`ml-1 px-1.5 py-0.5 rounded text-[10px] ${dec.cls}`}>{dec.label}</span>}
                    </td>
                    <td className="px-3 py-2 font-mono">{p.buy_limit_price ? p.buy_limit_price.toFixed(3) : '—'}</td>
                    <td className="px-3 py-2 font-mono">{p.sell_limit_price ? p.sell_limit_price.toFixed(3) : '—'}</td>
                    <td className="px-3 py-2 font-mono text-slate-500">{p.prev_close ? p.prev_close.toFixed(2) : '—'}</td>
                    <td className="px-3 py-2 font-mono font-bold text-slate-800">{p.current_price ? p.current_price.toFixed(2) : '—'}</td>
                    <td className="px-3 py-2">
                      <span className={`px-2 py-0.5 rounded font-semibold ${STATUS_STYLES[p.status] || 'bg-slate-100'}`}>
                        {STATUS_LABELS[p.status] || p.status}
                      </span>
                      {!p.ai_priced && (
                        <span className="ml-1 px-1.5 py-0.5 rounded text-[10px] bg-amber-100 text-amber-700">模拟</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-slate-600 max-w-xs truncate" title={p.reason}>{p.reason}</td>
                    <td className="px-3 py-2 text-slate-400 whitespace-nowrap">{p.updated_at?.split(' ')[1] || ''}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 准入决策表 */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-100">
          <h3 className="text-sm font-bold text-slate-800">准入审查决策 (信用排雷 / 条款博弈 / 正股动量)</h3>
        </div>
        <div className="divide-y divide-slate-50">
          {decisions.length === 0 && (
            <div className="px-4 py-8 text-center text-xs text-slate-400">暂无审查记录</div>
          )}
          {decisions.map((d) => {
            const dec = DECISION_BADGES[d.decision] || DECISION_BADGES.watch;
            const Icon = dec.icon;
            return (
              <div key={d.id} className="px-4 py-2.5 flex items-start gap-3 hover:bg-slate-50/60">
                <span className={`flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold shrink-0 ${dec.cls}`}>
                  <Icon className="w-3 h-3" />{dec.label}
                </span>
                <div className="min-w-0">
                  <div className="text-xs">
                    <b className="text-slate-800">{d.bond_name}</b>
                    <span className="text-slate-400 ml-1">{d.bond_code}</span>
                    <span className="text-slate-300 ml-2">
                      {d.stage === 'premarket' ? '盘前' : d.stage === 'midday' ? '午间复检' : '手动'} · {d.created_at?.split(' ')[1]}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">{d.reason}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
