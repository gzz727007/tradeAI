import { Strategy, BacktestResult, Account, AgentResult } from '../types';

const API_BASE = '/api';

export const api = {
  // 系统与行情
  getSystemStatus: async () => {
    const res = await fetch(`${API_BASE}/system/status`);
    return res.json();
  },

  getMarketQuotes: async (page = 1, pageSize = 20, search = '', sortBy = 'double_low', ascending = true) => {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
      sort_by: sortBy,
      ascending: ascending.toString(),
    });
    if (search) params.append('search', search);
    const res = await fetch(`${API_BASE}/market/quotes?${params}`);
    return res.json();
  },

  // 策略库
  getStrategies: async (): Promise<Strategy[]> => {
    const res = await fetch(`${API_BASE}/strategies`);
    return res.json();
  },

  createStrategy: async (data: { name: string; description: string; category?: string; params: any }) => {
    const res = await fetch(`${API_BASE}/strategies`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      let msg = '创建策略失败';
      try {
        const err = await res.json();
        msg = err.detail || msg;
      } catch {
        msg = await res.text().catch(() => msg);
      }
      throw new Error(msg);
    }
    return res.json();
  },

  updateStrategy: async (id: string, data: { name?: string; description?: string; params?: any }) => {
    const res = await fetch(`${API_BASE}/strategies/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      let msg = '更新策略失败';
      try {
        const err = await res.json();
        msg = err.detail || msg;
      } catch {
        msg = await res.text().catch(() => msg);
      }
      throw new Error(msg);
    }
    return res.json();
  },

  cloneStrategy: async (id: string, newName?: string) => {
    const res = await fetch(`${API_BASE}/strategies/${id}/clone`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_name: newName }),
    });
    if (!res.ok) {
      let msg = '复制策略失败';
      try {
        const err = await res.json();
        msg = err.detail || msg;
      } catch {
        msg = await res.text().catch(() => msg);
      }
      throw new Error(msg);
    }
    return res.json();
  },

  deleteStrategy: async (id: string) => {
    const res = await fetch(`${API_BASE}/strategies/${id}`, { method: 'DELETE' });
    return res.json();
  },

  aiDiscoverStrategy: async (userIdea: string) => {
    const res = await fetch(`${API_BASE}/strategies/ai-discover`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_idea: userIdea }),
    });
    return res.json();
  },

  // 回测对决
  runBacktest: async (
    strategyIds: string[],
    startDate: string,
    endDate?: string,
    rebalanceInterval = 5,
    mode = 'real'
  ): Promise<BacktestResult> => {
    const res = await fetch(`${API_BASE}/backtest/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        strategy_ids: strategyIds,
        start_date: startDate.replace(/-/g, ''),
        end_date: endDate ? endDate.replace(/-/g, '') : undefined,
        rebalance_interval_days: rebalanceInterval,
        mode: mode,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || '回测执行失败');
    }
    return res.json();
  },

  // 账户记账
  getAccounts: async (type?: 'REAL' | 'PAPER'): Promise<Account[]> => {
    const url = type ? `${API_BASE}/accounts?account_type=${type}` : `${API_BASE}/accounts`;
    const res = await fetch(url);
    return res.json();
  },

  refreshAccountsValuation: async () => {
    const res = await fetch(`${API_BASE}/accounts/refresh_valuation`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '刷新估值失败');
    }
    return res.json();
  },

  createAccount: async (data: { account_id: string; account_name: string; associated_strategy: string; account_type: string; initial_capital: number; auto_seed?: boolean }) => {
    const res = await fetch(`${API_BASE}/accounts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || '创建账户失败');
    }
    return res.json();
  },

  // 模拟赛马竞技场专属生命周期控制 API
  getPaperNavHistory: async (accountId: string) => {
    const res = await fetch(`${API_BASE}/paper/accounts/${accountId}/nav_history`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '获取模拟净值时序失败');
    }
    return res.json();
  },

  startPaperAccount: async (accountId: string) => {
    const res = await fetch(`${API_BASE}/paper/accounts/${accountId}/start`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '启动模拟赛马失败');
    }
    return res.json();
  },

  pausePaperAccount: async (accountId: string) => {
    const res = await fetch(`${API_BASE}/paper/accounts/${accountId}/pause`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '暂停模拟赛马失败');
    }
    return res.json();
  },

  endPaperAccount: async (accountId: string) => {
    const res = await fetch(`${API_BASE}/paper/accounts/${accountId}/end`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '结束模拟赛马失败');
    }
    return res.json();
  },

  resetPaperAccount: async (accountId: string) => {
    const res = await fetch(`${API_BASE}/paper/accounts/${accountId}/reset`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '重置模拟账户失败');
    }
    return res.json();
  },

  rebalancePaperAccount: async (accountId: string) => {
    const res = await fetch(`${API_BASE}/paper/accounts/${accountId}/rebalance`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '立即执行调仓失败');
    }
    return res.json();
  },

  seedPaperHistory: async (accountId: string, lookbackDays: number = 60) => {
    const res = await fetch(`${API_BASE}/paper/accounts/${accountId}/seed_history?lookback_days=${lookbackDays}`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '补齐前向轨迹失败');
    }
    return res.json();
  },

  deletePaperAccount: async (accountId: string) => {
    const res = await fetch(`${API_BASE}/paper/accounts/${accountId}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '删除模拟账户失败');
    }
    return res.json();
  },

  recordBuy: async (accountId: string, data: { bond_code: string; bond_name: string; price: number; amount: number; reason?: string }) => {
    const res = await fetch(`${API_BASE}/accounts/${accountId}/buy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || '买入记账失败');
    }
    return res.json();
  },

  recordSell: async (accountId: string, data: { bond_code: string; price: number; amount: number; reason?: string }) => {
    const res = await fetch(`${API_BASE}/accounts/${accountId}/sell`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || '卖出记账失败');
    }
    return res.json();
  },

  // 智能体会诊
  getAgentResult: async (): Promise<AgentResult> => {
    const res = await fetch(`${API_BASE}/agents/result`);
    return res.json();
  },

  runAgents: async (strategyId?: string, chamberId?: string): Promise<AgentResult> => {
    const params = new URLSearchParams();
    if (strategyId && strategyId !== 'default') params.append('strategy_id', strategyId);
    if (chamberId) params.append('chamber_id', chamberId);
    const qs = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/agents/run${qs}`, { method: 'POST' });
    return res.json();
  },

  // 数据湖可视化管理
  getDataLakeOverview: async () => {
    const res = await fetch(`${API_BASE}/datalake/overview`);
    return res.json();
  },

  getDataLakeSymbols: async (category = 'cb', search = '', page = 1, pageSize = 20) => {
    const params = new URLSearchParams({
      category,
      search,
      page: page.toString(),
      page_size: pageSize.toString(),
    });
    const res = await fetch(`${API_BASE}/datalake/symbols?${params}`);
    return res.json();
  },

  previewDataLakeSymbol: async (symbol: string, category = 'cb', limit = 30) => {
    const res = await fetch(`${API_BASE}/datalake/preview/${symbol}?category=${category}&limit=${limit}`);
    return res.json();
  },

  startDataLakeSync: async (action: string = 'incremental_update', symbols?: string[]) => {
    const res = await fetch(`${API_BASE}/datalake/sync`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, symbols }),
    });
    return res.json();
  },

  getDataLakeSyncStatus: async () => {
    const res = await fetch(`${API_BASE}/datalake/sync/status`);
    return res.json();
  },

  resolveDataLakeSymbols: async (symbols: string[], category = 'stock') => {
    const res = await fetch(`${API_BASE}/datalake/resolve_symbols`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbols, category }),
    });
    return res.json();
  },

  // LLM 大模型供应商与 Token 管理
  getLLMConfig: async () => {
    const res = await fetch(`${API_BASE}/llm/config`);
    return res.json();
  },

  saveLLMConfig: async (data: { provider: string; api_key?: string; base_url?: string; model?: string }) => {
    const res = await fetch(`${API_BASE}/llm/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return res.json();
  },

  testLLMConnection: async (data: { provider: string; api_key?: string; base_url?: string; model?: string }) => {
    const res = await fetch(`${API_BASE}/llm/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return res.json();
  },

  // 议事空间与法庭 (Chambers & Multi-Agent Deliberation)
  getChambers: async () => {
    const res = await fetch(`${API_BASE}/chambers`);
    return res.json();
  },

  getAgentTalentPool: async () => {
    const res = await fetch(`${API_BASE}/agents/talent_pool`);
    return res.json();
  },

  saveCustomAgent: async (agentData: any) => {
    const res = await fetch(`${API_BASE}/agents/custom`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(agentData),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '保存智能体失败');
    }
    return res.json();
  },

  deleteCustomAgent: async (agentId: string) => {
    const res = await fetch(`${API_BASE}/agents/custom/${agentId}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '删除智能体失败');
    }
    return res.json();
  },

  // 历史投研报告归档 (Agent Consultation History Archive)
  getAgentReportsHistory: async (): Promise<any[]> => {
    const res = await fetch(`${API_BASE}/agents/history`);
    return res.json();
  },

  getAgentReportDetail: async (id: string): Promise<AgentResult> => {
    const res = await fetch(`${API_BASE}/agents/history/${id}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '获取历史报告详情失败');
    }
    return res.json();
  },

  deleteAgentReport: async (id: string) => {
    const res = await fetch(`${API_BASE}/agents/history/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '删除历史报告失败');
    }
    return res.json();
  },
};



