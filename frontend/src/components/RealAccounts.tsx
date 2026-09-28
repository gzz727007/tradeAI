import React, { useState, useEffect } from 'react';
import { Account, Strategy } from '../types';
import { api } from '../api/client';
import {
  Wallet,
  Plus,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  AlertCircle,
  Briefcase,
  Layers,
  X
} from 'lucide-react';

interface RealAccountsProps {
  strategies: Strategy[];
}

export const RealAccounts: React.FC<RealAccountsProps> = ({ strategies }) => {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selectedAccId, setSelectedAccId] = useState<string>('');
  const [loading, setLoading] = useState(false);

  // New account modal
  const [isNewAccModalOpen, setIsNewAccModalOpen] = useState(false);
  const [newAccId, setNewAccId] = useState('');
  const [newAccName, setNewAccName] = useState('');
  const [newAccStrat, setNewAccStrat] = useState('');
  const [newAccCapital, setNewAccCapital] = useState(20000);

  // Buy form
  const [buyCode, setBuyCode] = useState('');
  const [buyName, setBuyName] = useState('');
  const [buyPrice, setBuyPrice] = useState(100.0);
  const [buyAmount, setBuyAmount] = useState(20);
  const [buyReason, setBuyReason] = useState('跟随策略买入');

  // Sell form
  const [sellCode, setSellCode] = useState('');
  const [sellPrice, setSellPrice] = useState(105.0);
  const [sellAmount, setSellAmount] = useState(10);
  const [sellReason, setSellReason] = useState('达到止盈目标或调仓换出');

  // Feedback messages
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadAccounts = async () => {
    setLoading(true);
    try {
      const data = await api.getAccounts('REAL');
      setAccounts(data);
      if (data.length > 0 && !selectedAccId) {
        setSelectedAccId(data[0].account_id);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAccounts();
  }, []);

  const curAcc = accounts.find((a) => a.account_id === selectedAccId);

  const handleCreateAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAccId.trim() || !newAccName.trim()) return;
    try {
      await api.createAccount({
        account_id: newAccId.trim(),
        account_name: newAccName.trim(),
        associated_strategy: newAccStrat || (strategies[0]?.name || '经典双低轮动策略'),
        account_type: 'REAL',
        initial_capital: newAccCapital,
      });
      setIsNewAccModalOpen(false);
      setNewAccId('');
      setNewAccName('');
      loadAccounts();
      setMessage({ type: 'success', text: `✅ 实盘账户【${newAccName}】创建成功！` });
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '创建账户失败' });
    }
  };

  const handleBuy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!curAcc) return;
    try {
      await api.recordBuy(curAcc.account_id, {
        bond_code: buyCode.trim(),
        bond_name: buyName.trim(),
        price: buyPrice,
        amount: buyAmount,
        reason: buyReason,
      });
      loadAccounts();
      setMessage({ type: 'success', text: `✅ 成功记录买入 ${buyName} (${buyCode}) ${buyAmount}张！` });
      setBuyCode('');
      setBuyName('');
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '买入失败' });
    }
  };

  const handleSell = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!curAcc || !sellCode) return;
    try {
      await api.recordSell(curAcc.account_id, {
        bond_code: sellCode,
        price: sellPrice,
        amount: sellAmount,
        reason: sellReason,
      });
      loadAccounts();
      setMessage({ type: 'success', text: `✅ 成功记录卖出 ${sellCode} ${sellAmount}张！` });
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || '卖出失败' });
    }
  };

  return (
    <div className="space-y-4">
      {/* Introduction Card */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Wallet className="w-5 h-5 text-emerald-600" />
            <h3 className="font-bold text-sm text-slate-900">
              我的实盘多账号管家 (分策略、多账号独立记账)
            </h3>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            散户半自动跟单神器：你在券商 App 手机上点一下买卖，这里记一笔。系统自动 7x24 小时核算真实净值，专属 AI 盯盘排雷！
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Account Selector */}
          <select
            value={selectedAccId}
            onChange={(e) => setSelectedAccId(e.target.value)}
            className="text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 font-semibold text-slate-800 focus:outline-hidden"
          >
            {accounts.map((a) => (
              <option key={a.account_id} value={a.account_id}>
                🏦 {a.account_name}
              </option>
            ))}
          </select>

          <button
            onClick={() => setIsNewAccModalOpen(true)}
            className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-3 py-1.5 rounded-lg shadow-xs transition-colors cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>新增实盘账户</span>
          </button>
        </div>
      </div>

      {message && (
        <div
          className={`p-3 rounded-lg text-xs flex items-center justify-between border ${
            message.type === 'success'
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : 'bg-rose-50 text-rose-700 border-rose-200'
          }`}
        >
          <div className="flex items-center gap-2">
            {message.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 shrink-0" />
            )}
            <span>{message.text}</span>
          </div>
          <button onClick={() => setMessage(null)} className="p-0.5 hover:opacity-75">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {curAcc && (
        <div className="space-y-4">
          {/* Top 4 Account Balance Cards */}
          {(() => {
            const latestNav = curAcc.nav_history[curAcc.nav_history.length - 1];
            const profitPct = Math.round((latestNav.nav - 1.0) * 10000) / 100;
            const marketVal = latestNav.total_assets - curAcc.available_cash;

            return (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
                  <div className="text-[11px] text-slate-500 font-medium">账户总资产</div>
                  <div className="text-lg font-bold text-slate-900 mt-1">
                    ¥ {latestNav.total_assets.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
                  </div>
                  <div className={`text-xs font-semibold mt-0.5 ${profitPct >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                    {profitPct >= 0 ? '+' : ''}{profitPct}% (真实净值: {latestNav.nav.toFixed(4)})
                  </div>
                </div>

                <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
                  <div className="text-[11px] text-slate-500 font-medium">可用现金</div>
                  <div className="text-lg font-bold text-slate-900 mt-1">
                    ¥ {curAcc.available_cash.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
                  </div>
                  <div className="text-xs text-slate-400 mt-0.5">随时可用于买入新标的</div>
                </div>

                <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
                  <div className="text-[11px] text-slate-500 font-medium">持仓转债市值</div>
                  <div className="text-lg font-bold text-slate-900 mt-1">
                    ¥ {marketVal.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
                  </div>
                  <div className="text-xs text-slate-400 mt-0.5">
                    共持仓 {Object.keys(curAcc.positions).length} 只品种
                  </div>
                </div>

                <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
                  <div className="text-[11px] text-slate-500 font-medium">绑定跟随策略</div>
                  <div className="text-base font-bold text-slate-900 mt-1 truncate">
                    {curAcc.associated_strategy}
                  </div>
                  <div className="text-xs text-emerald-600 font-semibold mt-0.5">
                    AI 专属盯盘风控中
                  </div>
                </div>
              </div>
            );
          })()}

          {/* Current Real Positions Table */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
              <span className="font-bold text-xs text-slate-800 flex items-center gap-1.5">
                <Briefcase className="w-4 h-4 text-emerald-600" />
                <span>当前实盘真实持仓清单</span>
              </span>
              <span className="text-[11px] text-slate-500">
                实时自动市值重估
              </span>
            </div>

            {Object.keys(curAcc.positions).length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
                    <tr>
                      <th className="py-2.5 px-4">转债代码</th>
                      <th className="py-2.5 px-4">转债名称</th>
                      <th className="py-2.5 px-4">买入均价</th>
                      <th className="py-2.5 px-4">最新市价</th>
                      <th className="py-2.5 px-4">持仓张数</th>
                      <th className="py-2.5 px-4">持仓市值 (元)</th>
                      <th className="py-2.5 px-4">浮动盈亏 (%)</th>
                      <th className="py-2.5 px-4">建仓日期</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {Object.values(curAcc.positions).map((pos) => {
                      const profitRate = pos.profit_rate || 0;
                      return (
                        <tr key={pos.bond_code} className="hover:bg-slate-50/50">
                          <td className="py-2.5 px-4 font-mono font-semibold text-slate-700">{pos.bond_code}</td>
                          <td className="py-2.5 px-4 font-bold text-slate-800">{pos.bond_name}</td>
                          <td className="py-2.5 px-4 text-slate-600">¥{pos.avg_price?.toFixed(2)}</td>
                          <td className="py-2.5 px-4 text-slate-800 font-semibold">¥{pos.current_price?.toFixed(2)}</td>
                          <td className="py-2.5 px-4 text-slate-600">{pos.amount} 张</td>
                          <td className="py-2.5 px-4 font-semibold text-slate-800">
                            ¥{pos.market_value?.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
                          </td>
                          <td className="py-2.5 px-4 font-bold">
                            <span
                              className={`px-2 py-0.5 rounded text-[11px] ${
                                profitRate >= 0
                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                  : 'bg-rose-50 text-rose-700 border border-rose-200'
                              }`}
                            >
                              {profitRate >= 0 ? '+' : ''}{profitRate.toFixed(2)}%
                            </span>
                          </td>
                          <td className="py-2.5 px-4 text-slate-400">{pos.buy_date || '-'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-8 text-center text-slate-400 text-xs">
                <Briefcase className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                <p>该实盘账号暂无持仓记录。可在下方录入你在券商 App 实际成交的买入单！</p>
              </div>
            )}
          </div>

          {/* Trade Execution Tickets (Buy & Sell) */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Buy Form */}
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
              <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 mb-3 border-b border-slate-100 pb-2">
                <ArrowDownRight className="w-4 h-4 text-emerald-600" />
                <span>✍️ 记一笔【买入成交】(券商 App 买入后同步)</span>
              </div>
              <form onSubmit={handleBuy} className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">转债代码:</label>
                    <input
                      type="text"
                      required
                      placeholder="如 123112"
                      value={buyCode}
                      onChange={(e) => setBuyCode(e.target.value)}
                      className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">转债名称:</label>
                    <input
                      type="text"
                      required
                      placeholder="如 万讯转债"
                      value={buyName}
                      onChange={(e) => setBuyName(e.target.value)}
                      className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">成交单价 (元):</label>
                    <input
                      type="number"
                      step="0.01"
                      required
                      value={buyPrice}
                      onChange={(e) => setBuyPrice(Number(e.target.value))}
                      className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">买入张数 (1手=10张):</label>
                    <input
                      type="number"
                      step="10"
                      required
                      value={buyAmount}
                      onChange={(e) => setBuyAmount(Number(e.target.value))}
                      className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">买入理由:</label>
                  <input
                    type="text"
                    value={buyReason}
                    onChange={(e) => setBuyReason(e.target.value)}
                    className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5"
                  />
                </div>
                <button
                  type="submit"
                  className="w-full bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold py-2 rounded-lg shadow-xs transition-colors cursor-pointer"
                >
                  💾 确认记录买入
                </button>
              </form>
            </div>

            {/* Sell Form */}
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
              <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 mb-3 border-b border-slate-100 pb-2">
                <ArrowUpRight className="w-4 h-4 text-rose-600" />
                <span>✍️ 记一笔【卖出成交】(券商 App 卖出后同步)</span>
              </div>
              <form onSubmit={handleSell} className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div className="col-span-2">
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">选择卖出持仓转债:</label>
                    <select
                      value={sellCode}
                      onChange={(e) => setSellCode(e.target.value)}
                      className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5"
                    >
                      <option value="">-- 选择持仓标的 --</option>
                      {Object.values(curAcc.positions).map((pos) => (
                        <option key={pos.bond_code} value={pos.bond_code}>
                          {pos.bond_name} ({pos.bond_code}) · 现持仓 {pos.amount} 张
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">卖出单价 (元):</label>
                    <input
                      type="number"
                      step="0.01"
                      required
                      value={sellPrice}
                      onChange={(e) => setSellPrice(Number(e.target.value))}
                      className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">卖出张数:</label>
                    <input
                      type="number"
                      step="10"
                      required
                      value={sellAmount}
                      onChange={(e) => setSellAmount(Number(e.target.value))}
                      className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">卖出理由:</label>
                  <input
                    type="text"
                    value={sellReason}
                    onChange={(e) => setSellReason(e.target.value)}
                    className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5"
                  />
                </div>
                <button
                  type="submit"
                  disabled={!sellCode}
                  className="w-full bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold py-2 rounded-lg shadow-xs transition-colors cursor-pointer disabled:opacity-50"
                >
                  💾 确认记录卖出
                </button>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Modal: 新增实盘账户 */}
      {isNewAccModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full border border-slate-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
              <div className="font-bold text-sm text-slate-900 flex items-center gap-2">
                <Wallet className="w-4 h-4 text-emerald-600" />
                <span>➕ 登记新的实盘账户</span>
              </div>
              <button
                onClick={() => setIsNewAccModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateAccount} className="p-5 space-y-3.5">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">账号唯一 ID (如 huatai_01):</label>
                <input
                  type="text"
                  required
                  placeholder="huatai_01"
                  value={newAccId}
                  onChange={(e) => setNewAccId(e.target.value)}
                  className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">账号备注名称 (如 华泰证券-低溢价稳健仓):</label>
                <input
                  type="text"
                  required
                  placeholder="如: 华泰证券-双低轮动仓"
                  value={newAccName}
                  onChange={(e) => setNewAccName(e.target.value)}
                  className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">绑定的量化策略:</label>
                <select
                  value={newAccStrat}
                  onChange={(e) => setNewAccStrat(e.target.value)}
                  className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800"
                >
                  {strategies.map((s) => (
                    <option key={s.id} value={s.name}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">初始资金 (元):</label>
                <input
                  type="number"
                  step="1000"
                  min="1000"
                  value={newAccCapital}
                  onChange={(e) => setNewAccCapital(Number(e.target.value))}
                  className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800"
                />
              </div>

              <div className="pt-2 flex justify-end gap-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsNewAccModalOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-xs"
                >
                  确认创建并保存
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
