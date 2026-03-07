import type React from 'react';
import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import type {
  HistoryItem,
  AnalysisReport,
  TaskInfo,
  HistoryModuleKey,
  ModuleRefreshJob,
} from '../types/analysis';
import { historyApi } from '../api/history';
import { analysisApi, DuplicateTaskError } from '../api/analysis';
import { validateStockCode } from '../utils/validation';
import { getRecentStartDate, toDateInputValue } from '../utils/format';
import { useAnalysisStore } from '../stores/analysisStore';
import { ReportSummary } from '../components/report';
import { HistoryList } from '../components/history';
import { TaskPanel } from '../components/tasks';
import { useTaskStream } from '../hooks';
import { moduleLabelMap } from '../utils/moduleRefresh';

/**
 * 首页 - 单页设计
 * 顶部输入 + 左侧历史 + 右侧报告
 */
const HomePage: React.FC = () => {
  const { setLoading, setError: setStoreError } = useAnalysisStore();
  const navigate = useNavigate();

  // 输入状态
  const [stockCode, setStockCode] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [inputError, setInputError] = useState<string>();

// 历史列表状态
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const pageSize = 20;

  // 报告详情状态
  const [selectedReport, setSelectedReport] = useState<AnalysisReport | null>(null);
  const [isLoadingReport, setIsLoadingReport] = useState(false);
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const [isDeletingHistory, setIsDeletingHistory] = useState(false);
  const [moduleJobs, setModuleJobs] = useState<ModuleRefreshJob[]>([]);
  const [refreshNotice, setRefreshNotice] = useState<{ type: 'info' | 'success' | 'error'; text: string } | null>(null);

  // 任务队列状态
  const [activeTasks, setActiveTasks] = useState<TaskInfo[]>([]);
  const [duplicateError, setDuplicateError] = useState<string | null>(null);

  // 用于跟踪当前分析请求，避免竞态条件
  const analysisRequestIdRef = useRef<number>(0);
  const completedModuleJobsRef = useRef<Record<string, string>>({});
  const noticeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const currentPageRef = useRef<number>(1);
  const loadedHistoryCountRef = useRef<number>(0);
  const selectedReportRef = useRef<AnalysisReport | null>(null);

  // 更新任务列表中的任务
  const updateTask = useCallback((updatedTask: TaskInfo) => {
    setActiveTasks((prev) => {
      const index = prev.findIndex((t) => t.taskId === updatedTask.taskId);
      if (index >= 0) {
        const newTasks = [...prev];
        newTasks[index] = updatedTask;
        return newTasks;
      }
      return prev;
    });
  }, []);

  // 移除已完成/失败的任务
  const removeTask = useCallback((taskId: string) => {
    setActiveTasks((prev) => prev.filter((t) => t.taskId !== taskId));
  }, []);

  // SSE 任务流
  useTaskStream({
    onTaskCreated: (task) => {
      setActiveTasks((prev) => {
        // 避免重复添加
        if (prev.some((t) => t.taskId === task.taskId)) return prev;
        return [...prev, task];
      });
    },
    onTaskStarted: updateTask,
    onTaskCompleted: (task) => {
      // 刷新历史列表
      fetchHistory();
      // 延迟移除任务，让用户看到完成状态
      setTimeout(() => removeTask(task.taskId), 2000);
    },
    onTaskFailed: (task) => {
      updateTask(task);
      // 显示错误提示
      setStoreError(task.error || '分析失败');
      // 延迟移除任务
      setTimeout(() => removeTask(task.taskId), 5000);
    },
    onError: () => {
      console.warn('SSE 连接断开，正在重连...');
    },
    enabled: true,
  });

  // 加载历史列表
  const fetchHistory = useCallback(async (autoSelectFirst = false, reset = true, silent = false) => {
    if (!silent) {
      if (reset) {
        setIsLoadingHistory(true);
        currentPageRef.current = 1;
      } else {
        setIsLoadingMore(true);
      }
    } else if (reset) {
      // Silent reset still needs page reset for correct API call
      currentPageRef.current = 1;
    }

    const page = reset ? 1 : currentPageRef.current + 1;

    try {
      // TODO: Proper timezone handling needed
      // Using tomorrow as endDate is a temporary workaround to include today's records.
      // This may incorrectly include tomorrow's data and is semantically inconsistent across timezones.
      // Better solution: standardize backend & frontend to use UTC or fixed timezone (Asia/Shanghai),
      // or construct endDate on frontend as end-of-day timestamp.
      const tomorrowDate = new Date();
      tomorrowDate.setDate(tomorrowDate.getDate() + 1);
      
      const response = await historyApi.getList({
        startDate: getRecentStartDate(30),
        endDate: toDateInputValue(tomorrowDate),
        page,
        limit: pageSize,
      });

      if (reset) {
        setHistoryItems(response.items);
        loadedHistoryCountRef.current = response.items.length;
      } else {
        setHistoryItems(prev => [...prev, ...response.items]);
        loadedHistoryCountRef.current += response.items.length;
      }

      // 判断是否还有更多数据
      setHasMore(loadedHistoryCountRef.current < response.total);
      currentPageRef.current = page;

      // 如果需要自动选择第一条，且有数据，且当前没有选中报告
      if (autoSelectFirst && response.items.length > 0 && !selectedReportRef.current) {
        const firstItem = response.items[0];
        setIsLoadingReport(true);
        try {
          const report = await historyApi.getDetail(firstItem.id);
          setSelectedReport(report);
        } catch (err) {
          console.error('Failed to fetch first report:', err);
        } finally {
          setIsLoadingReport(false);
        }
      }
    } catch (err) {
      console.error('Failed to fetch history:', err);
    } finally {
      setIsLoadingHistory(false);
      setIsLoadingMore(false);
    }
  }, [pageSize]);

  // 加载更多历史记录
  const handleLoadMore = useCallback(() => {
    if (!isLoadingMore && hasMore) {
      fetchHistory(false, false);
    }
  }, [fetchHistory, isLoadingMore, hasMore]);

  const displayHistoryItems = useMemo(() => {
    const unique = new Map<string, HistoryItem>();
    for (const item of historyItems) {
      const key = String(item.stockCode || '').toUpperCase();
      if (!key) continue;
      if (!unique.has(key)) {
        unique.set(key, item);
      }
    }
    return Array.from(unique.values());
  }, [historyItems]);

  useEffect(() => {
    selectedReportRef.current = selectedReport;
  }, [selectedReport]);

  // 初始加载 - 自动选择第一条
  useEffect(() => {
    fetchHistory(true);
  }, [fetchHistory]);

  // Background polling: re-fetch history every 30s for CLI-initiated analyses
  useEffect(() => {
    const interval = setInterval(() => {
      if (currentPageRef.current === 1) {
        fetchHistory(false, true, true);
      }
    }, 30_000);
    return () => clearInterval(interval);
  }, [fetchHistory]);

  // Refresh when tab regains visibility (e.g. user ran main.py in another terminal)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        if (currentPageRef.current === 1) {
          fetchHistory(false, true, true);
        }
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [fetchHistory]);

  useEffect(() => {
    return () => {
      if (noticeTimerRef.current) {
        clearTimeout(noticeTimerRef.current);
      }
    };
  }, []);

  // 点击历史项加载报告
  const handleHistoryClick = async (recordId: number) => {
    // 取消当前分析请求的结果显示（通过递增 requestId）
    analysisRequestIdRef.current += 1;

    setIsLoadingReport(true);
    try {
      const report = await historyApi.getDetail(recordId);
      setSelectedReport(report);
    } catch (err) {
      console.error('Failed to fetch report:', err);
    } finally {
      setIsLoadingReport(false);
    }
  };

  const handleDeleteHistory = useCallback((recordId: number) => {
    setDeleteConfirmId(recordId);
  }, []);

  const confirmDeleteHistory = useCallback(async () => {
    if (deleteConfirmId === null) return;

    setIsDeletingHistory(true);
    try {
      await historyApi.deleteRecord(deleteConfirmId);

      setHistoryItems((prev) => prev.filter((item) => item.id !== deleteConfirmId));
      if (selectedReport?.meta.id === deleteConfirmId) {
        setSelectedReport(null);
      }
      setDeleteConfirmId(null);
      await fetchHistory(false, true, true);
    } catch (err) {
      console.error('Failed to delete history record:', err);
      setStoreError(err instanceof Error ? err.message : '删除关注项失败');
    } finally {
      setIsDeletingHistory(false);
    }
  }, [deleteConfirmId, selectedReport, fetchHistory, setStoreError]);

  const fetchModuleJobs = useCallback(async (recordId: number): Promise<ModuleRefreshJob[]> => {
    try {
      const response = await historyApi.getModuleRefreshJobs(recordId, 50);
      const jobs = response.items || [];
      setModuleJobs(jobs);
      return jobs;
    } catch (err) {
      console.error('Failed to fetch module refresh jobs:', err);
      return [];
    }
  }, []);

  const handleRefreshModule = useCallback(async (module: HistoryModuleKey) => {
    const recordId = selectedReport?.meta.id;
    if (!recordId) return;

    setStoreError(null);
    try {
      await historyApi.startModuleRefresh(recordId, module);
      if (noticeTimerRef.current) clearTimeout(noticeTimerRef.current);
      setRefreshNotice({
        type: 'info',
        text: `${moduleLabelMap[module]} 更新任务已提交`,
      });
      noticeTimerRef.current = setTimeout(() => setRefreshNotice(null), 4000);
      await fetchModuleJobs(recordId);
    } catch (err) {
      console.error('Failed to start module refresh job:', err);
      setStoreError(err instanceof Error ? err.message : '启动更新任务失败');
    }
  }, [selectedReport, setStoreError, fetchModuleJobs]);

  useEffect(() => {
    const recordId = selectedReport?.meta.id;
    if (!recordId) {
      setModuleJobs([]);
      return undefined;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const poll = async (): Promise<void> => {
      const jobs = await fetchModuleJobs(recordId);
      if (cancelled) return;

      let shouldReloadDetail = false;
      for (const job of jobs) {
        const prevStatus = completedModuleJobsRef.current[job.jobId];
        if (prevStatus !== job.status) {
          completedModuleJobsRef.current[job.jobId] = job.status;
          if (noticeTimerRef.current) clearTimeout(noticeTimerRef.current);
          if (job.status === 'queued') {
            setRefreshNotice({ type: 'info', text: `${moduleLabelMap[job.module]} 已进入队列` });
          } else if (job.status === 'running') {
            setRefreshNotice({ type: 'info', text: `${moduleLabelMap[job.module]} 更新进行中` });
          } else if (job.status === 'succeeded') {
            setRefreshNotice({ type: 'success', text: `${moduleLabelMap[job.module]} 更新完成` });
          } else if (job.status === 'failed') {
            setRefreshNotice({ type: 'error', text: `${moduleLabelMap[job.module]} 更新失败：${job.message || '请重试'}` });
          }
          noticeTimerRef.current = setTimeout(() => setRefreshNotice(null), 4000);
          if (job.status === 'succeeded') {
            shouldReloadDetail = true;
          }
        }
      }

      if (shouldReloadDetail) {
        try {
          const report = await historyApi.getDetail(recordId);
          if (!cancelled) {
            setSelectedReport(report);
          }
          await fetchHistory(false, true, true);
        } catch (err) {
          console.error('Failed to refresh report after module update:', err);
        }
      }

      const hasRunningJob = jobs.some((job) => job.status === 'queued' || job.status === 'running');
      timer = setTimeout(poll, hasRunningJob ? 2000 : 10000);
    };

    void poll();

    return () => {
      cancelled = true;
      if (timer) {
        clearTimeout(timer);
      }
      if (noticeTimerRef.current) {
        clearTimeout(noticeTimerRef.current);
      }
    };
  }, [selectedReport?.meta.id, fetchHistory, fetchModuleJobs]);

  // 分析股票（异步模式）
  const handleAnalyze = async () => {
    const { valid, message, normalized } = validateStockCode(stockCode);
    if (!valid) {
      setInputError(message);
      return;
    }

    setInputError(undefined);
    setDuplicateError(null);
    setIsAnalyzing(true);
    setLoading(true);
    setStoreError(null);

    // 记录当前请求的 ID
    const currentRequestId = ++analysisRequestIdRef.current;

    try {
      // 使用异步模式提交分析
      const response = await analysisApi.analyzeAsync({
        stockCode: normalized,
        reportType: 'detailed',
      });

      // 清空输入框
      if (currentRequestId === analysisRequestIdRef.current) {
        setStockCode('');
      }

      // 任务已提交，SSE 会推送更新
      console.log('Task submitted:', response.taskId);
    } catch (err) {
      console.error('Analysis failed:', err);
      if (currentRequestId === analysisRequestIdRef.current) {
        if (err instanceof DuplicateTaskError) {
          // 显示重复任务错误
          setDuplicateError(`股票 ${err.stockCode} 正在分析中，请等待完成`);
        } else {
          setStoreError(err instanceof Error ? err.message : '分析失败');
        }
      }
    } finally {
      setIsAnalyzing(false);
      setLoading(false);
    }
  };

  // 回车提交
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && stockCode && !isAnalyzing) {
      handleAnalyze();
    }
  };

  return (
    <div
      className="h-[100dvh] min-h-screen grid overflow-hidden w-full"
      style={{ gridTemplateColumns: 'minmax(12px, 1fr) 256px 24px minmax(auto, 896px) minmax(12px, 1fr)', gridTemplateRows: 'auto 1fr' }}
    >
      {/* Top input row aligned with watchlist on the left and report area on the right. */}
      <header
        className="col-start-2 col-end-5 row-start-1 py-3 border-b border-white/5 flex-shrink-0 flex items-center min-w-0 overflow-hidden"
      >
        <div className="flex w-full min-w-0 items-center justify-between gap-3" style={{ maxWidth: 'min(100%, 1168px)' }}>
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <div className="flex-1 relative min-w-0">
              <input
                type="text"
                value={stockCode}
                onChange={(e) => {
                  setStockCode(e.target.value.toUpperCase());
                  setInputError(undefined);
                }}
                onKeyDown={handleKeyDown}
                placeholder="输入股票代码，如 600519、00700、AAPL"
                disabled={isAnalyzing}
                className={`input-terminal w-full ${inputError ? 'border-danger/50' : ''}`}
              />
              {inputError && (
                <p className="absolute -bottom-4 left-0 text-xs text-danger">{inputError}</p>
              )}
              {duplicateError && (
                <p className="absolute -bottom-4 left-0 text-xs text-warning">{duplicateError}</p>
              )}
            </div>
            <button
              type="button"
              onClick={handleAnalyze}
              disabled={!stockCode || isAnalyzing}
              className="btn-primary flex items-center gap-1.5 whitespace-nowrap flex-shrink-0"
            >
              {isAnalyzing ? (
                <>
                  <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  分析中
                </>
              ) : (
                '分析'
              )}
            </button>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <button
              type="button"
              className="px-3 py-1.5 rounded-lg border border-cyan/25 bg-cyan/10 text-cyan text-xs hover:bg-cyan/20 transition-colors"
              onClick={() => navigate('/chat')}
            >
              问股
            </button>
            <button
              type="button"
              className="px-3 py-1.5 rounded-lg border border-emerald-400/35 bg-emerald-500/15 text-emerald-200 text-xs hover:text-emerald-100 hover:bg-emerald-500/25 transition-colors"
              onClick={() => navigate('/backtest')}
            >
              回测
            </button>
          </div>
        </div>
      </header>

      {/* Left column: task panel + watchlist */}
      <div
        className="col-start-2 row-start-2 flex h-full flex-col gap-3 overflow-hidden min-h-0"
      >
        <TaskPanel tasks={activeTasks} />
        <HistoryList
          items={displayHistoryItems}
          isLoading={isLoadingHistory}
          isLoadingMore={isLoadingMore}
          hasMore={hasMore}
          selectedId={selectedReport?.meta.id}
          onItemClick={handleHistoryClick}
          onDeleteClick={handleDeleteHistory}
          onLoadMore={handleLoadMore}
          className="flex-1 min-h-0 overflow-hidden"
        />
      </div>

      {/* 右侧报告详情 */}
      <section className="col-start-4 row-start-2 flex-1 overflow-y-auto pl-1 min-w-0 min-h-0">
        {isLoadingReport ? (
          <div className="flex flex-col items-center justify-center h-full">
            <div className="w-10 h-10 border-3 border-cyan/20 border-t-cyan rounded-full animate-spin" />
            <p className="mt-3 text-secondary text-sm">加载报告中...</p>
          </div>
        ) : selectedReport ? (
          <div className="max-w-4xl">
            {refreshNotice ? (
              <div
                className={`rounded-md border px-3 py-2 mb-2 text-xs ${
                  refreshNotice.type === 'success'
                    ? 'border-emerald-400/30 bg-emerald-500/15 text-emerald-200'
                    : refreshNotice.type === 'error'
                      ? 'border-red-400/30 bg-red-500/15 text-red-200'
                      : 'border-cyan-400/30 bg-cyan-500/15 text-cyan-100'
                }`}
              >
                {refreshNotice.text}
              </div>
            ) : null}
            <ReportSummary
              data={selectedReport}
              isHistory
              onRefreshModule={handleRefreshModule}
              moduleJobs={moduleJobs}
            />
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-12 h-12 mb-3 rounded-xl bg-elevated flex items-center justify-center">
              <svg className="w-6 h-6 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <h3 className="text-base font-medium text-white mb-1.5">开始分析</h3>
            <p className="text-xs text-muted max-w-xs">
              输入股票代码进行分析，或从左侧选择关注列表查看
            </p>
          </div>
        )}
      </section>

      {deleteConfirmId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setDeleteConfirmId(null)}>
          <div className="bg-elevated border border-white/10 rounded-xl p-6 max-w-sm mx-4 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-white font-medium mb-2">删除关注项</h3>
            <p className="text-sm text-secondary mb-5">删除后该条分析记录不可恢复，确认删除吗？</p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setDeleteConfirmId(null)}
                disabled={isDeletingHistory}
                className="px-4 py-1.5 rounded-lg text-sm text-secondary hover:text-white hover:bg-white/5 border border-white/10 transition-colors disabled:opacity-50"
              >
                取消
              </button>
              <button
                onClick={confirmDeleteHistory}
                disabled={isDeletingHistory}
                className="px-4 py-1.5 rounded-lg text-sm text-white bg-red-500/80 hover:bg-red-500 transition-colors disabled:opacity-50"
              >
                {isDeletingHistory ? '删除中...' : '删除'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default HomePage;
