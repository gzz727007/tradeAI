import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { GlobalSettingsModal } from './components/GlobalSettingsModal';
import { DataLakeModal } from './components/DataLakeModal';
import { StrategyStudio } from './components/StrategyStudio';
import { PaperTournament } from './components/PaperTournament';
import { RealAccounts } from './components/RealAccounts';
import { AgentConsultation } from './components/AgentConsultation';
import { TradingCommittee } from './components/TradingCommittee';
import { Strategy } from './types';
import { api } from './api/client';
import { Layers, Gamepad2, Wallet, Bot, Gavel } from 'lucide-react';

export function App() {
  const [activeTab, setActiveTab] = useState<'studio' | 'paper' | 'real' | 'agent' | 'committee'>('studio');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isDataLakeOpen, setIsDataLakeOpen] = useState(false);
  const [startDate, setStartDate] = useState('2023-01-01');
  const [endDate, setEndDate] = useState(new Date().toISOString().split('T')[0]);
  const [rebalanceFreq, setRebalanceFreq] = useState(5);
  const [systemStatus, setSystemStatus] = useState<any>(null);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [selectedStrategyForAgent, setSelectedStrategyForAgent] = useState<string | null>(null);

  const handleSendToAgent = (strategyId: string) => {
    setSelectedStrategyForAgent(strategyId);
    setActiveTab('agent');
  };

  const loadStatusAndStrategies = async () => {
    try {
      const [status, strats] = await Promise.all([
        api.getSystemStatus(),
        api.getStrategies(),
      ]);
      setSystemStatus(status);
      setStrategies(strats);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadStatusAndStrategies();
  }, []);

  const handleRefreshQuotes = async () => {
    setRefreshing(true);
    setRefreshKey((prev) => prev + 1);
    await loadStatusAndStrategies();
    setTimeout(() => setRefreshing(false), 500);
  };

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col font-sans">
      {/* Top Professional Header */}
      <Header
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenDataLake={() => setIsDataLakeOpen(true)}
        systemStatus={systemStatus}
        onRefreshQuotes={handleRefreshQuotes}
        refreshing={refreshing}
      />

      {/* Main Content Area: Full width flex layout */}
      <main className="flex-1 w-full px-4 sm:px-6 lg:px-8 py-4 space-y-4">
        {/* Navigation Tabs Bar */}
        <div className="bg-white p-1.5 rounded-xl border border-slate-200 shadow-xs flex items-center justify-between overflow-x-auto">
          <div className="flex gap-1">
            <button
              onClick={() => setActiveTab('studio')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'studio'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              <Layers className="w-4 h-4" />
              <span>1. 策略工坊与历史对决</span>
            </button>

            <button
              onClick={() => setActiveTab('paper')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'paper'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              <Gamepad2 className="w-4 h-4" />
              <span>2. 实盘模拟竞技场</span>
            </button>

            <button
              onClick={() => setActiveTab('real')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'real'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              <Wallet className="w-4 h-4" />
              <span>3. 我的实盘多账号管家</span>
            </button>

            <button
              onClick={() => setActiveTab('agent')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'agent'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              <Bot className="w-4 h-4" />
              <span>4. 今日 AI 智能体会诊室</span>
            </button>

            <button
              onClick={() => setActiveTab('committee')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'committee'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              <Gavel className="w-4 h-4" />
              <span>5. AI 交易委员会</span>
            </button>
          </div>
        </div>

        {/* Tab 1: Strategy Studio */}
        {activeTab === 'studio' && (
          <StrategyStudio
            startDate={startDate}
            endDate={endDate}
            rebalanceFreq={rebalanceFreq}
            refreshKey={refreshKey}
            onSendToAgent={handleSendToAgent}
          />
        )}

        {/* Tab 2: Paper Tournament */}
        {activeTab === 'paper' && <PaperTournament />}

        {/* Tab 3: Real Accounts */}
        {activeTab === 'real' && <RealAccounts strategies={strategies} />}

        {/* Tab 4: Agent Consultation */}
        {activeTab === 'agent' && (
          <AgentConsultation
            selectedStrategyId={selectedStrategyForAgent}
            onSelectStrategyId={setSelectedStrategyForAgent}
            strategies={strategies}
          />
        )}

        {/* Tab 5: Trading Committee */}
        {activeTab === 'committee' && <TradingCommittee />}
      </main>

      {/* Global Settings Modal */}
      <GlobalSettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        startDate={startDate}
        setStartDate={setStartDate}
        endDate={endDate}
        setEndDate={setEndDate}
        rebalanceFreq={rebalanceFreq}
        setRebalanceFreq={setRebalanceFreq}
      />

      {/* Data Lake Studio Modal */}
      <DataLakeModal
        isOpen={isDataLakeOpen}
        onClose={() => setIsDataLakeOpen(false)}
      />
    </div>
  );
}

export default App;
