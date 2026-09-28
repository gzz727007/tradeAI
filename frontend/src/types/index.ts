export interface StrategyParams {
  min_price: number;
  max_price: number;
  max_scale: number;
  max_premium: number;
  double_low_weight: number;
  top_n: number;
  sort_by: string;
  sort_ascending: boolean;
}

export interface Strategy {
  id: string;
  name: string;
  category: string;
  description: string;
  params: StrategyParams;
  created_at?: string;
}

export interface BacktestResult {
  dates: string[];
  nav_series: Record<string, number[]>;
  drawdown_series: Record<string, number[]>;
  metrics_summary: Record<string, {
    cagr: number;
    max_drawdown: number;
    sharpe_ratio: number;
    calmar_ratio: number;
    annual_volatility: number;
    total_return: number;
  }>;
}

export interface PositionItem {
  bond_code: string;
  bond_name: string;
  avg_price: number;
  current_price: number;
  amount: number;
  market_value: number;
  profit_rate: number;
  buy_date?: string;
  buy_reason?: string;
}

export interface Account {
  account_id: string;
  account_name: string;
  associated_strategy: string;
  account_type: 'REAL' | 'PAPER';
  initial_capital: number;
  available_cash: number;
  total_asset?: number;
  status?: string;
  created_at?: string;
  positions: Record<string, PositionItem>;
  trade_history?: any[];
  history_trades?: Array<{
    order_id: string;
    trade_time: string;
    action: 'BUY' | 'SELL';
    bond_code: string;
    bond_name: string;
    price: number;
    amount: number;
    fee: number;
    reason: string;
  }>;
  nav_history: Array<{
    date: string;
    nav: number;
    total_assets: number;
    benchmark_nav?: number;
    portfolio_return?: number;
    benchmark_return?: number;
    excess_return?: number;
  }>;
}

export interface PaperNavHistoryResponse {
  account: {
    account_id: string;
    account_name: string;
    account_type: string;
    associated_strategy: string;
    initial_capital: number;
    available_cash: number;
    total_asset: number;
    status: string;
    created_at: string;
  };
  curve_data: Array<{
    date: string;
    total_assets: number;
    nav: number;
    benchmark_nav: number;
    portfolio_return: number;
    benchmark_return: number;
    excess_return: number;
  }>;
  metrics: {
    total_return: number;
    benchmark_return: number;
    excess_return: number;
    annual_return: number;
    max_drawdown: number;
    sharpe_ratio: number;
    win_rate: number;
    total_trades: number;
    rebalance_count: number;
    trading_days: number;
  };
  positions: PositionItem[];
  history_trades: Array<{
    order_id: string;
    trade_time: string;
    action: 'BUY' | 'SELL';
    bond_code: string;
    bond_name: string;
    price: number;
    amount: number;
    fee: number;
    reason: string;
  }>;
}

export interface CandidateBond {
  bond_code: string;
  bond_name: string;
  price: number;
  premium_rate: number;
  double_low: number;
  remaining_scale: number;
  rating: string;
}

export interface AgentModelMeta {
  role: string;
  provider: string;
  provider_name: string;
  model: string;
  is_llm: boolean;
  label: string;
}

export interface AgentSpeech {
  speech_id?: string;
  speaker_id: string;
  speaker_name: string;
  avatar: string;
  role_type?: string;
  speaker_role?: string;
  model_used: string;
  stance: string; // BULL / BEAR / VETO / PASS / JUDGEMENT
  score?: number;
  vote_score?: number;
  verdict?: string; // REJECT / WATCH / ACQUIT_BUY
  statement: string; // 智能体发言实录全文
  key_evidence: string[]; // 核心依据清单
  timestamp: string;
}

export interface MeetingChamber {
  id: string;
  name: string;
  chamber_type: 'ROUNDTABLE' | 'COURTROOM';
  target_asset: string;
  description: string;
  icon: string;
  agent_ids: string[];
  is_active: boolean;
  sort_order: number;
}

export interface AgentDefinition {
  id: string;
  name: string;
  avatar: string;
  target_asset: string;
  role_type: string;
  description: string;
  model_provider: string;
  model_name: string;
  system_prompt: string;
  user_prompt_template: string;
  is_builtin: boolean;
  is_active: boolean;
  sort_order: number;
}

export interface AgentResult {
  has_run: boolean;
  run_time?: string;
  strategy_id?: string;
  strategy_name?: string;
  strategy_category?: string;
  strategy_params?: any;
  screened_count?: number;
  chamber_id?: string;
  chamber_name?: string;
  chamber_type?: 'ROUNDTABLE' | 'COURTROOM';
  models_used?: {
    active_provider?: string;
    credit?: AgentModelMeta;
    equity?: AgentModelMeta;
    clause?: AgentModelMeta;
    pm?: AgentModelMeta;
  };
  candidates: CandidateBond[];
  credit_reviews: Record<string, { risk_level: string; reason: string }>;
  equity_reviews: Record<string, { momentum_score: number; sector_themes: string[]; catalyst_summary: string }>;
  clause_reviews: Record<string, { call_risk_level: string; game_summary: string }>;
  court_verdicts?: Record<string, {
    verdict: string;
    verdict_label?: string;
    sentence_summary?: string;
    weight: number;
    suggested_weight?: number;
    rating_stars: number;
    severity_stars?: number;
  }>;
  all_bond_speeches?: Record<string, AgentSpeech[]>;
  final_portfolio: Array<{
    bond_code: string;
    bond_name: string;
    price: number;
    double_low: number;
    weight: number;
    rating_stars: number;
    pm_verdict: string;
  }>;
  vetoed_bonds: any[];
  report_md?: string;
  is_archived?: boolean;
}

export interface AgentReportSummary {
  id: string;
  strategy_id?: string;
  strategy_name: string;
  run_time: string;
  candidates_count: number;
  vetoed_count: number;
  portfolio_count: number;
  chamber_name: string;
  chamber_type: 'ROUNDTABLE' | 'COURTROOM';
  created_at: string;
}
