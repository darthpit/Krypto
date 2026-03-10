<?php
// index.php - Crypto Sniper Futures V4.5
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crypto Sniper Futures V4.5</title>
    
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    
    <!-- ApexCharts for advanced charting -->
    <script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>
    
    <!-- Tailwind CSS for Satellite Module -->
    <script src="https://cdn.tailwindcss.com"></script>

    <style>
        :root {
            --bg-body: #0a0e27;
            --bg-card: #1a1f3a;
            --bg-pulse: #252d4a;
            --bg-chat: #151b2e;
            --text-main: #e2e8f0;
            --text-muted: #94a3b8;
            --primary: #3b82f6;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
            --border: #334155;
            --pulse-active: #06b6d4;
        }

        * { 
            box-sizing: border-box; 
            margin: 0; 
            padding: 0; 
        }

        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-body);
            color: var(--text-main);
            line-height: 1.6;
            overflow-x: hidden;
        }

        .container {
            max-width: 2000px;
            margin: 0 auto;
            padding: 1.5rem;
        }

        /* Header */
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
            padding-bottom: 1rem;
            border-bottom: 2px solid var(--border);
        }

        .brand {
            font-size: 1.75rem;
            font-weight: 800;
            background: linear-gradient(135deg, var(--primary), var(--pulse-active));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .status-indicator {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            background: var(--bg-card);
            border-radius: 0.5rem;
            border: 1px solid var(--border);
        }

        .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: var(--success);
            animation: pulse 2s infinite;
        }

        .status-dot.offline {
            background: var(--danger);
            animation: none;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        /* Main Layout */
        .main-layout {
            display: grid;
            grid-template-columns: 300px 1fr 380px;
            gap: 1.5rem;
            margin-bottom: 1.5rem;
        }

        /* Sidebar - Market Watch */
        .sidebar {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        .card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 0.75rem;
            overflow: hidden;
        }

        .card-header {
            padding: 1rem 1.5rem;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .card-title {
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-main);
        }

        .card-body {
            padding: 1rem;
        }

        /* Market Watch List */
        .market-watch-list {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }

        .market-item {
            padding: 0.75rem;
            background: var(--bg-pulse);
            border-radius: 0.5rem;
            cursor: pointer;
            transition: all 0.2s;
            border: 2px solid transparent;
        }

        .market-item:hover {
            background: #2d3550;
            transform: translateX(5px);
        }

        .market-item.active {
            border-color: var(--primary);
            background: #2d3550;
        }

        .market-item-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.25rem;
        }

        .market-ticker {
            font-weight: 600;
            font-size: 0.875rem;
        }

        .market-extra {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-top: 4px;
        }

        .condition-bar {
            flex: 1;
            height: 4px;
            background: rgba(255,255,255,0.1);
            border-radius: 2px;
            margin-right: 8px;
            overflow: hidden;
        }

        .condition-fill {
            height: 100%;
            background: #94a3b8;
            transition: width 0.3s ease;
        }

        .history-badge {
            font-size: 0.65rem;
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-muted);
            padding: 3px 6px;
            border-radius: 4px;
            white-space: nowrap;
        }
        
        .history-badge .fa-info-circle {
            animation: pulse-info 2s ease-in-out infinite;
        }
        
        @keyframes pulse-info {
            0%, 100% { opacity: 0.7; }
            50% { opacity: 1; }
        }

        .market-change {
            font-size: 0.75rem;
            font-weight: 600;
        }

        .market-change.positive {
            color: var(--success);
        }

        .market-change.negative {
            color: var(--danger);
        }

        .market-price {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.875rem;
            color: var(--text-muted);
        }

        /* Center Column - Charts & Pulses */
        .center-column {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        /* Pulse Engine */
        .pulse-engine {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1rem;
        }

        .pulse-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 0.75rem;
            padding: 1rem;
            position: relative;
            overflow: hidden;
        }

        .pulse-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, var(--primary), var(--pulse-active));
        }

        .pulse-card.active::before {
            animation: slideRight 2s infinite;
        }

        @keyframes slideRight {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }

        .pulse-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
        }

        .pulse-title {
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            color: var(--text-muted);
        }

        .pulse-status {
            padding: 0.25rem 0.5rem;
            border-radius: 1rem;
            font-size: 0.65rem;
            font-weight: 600;
        }

        .pulse-status.running {
            background: rgba(16, 185, 129, 0.2);
            color: var(--success);
        }

        .pulse-status.idle {
            background: rgba(148, 163, 184, 0.2);
            color: var(--text-muted);
        }

        .pulse-status.error {
            background: rgba(239, 68, 68, 0.2);
            color: var(--danger);
        }

        .pulse-timer {
            font-size: 1.5rem;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            text-align: center;
            color: var(--primary);
            margin: 0.5rem 0;
        }

        .pulse-details {
            font-size: 0.75rem;
            color: var(--text-muted);
            text-align: center;
        }

        .progress-bar {
            width: 100%;
            height: 6px;
            background: var(--bg-pulse);
            border-radius: 1rem;
            overflow: hidden;
            margin-top: 0.75rem;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--primary), var(--pulse-active));
            transition: width 0.3s ease;
        }

        /* Chart Container */
        .chart-container {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 0.75rem;
            padding: 1.5rem;
            height: 500px;
        }

        .chart-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }

        .chart-title {
            font-size: 1.125rem;
            font-weight: 600;
        }

        .chart-controls {
            display: flex;
            gap: 0.5rem;
        }

        .chart-button {
            padding: 0.5rem 1rem;
            background: var(--bg-pulse);
            border: 1px solid var(--border);
            border-radius: 0.5rem;
            color: var(--text-main);
            cursor: pointer;
            font-size: 0.875rem;
            transition: all 0.2s;
        }

        .chart-button:hover {
            background: #2d3550;
        }

        .chart-button.active {
            background: var(--primary);
            border-color: var(--primary);
        }

        /* Right Column - AI Chat & Stats */
        .right-column {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1rem;
        }

        .stat-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 0.5rem;
            padding: 1rem;
        }

        .stat-label {
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            margin-bottom: 0.5rem;
        }

        .stat-value {
            font-size: 1.25rem;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        }

        /* AI Chat */
        .ai-chat {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 0.75rem;
            display: flex;
            flex-direction: column;
            height: 500px;
        }

        .chat-header {
            padding: 1rem 1.5rem;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .chat-header i {
            color: var(--primary);
        }

        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 1rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .chat-message {
            display: flex;
            gap: 0.75rem;
            animation: slideIn 0.3s ease;
        }

        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .chat-message.user {
            flex-direction: row-reverse;
        }

        .chat-avatar {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            font-size: 0.875rem;
        }

        .chat-avatar.user {
            background: var(--primary);
        }

        .chat-avatar.ai {
            background: var(--success);
        }

        .chat-bubble {
            background: var(--bg-pulse);
            padding: 0.75rem 1rem;
            border-radius: 0.75rem;
            max-width: 80%;
        }

        .chat-message.user .chat-bubble {
            background: var(--primary);
        }

        .chat-bubble-text {
            font-size: 0.875rem;
            line-height: 1.5;
        }

        .chat-timestamp {
            font-size: 0.65rem;
            color: var(--text-muted);
            margin-top: 0.25rem;
        }

        .chat-input-container {
            padding: 1rem;
            border-top: 1px solid var(--border);
            display: flex;
            gap: 0.75rem;
        }

        .chat-input {
            flex: 1;
            background: var(--bg-pulse);
            border: 1px solid var(--border);
            border-radius: 0.5rem;
            padding: 0.75rem 1rem;
            color: var(--text-main);
            font-size: 0.875rem;
            font-family: 'Inter', sans-serif;
        }

        .chat-input:focus {
            outline: none;
            border-color: var(--primary);
        }

        .chat-send-btn {
            background: var(--primary);
            border: none;
            border-radius: 0.5rem;
            padding: 0.75rem 1.5rem;
            color: white;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s;
        }

        .chat-send-btn:hover {
            background: #2563eb;
        }

        .chat-send-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        /* AI Context Box */
        .ai-context-box {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 0.75rem;
            padding: 1.5rem;
        }

        .ai-signal {
            display: inline-block;
            padding: 0.5rem 1rem;
            border-radius: 0.5rem;
            font-weight: 700;
            font-size: 1.125rem;
            margin-bottom: 1rem;
        }

        .ai-signal.LONG {
            background: rgba(16, 185, 129, 0.2);
            color: var(--success);
        }

        .ai-signal.SHORT {
            background: rgba(239, 68, 68, 0.2);
            color: var(--danger);
        }

        .ai-signal.NEUTRAL {
            background: rgba(148, 163, 184, 0.2);
            color: var(--text-muted);
        }

        .ai-reason {
            font-size: 0.875rem;
            line-height: 1.6;
            color: var(--text-muted);
        }

        /* Wallet Info */
        .wallet-info {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }

        .balance-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.75rem;
            background: var(--bg-pulse);
            border-radius: 0.5rem;
        }

        .balance-label {
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
        }

        .balance-value {
            font-size: 1rem;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        }

        /* Trader Book Styles */
        .trade-book-item {
            background: var(--bg-pulse);
            border-radius: 0.5rem;
            padding: 0.75rem;
            margin-bottom: 0.75rem;
            border-left: 3px solid transparent;
            transition: all 0.2s;
        }

        .trade-book-item:hover {
            background: #2d3550;
            transform: translateX(3px);
        }

        .trade-book-item.profit {
            border-left-color: var(--success);
        }

        .trade-book-item.loss {
            border-left-color: var(--danger);
        }

        .trade-book-header {
            display: flex;
            justify-content: flex-start;
            align-items: center;
            margin-bottom: 0.5rem;
            gap: 0.5rem;
        }

        .trade-book-symbol {
            font-weight: 600;
            font-size: 0.875rem;
            color: var(--text-main);
        }
        
        /* LONG/SHORT Badge Styles */
        .badge-success {
            background: rgba(40, 167, 69, 0.2);
            color: var(--success);
            border: 1px solid var(--success);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .badge-danger {
            background: rgba(220, 53, 69, 0.2);
            color: var(--danger);
            border: 1px solid var(--danger);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .trade-book-pnl {
            font-weight: 700;
            font-size: 0.875rem;
            font-family: 'JetBrains Mono', monospace;
        }

        .trade-book-pnl.positive {
            color: var(--success);
        }

        .trade-book-pnl.negative {
            color: var(--danger);
        }

        .trade-book-details {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.5rem;
            font-size: 0.75rem;
            color: var(--text-muted);
        }

        .trade-book-row {
            display: flex;
            justify-content: space-between;
            padding: 0.25rem 0;
        }

        .trade-book-label {
            color: var(--text-muted);
        }

        .trade-book-value {
            color: var(--text-main);
            font-family: 'JetBrains Mono', monospace;
            font-weight: 500;
        }

        .trade-book-badge {
            display: inline-block;
            padding: 0.125rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.65rem;
            font-weight: 600;
            text-transform: uppercase;
        }

        .trade-book-badge.optimal {
            background: rgba(16, 185, 129, 0.2);
            color: var(--success);
        }

        .trade-book-badge.suboptimal {
            background: rgba(245, 158, 11, 0.2);
            color: var(--warning);
        }

        .trade-book-badge.poor {
            background: rgba(239, 68, 68, 0.2);
            color: var(--danger);
        }

        /* Log Tabs */
        .log-tabs {
            display: flex;
            gap: 0.5rem;
            border-bottom: 1px solid var(--border);
            padding-bottom: 0.5rem;
        }

        .log-tab-btn {
            padding: 0.5rem 1rem;
            background: transparent;
            border: 1px solid var(--border);
            border-radius: 0.375rem;
            color: var(--text-muted);
            font-size: 0.875rem;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .log-tab-btn:hover {
            background: var(--bg-pulse);
            border-color: var(--primary);
            color: var(--text-main);
        }

        .log-tab-btn.active {
            background: var(--primary);
            border-color: var(--primary);
            color: white;
        }

        /* Terminal Logs */
        .terminal {
            background: #0d1117;
            border-radius: 0.5rem;
            padding: 1rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            max-height: 300px;
            overflow-y: auto;
            line-height: 1.6;
        }

        .log-entry {
            color: #8b949e;
            margin-bottom: 0.25rem;
        }

        .log-entry.log-error {
            color: var(--danger);
        }

        .log-entry.log-success {
            color: var(--success);
        }

        .log-entry.log-warning {
            color: var(--warning);
        }

        /* Scrollbar Styling */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }

        ::-webkit-scrollbar-track {
            background: var(--bg-pulse);
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb {
            background: var(--border);
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: var(--text-muted);
        }

        /* Loading Spinner */
        .spinner {
            border: 3px solid var(--bg-pulse);
            border-top: 3px solid var(--primary);
            border-radius: 50%;
            width: 20px;
            height: 20px;
            animation: spin 1s linear infinite;
            display: inline-block;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        /* Footer Panel - Glass Box Stats */
        .glass-box-panel {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1.5rem;
            margin-top: 1.5rem;
        }

        .glass-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 0.75rem;
            padding: 1rem;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }

        .glass-header {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--primary);
            text-transform: uppercase;
            border-bottom: 1px solid var(--border);
            padding-bottom: 0.5rem;
            margin-bottom: 0.5rem;
        }

        .glass-content {
            font-size: 0.8rem;
            color: var(--text-muted);
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }

        .glass-row {
            display: flex;
            justify-content: space-between;
        }

        .glass-value {
            color: var(--text-main);
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
        }

        .waiting-tag {
            background: rgba(245, 158, 11, 0.1);
            color: var(--warning);
            padding: 0.2rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.75rem;
            margin-top: 0.25rem;
        }

        /* Responsive Design */
        @media (max-width: 1600px) {
            .main-layout {
                grid-template-columns: 250px 1fr 350px;
            }
        }

        @media (max-width: 1200px) {
            .main-layout {
                grid-template-columns: 1fr;
            }
            
            .sidebar, .right-column {
                display: none;
            }
        }

        /* Utility Classes */
        .text-primary { color: var(--primary) !important; }
        .text-success { color: var(--success) !important; }
        .text-danger { color: var(--danger) !important; }
        .text-warning { color: var(--warning) !important; }
        .text-muted { color: var(--text-muted) !important; }
        .text-main { color: var(--text-main) !important; }
        .text-dark { color: #000 !important; }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <div class="brand">
                <i class="fas fa-rocket"></i>
                Crypto Sniper Futures V4.5
            </div>
            <div class="status-indicator">
                <div class="status-dot" id="engine-status-dot"></div>
                <span id="engine-status-text">CHECKING...</span>
            </div>
        </div>

        <!-- Main Layout -->
        <div class="main-layout">
            <!-- Left Sidebar - Market Watch -->
            <div class="sidebar">
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">
                            <i class="fas fa-chart-line"></i> Market Watch
                        </div>
                    </div>
                    <div class="card-body">
                        <div class="market-watch-list" id="market-watch-list">
                            <div class="market-item">
                                <div class="market-item-header">
                                    <span class="market-ticker">Loading...</span>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Data Sync Progress Bar -->
                        <div id="market-watch-sync-progress" style="display: none; margin-top: 1rem; padding: 0.75rem; background: var(--bg-pulse); border-radius: 0.5rem; border: 1px solid var(--border);">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                                <span style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">
                                    <i class="fas fa-download" style="margin-right: 4px;"></i> Pobieranie Danych BTC
                                </span>
                                <span id="sync-progress-percent" style="font-size: 0.75rem; color: var(--primary); font-weight: bold;">0%</span>
                            </div>
                            <div style="font-size: 0.65rem; color: var(--text-muted); margin-bottom: 0.5rem;">
                                <span id="sync-date-range">Od -- do --</span>
                            </div>
                            <div class="progress-bar" style="height: 8px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden;">
                                <div class="progress-fill" id="sync-progress-fill" style="width: 0%; background: linear-gradient(90deg, var(--primary), var(--pulse-active)); transition: width 0.3s ease;"></div>
                            </div>
                            <div id="sync-status-message" style="font-size: 0.65rem; color: var(--text-muted); text-align: center; margin-top: 0.5rem;">
                                Oczekiwanie...
                            </div>
                        </div>
                    </div>
                </div>

                <!-- AI Trader Performance -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">
                            <i class="fas fa-tachometer-alt"></i> AI Trader Performance
                        </div>
                    </div>
                    <div class="card-body">
                        <div class="wallet-info" id="trader-performance">
                            <div class="balance-item">
                                <div>
                                    <div class="balance-label"><i class="fas fa-arrow-circle-up text-green-500"></i> Total Bought</div>
                                    <div class="balance-value text-blue-400" id="perf-buys">--</div>
                                </div>
                            </div>
                            <div class="balance-item">
                                <div>
                                    <div class="balance-label"><i class="fas fa-arrow-circle-down text-red-500"></i> Total Sold</div>
                                    <div class="balance-value text-purple-400" id="perf-sells">--</div>
                                </div>
                            </div>
                            <div class="balance-item">
                                <div>
                                    <div class="balance-label"><i class="fas fa-coins"></i> Realized PnL</div>
                                    <div class="balance-value font-bold" id="perf-pnl" style="font-size: 1.1rem;">--</div>
                                </div>
                            </div>
                            <div class="balance-item">
                                <div>
                                    <div class="balance-label"><i class="fas fa-percent"></i> Total Fees</div>
                                    <div class="balance-value" id="perf-fees" style="color: #ef4444; font-size: 0.9rem;">--</div>
                                </div>
                            </div>
                            <div class="balance-item">
                                <div>
                                    <div class="balance-label"><i class="fas fa-bullseye"></i> Accuracy</div>
                                    <div class="balance-value" id="perf-accuracy">--</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Wallet Card (FUTURES) -->
                <div class="card p-4 mb-4" id="wallet-info">
                    <div class="flex justify-between items-center mb-4">
                        <h2 class="text-xl font-bold header-font text-blue-400">
                            <i class="fas fa-wallet mr-2"></i>FUTURES WALLET (x20)
                        </h2>
                        <span class="badge badge-primary px-3 py-1">ISOLATED MARGIN</span>
                    </div>

                    <div class="grid grid-cols-2 gap-4">
                        <div class="bg-gray-800 p-3 rounded border border-gray-700">
                            <div class="text-gray-400 text-xs uppercase">Total Balance (USDT)</div>
                            <div class="text-2xl font-bold text-white mt-1" id="balance-total">$100.00</div>
                        </div>

                        <div class="bg-gray-800 p-3 rounded border border-blue-900/50">
                            <div class="text-blue-400 text-xs uppercase">Single Trade Size (10%)</div>
                            <div class="text-xl font-bold text-blue-300 mt-1" id="trade-size">$10.00</div>
                            <div class="text-xs text-gray-500">Margin Power: $200.00</div>
                        </div>
                    </div>

                    <!-- Open Positions List -->
                    <div class="mt-4 pt-4 border-t border-gray-700">
                        <div class="text-sm font-bold text-gray-300 mb-3">
                            <i class="fas fa-chart-line mr-2"></i>Otwarte Kontrakty
                        </div>
                        <div id="open-positions-list" class="space-y-2">
                            <div class="text-center text-gray-500 text-xs py-2">Brak otwartych pozycji</div>
                        </div>
                    </div>
                </div>

                <!-- AI Control Center (Training Monitor) -->
                <div class="card" style="background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%); border-color: #4c1d95;">
                    <div class="card-header" style="border-color: #4c1d95;">
                        <div class="card-title" style="color: #a78bfa;">
                            <i class="fas fa-brain"></i> AI Training Center
                        </div>
                        <span style="font-size: 10px; color: #9ca3af; font-family: 'JetBrains Mono', monospace;">
                            Auto-Check: 6 Days
                        </span>
                    </div>
                    <div class="card-body" style="padding: 1rem;">
                        <div id="ai-models-container" class="space-y-3">
                            <div class="text-center" style="color: #94a3b8; font-size: 14px;">Loading AI Status...</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Center Column - Pulses & Charts -->
            <div class="center-column">
                <!-- Pulse Engine -->
                <div class="pulse-engine">
                    <!-- Pulse 1M -->
                    <div class="pulse-card" id="pulse-1m-card">
                        <div class="pulse-header">
                            <div class="pulse-title">⚡ PULSE 1M</div>
                            <div class="pulse-status idle" id="pulse-1m-status">IDLE</div>
                        </div>
                        <div class="pulse-timer" id="pulse-1m-timer">0:00</div>
                        <div class="pulse-details" id="pulse-1m-action">Fast Price Check</div>
                        <div class="progress-bar">
                            <div class="progress-fill" id="pulse-1m-progress" style="width: 0%"></div>
                        </div>
                    </div>

                    <!-- Pulse 5M -->
                    <div class="pulse-card" id="pulse-5m-card">
                        <div class="pulse-header">
                            <div class="pulse-title">🧠 PULSE 5M</div>
                            <div class="pulse-status idle" id="pulse-5m-status">IDLE</div>
                        </div>
                        <div class="pulse-timer" id="pulse-5m-timer">0:00</div>
                        <div class="pulse-details" id="pulse-5m-action">AI Analysis</div>
                        <div class="progress-bar">
                            <div class="progress-fill" id="pulse-5m-progress" style="width: 0%"></div>
                        </div>
                    </div>

                    <!-- Pulse 30M -->
                    <div class="pulse-card" id="pulse-30m-card">
                        <div class="pulse-header">
                            <div class="pulse-title">🎓 PULSE 30M</div>
                            <div class="pulse-status idle" id="pulse-30m-status">IDLE</div>
                        </div>
                        <div class="pulse-timer" id="pulse-30m-timer">0:00</div>
                        <div class="pulse-details" id="pulse-30m-action">Model Training</div>
                        <div class="progress-bar">
                            <div class="progress-fill" id="pulse-30m-progress" style="width: 0%"></div>
                        </div>
                    </div>
                </div>

                <!-- Advanced Chart -->
                <div class="chart-container" style="position:relative;">
                    <div class="chart-header">
                        <div class="chart-title" id="chart-title">BTC/USDT Chart</div>
                        <div class="chart-controls">
                            <button class="chart-button active" data-timeframe="1h">1H</button>
                            <button class="chart-button" data-timeframe="4h">4H</button>
                            <button class="chart-button" data-timeframe="1d">1D</button>
                            <button class="chart-button" data-timeframe="4d">4D</button>
                        </div>
                    </div>
                    <div id="chart-loader" style="display:none; position:absolute; top:0; left:0; right:0; bottom:0; background:rgba(26, 31, 58, 0.8); z-index:10; justify-content:center; align-items:center; flex-direction:column; border-radius:0.75rem;">
                        <div class="spinner"></div>
                        <div style="margin-top:1rem; color:var(--text-muted); font-size:0.875rem;">Pobieranie pełnej historii...</div>
                    </div>
                    <div id="advanced-chart"></div>
                </div>


                <!-- Stats Grid -->
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-label">Current Price</div>
                        <div class="stat-value" id="stat-price">--</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Predicted Price</div>
                        <div class="stat-value" id="stat-predicted">--</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">AI Signal</div>
                        <div class="stat-value" id="stat-signal">--</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Portfolio Value</div>
                        <div class="stat-value" id="stat-balance">--</div>
                    </div>
                    <div class="stat-card" style="grid-column: span 2;">
                        <div class="stat-label">Meta-Model Confidence</div>
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div class="stat-value" id="stat-confidence">--%</div>
                            <div id="stat-verdict" style="font-weight:600; font-size:0.875rem;">--</div>
                        </div>
                        <div class="progress-bar" style="margin-top:0.5rem; height:8px; background:rgba(255,255,255,0.1);">
                            <div class="progress-fill" id="confidence-bar" style="width: 0%; background: var(--text-muted);"></div>
                        </div>
                    </div>
                </div>

                <!-- High Velocity & Quant Metrics -->
                <div style="display: grid; grid-template-columns: 1fr; gap: 1rem; margin-bottom: 1.5rem;">
                    
                    <!-- Quant Protocol Metrics Panel (Added manually per user request) -->
                    <div class="row g-3 mb-4" style="display: flex; flex-wrap: wrap; width: 100%;">
                        <div class="col-12" style="flex: 1; width: 100%;">
                            <div class="card border-0 shadow-sm" style="background: var(--bg-card); border: 1px solid var(--border);">
                                <div class="card-header py-3" style="background-color: var(--bg-card); border-bottom: 1px solid var(--border);">
                                    <h6 class="mb-0 fw-bold" style="color: var(--text-main);"><i class="fas fa-microchip me-2"></i>Titan Quant Protocol Metrics</h6>
                                </div>
                                <div class="card-body">
                                    <div class="row text-center" style="display: flex; justify-content: space-between;">
                                        <div class="col-md-4 border-end" style="flex: 1; border-right: 1px solid var(--border); padding: 0.5rem;">
                                            <small class="text-muted text-uppercase">Memory Preservation (FracDiff)</small>
                                            <h4 class="my-2 text-primary" id="quant-memory">95%</h4>
                                            <span class="badge" style="background: rgba(255,255,255,0.1); color: var(--text-main);">Non-Stationary Fixed</span>
                                        </div>
                                        <div class="col-md-4 border-end" style="flex: 1; border-right: 1px solid var(--border); padding: 0.5rem;">
                                            <small class="text-muted text-uppercase">Triple Barrier Training</small>
                                            <h4 class="my-2 text-success" id="quant-barrier">Active</h4>
                                            <span class="badge" style="background: rgba(16, 185, 129, 0.1); color: var(--success);">TP / SL / Time</span>
                                        </div>
                                        <div class="col-md-4" style="flex: 1; padding: 0.5rem;">
                                            <small class="text-muted text-uppercase">Microstructure (Spread)</small>
                                            <h4 class="my-2" id="quant-spread" style="color: var(--text-main);">0.00%</h4>
                                            <span class="badge" id="quant-liquidity" style="background: var(--bg-pulse);">Checking...</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- System Logs (with tabs) -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">
                            <i class="fas fa-terminal"></i> System Logs
                        </div>
                        <!-- Log Tabs -->
                        <div class="log-tabs" style="margin-top: 0.75rem;">
                            <button class="log-tab-btn active" onclick="switchLogTab('system')">
                                <i class="fas fa-server"></i> System
                            </button>
                            <button class="log-tab-btn" onclick="switchLogTab('ppo')">
                                <i class="fas fa-brain"></i> PPO Logs
                            </button>
                            <button class="log-tab-btn" onclick="switchLogTab('lstm')">
                                <i class="fas fa-project-diagram"></i> LSTM Logs
                            </button>
                        </div>
                    </div>
                    <div class="card-body">
                        <!-- System Logs Terminal -->
                        <div class="terminal log-terminal active" id="terminal-system-logs">
                            <div class="log-entry">Waiting for system logs...</div>
                        </div>
                        <!-- PPO Logs Terminal -->
                        <div class="terminal log-terminal" id="terminal-ppo-logs" style="display: none;">
                            <div class="log-entry">Waiting for PPO training logs...</div>
                        </div>
                        <!-- LSTM Logs Terminal -->
                        <div class="terminal log-terminal" id="terminal-lstm-logs" style="display: none;">
                            <div class="log-entry">Waiting for LSTM training logs...</div>
                        </div>
                    </div>
                </div>

                <!-- Daily PnL (PLN) -->
                <div class="card" style="margin-top: 1.5rem;">
                    <div class="card-header">
                        <div class="card-title">
                            <i class="fas fa-chart-bar"></i> Daily PnL (PLN)
                        </div>
                    </div>
                    <div class="card-body">
                        <div id="daily-pnl-chart" style="min-height: 250px;"></div>
                    </div>
                </div>
            </div>

            <!-- Right Column - AI Chat & Context -->
            <div class="right-column">
                <!-- AI Chat -->
                <div class="ai-chat">
                    <div class="chat-header">
                        <i class="fas fa-robot"></i>
                        <div class="card-title">AI Command Center</div>
                    </div>
                    <div class="chat-messages" id="chat-messages">
                        <div class="chat-message ai">
                            <div class="chat-avatar ai">
                                <i class="fas fa-robot"></i>
                            </div>
                            <div class="chat-bubble">
                                <div class="chat-bubble-text">
                                    Hello! I'm Janosik, your AI trading assistant. I can help you understand market conditions, analyze AI predictions, and manage your portfolio. What would you like to know?
                                </div>
                                <div class="chat-timestamp" id="initial-timestamp"></div>
                            </div>
                        </div>
                    </div>
                    <div class="chat-input-container">
                        <input 
                            type="text" 
                            class="chat-input" 
                            id="chat-input" 
                            placeholder="Ask me anything about the market..."
                            onkeypress="if(event.key === 'Enter') sendMessage()"
                        />
                        <button class="chat-send-btn" id="chat-send-btn" onclick="sendMessage()">
                            <i class="fas fa-paper-plane"></i>
                        </button>
                    </div>
                </div>

                <!-- AI Context -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">
                            <i class="fas fa-brain"></i> AI Decision Context
                        </div>
                    </div>
                    <div class="card-body">
                        <div id="ai-context">
                            <div class="ai-signal NEUTRAL">NEUTRAL</div>
                            <div class="ai-reason">Waiting for AI analysis...</div>
                        </div>
                    </div>
                </div>

                <!-- Model Profitability (Real PnL) -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">
                            <i class="fas fa-coins"></i> Total PnL (Realized + Unrealized)
                        </div>
                    </div>
                    <div class="card-body">
                        <!-- Total PnL Summary -->
                        <div class="grid grid-cols-2 gap-4 mb-4">
                            <div class="bg-gray-800 p-3 rounded border border-gray-700">
                                <div class="text-gray-400 text-xs uppercase">Realized PnL</div>
                                <div class="text-xl font-bold mt-1" id="realized-pnl">$0.00</div>
                                <div class="text-xs text-gray-500">Zamknięte pozycje</div>
                            </div>
                            <div class="bg-gray-800 p-3 rounded border border-gray-700">
                                <div class="text-gray-400 text-xs uppercase">Unrealized PnL</div>
                                <div class="text-xl font-bold mt-1" id="unrealized-pnl">$0.00</div>
                                <div class="text-xs text-gray-500">Otwarte pozycje</div>
                            </div>
                        </div>
                        <div class="bg-gradient-to-r from-blue-900/30 to-purple-900/30 p-4 rounded border border-blue-700/50">
                            <div class="text-gray-400 text-xs uppercase mb-1">Total PnL</div>
                            <div class="text-3xl font-bold" id="total-pnl">$0.00</div>
                            <div class="text-xs text-gray-500 mt-1">
                                Return: <span id="total-pnl-percent">0.00%</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Trader Book - Trade History & Decision Analysis -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">
                            <i class="fas fa-book"></i> Trader Book
                        </div>
                        <div style="font-size: 0.75rem; color: var(--text-muted);">
                            Analiza decyzji sprzedażowych
                        </div>
                    </div>
                    <div class="card-body" style="padding: 0;">
                        <!-- Trader Book List (Scrollable) -->
                        <div id="trader-book-container" style="max-height: 400px; overflow-y: auto; padding: 1rem;">
                            <div id="trader-book-list">
                                <!-- Trader Book items will be inserted here by JavaScript -->
                                <div style="text-align: center; padding: 2rem; color: var(--text-muted);">
                                    <i class="fas fa-spinner fa-spin" style="font-size: 2rem; margin-bottom: 1rem;"></i>
                                    <div>Ładowanie historii transakcji...</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Removed: "Wyniki wg Strategii" section -->

                <!-- Data Sync Monitor (Moved) -->
                <div class="card" id="sync-monitor-card" style="display:none;">
                    <div class="card-header">
                        <div class="card-title">
                            <i class="fas fa-sync-alt"></i> Synchronizacja Historii
                        </div>
                    </div>
                    <div class="card-body">
                        <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem; font-size:0.75rem; color:var(--text-muted);">
                            <span id="sync-target-date">Do: --</span>
                            <span id="sync-current-date">Pobieranie od: --</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" id="sync-progress-bar" style="width: 0%"></div>
                        </div>
                        <div id="sync-status-text" style="font-size:0.75rem; text-align:center; margin-top:0.5rem; color:var(--primary);">
                            Łatanie ciągłości danych...
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Bottom Panel - Transparency Protocol -->
        <div class="glass-box-panel">
            <!-- Col 1: LSTM Brain Stats -->
            <div class="glass-card">
                <div class="glass-header">
                    <i class="fas fa-brain"></i> LSTM Brain Stats
                </div>
                <div class="glass-content">
                    <div class="glass-row">
                        <span>Training:</span>
                        <span class="glass-value" id="lstm-params">--</span>
                    </div>
                    <div class="glass-row">
                        <span>Wytrenowany (razy):</span>
                        <span class="glass-value" id="lstm-training-count">--</span>
                    </div>
                    <div class="glass-row">
                        <span>Kompletność modelu:</span>
                        <span class="glass-value" id="lstm-progress">--%</span>
                    </div>
                    <div class="glass-row">
                        <span>Accuracy (Aktualny):</span>
                        <span class="glass-value" id="lstm-accuracy">--%</span>
                    </div>
                    <div class="glass-row">
                        <span>Hits / Misses:</span>
                        <span class="glass-value" id="lstm-hits-misses">-- / --</span>
                    </div>
                    <div class="glass-row">
                        <span>Do celu (90%):</span>
                        <span class="glass-value" id="lstm-accuracy-to-goal">--%</span>
                    </div>
                    <div class="glass-row">
                        <span>Kolejny trening za:</span>
                        <span class="glass-value" id="lstm-next-training">--</span>
                    </div>
                    <div class="glass-row">
                        <span>Last Check:</span>
                        <span class="glass-value" id="lstm-last-check">--</span>
                    </div>
                </div>
            </div>

            <!-- Col 2: RL Agent Brain Stats (NEW!) -->
            <div class="glass-card">
                <div class="glass-header">
                    <i class="fas fa-robot"></i> RL Agent Brain Stats
                </div>
                <div class="glass-content">
                    <div class="glass-row">
                        <span>Training Status:</span>
                        <span class="glass-value" id="rl-training-status">--</span>
                    </div>
                    <div class="glass-row">
                        <span>Win Rate (7d):</span>
                        <span class="glass-value" id="rl-win-rate">--%</span>
                    </div>
                    <div class="glass-row">
                        <span>Last Decision:</span>
                        <span class="glass-value" id="rl-last-decision">--</span>
                    </div>
                    <div class="glass-row">
                        <span>Hits / Misses:</span>
                        <span class="glass-value" id="rl-hits-misses">-- / --</span>
                    </div>
                    <div class="glass-row">
                        <span>Next Training:</span>
                        <span class="glass-value" id="rl-next-training">--</span>
                    </div>
                </div>
            </div>

            <!-- Col 3: AI Trader Intent -->
            <div class="glass-card">
                <div class="glass-header">
                    <i class="fas fa-user-secret"></i> AI Trader Intent
                </div>
                <div class="glass-content">
                    <div class="glass-row">
                        <span>Status:</span>
                        <span class="glass-value" id="trader-status">Watching...</span>
                    </div>
                    <div class="glass-row">
                        <span>Analysis Attempts:</span>
                        <span class="glass-value" id="trader-attempts">0</span>
                    </div>
                    <div class="glass-row">
                        <span>Trades Executed:</span>
                        <span class="glass-value" id="trader-execs">0</span>
                    </div>
                    <div id="trader-waiting-container">
                        <!-- Dynamic waiting tags -->
                    </div>
                    <!-- Active Strategies List -->
                    <div id="active-strategies-container" style="margin-top: 1rem; border-top: 1px solid var(--border); padding-top: 0.5rem;">
                        <div style="font-size: 0.75rem; font-weight: 600; color: var(--text-muted); margin-bottom: 0.5rem;">🎯 Active Strategies (48h)</div>
                        <div id="strategies-list" style="display: flex; flex-direction: column; gap: 0.25rem; max-height: 100px; overflow-y: auto;">
                            <!-- Strategies injected here -->
                        </div>
                    </div>
                </div>
            </div>

            <!-- Col 3: Dynamic Optimizer -->
            <div class="glass-card">
                <div class="glass-header">
                    <i class="fas fa-cogs"></i> 6H Dynamic Optimizer
                </div>
                <div class="glass-content">
                    <div class="glass-row">
                        <span>Active Strategy:</span>
                        <span class="glass-value" id="opt-strategy">Trend Following</span>
                    </div>
                    <div class="glass-row">
                        <span>Detected Pattern:</span>
                        <span class="glass-value" id="opt-pattern">--</span>
                    </div>
                    <div class="glass-row">
                        <span>PSND Magnet:</span>
                        <span class="glass-value" id="opt-psnd">--</span>
                    </div>
                    <div class="glass-row">
                        <span class="text-muted">Est. Profit (3 Days):</span>
                        <span id="opt-projected" class="text-success fw-bold">--</span>
                    </div>
                    <div class="glass-row">
                        <span>Next Update:</span>
                        <span class="glass-value" id="opt-next">--:--:--</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- AI Radar Scout (Moved to bottom) -->
        <div class="card mb-4" id="radar-panel" style="display:none; border: 1px solid var(--primary); margin: 1.5rem 0;">
            <div class="card-header d-flex justify-content-between align-items-center" style="background: rgba(59, 130, 246, 0.1);">
                <h5 class="mb-0" style="font-size: 1rem;"><i class="fas fa-satellite-dish"></i> AI Radar Scout</h5>
                <span class="badge bg-primary" id="radar-timestamp" style="font-size: 0.75rem;">Scanning...</span>
            </div>
            <div class="card-body p-0" style="padding: 0;">
                <div class="table-responsive">
                    <table class="table table-dark table-sm mb-0" style="width: 100%; text-align: left; border-collapse: collapse;">
                        <thead style="background: var(--bg-pulse);">
                            <tr>
                                <th style="padding: 0.75rem;">Asset</th>
                                <th style="padding: 0.75rem;">Signal Detected</th>
                                <th style="padding: 0.75rem;">Price</th>
                                <th style="padding: 0.75rem;">Action</th>
                            </tr>
                        </thead>
                        <tbody id="radar-list">
                            </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Matrix Scout Heatmap (Moved to bottom) -->
        <div class="card mb-3" id="matrix-panel" style="border: 1px solid var(--border); margin-bottom: 2rem;">
            <div class="card-header d-flex justify-content-between align-items-center">
                <span class="fw-bold"><i class="fas fa-th text-primary"></i> Market Matrix (Correlation)</span>
                <div style="display: flex; align-items: center; gap: 10px;">
                     <button onclick="downloadMatrixData()" class="btn btn-sm btn-outline-secondary" style="font-size: 0.7rem; padding: 2px 8px; border: 1px solid var(--border); color: var(--text-muted); background: transparent; cursor: pointer;">
                         <i class="fas fa-download"></i> TXT
                     </button>
                     <small class="text-muted" id="matrix-time">--:--</small>
                </div>
            </div>
            <div class="card-body">
                 <div id="matrix-heatmap" style="min-height: 350px;">
                     <div class="text-center text-muted p-5">Loading Matrix...</div>
                 </div>
            </div>
        </div>

    </div>

    <script>
        // --- SMART PAUSE & VISIBILITY MANAGER ---

        // Global variables
        // --- HELPER FUNCTIONS ---
        function formatPrice(price) {
            if (price === undefined || price === null) return '--';
            const p = parseFloat(price);
            if (isNaN(p)) return '--';
            if (p === 0) return '0.00';
            if (p < 0.0001) return p.toFixed(8);
            if (p < 0.01) return p.toFixed(6);
            if (p < 1.0) return p.toFixed(4);
            return p.toFixed(2);
        }

        let chart = null;
        let updateInterval = null;
        let currentTicker = 'BTC/USDT';
        let chartData = {};
        let conversationHistory = [];
        let isPageVisible = true; // Track visibility state
        let systemConfig = null; // Store config globally

        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            console.log('Dashboard initialized with Smart Pause Protocol');

            // Load Config first
            fetch('api/data.php?file=config.json')
                .then(res => res.json())
                .then(config => {
                    systemConfig = config;
                    console.log("System Config Loaded", config);
                })
                .catch(e => console.error("Failed to load config", e));

            initializeChart();

            // Load initial chart data for BTC/USDT with FULL history for LSTM
            loadTickerHistory('BTC/USDT', 'FULL');

            // Initial Wallet Load (Force Logic)
            forceLoadWallet();
            
            // Set initial timestamp
            const tsEl = document.getElementById('initial-timestamp');
            if(tsEl) tsEl.textContent = new Date().toLocaleTimeString();
            
            // Setup chart controls
            document.querySelectorAll('.chart-button').forEach(btn => {
                btn.addEventListener('click', function() {
                    document.querySelectorAll('.chart-button').forEach(b => b.classList.remove('active'));
                    this.classList.add('active');
                    updateChartTimeframe(this.dataset.timeframe);
                });
            });

            // VISIBILITY LISTENER (The Fix)
            document.addEventListener("visibilitychange", handleVisibilityChange);
        });

        // Handle Tab Switching
        function handleVisibilityChange() {
            if (document.hidden) {
                // User left the tab -> PAUSE EVERYTHING
                console.log("Tab hidden - Pausing updates to save resources");
                isPageVisible = false;
                if (updateInterval) {
                    clearInterval(updateInterval);
                    updateInterval = null;
                }
                document.title = "💤 AI Pilot (Paused)";
            } else {
                // User returned -> RESUME IMMEDIATELY
                console.log("Tab visible - Resuming updates");
                isPageVisible = true;
                document.title = "Crypto Sniper Futures V4.5";

                // 1. Instant lightweight update (text only)
                updateResults();
                updateWallet();

                // 2. Full update & restart loop (small delay to let UI breathe)
                setTimeout(() => {
                    updateDashboard();
                    startUpdates();
                }, 300);
            }
        }

        let chartRefreshInterval = null;
        let lastChartRefresh = 0;
        
        function startUpdates() {
            // Prevent multiple intervals
            if (updateInterval) clearInterval(updateInterval);
            
            // Standard loop - Dashboard updates every 5 seconds
            updateInterval = setInterval(() => {
                if (isPageVisible) {
                    updateDashboard();
                }
            }, 5000);
            
            // Chart data refresh - Reload fresh candles from database every 5 minutes
            if (chartRefreshInterval) clearInterval(chartRefreshInterval);
            
            chartRefreshInterval = setInterval(() => {
                if (isPageVisible && currentTicker) {
                    console.log('Auto-refreshing chart data from database...');
                    loadTickerHistory(currentTicker, 'FULL');  // Use FULL for complete history
                }
            }, 300000); // 5 minutes = 300,000ms
        }

        function forceLoadWallet() {
             fetch('api/data.php?file=paper_wallet.json&t=' + Date.now())
             .then(res => {
                 if (!res.ok) throw new Error("Not found");
                 return res.json();
             })
             .then(data => {
                 console.log("Wallet loaded successfully.");
                 // First run
                 updateDashboard();
                 startUpdates();
             })
             .catch(e => {
                 console.warn("Wallet wait... retrying in 1s");
                 setTimeout(forceLoadWallet, 1000);
             });
        }

        let currentTimeframe = '1h'; // Globalna zmienna stanu (default 1H)

        async function updateDashboard() {
            await Promise.all([
                updateStatus(),
                updateEngineStatus(),
                updateResults(),
                updateWallet(),
                updateLogs(),
                updateMarketWatch(),
                updatePerformance(),
                updateSyncMonitor(),
                updateGlassBox(),
                updateModelProfitability(),
                // updateStrategyPerformance(), // REMOVED - replaced with live PnL
                updateDailyPnL(),
                updateMatrixScout(),
                updateHolisticGuardian(),
                updateAIStatus(),
                updateTraderBook()
            ]);
            
            // Chart update (zachowaj timeframe użytkownika)
            // Zawsze odśwież z aktualnym filtrem - nie przeładowuj danych
            if (chartData[currentTicker]) {
                // Zastosuj aktualny filtr timeframe zamiast pełnych danych
                let filteredData = chartData[currentTicker];
                const now = Date.now();
                
                if (currentTimeframe === '1h') {
                    filteredData = chartData[currentTicker].filter(c => c[0] > now - 3600000);
                } else if (currentTimeframe === '4h') {
                    filteredData = chartData[currentTicker].filter(c => c[0] > now - 14400000);
                } else if (currentTimeframe === '1d') {
                    filteredData = chartData[currentTicker].filter(c => c[0] > now - 86400000);
                } else if (currentTimeframe === '4d') {
                    filteredData = chartData[currentTicker].filter(c => c[0] > now - 345600000);
                }
                
                updateChart(filteredData);
            }
        }

        async function updateGlassBox() {
            // 1. LSTM Stats (Handled by updateStats now)
            try {
                const res = await fetch('api/data.php?file=model_stats.json&t=' + Date.now());
                const data = await res.json();

                if (data) {
                    const params = data.current_training_params || {};
                    const paramStr = params.epochs ? `${params.epochs} Epochs | ${params.lookback} Lookback` : '--';
                    document.getElementById('lstm-params').textContent = paramStr;

                    // DISABLED OLD LOGIC
                    /*
                    document.getElementById('lstm-accuracy').textContent = (data.accuracy_rate || 0) + '%';
                    const lastCheck = data.last_minute_check || '--';
                    const lastCheckEl = document.getElementById('lstm-last-check');
                    lastCheckEl.textContent = lastCheck;
                    lastCheckEl.style.color = lastCheck === 'HIT' ? 'var(--success)' : (lastCheck === 'MISS' ? 'var(--danger)' : 'var(--text-muted)');
                    document.getElementById('lstm-hits-misses').textContent = `${data.total_hits || 0} / ${data.total_misses || 0}`;
                    */
                }
            } catch(e) {}

            // 2. Trader Intent
            try {
                const res = await fetch('api/data.php?file=trader_intent.json&t=' + Date.now());
                const data = await res.json();

                if (data) {
                    // Status based on signal
                    let status = 'Monitoring';
                    if (data.signal === 'LONG') status = '📈 LONG Signal';
                    else if (data.signal === 'SHORT') status = '📉 SHORT Signal';
                    else if (data.signal === 'VETO_LONG') status = '🚫 VETO LONG';
                    else if (data.signal === 'VETO_SHORT') status = '🚫 VETO SHORT';
                    else if (data.position === 'IN_POSITION') status = '💰 In Position';
                    
                    document.getElementById('trader-status').textContent = status;
                    
                    // Analysis attempts = prediction count from database
                    fetch('api/data.php?endpoint=stats&type=prediction_count')
                        .then(r => r.json())
                        .then(stats => {
                            if (stats.count) {
                                document.getElementById('trader-attempts').textContent = stats.count.toLocaleString();
                            }
                        })
                        .catch(() => {});
                    
                    // Trades executed (always 0 in PAPER mode)
                    document.getElementById('trader-execs').textContent = 0;

                    const container = document.getElementById('trader-waiting-container');
                    container.innerHTML = '';
                    if (data.waiting_for && data.waiting_for.length > 0) {
                        data.waiting_for.forEach(reason => {
                            container.innerHTML += `<div class="waiting-tag">${reason}</div>`;
                        });
                    }
                }
            } catch(e) {}

            // 2b. Active Strategies (New)
            try {
                const res = await fetch('api/data.php?file=active_strategies.json&t=' + Date.now());
                const data = await res.json();

                const list = document.getElementById('strategies-list');
                if (data && list) {
                    list.innerHTML = '';

                    for (const [ticker, info] of Object.entries(data)) {
                        const shortTicker = ticker.split('/')[0];
                        let statusIcon = info.status === 'ACTIVE' ? '🟢' : '⏳';
                        let text = info.best_combo || 'Analyzing...';
                        let winRate = info.win_rate_48h || 'N/A';
                        let tooltip = `Win Rate: ${winRate}`;

                        if (info.status === 'GATHERING_DATA') {
                            text = `Gathering (${info.progress || '0%'})`;
                        }

                        // Limit text length
                        const displayText = text.length > 20 ? text.substring(0, 20) + '...' : text;
                        let color = info.status === 'ACTIVE' ? 'var(--success)' : 'var(--warning)';

                        const row = document.createElement('div');
                        row.style.display = 'flex';
                        row.style.justifyContent = 'space-between';
                        row.style.fontSize = '0.75rem';
                        row.style.alignItems = 'center';
                        row.style.marginBottom = '0.25rem';
                        row.title = tooltip;

                        row.innerHTML = `
                            <span style="font-weight:600; color:var(--text-main); width: 60px;">${shortTicker}</span>
                            <span style="color:${color}; cursor:help; text-align:right; flex:1;">${statusIcon} [${displayText}]</span>
                        `;
                        list.appendChild(row);
                    }
                }
            } catch(e) {}

            // 3. Dynamic Optimizer - Calculate from current market data
            try {
                const res = await fetch('api/data.php?file=latest_results.json&ticker=BTC/USDT&t=' + Date.now());
                const data = await res.json();
                
                if (data && data.signal) {
                    // Active Strategy based on signal
                    let strategy = 'Trend Following';
                    if (data.signal === 'LONG') strategy = 'Long Position';
                    else if (data.signal === 'SHORT') strategy = 'Short Position';
                    else if (data.signal.includes('VETO')) strategy = 'Risk Management';
                    
                    document.getElementById('opt-strategy').textContent = strategy;
                    
                    // Detected Pattern based on confidence
                    let pattern = 'Bullish Momentum';
                    if (data.signal === 'SHORT') pattern = 'Bearish Momentum';
                    else if (data.confidence_score < 0.6) pattern = 'Consolidation';
                    
                    document.getElementById('opt-pattern').textContent = pattern;
                    
                    // PSND Magnet (predicted price target)
                    if (data.predicted_price) {
                        document.getElementById('opt-psnd').textContent = '$' + data.predicted_price.toFixed(2);
                    }
                    
                    // Estimated profit (based on confidence and direction)
                    if (data.predicted_price && data.current_price) {
                        const priceDiff = data.predicted_price - data.current_price;
                        const profitPercent = (priceDiff / data.current_price) * 100;
                        const projected = (profitPercent * 3).toFixed(2); // 3-day projection
                        
                        const projEl = document.getElementById('opt-projected');
                        projEl.textContent = (projected > 0 ? '+' : '') + projected + '%';
                        projEl.className = projected > 0 ? 'text-success fw-bold' : 'text-danger fw-bold';
                    }
                    
                    // Next update (always in 6 hours for 6H optimizer)
                    const nextUpdate = new Date(Date.now() + 6 * 60 * 60 * 1000);
                    document.getElementById('opt-next').textContent = nextUpdate.toLocaleTimeString('pl-PL', {
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                }
            } catch(e) {
                console.log('6H Optimizer data not available');
            }
        }

        async function updateSyncMonitor() {
            try {
                const res = await fetch('api/data.php?file=sync_status.json&t=' + Date.now());
                if (!res.ok) return;
                const data = await res.json();

                // Validation
                if (!data || !data.status) return;

                const card = document.getElementById('sync-monitor-card');
                const progress = data.progress_percent || 0;

                if (data.status === 'COMPLETE' || data.status === 'COMPLETED' || progress === 100) {
                     // Show completion for a moment
                     if (card.style.display !== 'none') {
                         document.getElementById('sync-status-text').innerHTML = '<i class="fas fa-check-circle"></i> ' + (data.message || 'Synced');
                         document.getElementById('sync-status-text').style.color = 'var(--success)';
                         document.getElementById('sync-progress-bar').style.width = '100%';
                         document.getElementById('sync-progress-bar').style.background = 'var(--success)';

                         // Hide after 5 seconds if complete
                         setTimeout(() => {
                             card.style.display = 'none';
                         }, 5000);
                     }
                } else {
                     card.style.display = 'block';
                     document.getElementById('sync-progress-bar').style.width = progress + '%';

                     let msg = data.message || 'Synchronizing...';
                     if (data.current_ticker) {
                         msg = `[${data.current_ticker}] ` + msg;
                     }

                     document.getElementById('sync-status-text').textContent = msg;
                     document.getElementById('sync-status-text').style.color = 'var(--primary)';
                     document.getElementById('sync-current-date').textContent = 'Fetching: ' + (data.current_fetching_date || '--');
                     document.getElementById('sync-target-date').textContent = 'Target: ' + (data.target_date || '--');
                }

                // Update Market Watch sync progress bar
                updateMarketWatchSyncProgress(data);

            } catch (e) {
                // Ignore errors if file doesn't exist
            }
        }

        async function updateMarketWatchSyncProgress(syncData) {
            try {
                const progressContainer = document.getElementById('market-watch-sync-progress');
                const progressFill = document.getElementById('sync-progress-fill');
                const progressPercent = document.getElementById('sync-progress-percent');
                const dateRange = document.getElementById('sync-date-range');
                const statusMessage = document.getElementById('sync-status-message');

                if (!progressContainer) return;

                const progress = syncData.progress_percent || 0;
                const status = syncData.status || 'IDLE';
                const daysDownloaded = syncData.days_downloaded || 0;
                const totalDays = syncData.total_days || 180;
                const currentDate = syncData.current_fetching_date || '--';

                // Show/hide progress bar based on status
                if (status === 'DOWNLOADING') {
                    progressContainer.style.display = 'block';
                    
                    // Update progress
                    progressFill.style.width = progress + '%';
                    progressPercent.textContent = progress + '%';
                    
                    // Update date range
                    const startDate = new Date();
                    startDate.setDate(startDate.getDate() - totalDays);
                    dateRange.textContent = `Od ${startDate.toLocaleDateString('pl-PL')} do ${new Date().toLocaleDateString('pl-PL')}`;
                    
                    // Update status message
                    statusMessage.textContent = `Pobrano ${daysDownloaded}/${totalDays} dni (${currentDate})`;
                    statusMessage.style.color = 'var(--primary)';
                    
                } else if (status === 'COMPLETED' || status === 'COMPLETE') {
                    // Show completion
                    progressFill.style.width = '100%';
                    progressFill.style.background = 'var(--success)';
                    progressPercent.textContent = '100%';
                    statusMessage.innerHTML = '<i class="fas fa-check-circle"></i> Pobieranie zakończone';
                    statusMessage.style.color = 'var(--success)';
                    
                    // Hide after 10 seconds
                    setTimeout(() => {
                        progressContainer.style.display = 'none';
                    }, 10000);
                } else {
                    // Hide if idle or unknown status
                    progressContainer.style.display = 'none';
                }

            } catch (e) {
                console.error('Error updating Market Watch sync progress:', e);
            }
        }

        async function updateStatus() {
            try {
                const res = await fetch('api/data.php?file=status.json&t=' + Date.now());
                const data = await res.json();
                
                // Update engine status based on strict timestamp check (90s limit)
                let isOnline = false;

                if (data.timestamp) {
                    const heartbeatTime = new Date(data.timestamp).getTime();
                    const now = Date.now();
                    const diffSeconds = (now - heartbeatTime) / 1000;

                    if (diffSeconds < 90) {
                        isOnline = true;
                    }
                }

                const statusDot = document.getElementById('engine-status-dot');
                const statusText = document.getElementById('engine-status-text');
                
                if (isOnline) {
                    statusDot.classList.remove('offline');
                    statusText.textContent = 'ONLINE';
                } else {
                    statusDot.classList.add('offline');
                    statusText.textContent = 'OFFLINE';
                }
                
            } catch (e) {
                console.error('Failed to update status:', e);
                document.getElementById('engine-status-dot').classList.add('offline');
                document.getElementById('engine-status-text').textContent = 'OFFLINE';
            }
        }

        async function updateEngineStatus() {
            try {
                const res = await fetch('api/data.php?file=engine_status.json&t=' + Date.now());
                const data = await res.json();
                
                // Update each pulse
                updatePulseCard('1m', data.pulse_1m, 60);
                updatePulseCard('5m', data.pulse_5m, 300);
                updatePulseCard('30m', data.pulse_30m, 1800);
                
            } catch (e) {
                console.warn('Engine status not available yet');
            }
        }

        function updatePulseCard(pulseType, pulseData, intervalSeconds) {
            if (!pulseData) return;
            
            const statusEl = document.getElementById(`pulse-${pulseType}-status`);
            const actionEl = document.getElementById(`pulse-${pulseType}-action`);
            const cardEl = document.getElementById(`pulse-${pulseType}-card`);
            
            // Update status
            statusEl.className = 'pulse-status ' + pulseData.status;
            statusEl.textContent = pulseData.status.toUpperCase();
            
            // Update action
            if (pulseData.details && pulseData.details.action) {
                actionEl.textContent = pulseData.details.action;
            }
            
            // Add active class if running
            if (pulseData.status === 'running') {
                cardEl.classList.add('active');
            } else {
                cardEl.classList.remove('active');
            }
            
            // Calculate countdown
            if (pulseData.last_run) {
                const lastRun = new Date(pulseData.last_run);
                const now = new Date();
                const elapsed = Math.floor((now - lastRun) / 1000);
                const remaining = Math.max(0, intervalSeconds - elapsed);
                
                const minutes = Math.floor(remaining / 60);
                const seconds = remaining % 60;
                const timerEl = document.getElementById(`pulse-${pulseType}-timer`);
                timerEl.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
                
                // Update progress bar
                const progress = ((intervalSeconds - remaining) / intervalSeconds) * 100;
                const progressEl = document.getElementById(`pulse-${pulseType}-progress`);
                progressEl.style.width = progress + '%';
            }
        }

        async function updateResults() {
            try {
                // Fetch latest results for CURRENT TICKER specifically
                const res = await fetch('api/data.php?file=latest_results.json&ticker=' + encodeURIComponent(currentTicker) + '&t=' + Date.now());
                const data = await res.json();
                
                const isPrimary = data.ticker === currentTicker;

                // Update 6H Optimizer (Global)
                if (data.optimizer) {
                    document.getElementById('opt-strategy').textContent = data.optimizer.active_strategy || '--';
                    document.getElementById('opt-pattern').textContent = data.optimizer.detected_pattern || '--';
                    const nextEl = document.getElementById('opt-next');
                    if(nextEl) nextEl.textContent = data.optimizer.next_update || '--';

                    // NEW: Update Projection
                    const projEl = document.getElementById('opt-projected');
                    if(projEl) {
                        const val = data.optimizer.projected_profit || '--';
                        projEl.textContent = val;
                        // Color logic: Green if positive, Red if negative (rare)
                        projEl.className = val.includes('+') ? 'text-success fw-bold' : 'text-muted fw-bold';
                    }

                    // PSND Display
                    const psndEl = document.getElementById('opt-psnd');
                    if(psndEl) psndEl.textContent = data.optimizer.psnd_level || '--';
                }

                if (isPrimary) {
                    // Standard update for Primary Ticker
                    document.getElementById('stat-price').textContent = '$' + formatPrice(data.current_price);
                    document.getElementById('stat-predicted').textContent = '$' + formatPrice(data.predicted_price);
                    document.getElementById('stat-signal').textContent = data.signal || '--';

                    // Update Confidence Meter
                    if (data.confidence_score !== undefined) {
                        const conf = data.confidence_score * 100;
                        document.getElementById('stat-confidence').textContent = conf.toFixed(0) + '%';
                        const verdict = data.rf_verdict || 'UNKNOWN';
                        document.getElementById('stat-verdict').textContent = verdict;

                        const bar = document.getElementById('confidence-bar');
                        bar.style.width = conf + '%';

                        // Color logic
                        if (conf > 80) {
                            bar.style.background = 'var(--success)';
                            document.getElementById('stat-verdict').style.color = 'var(--success)';
                        } else if (conf > 40) {
                            bar.style.background = 'var(--warning)';
                            document.getElementById('stat-verdict').style.color = 'var(--warning)';
                        } else {
                            bar.style.background = 'var(--danger)';
                            document.getElementById('stat-verdict').style.color = 'var(--danger)';
                        }
                    } else {
                        document.getElementById('stat-confidence').textContent = '--%';
                        document.getElementById('confidence-bar').style.width = '0%';
                        document.getElementById('stat-verdict').textContent = 'Waiting...';
                    }

                    // Update AI context
                    const aiBox = document.getElementById('ai-context');
                    if (data.signal) {
                        const contextRes = await fetch('api/data.php?file=ai_context.json&t=' + Date.now());
                        const contextData = await contextRes.json();

                        // Add Primary Concern if low confidence
                        let extraInfo = '';
                        if (data.primary_concern && data.primary_concern !== 'None') {
                            extraInfo = `<div style="margin-top:0.5rem; color:var(--warning); font-size:0.75rem;"><i class="fas fa-exclamation-triangle"></i> Concern: ${data.primary_concern}</div>`;
                        }

                        // SMC Context Logic
                        let smcText = '';
                        const status = data.fvg_status || 'NEUTRAL';
                        if (status === 'INSIDE_BULLISH') smcText = '🟢 SNIPER MODE: W strefie zakupu (INSIDE BULLISH)';
                        else if (status === 'INSIDE_BEARISH') smcText = '🔴 SNIPER MODE: W strefie sprzedaży (INSIDE BEARISH)';
                        else if (status === 'ABOVE_BULLISH') smcText = '⏳ WAITING: Czekam na korektę do FVG (ABOVE BULLISH)';
                        else if (status === 'BELOW_BEARISH') smcText = '⏳ WAITING: Czekam na podbicie do FVG (BELOW BEARISH)';
                        else smcText = '⚪ Geometria neutralna';

                        const smcHtml = `<div class="smc-status" style="font-weight: bold; margin: 5px 0; color: #cbd5e1;">🏛️ SMC: ${smcText}</div>`;

                        aiBox.innerHTML = `
                            <div class="ai-signal ${data.signal}">${data.signal}</div>
                            ${smcHtml}
                            <div class="ai-reason">${contextData.reason || 'No reason available'}</div>
                            ${extraInfo}
                        `;
                    }

                // --- QUANT METRICS UPDATE (from new quant_metrics endpoint) ---
                try {
                    const quantRes = await fetch('api/data.php?file=quant_metrics.json&t=' + Date.now());
                    const q = await quantRes.json();
                    
                    // Update FracDiff (Memory Preservation)
                    const memEl = document.getElementById('quant-memory');
                    if(memEl && q.fracdiff_score !== undefined) {
                        memEl.innerText = q.fracdiff_score.toFixed(0) + '%';
                    }
                    
                    // Update Triple Barrier
                    const barrierEl = document.getElementById('quant-barrier');
                    if(barrierEl && q.triple_barrier_active) {
                        barrierEl.innerText = q.triple_barrier_active;
                    }

                    // Update Spread
                    const spreadEl = document.getElementById('quant-spread');
                    if(spreadEl && q.spread_pct !== undefined) {
                        spreadEl.innerText = q.spread_pct.toFixed(2) + '%';
                        // Koloruj na czerwono jeśli spread wysoki (>0.5%)
                        spreadEl.className = (q.spread_pct > 0.5) ? "my-2 text-danger" : "my-2 text-main";
                    }

                    // Update Liquidity Badge
                    const liqEl = document.getElementById('quant-liquidity');
                    if(liqEl && q.liquidity_status) {
                        liqEl.innerText = q.liquidity_status;
                        if (q.liquidity_status === 'HEALTHY') {
                            liqEl.className = "badge bg-success";
                        } else if (q.liquidity_status === 'MODERATE') {
                            liqEl.className = "badge bg-warning text-dark";
                        } else {
                            liqEl.className = "badge bg-danger";
                        }
                    }
                } catch(e) {
                    // Quant metrics not available yet
                }

                } else {
                    // Update for other tickers
                    // We need to fetch price from market_watch data (which we might have locally or need to fetch)
                    try {
                        const mwRes = await fetch('api/data.php?file=market_watch.json&t=' + Date.now());
                        const mwData = await mwRes.json();
                        const item = mwData.find(x => x.ticker === currentTicker);

                        if (item) {
                            document.getElementById('stat-price').textContent = '$' + formatPrice(item.price);
                        } else {
                             document.getElementById('stat-price').textContent = '--';
                        }
                    } catch(e) {}

                    document.getElementById('stat-predicted').textContent = '--';
                    document.getElementById('stat-signal').textContent = 'MONITORING';
                    
                    const aiBox = document.getElementById('ai-context');
                    aiBox.innerHTML = `
                        <div class="ai-signal NEUTRAL">MONITORING</div>
                        <div class="ai-reason">AI is currently optimized for ${data.ticker || 'Primary'}. Monitoring ${currentTicker}.</div>
                    `;
                }
                
            } catch (e) {
                console.warn('Results not available yet');
            }
        }

        async function updateWallet() {
            try {
                // Fetch wallet and market data in parallel
                const [resWallet, resMarket] = await Promise.all([
                    fetch('api/data.php?file=paper_wallet.json&t=' + Date.now()),
                    fetch('api/data.php?file=market_watch.json&t=' + Date.now())
                ]);
                
                if (!resWallet.ok) throw new Error("Wallet file locked/missing");
                
                const data = await resWallet.json();
                const marketData = resMarket.ok ? await resMarket.json() : [];

                // Create a price map
                const prices = {};
                if (marketData && Array.isArray(marketData)) {
                    marketData.forEach(m => {
                        prices[m.ticker] = m.price;
                        // Also map base currency (e.g. BTC -> BTC/USDT price)
                        const base = m.ticker.split('/')[0];
                        prices[base] = m.price;
                    });
                }

                const usdtAvailable = parseFloat(data.USDT) || 0;
                let totalPortfolioValue = usdtAvailable;

                // Iterate keys to calculate positions value
                const metaKeys = ['USDT', 'pln_value', 'initial_balance', 'trades', 'history', 'pnl_history', 'total_volume_bought', 'total_volume_sold', 'realized_pnl', 'total_usdt_est', 'timestamp', 'avg_prices'];

                for (const [key, value] of Object.entries(data)) {
                    if (metaKeys.includes(key)) continue;

                    let positionValue = 0;
                    let currentPrice = 0;
                    let tickerDisplay = key;

                    // CHECK FOR SHORT POSITIONS
                    if (key.endsWith('_SHORT')) {
                        tickerDisplay = key.replace('_SHORT', '');
                        const positionData = value; // Object {entry_price, margin_usdt, amount_coins...}

                        // Robustness check
                        if (typeof positionData !== 'object') continue;

                        const margin = positionData.margin_usdt || 0;
                        const entryPrice = positionData.entry_price || 0;
                        const amountCoins = positionData.amount_coins || 0;

                        // Find current price
                        currentPrice = prices[tickerDisplay];
                        if (!currentPrice && !tickerDisplay.includes('/')) {
                             currentPrice = prices[tickerDisplay + '/USDT'];
                        }
                        if (!currentPrice) currentPrice = entryPrice; // Fallback to entry so PnL is 0

                        const pnl = (entryPrice - currentPrice) * amountCoins;
                        positionValue = margin + pnl;
                        
                        totalPortfolioValue += positionValue;

                    } else {
                        // CHECK FOR LONG POSITIONS (Standard tickers)
                        if (typeof value !== 'number') continue;
                        const quantity = value;
                        if (quantity <= 0.00001) continue; 

                        // Try to resolve price
                        currentPrice = prices[key];
                        if (!currentPrice && !key.includes('/')) {
                             currentPrice = prices[key + '/USDT'];
                        }
                        if (!currentPrice) continue;

                        positionValue = quantity * currentPrice;
                        totalPortfolioValue += positionValue;
                    }
                }

                // 1. Update Portfolio Elements (New Structure)
                const balanceTotalEl = document.getElementById('balance-total');
                if (balanceTotalEl) balanceTotalEl.textContent = '$' + totalPortfolioValue.toFixed(2);
                
                const tradeSizeEl = document.getElementById('trade-size');
                if (tradeSizeEl) {
                    // Assuming 10% allocation per trade (fixed logic from user request)
                    const tradeSize = totalPortfolioValue * 0.10;
                    tradeSizeEl.textContent = '$' + tradeSize.toFixed(2);
                }

                // 2. Update Small Tile "Portfolio Value"
                const statBal = document.getElementById('stat-balance');
                if(statBal) statBal.textContent = '$' + totalPortfolioValue.toFixed(2);

                // 3. Update Performance
                document.getElementById('perf-buys').textContent = '$' + (data.total_volume_bought || 0).toFixed(2);
                document.getElementById('perf-sells').textContent = '$' + (data.total_volume_sold || 0).toFixed(2);

                const pnl = data.realized_pnl || 0;
                const pnlEl = document.getElementById('perf-pnl');
                pnlEl.textContent = (pnl >= 0 ? '+' : '') + '$' + pnl.toFixed(2);
                pnlEl.style.color = pnl >= 0 ? 'var(--success)' : 'var(--danger)';
                
                // Update Total Fees
                const feesEl = document.getElementById('perf-fees');
                if (feesEl) {
                    const totalFees = data.total_fees_paid || 0;
                    feesEl.textContent = '$' + totalFees.toLocaleString(undefined, {minimumFractionDigits: 4, maximumFractionDigits: 4});
                }

                // --- FIX: HIGH VELOCITY ALLOCATION (Keep existing logic if elements exist) ---
                let hvBal = 0;
                if (systemConfig && systemConfig.assets && systemConfig.assets.high_velocity) {
                    const hvTickers = systemConfig.assets.high_velocity.tickers || [];
                    hvTickers.forEach(t => {
                         const base = t.split('/')[0];
                         if (data[base]) { // LONG
                              const price = prices[t] || prices[base + '/USDT'] || 0;
                              hvBal += data[base] * price;
                         }
                    });
                }
                const hvAlloc = (totalPortfolioValue > 0) ? (hvBal / totalPortfolioValue) * 100 : 0;
                const hvEl = document.getElementById('high-velocity-balance');
                if(hvEl) {
                    hvEl.innerText = '$' + hvBal.toFixed(2);
                    const hvPnl = document.getElementById('high-velocity-pnl');
                    if(hvPnl) hvPnl.innerText = hvAlloc.toFixed(1) + '% Alloc';
                    const hvHeaderAlloc = document.getElementById('hv-allocation');
                    if (hvHeaderAlloc && systemConfig && systemConfig.allocation) {
                         hvHeaderAlloc.innerText = (systemConfig.allocation.high_velocity * 100).toFixed(0) + '%';
                    }
                }
                const hvBar = document.getElementById('high-velocity-bar');
                if(hvBar) hvBar.style.width = hvAlloc + '%';

            } catch (e) {
                console.warn('Wallet display error:', e);
                // Fallback
                const balanceTotalEl = document.getElementById('balance-total');
                if (balanceTotalEl) balanceTotalEl.textContent = '$--';
                const statBal = document.getElementById('stat-balance');
                if(statBal) statBal.textContent = '$--';
            }
        }

        async function updateModelProfitability() {
            try {
                // Fetch current price, positions, and trades
                const [resPrice, resPositions, resTrades] = await Promise.all([
                    fetch('api/data.php?file=latest_results.json&ticker=BTC/USDT&t=' + Date.now()),
                    fetch('api/data.php?endpoint=positions&t=' + Date.now()),
                    fetch('api/data.php?endpoint=trades_summary&t=' + Date.now())
                ]);
                
                const priceData = await resPrice.json();
                const currentPrice = priceData.current_price || 0;
                
                // Get open positions
                let openPositions = {};
                try {
                    openPositions = await resPositions.json();
                } catch(e) {
                    openPositions = {};
                }
                
                // Get trades summary
                let tradesSummary = { realized_pnl: 0, total_trades: 0 };
                try {
                    tradesSummary = await resTrades.json();
                } catch(e) {}
                
                // Calculate Unrealized PnL from open positions
                let unrealizedPnL = 0;
                for (const [ticker, pos] of Object.entries(openPositions)) {
                    const entryPrice = pos.entry_price || 0;
                    const amount = pos.amount || 0;
                    const side = pos.side; // 'LONG' or 'SHORT'
                    
                    if (side === 'LONG') {
                        unrealizedPnL += (currentPrice - entryPrice) * amount;
                    } else if (side === 'SHORT') {
                        unrealizedPnL += (entryPrice - currentPrice) * amount;
                    }
                }
                
                // Realized PnL
                const realizedPnL = tradesSummary.realized_pnl || 0;
                
                // Total PnL
                const totalPnL = realizedPnL + unrealizedPnL;
                const initialBalance = 1000; // Initial balance
                const totalPnLPercent = (totalPnL / initialBalance) * 100;
                
                // Update UI
                const realizedEl = document.getElementById('realized-pnl');
                const unrealizedEl = document.getElementById('unrealized-pnl');
                const totalEl = document.getElementById('total-pnl');
                const totalPercentEl = document.getElementById('total-pnl-percent');
                
                if (realizedEl) {
                    realizedEl.textContent = '$' + realizedPnL.toFixed(2);
                    realizedEl.className = 'text-xl font-bold mt-1 ' + (realizedPnL >= 0 ? 'text-green-400' : 'text-red-400');
                }
                
                if (unrealizedEl) {
                    unrealizedEl.textContent = '$' + unrealizedPnL.toFixed(2);
                    unrealizedEl.className = 'text-xl font-bold mt-1 ' + (unrealizedPnL >= 0 ? 'text-green-400' : 'text-red-400');
                }
                
                if (totalEl) {
                    totalEl.textContent = '$' + totalPnL.toFixed(2);
                    totalEl.className = 'text-3xl font-bold ' + (totalPnL >= 0 ? 'text-green-400' : 'text-red-400');
                }
                
                if (totalPercentEl) {
                    totalPercentEl.textContent = (totalPnL >= 0 ? '+' : '') + totalPnLPercent.toFixed(2) + '%';
                    totalPercentEl.className = (totalPnL >= 0 ? 'text-green-400' : 'text-red-400') + ' font-bold';
                }
                
                // Update Open Positions List in Wallet section
                const positionsListEl = document.getElementById('open-positions-list');
                if (positionsListEl && Object.keys(openPositions).length > 0) {
                    let html = '';
                    for (const [ticker, pos] of Object.entries(openPositions)) {
                        const entryPrice = pos.entry_price || 0;
                        const amount = pos.amount || 0;
                        const side = pos.side;
                        const leverage = pos.leverage || 1;
                        const margin = pos.margin || 0;
                        
                        // Calculate PnL for this position
                        let pnl = 0;
                        if (side === 'LONG') {
                            pnl = (currentPrice - entryPrice) * amount;
                        } else if (side === 'SHORT') {
                            pnl = (entryPrice - currentPrice) * amount;
                        }
                        
                        const pnlPercent = (pnl / margin) * 100;
                        const pnlColor = pnl >= 0 ? 'text-green-400' : 'text-red-400';
                        const sideColor = side === 'LONG' ? 'text-green-400' : 'text-red-400';
                        const sideIcon = side === 'LONG' ? '📈' : '📉';
                        
                        html += `
                            <div class="bg-gray-800 p-3 rounded border border-gray-700">
                                <div class="flex justify-between items-center mb-2">
                                    <div>
                                        <span class="${sideColor} font-bold text-xs">${sideIcon} ${side}</span>
                                        <span class="text-gray-400 text-xs ml-2">${ticker}</span>
                                    </div>
                                    <span class="${pnlColor} font-bold text-sm">${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}</span>
                                </div>
                                <div class="grid grid-cols-4 gap-2 text-xs">
                                    <div>
                                        <div class="text-gray-500">Entry</div>
                                        <div class="text-white font-mono">$${entryPrice.toFixed(2)}</div>
                                    </div>
                                    <div>
                                        <div class="text-gray-500">Amount</div>
                                        <div class="text-white font-mono">${amount.toFixed(6)}</div>
                                    </div>
                                    <div>
                                        <div class="text-gray-500">Leverage</div>
                                        <div class="text-blue-400 font-bold">${leverage}x</div>
                                    </div>
                                    <div>
                                        <div class="text-gray-500">ROI</div>
                                        <div class="${pnlColor} font-bold">${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(1)}%</div>
                                    </div>
                                </div>
                            </div>
                        `;
                    }
                    positionsListEl.innerHTML = html;
                } else if (positionsListEl) {
                    positionsListEl.innerHTML = '<div class="text-center text-gray-500 text-xs py-2">Brak otwartych pozycji</div>';
                }
                
            } catch (e) {
                console.error('updateModelProfitability error:', e);
            }
        }

        async function updateStrategyPerformance() {
            try {
                // 1. Pobieramy konfigurację (żeby wiedzieć co jest czym) i historię transakcji
                const [resConfig, resWallet] = await Promise.all([
                    fetch('api/data.php?file=config.json&t=' + Date.now()),
                    fetch('api/data.php?file=paper_wallet.json&t=' + Date.now())
                ]);

                const config = await resConfig.json();
                const wallet = await resWallet.json();

                if (!wallet.trades || wallet.trades.length === 0) {
                    const list = document.getElementById('strategy-pnl-list');
                    if (list) list.innerHTML = '<tr><td colspan="3" class="text-center text-muted p-3">Brak zamkniętych transakcji</td></tr>';
                    return;
                }

                // 2. Definiujemy koszyki
                const strategies = {
                    'core': { name: '🛡️ Core (Safe)', pnl: 0, tickers: config.assets.core.tickers, alloc: config.allocation.core },
                    'speculative': { name: '🚀 Speculative', pnl: 0, tickers: config.assets.speculative.tickers, alloc: config.allocation.speculative },
                    'high_velocity': { name: '⚡ High Velocity', pnl: 0, tickers: config.assets.high_velocity.tickers, alloc: config.allocation.high_velocity },
                    'short_reserve': { name: '📉 Short Reserve', pnl: 0, tickers: config.assets.real_short.tickers, alloc: config.allocation.short_reserve }
                };

                // 3. Iterujemy przez transakcje i sumujemy zyski
                wallet.trades.forEach(trade => {
                    // Interesują nas tylko zamknięcia pozycji (SELL lub SHORT_CLOSE)
                    if (trade.action === 'SELL' || trade.action === 'SHORT_CLOSE') {
                        const pnl = parseFloat(trade.pnl || 0);
                        const ticker = trade.ticker;

                        // Specjalny przypadek: Short Reserve
                        if (trade.action === 'SHORT_CLOSE') {
                            strategies['short_reserve'].pnl += pnl;
                        } else {
                            // Dla SELL sprawdzamy, do której listy należy ticker
                            if (strategies['core'].tickers.includes(ticker)) {
                                strategies['core'].pnl += pnl;
                            } else if (strategies['speculative'].tickers.includes(ticker)) {
                                strategies['speculative'].pnl += pnl;
                            } else if (strategies['high_velocity'].tickers.includes(ticker)) {
                                strategies['high_velocity'].pnl += pnl;
                            } else {
                                // Fallback (np. jeśli ticker usunięto z configu)
                                // Można dodać do 'Speculative' lub osobnej kategorii 'Legacy'
                            }
                        }
                    }
                });

                // 4. Generujemy HTML
                const tbody = document.getElementById('strategy-pnl-list');
                if (tbody) {
                    tbody.innerHTML = '';

                    Object.values(strategies).forEach(strat => {
                        const pnlColor = strat.pnl >= 0 ? 'var(--success)' : 'var(--danger)';
                        const pnlSign = strat.pnl >= 0 ? '+' : '';
                        const allocPct = (strat.alloc * 100).toFixed(0) + '%';

                        tbody.innerHTML += `
                            <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                                <td style="padding: 0.75rem; font-weight: 600;">${strat.name}</td>
                                <td style="padding: 0.75rem; color: var(--text-muted); font-size: 0.85rem;">${allocPct}</td>
                                <td style="padding: 0.75rem; text-align: right; font-family: 'JetBrains Mono', monospace; font-weight: 700; color: ${pnlColor};">
                                    ${pnlSign}$${strat.pnl.toFixed(2)}
                                </td>
                            </tr>
                        `;
                    });
                }

            } catch (e) {
                console.warn('Błąd obliczania strategii:', e);
            }
        }

        async function updatePerformance() {
            try {
                const res = await fetch('api/data.php?file=paper_wallet.json&t=' + Date.now());
                const data = await res.json();

                const volBuys = data.total_volume_bought || 0;
                const volSells = data.total_volume_sold || 0;
                const realPnL = data.realized_pnl || 0;
                const totalFees = data.total_fees_paid || 0;

                // Update Total Bought (green/blue styling)
                const buysEl = document.getElementById('perf-buys');
                buysEl.textContent = '$' + volBuys.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                buysEl.style.color = '#60a5fa'; // Blue
                
                // Update Total Sold (purple styling)
                const sellsEl = document.getElementById('perf-sells');
                sellsEl.textContent = '$' + volSells.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                sellsEl.style.color = '#a78bfa'; // Purple

                // Update Realized PnL with proper +/- sign and color
                const pnlEl = document.getElementById('perf-pnl');
                const pnlSign = realPnL > 0 ? '+' : (realPnL < 0 ? '' : '');
                pnlEl.textContent = pnlSign + '$' + realPnL.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                pnlEl.style.color = realPnL > 0 ? '#10b981' : (realPnL < 0 ? '#ef4444' : '#94a3b8'); // Green/Red/Gray
                pnlEl.style.fontWeight = 'bold';

                // Update Total Fees (red as it's a cost)
                const feesEl = document.getElementById('perf-fees');
                if (feesEl) {
                    feesEl.textContent = '-$' + totalFees.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 4});
                    feesEl.style.color = '#ef4444'; // Red
                }

                // Accuracy from Model Stats (Scorekeeper)
                try {
                    const accRes = await fetch('api/data.php?file=model_stats.json&t=' + Date.now());
                    const accData = await accRes.json();

                    if (accData.accuracy) {
                        const score = parseFloat(accData.accuracy);
                        const accEl = document.getElementById('perf-accuracy');
                        accEl.textContent = score.toFixed(1) + '%';
                        accEl.style.color = score > 70 ? '#10b981' : (score > 50 ? '#f59e0b' : '#ef4444');
                        accEl.style.fontWeight = score > 70 ? 'bold' : 'normal';
                    } else {
                        // Fallback
                        document.getElementById('perf-accuracy').textContent = '--';
                    }
                } catch (e) {
                    // console.warn('Accuracy data missing');
                }

            } catch (e) {
                 // console.warn('Performance data not available');
            }
        }

        async function updateMarketWatch() {
            try {
                const res = await fetch('api/data.php?file=market_watch.json&t=' + Date.now());
                const data = await res.json();
                
                const listEl = document.getElementById('market-watch-list');
                // Clear loading state on first valid response (empty or not)
                if (listEl.innerHTML.includes('Loading...')) {
                    listEl.innerHTML = '';
                }

                if (!data || data.length === 0) return;
                
                // Clear again to rebuild list
                listEl.innerHTML = '';

                // Wykrywanie trybu na podstawie configu (jeśli dostępny)
                // Domyślnie FUTURES (bot pracuje na kontraktach MEXC)
                let marketType = 'FUTURES';
                if (systemConfig && systemConfig.futures_enabled) {
                    // Opcjonalnie: można tu dodać logikę wykrywania np. ":USDT" dla futures
                    marketType = 'FUTURES';
                }
                // Etykieta FUTURES w UI
                const displayType = '(FUTURES)';
                
                data.forEach(item => {
                    const isActive = item.ticker === currentTicker;
                    const changeClass = item.change_24h >= 0 ? 'positive' : 'negative';
                    const changeSign = item.change_24h >= 0 ? '+' : '';
                    
                    // Condition Score Color Logic
                    const score = item.condition_score || 0;
                    let barColor = '#94a3b8'; // Grey default
                    if (score > 75) barColor = 'var(--success)';
                    else if (score > 40) barColor = 'var(--warning)';
                    else barColor = 'var(--danger)';

                    const historyDays = item.history_days || 0;
                    const targetDays = 180; // Default target days for training
                    
                    // Check if exchange has limit (MEXC Futures = ~30 days)
                    const isExchangeLimited = historyDays > 0 && historyDays < 60; // If < 60 days, assume exchange limit
                    const effectiveTarget = isExchangeLimited ? historyDays : targetDays;
                    const dataProgress = Math.min(100, (historyDays / effectiveTarget) * 100);
                    
                    // Data progress color
                    let dataColor = '#ef4444'; // Red (< 30%)
                    if (dataProgress >= 90) dataColor = '#10b981'; // Green (> 90%)
                    else if (dataProgress >= 50) dataColor = '#f59e0b'; // Orange (50-90%)
                    
                    // Tooltip with exchange limit info
                    let tooltipText = `Data: ${historyDays}/${effectiveTarget} days (${dataProgress.toFixed(0)}%)`;
                    if (isExchangeLimited) {
                        tooltipText += `\n⚠️ Exchange limit: MEXC Futures has ~30 days max`;
                    }

                    // Smart Price Formatting
                    const displayPrice = formatPrice(item.price);

                    listEl.innerHTML += `
                        <div class="market-item ${isActive ? 'active' : ''}" data-ticker="${item.ticker}" onclick="selectTicker('${item.ticker}')">
                            <div class="market-item-header">
                                <span class="market-ticker">
                                    ${item.ticker} <span style="font-size: 0.65rem; color: var(--text-muted); font-weight: normal;">${displayType}</span>
                                </span>
                                <span class="market-change ${changeClass}">${changeSign}${item.change_24h.toFixed(2)}%</span>
                            </div>
                            <div class="market-price" style="margin-bottom:2px;">$${displayPrice}</div>

                            <div class="market-extra">
                                <div class="condition-bar" title="Trade Probability: ${score}%">
                                    <div class="condition-fill" style="width: ${score}%; background: ${barColor};"></div>
                                </div>
                                <div class="history-badge" title="${tooltipText}" style="display: flex; align-items: center; gap: 4px;">
                                    <span style="font-size: 0.65rem; font-weight: 600; color: ${dataColor};">${historyDays}D</span>
                                    <span style="font-size: 0.55rem; color: var(--text-muted);">/</span>
                                    <span style="font-size: 0.65rem; color: ${isExchangeLimited ? dataColor : 'var(--text-muted)'};">${effectiveTarget}D</span>
                                    ${isExchangeLimited ? '<i class="fas fa-info-circle" style="font-size: 0.55rem; color: #f59e0b; margin-left: 2px;" title="Exchange limit"></i>' : ''}
                                    <div style="width: 30px; height: 4px; background: rgba(255,255,255,0.1); border-radius: 2px; overflow: hidden; margin-left: 2px;">
                                        <div style="width: ${dataProgress}%; height: 100%; background: ${dataColor}; transition: width 0.3s ease;"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                });
                
            } catch (e) {
                console.warn('Market watch not available yet');
            }
        }

        /**
         * AI Training Center - Updates model training status
         * Reads from models/ai_status.json
         */
        async function updateAIStatus() {
            try {
                const res = await fetch('models/ai_status.json?t=' + Date.now());
                const data = await res.json();
                
                const container = document.getElementById('ai-models-container');
                if (!container) return;
                
                container.innerHTML = '';

                Object.keys(data).forEach(key => {
                    const model = data[key];
                    const isTraining = model.status === 'TRAINING';
                    const isError = model.status === 'ERROR';
                    
                    // Calculate time to next training
                    let countdown = "N/A";
                    let countdownColor = "#9ca3af";
                    if (model.next_training) {
                        try {
                            const nextDate = new Date(model.next_training);
                            const now = new Date();
                            const diff = nextDate - now;
                            if (diff > 0) {
                                const days = Math.floor(diff / (1000 * 60 * 60 * 24));
                                const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                                countdown = `${days}d ${hours}h`;
                                countdownColor = days <= 1 ? "#fbbf24" : "#60a5fa";
                            } else {
                                countdown = "DUE NOW";
                                countdownColor = "#ef4444";
                            }
                        } catch (e) {
                            countdown = "N/A";
                        }
                    }

                    // Progress bar color
                    const progressColor = isTraining ? '#a78bfa' : (model.accuracy > 80 ? '#10b981' : '#3b82f6');
                    const statusColor = isTraining ? '#a78bfa' : (isError ? '#ef4444' : '#9ca3af');
                    const statusIcon = isTraining ? '<i class="fa-solid fa-circle-notch fa-spin"></i>' : 
                                       (isError ? '<i class="fa-solid fa-exclamation-triangle"></i>' : 
                                        '<i class="fa-solid fa-check-circle" style="color: #10b981;"></i>');

                    // Accuracy color
                    const accuracyColor = model.accuracy > 85 ? '#10b981' : 
                                         model.accuracy > 70 ? '#fbbf24' : 
                                         '#ef4444';

                    const html = `
                    <div style="background: rgba(15, 23, 42, 0.8); border-radius: 8px; padding: 12px; border: 1px solid rgba(71, 85, 105, 0.4);">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                            <div>
                                <h3 style="font-weight: 600; color: #e2e8f0; font-size: 13px; margin-bottom: 2px;">${model.name}</h3>
                                <p style="font-size: 11px; color: ${statusColor}; margin: 0;">
                                    ${statusIcon} ${model.message}
                                </p>
                            </div>
                            <div style="text-align: right;">
                                <div style="font-size: 20px; font-weight: 700; color: ${accuracyColor}; line-height: 1;">
                                    ${model.accuracy}%
                                </div>
                                <div style="font-size: 9px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px;">Accuracy</div>
                            </div>
                        </div>

                        <div style="width: 100%; background: #1e293b; border-radius: 4px; height: 8px; margin-bottom: 10px; position: relative; overflow: hidden;">
                            <div style="background: ${progressColor}; height: 8px; border-radius: 4px; transition: width 0.5s ease; width: ${model.progress}%; ${isTraining ? 'animation: pulse 2s infinite;' : ''}" ></div>
                        </div>

                        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; font-size: 11px; border-top: 1px solid rgba(71, 85, 105, 0.3); padding-top: 8px;">
                            <div style="text-align: center;">
                                <div style="color: #64748b; margin-bottom: 2px;">Data Depth</div>
                                <div style="font-family: 'JetBrains Mono', monospace; color: #cbd5e1; font-weight: 600;">${model.data_days} Days</div>
                            </div>
                            <div style="text-align: center; border-left: 1px solid rgba(71, 85, 105, 0.3);">
                                <div style="color: #64748b; margin-bottom: 2px;">Last Update</div>
                                <div style="font-family: 'JetBrains Mono', monospace; color: #cbd5e1; font-weight: 600;">${model.last_trained ? model.last_trained.split(' ')[0] : 'Never'}</div>
                            </div>
                            <div style="text-align: center; border-left: 1px solid rgba(71, 85, 105, 0.3);">
                                <div style="color: #64748b; margin-bottom: 2px;">Next Train</div>
                                <div style="font-family: 'JetBrains Mono', monospace; color: ${countdownColor}; font-weight: 600; ${countdown === 'DUE NOW' ? 'animation: pulse 2s infinite;' : ''}">
                                    ${countdown}
                                </div>
                            </div>
                        </div>
                    </div>
                    `;
                    container.innerHTML += html;
                });
            } catch (err) {
                console.warn("AI Status not available:", err);
                // Keep loading state if error
            }
        }

        // Trader Book - Trade History & Decision Analysis
        async function updateTraderBook() {
            try {
                const res = await fetch('api/trader_book.php?t=' + Date.now());
                const data = await res.json();
                
                const container = document.getElementById('trader-book-list');
                if (!container) return;
                
                if (!data || !data.trades || data.trades.length === 0) {
                    container.innerHTML = `
                        <div style="text-align: center; padding: 2rem; color: var(--text-muted);">
                            <i class="fas fa-inbox" style="font-size: 2rem; margin-bottom: 0.5rem; opacity: 0.5;"></i>
                            <div>Brak transakcji do wyświetlenia</div>
                        </div>
                    `;
                    return;
                }
                
                // Render trades (first 10 visible, rest scrollable)
                let html = '';
                data.trades.forEach((trade, index) => {
                    const isProfit = trade.realized_pnl_pct >= 0;
                    const profitClass = isProfit ? 'profit' : 'loss';
                    const pnlClass = isProfit ? 'positive' : 'negative';
                    const pnlSign = isProfit ? '+' : '';
                    
                    // Determine decision quality badge
                    let decisionBadge = '';
                    let decisionClass = '';
                    const efficiency = (trade.realized_pnl_pct / trade.max_possible_pnl_pct) * 100;
                    
                    if (efficiency >= 80) {
                        decisionClass = 'optimal';
                        decisionBadge = 'Optimal';
                    } else if (efficiency >= 50) {
                        decisionClass = 'suboptimal';
                        decisionBadge = 'Suboptimal';
                    } else {
                        decisionClass = 'poor';
                        decisionBadge = 'Poor Timing';
                    }
                    
                    // Determine side badge styling
                    const sideBadgeClass = trade.side === 'LONG' ? 'badge-success' : 'badge-danger';
                    const sideBadgeIcon = trade.side === 'LONG' ? '📈' : '📉';
                    
                    html += `
                        <div class="trade-book-item ${profitClass}">
                            <div class="trade-book-header">
                                <span class="trade-book-symbol">
                                    <i class="fas fa-${trade.side === 'LONG' ? 'arrow-up' : 'arrow-down'}"></i>
                                    ${trade.symbol}
                                </span>
                                <span class="badge ${sideBadgeClass}" style="font-size: 0.7rem; padding: 0.25rem 0.5rem; margin-left: 0.5rem;">
                                    ${sideBadgeIcon} ${trade.side}
                                </span>
                                <span class="trade-book-pnl ${pnlClass}" style="margin-left: auto;">
                                    ${pnlSign}${trade.realized_pnl_pct.toFixed(2)}%
                                </span>
                            </div>
                            <div class="trade-book-details">
                                <div class="trade-book-row">
                                    <span class="trade-book-label">Kupno:</span>
                                    <span class="trade-book-value">$${trade.entry_price.toFixed(2)}</span>
                                </div>
                                <div class="trade-book-row">
                                    <span class="trade-book-label">Sprzedaż:</span>
                                    <span class="trade-book-value">$${trade.exit_price.toFixed(2)}</span>
                                </div>
                                <div class="trade-book-row">
                                    <span class="trade-book-label">Wydano:</span>
                                    <span class="trade-book-value">$${trade.invested_usdt.toFixed(2)}</span>
                                </div>
                                <div class="trade-book-row">
                                    <span class="trade-book-label">PnL:</span>
                                    <span class="trade-book-value ${pnlClass}">
                                        ${pnlSign}$${trade.realized_pnl_usdt.toFixed(2)}
                                    </span>
                                </div>
                                <div class="trade-book-row" style="background: rgba(255, 193, 7, 0.05); padding: 0.25rem; border-radius: 4px; margin: 0.25rem 0;">
                                    <span class="trade-book-label" style="font-weight: 600;">
                                        <i class="fas fa-star"></i> Max możliwy:
                                    </span>
                                    <span class="trade-book-value" style="color: var(--warning); font-weight: 700;">
                                        +${trade.max_possible_pnl_pct.toFixed(2)}%
                                    </span>
                                </div>
                                <div class="trade-book-row">
                                    <span class="trade-book-label">Decyzja:</span>
                                    <span class="trade-book-badge ${decisionClass}">${decisionBadge}</span>
                                </div>
                            </div>
                            <div style="margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid rgba(255,255,255,0.05); font-size: 0.65rem; color: var(--text-muted); display: flex; justify-content: space-between;">
                                <span><i class="fas fa-sign-in-alt"></i> ${trade.entry_time}</span>
                                <span><i class="fas fa-sign-out-alt"></i> ${trade.exit_time}</span>
                            </div>
                        </div>
                    `;
                });
                
                container.innerHTML = html;
                
            } catch (err) {
                console.warn("Trader Book not available:", err);
                const container = document.getElementById('trader-book-list');
                if (container) {
                    container.innerHTML = `
                        <div style="text-align: center; padding: 2rem; color: var(--danger);">
                            <i class="fas fa-exclamation-triangle" style="font-size: 2rem; margin-bottom: 0.5rem;"></i>
                            <div>Błąd ładowania Trader Book</div>
                        </div>
                    `;
                }
            }
        }

    // --- NAPRAWIONA FUNKCJA (Wklej w index.php zamiast starej selectTicker) ---
    async function selectTicker(input) {
        let ticker;
        let element = null;

        // 1. Jeśli wywołano przez kliknięcie myszką
        if (input && input.target) {
            const target = input.target.closest('[data-ticker]');
            if (target) {
                ticker = target.getAttribute('data-ticker');
                element = target;
            }
        }
        // 2. Jeśli wywołano automatycznie przy starcie (jako tekst)
        else if (typeof input === 'string') {
            ticker = input;
            element = document.querySelector(`[data-ticker="${ticker}"]`);
        }

        if (!ticker) return; // Jeśli nie udało się znaleźć tickera, przerwij

        console.log("Wybrano ticker:", ticker);
        currentTicker = ticker;

        // Podświetlenie na liście
        document.querySelectorAll('.market-item').forEach(el => {
            el.classList.remove('active');
        });
        if (element) {
            element.classList.add('active');
        }

        // Aktualizacja nagłówka
        const chartTitle = document.getElementById('chart-title');
        if (chartTitle) chartTitle.innerHTML = ticker + ' <span style="font-size:0.8rem; color:#94a3b8;">(FUTURES)</span> Chart';

        // Update stats immediately from local market watch if available
        const mwList = document.querySelectorAll('.market-item');
        mwList.forEach(item => {
             // Używamy data-ticker dla pewności
             if (item.getAttribute('data-ticker') === ticker) {
                 const priceTxt = item.querySelector('.market-price').innerText;
                 const statPrice = document.getElementById('stat-price');
                 if (statPrice) statPrice.textContent = priceTxt;
             }
        });

        // WYWOŁANIE RYSOWANIA WYKRESU (Mapowanie na istniejące funkcje)
        if (typeof updateResults === 'function') {
            updateResults();
        }
        if (typeof loadTickerHistory === 'function') {
            await loadTickerHistory(ticker);
        }
    }

        async function loadTickerHistory(ticker, type = 'LITE') {
            // KEEP - nie resetuj wykresu, tylko odśwież predykcje
            if (type === 'KEEP') {
                if (chartData[ticker]) {
                    // Zachowaj obecny timeframe i tylko odśwież wykres z istniejącymi danymi
                    updateChart(chartData[ticker]);
                }
                return;
            }

            try {
                const tickerClean = ticker.replace('/', '');
                const filename = type === 'FULL'
                    ? `history_${tickerClean}_FULL.json`
                    : `history_${tickerClean}_LITE.json`;

                const res = await fetch(`api/data.php?file=${filename}&t=` + Date.now());

                if (!res.ok) throw new Error('File not found');

                const data = await res.json();
                
                // Store data
                chartData[ticker] = data;
                chartData[ticker + '_type'] = type; // Track what type we have loaded

                // Jeśli użytkownik jest w trybie filtrowanym (np. 1H), zaaplikuj filtr
                if (currentTimeframe !== 'all') {
                    updateChartTimeframe(currentTimeframe);
                } else {
                    updateChart(data);
                }
                
            } catch (e) {
                console.error('Failed to load history for', ticker, e);
                // Fallback to standard if LITE/FULL missing (backward compatibility)
                if (type !== 'standard') {
                     try {
                        const tickerClean = ticker.replace('/', '');
                        const res = await fetch(`api/data.php?file=history_${tickerClean}.json&t=` + Date.now());
                        const data = await res.json();
                        chartData[ticker] = data;
                        chartData[ticker + '_type'] = 'standard';
                        updateChart(data);
                     } catch (err) {}
                }
            }
        }

        function initializeChart() {
            const options = {
                series: [
                    {
                        name: 'Price',
                        type: 'candlestick',
                        data: []
                    },
                    {
                        name: 'Volume',
                        type: 'bar',
                        data: []
                    },
                    {
                        name: 'LSTM Prediction (30min)',
                        type: 'boxPlot',  // boxPlot pozwala na custom kolor
                        data: []
                    },
                    {
                        name: 'Validation',
                        type: 'scatter',
                        data: []
                    },
                    {
                        name: 'RL Agent Hits (30min)',
                        type: 'scatter',
                        data: []
                    },
                    {
                        name: 'RL Agent Misses (30min)',
                        type: 'scatter',
                        data: []
                    }
                ],
                chart: {
                    type: 'candlestick',
                    height: 400,
                    background: 'transparent',
                    toolbar: {
                        show: true,
                        tools: {
                            download: true,
                            selection: true,
                            zoom: true,
                            zoomin: true,
                            zoomout: true,
                            pan: true,
                        }
                    }
                },
                theme: {
                    mode: 'dark'
                },
                xaxis: {
                    type: 'datetime',
                    labels: {
                        style: {
                            colors: '#94a3b8'
                        }
                    }
                },
                yaxis: [
                    {
                        seriesName: 'Price',
                        tooltip: { enabled: true },
                        labels: {
                            style: { colors: '#94a3b8' },
                            formatter: function(val) { return '$' + val.toFixed(2); }
                        }
                    },
                    {
                        seriesName: 'Volume',
                        opposite: true,
                        show: false
                    }
                ],
                grid: {
                    borderColor: '#334155'
                },
                plotOptions: {
                    candlestick: {
                        colors: {
                            upward: '#10b981',   // Zielone świece UP
                            downward: '#ef4444'  // Czerwone świece DOWN
                        },
                        wick: {
                            useFillColor: true
                        }
                    },
                    bar: {
                        columnWidth: '50%',
                        colors: {
                            ranges: [{
                                from: 0,
                                to: 1000000000,
                                color: 'rgba(100, 116, 139, 0.3)' // Szare volume
                            }]
                        }
                    },
                    boxPlot: {
                        colors: {
                            upper: '#00D9FF',  // Cyan/Niebieskie prediction
                            lower: '#00D9FF'
                        }
                    }
                },
                stroke: {
                    width: [1, 1, 3, 0, 0, 0],  // Price: 1, Volume: 1, Prediction: 3, Validation: 0, RL Hits: 0, RL Misses: 0
                    colors: ['#10b981', '#64748b', '#00D9FF', '#ff0000', '#a855f7', '#ffffff']  // Price: Green, Volume: Gray, LSTM: Cyan, Validation: Red, RL Hits: Purple, RL Misses: White
                },
                fill: {
                    opacity: [1, 0.3, 0.7, 1, 0.9, 0.9]  // Price: 100%, Volume: 30%, LSTM: 70%, Validation: 100%, RL Hits: 90%, RL Misses: 90%
                },
                markers: {
                     size: [0, 0, 0, 6, 8, 8],  // Price: 0, Volume: 0, LSTM: 0, Validation: 6, RL Hits: 8 (bigger!), RL Misses: 8
                     strokeWidth: 2,
                     strokeColors: ['#10b981', '#64748b', '#00D9FF', '#ff0000', '#a855f7', '#64748b'],  // RL Misses border: gray
                     hover: { size: 10 }
                },
                dataLabels: {
                    enabled: false
                },
                legend: {
                    show: true,
                    position: 'top',
                    horizontalAlign: 'left',
                    labels: {
                        colors: '#94a3b8'
                    }
                },
                tooltip: {
                    shared: false,
                    intersect: true,
                    custom: function({seriesIndex, dataPointIndex, w}) {
                        const data = w.globals.initialSeries[seriesIndex].data[dataPointIndex];
                        if (seriesIndex === 0 && data && data.y) {
                            // Price candlestick
                            return '<div class="apexcharts-tooltip-candlestick">' +
                                '<div>Open: <span>' + data.y[0].toFixed(2) + '</span></div>' +
                                '<div>High: <span>' + data.y[1].toFixed(2) + '</span></div>' +
                                '<div>Low: <span>' + data.y[2].toFixed(2) + '</span></div>' +
                                '<div>Close: <span>' + data.y[3].toFixed(2) + '</span></div>' +
                                '</div>';
                        }
                        // RL Predictions tooltip (seriesIndex 4 = Hits, 5 = Misses)
                        if ((seriesIndex === 4 || seriesIndex === 5) && data && data.meta) {
                            const isHit = seriesIndex === 4;
                            const statusColor = isHit ? '#a855f7' : '#ffffff';
                            const statusText = isHit ? 'HIT ✓' : 'MISS ✗';
                            
                            return '<div class="apexcharts-tooltip-custom" style="padding: 8px; background: rgba(0,0,0,0.9); border-radius: 4px;">' +
                                '<div style="color: ' + statusColor + '; font-weight: bold; margin-bottom: 4px;">RL Agent ' + statusText + '</div>' +
                                '<div style="color: #94a3b8;">Predicted: <span style="color: #fff;">$' + data.y.toFixed(2) + '</span></div>' +
                                (data.meta.actual ? '<div style="color: #94a3b8;">Actual: <span style="color: #fff;">$' + data.meta.actual.toFixed(2) + '</span></div>' : '') +
                                '</div>';
                        }
                        return '';
                    }
                }
            };

            chart = new ApexCharts(document.querySelector("#advanced-chart"), options);
            chart.render();
        }

        async function updateChart(data) {
            console.log('updateChart called', {
                hasChart: !!chart,
                hasData: !!data,
                dataLength: data ? data.length : 0,
                currentTicker: currentTicker
            });
            
            if (!chart || !data || data.length === 0) {
                console.warn('updateChart early return - missing chart or data');
                return;
            }
            
            // Transform data
            const candleData = data.map(candle => {
                return {
                    x: new Date(candle[0]),
                    y: [candle[1], candle[2], candle[3], candle[4]] // [open, high, low, close]
                };
            });

            const volumeData = data.map(candle => {
                return {
                    x: new Date(candle[0]),
                    y: candle[5] // volume
                };
            });
            
                // Fetch Prediction Candles (OHLC dla przezroczystych świec)
            let predictionCandleData = [];
            let validationData = [];
            let annotationPoints = []; // Defined in outer scope
            let predictedPrice = null;

            try {
                const res = await fetch('api/data.php?file=latest_results.json&ticker=' + encodeURIComponent(currentTicker) + '&t=' + Date.now());
                const results = await res.json();

                if (results.predicted_price) {
                     predictedPrice = results.predicted_price;
                }

                // Use prediction_candles if available - convert OHLC to boxPlot format
                // boxPlot format: [min, q1, median, q3, max] = [low, open, (open+close)/2, close, high]
                if (results.prediction_candles && Array.isArray(results.prediction_candles) && results.timestamp) {
                    const startTime = new Date(results.timestamp).getTime();
                    
                    results.prediction_candles.forEach((candle, index) => {
                        const median = (candle.open + candle.close) / 2;
                        const q1 = Math.min(candle.open, candle.close);
                        const q3 = Math.max(candle.open, candle.close);
                        
                        predictionCandleData.push({
                            x: new Date(startTime + (index + 1) * 15 * 60 * 1000),
                            y: [candle.low, q1, median, q3, candle.high]
                        });
                    });
                } 
                // Fallback to prediction_vector
                else if (results.prediction_vector && results.timestamp) {
                    const startTime = new Date(results.timestamp).getTime();
                    results.prediction_vector.forEach((price, index) => {
                        const smallRange = price * 0.002; // 0.2% range
                        predictionCandleData.push({
                            x: new Date(startTime + (index + 1) * 15 * 60 * 1000),
                            y: [price - smallRange, price - smallRange*0.5, price, price + smallRange*0.5, price + smallRange]
                        });
                    });
                }

                // Fetch Validation Points (Hits/Misses)
                try {
                    const refRes = await fetch('api/data.php?file=referee_history.json&t=' + Date.now());
                    const refData = await refRes.json();

                    const tickerHistory = refData[currentTicker] || [];

                    tickerHistory.forEach(entry => {
                        // Only add if within chart range
                        if (candleData.length > 0 && entry.t >= candleData[0].x.getTime()) {
                            // Backend sends 'result', not 'r'
                            const outcome = entry.result || entry.r || 'PENDING';
                            let color = '#FFA500'; // Pending Orange
                            if (outcome === 'HIT') color = '#00E396'; // Green
                            if (outcome === 'MISS') color = '#FF4560'; // Red

                            // Add to validation series for scatter plot
                            validationData.push({
                                x: entry.t,
                                y: entry.p,
                                fillColor: color,
                                strokeColor: '#fff',
                                meta: {
                                    result: outcome
                                }
                            });

                            // Also add as Annotation Point (per Requirement)
                            annotationPoints.push({
                                x: entry.t,
                                y: entry.p,
                                marker: {
                                    size: 4,
                                    fillColor: color,
                                    strokeColor: '#fff',
                                    strokeWidth: 2,
                                    shape: "circle",
                                    radius: 2
                                },
                                tooltip: {
                                    text: "AI Validation: " + outcome
                                }
                            });
                        }
                    });
                } catch (e) {
                    // console.warn('Referee history not available');
                }

            } catch (e) {
                // console.warn('Prediction data missing');
            }

            // Fetch RL Predictions (Hits & Misses) - NEW!
            let rlHitsData = [];
            let rlMissesData = [];
            
            try {
                const rlRes = await fetch('api/data.php?endpoint=rl_predictions&ticker=' + encodeURIComponent(currentTicker) + '&limit=100&t=' + Date.now());
                const rlPredictions = await rlRes.json();
                
                rlPredictions.forEach(pred => {
                    const point = {
                        x: pred.timestamp,
                        y: pred.predicted,
                        meta: {
                            actual: pred.actual,
                            hit: pred.hit
                        }
                    };
                    
                    // Separate hits and misses
                    if (pred.hit === true) {
                        rlHitsData.push(point);  // Purple dots
                    } else if (pred.hit === false) {
                        rlMissesData.push(point);  // White dots
                    }
                    // If hit === null, prediction is still pending (not shown)
                });
                
                console.log('RL Predictions loaded:', {
                    hits: rlHitsData.length,
                    misses: rlMissesData.length
                });
            } catch (e) {
                console.error('Failed to load RL predictions:', e);
            }

            chart.updateSeries([
                {
                    name: 'Price',
                    type: 'candlestick',
                    data: candleData
                },
                {
                    name: 'Volume',
                    type: 'bar',
                    data: volumeData
                },
                {
                    name: 'LSTM Prediction (30min)',
                    type: 'boxPlot',
                    data: predictionCandleData
                },
                {
                    name: 'Validation',
                    type: 'scatter',
                    data: validationData
                },
                {
                    name: 'RL Agent Hits (30min)',
                    type: 'scatter',
                    data: rlHitsData
                },
                {
                    name: 'RL Agent Misses (30min)',
                    type: 'scatter',
                    data: rlMissesData
                }
            ]);

            // Add Prediction Annotation if available
            let yaxisAnnotations = [];
            if (predictedPrice) {
                yaxisAnnotations.push({
                    y: predictedPrice,
                    borderColor: '#F6E05E',
                    strokeDashArray: 6,
                    label: {
                        borderColor: '#F6E05E',
                        style: {
                            color: '#000',
                            background: '#F6E05E',
                            fontSize: '12px',
                            fontWeight: 'bold'
                        },
                        text: 'AI Target (6H)'
                    }
                });
            }

            // Add FVG Annotations
            try {
                    const res = await fetch('api/data.php?file=latest_results.json&ticker=' + encodeURIComponent(currentTicker) + '&t=' + Date.now());
                const results = await res.json();

                if (results.active_fvgs && results.ticker === currentTicker) {
                    results.active_fvgs.forEach(fvg => {
                        const color = fvg.type === 'BULLISH' ? '#10b981' : '#ef4444';
                        const label = fvg.type === 'BULLISH' ? 'FVG BUY ZONE' : 'FVG SELL ZONE';
                        yaxisAnnotations.push({
                            y: fvg.bottom,
                            y2: fvg.top,
                            fillColor: color,
                            opacity: 0.2,
                            label: {
                                borderColor: color,
                                style: {
                                    color: '#fff',
                                    background: color,
                                    fontSize: '10px',
                                    padding: {
                                        left: 5,
                                        right: 5,
                                        top: 2,
                                        bottom: 2,
                                    }
                                },
                                text: label,
                                position: 'left'
                            }
                        });
                    });
                }
            } catch(e) {}

            // Update all annotations
            chart.updateOptions({
                annotations: {
                    yaxis: yaxisAnnotations,
                    points: annotationPoints
                }
            });
        }

        async function updateChartTimeframe(timeframe) {
            currentTimeframe = timeframe; // Zapamiętaj wybór użytkownika

            document.querySelectorAll('.chart-button').forEach(btn => {
                btn.classList.remove('active');
                if(btn.dataset.timeframe === timeframe) btn.classList.add('active');
            });

            // Filter chart data based on timeframe
            if (!chartData[currentTicker]) return;
            
            let filteredData = chartData[currentTicker];
            const now = Date.now();
            
            if (timeframe === '1h') {
                filteredData = chartData[currentTicker].filter(c => c[0] > now - 3600000);
            } else if (timeframe === '4h') {
                filteredData = chartData[currentTicker].filter(c => c[0] > now - 14400000);
            } else if (timeframe === '1d') {
                filteredData = chartData[currentTicker].filter(c => c[0] > now - 86400000);
            } else if (timeframe === '4d') {
                filteredData = chartData[currentTicker].filter(c => c[0] > now - 345600000); // 4 dni = 96h
            }
            
            updateChart(filteredData);
        }

        // Current active log tab
        let currentLogTab = 'system';

        // Switch between log tabs
        function switchLogTab(tab) {
            currentLogTab = tab;
            
            // Update tab buttons
            document.querySelectorAll('.log-tab-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.closest('.log-tab-btn').classList.add('active');
            
            // Update terminal visibility
            document.getElementById('terminal-system-logs').style.display = tab === 'system' ? 'block' : 'none';
            document.getElementById('terminal-ppo-logs').style.display = tab === 'ppo' ? 'block' : 'none';
            document.getElementById('terminal-lstm-logs').style.display = tab === 'lstm' ? 'block' : 'none';
            
            // Immediately update the active tab
            updateLogs();
        }

        async function updateLogs() {
            try {
                // Determine which log file to fetch based on active tab
                let logFile, terminalId;
                
                if (currentLogTab === 'system') {
                    logFile = 'logs/system.log';
                    terminalId = 'terminal-system-logs';
                } else if (currentLogTab === 'ppo') {
                    logFile = 'logs/PPO.log';
                    terminalId = 'terminal-ppo-logs';
                } else if (currentLogTab === 'lstm') {
                    logFile = 'logs/LSTM.log';
                    terminalId = 'terminal-lstm-logs';
                }
                
                const res = await fetch(`api/data.php?file=${logFile}&t=` + Date.now());
                const text = await res.text();
                
                const lines = text.trim().split('\n').slice(-20);  // Last 20 lines
                const logsEl = document.getElementById(terminalId);
                
                if (!logsEl) return;
                
                logsEl.innerHTML = '';
                
                lines.forEach(line => {
                    let className = 'log-entry';
                    if (line.includes('[ERROR]')) className += ' log-error';
                    else if (line.includes('[SUCCESS]')) className += ' log-success';
                    else if (line.includes('[WARNING]')) className += ' log-warning';
                    
                    logsEl.innerHTML += `<div class="${className}">${line}</div>`;
                });
                
                logsEl.scrollTop = logsEl.scrollHeight;
                
            } catch (e) {
                console.warn(`Logs not available yet (${currentLogTab})`);
            }
        }

        // AI Chat Functions
        async function sendMessage() {
            const input = document.getElementById('chat-input');
            const btn = document.getElementById('chat-send-btn');
            const message = input.value.trim();
            
            if (!message) return;
            
            // Disable input
            input.disabled = true;
            btn.disabled = true;
            
            // Add user message to chat
            addMessageToChat('user', message);
            input.value = '';
            
            // Show typing indicator
            const typingId = addMessageToChat('ai', '<div class="spinner"></div>');
            
            try {
                // Setup AbortController for timeout (30s)
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 30000);

                // Call AI chat backend
                const response = await fetch('api/ai_chat.php', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        message: message,
                        history: conversationHistory,
                        ticker: currentTicker
                    }),
                    signal: controller.signal
                });

                clearTimeout(timeoutId);

                // Check for HTTP errors (404, 500)
                if (!response.ok) {
                    throw new Error('Network response was not ok: ' + response.status);
                }
                
                const data = await response.json();
                
                if (data.success) {
                    // Add AI response
                    addMessageToChat('ai', data.response);
                    
                    // Update conversation history
                    conversationHistory.push({role: 'user', content: message});
                    conversationHistory.push({role: 'assistant', content: data.response});
                    
                    // Keep only last 20 exchanges
                    if (conversationHistory.length > 20) {
                        conversationHistory = conversationHistory.slice(-20);
                    }
                } else {
                    addMessageToChat('ai', data.fallback_response || 'Sorry, I encountered an error. Please try again.');
                }
                
            } catch (error) {
                console.error('Chat error:', error);
                addMessageToChat('ai', 'System Message: Chat Connection Failed (Check Console)');
            } finally {
                // Remove typing indicator safely
                try { document.getElementById(typingId).remove(); } catch(e){}

                // Re-enable input ALWAYS, even if error occurs
                input.disabled = false;
                btn.disabled = false;
                input.focus();
            }
        }

        function addMessageToChat(role, content) {
            const messagesContainer = document.getElementById('chat-messages');
            const messageId = 'msg-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
            
            const messageDiv = document.createElement('div');
            messageDiv.className = 'chat-message ' + role;
            messageDiv.id = messageId;
            
            const avatar = role === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';
            
            messageDiv.innerHTML = `
                <div class="chat-avatar ${role}">
                    ${avatar}
                </div>
                <div class="chat-bubble">
                    <div class="chat-bubble-text">${content}</div>
                    <div class="chat-timestamp">${new Date().toLocaleTimeString()}</div>
                </div>
            `;
            
            messagesContainer.appendChild(messageDiv);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
            
            return messageId;
        }

        async function updateRadar() {
            // 1. Zawsze pokaż panel (nawet jak pusty)
            const radarPanel = document.getElementById('radar-panel');
            if(radarPanel) {
                radarPanel.style.display = 'block';
                // Upewnij się, że styl jest nadpisany
                radarPanel.style.setProperty('display', 'block', 'important');
            }

            // 2. Pobierz status
            try {
                // Czytamy plik statusu (który main.py powinien generować)
                const res = await fetch('api/data.php?file=radar_scan.json&t=' + Date.now());
                const data = await res.json();

                // Auto-Clear Logic (Stale Data > 10m)
                // Relaxed check to handle potential server/client time mismatches (e.g. 2026 dates)
                let isStale = false;
                if (data.timestamp) {
                    const scanTime = new Date(data.timestamp);
                    const now = new Date();
                    const diffMins = (now - scanTime) / 1000 / 60;
                    // Only mark stale if POSITIVELY old (past data) > 10 mins.
                    // Future dates (negative diff) are treated as fresh/live.
                    if (diffMins > 10) isStale = true;
                }

                // Nagłówek i timestamp
                document.getElementById('radar-timestamp').innerText = data.timestamp ? "Last Scan: " + data.timestamp : "Scanning...";

                const list = document.getElementById('radar-list');
                list.innerHTML = '';

                if (isStale) {
                    // Show warning but DO NOT hide data
                    document.getElementById('radar-timestamp').innerHTML += ' <span class="badge bg-warning"><i class="fas fa-clock"></i> STALE</span>';
                }

                // Jeśli mamy znalezione "Gemy"
                if (data.gems && data.gems.length > 0) {
                    data.gems.forEach(gem => {
                        let badgeClass = 'bg-secondary';
                        let signalText = gem.trend || 'NEUTRAL';
                        let signalIcon = '';

                        // Map Trend to Visual Signal
                        if (signalText === 'BULLISH') {
                            badgeClass = 'bg-success';
                            signalIcon = '🚀';
                        } else if (signalText === 'BEARISH') {
                            badgeClass = 'bg-danger';
                            signalIcon = '📉';
                        } else if (signalText === 'RANGE') {
                            badgeClass = 'bg-warning text-dark';
                            signalIcon = '↔️';
                        }

                        // Use 'signal' field if present (legacy compatibility), otherwise use trend
                        if (gem.signal && gem.signal.includes('🚀')) {
                             signalText = gem.signal;
                             badgeClass = 'bg-purple'; // Purple for explicit signals
                        } else {
                             signalText = `${signalIcon} ${signalText}`;
                        }

                        list.innerHTML += `
                            <tr>
                                <td class="fw-bold text-white">${gem.ticker}</td>
                                <td><span class="badge ${badgeClass}">${signalText}</span></td>
                                <td>$${formatPrice(gem.price)}</td>
                                <td><button class="btn btn-xs btn-outline-success">COPY</button></td>
                            </tr>
                        `;
                    });
                } else {
                    // Jeśli nic nie znaleziono, pokaż animację skanowania
                    list.innerHTML = `
                        <tr>
                            <td colspan="4" style="text-align:center; padding: 20px; color: var(--text-muted);">
                                <div class="spinner" style="width: 15px; height: 15px; margin-right: 10px;"></div>
                                Scanning Market Deep Space (Targeting Top 50)...
                            </td>
                        </tr>
                    `;
                }
            } catch (e) {
                // Jeśli błąd odczytu, też pokaż loader
                console.error("Radar update error:", e);
                const list = document.getElementById('radar-list');
                if(list && list.innerHTML.trim() === '') {
                     list.innerHTML = '<tr><td colspan="4" class="text-center text-muted">Initializing Radar Uplink...</td></tr>';
                }
            }
        }

        // Uruchom odświeżanie co 5 sekund
        setInterval(updateRadar, 5000);
        updateRadar(); // Run immediately

        // --- SCOREKEEPER VIEWER ---
        function updateStats() {
            // Switch to brain_stats.json (Referee System)
            fetch('api/data.php?file=brain_stats.json&t=' + Date.now())
                .then(response => response.json())
                .then(data => {
                    // Training Status
                    if (data.training_status !== undefined) {
                        const statusEl = document.getElementById('lstm-params');
                        statusEl.textContent = data.training_status;
                        
                        // Color coding
                        if (data.training_status.includes('Aktywne') || data.training_status.includes('zakończony')) {
                            statusEl.style.color = 'var(--success)';
                        } else {
                            statusEl.style.color = 'var(--warning)';
                        }
                    }
                    
                    // Training Count
                    if (data.training_count !== undefined) {
                        document.getElementById('lstm-training-count').innerText = data.training_count;
                    }
                    
                    // Training Progress (Model Completeness)
                    if (data.training_progress !== undefined) {
                        const progress = parseFloat(data.training_progress).toFixed(1);
                        const progressEl = document.getElementById('lstm-progress');
                        progressEl.innerText = progress + "%";
                        
                        // Color based on completeness
                        if (progress >= 80) {
                            progressEl.style.color = 'var(--success)';
                        } else if (progress >= 50) {
                            progressEl.style.color = 'var(--warning)';
                        } else {
                            progressEl.style.color = 'var(--danger)';
                        }
                    }
                    
                    // Accuracy
                    if (data.accuracy !== undefined) {
                        // Display fix: Backend returns 0.65 for 65%.
                        const accVal = parseFloat(data.accuracy);
                        // If it's already > 1, assume percentage (e.g. 58.76)
                        const displayAcc = (accVal <= 1) ? (accVal * 100).toFixed(2) : accVal.toFixed(2);
                        const accEl = document.getElementById('lstm-accuracy');
                        accEl.innerText = displayAcc + "%";
                        
                        // Color based on accuracy
                        if (accVal >= 0.70) {
                            accEl.style.color = 'var(--success)';
                        } else if (accVal >= 0.55) {
                            accEl.style.color = 'var(--warning)';
                        } else {
                            accEl.style.color = 'var(--danger)';
                        }
                    } else {
                        // Fallback to model_stats if brain_stats empty
                        return fetch('api/data.php?file=model_stats.json&t=' + Date.now()).then(r=>r.json());
                    }

                    // Hits / Misses
                    if (data.hits !== undefined && data.misses !== undefined) {
                        document.getElementById('lstm-hits-misses').innerText = data.hits + " / " + data.misses;
                    }
                    
                    // Accuracy to Goal (% points remaining to 90%)
                    if (data.accuracy_to_goal !== undefined) {
                        const remaining = parseFloat(data.accuracy_to_goal).toFixed(1);
                        const goalEl = document.getElementById('lstm-accuracy-to-goal');
                        
                        if (remaining <= 0) {
                            goalEl.innerText = "🎯 Osiągnięto!";
                            goalEl.style.color = 'var(--success)';
                        } else {
                            goalEl.innerText = remaining + "% pozostało";
                            goalEl.style.color = 'var(--text-muted)';
                        }
                    }
                    
                    // Next Training
                    if (data.next_training_minutes !== undefined) {
                        const minutes = parseInt(data.next_training_minutes);
                        document.getElementById('lstm-next-training').innerText = minutes + " min";
                    } else if (data.training_status && data.training_status.includes('zakończony')) {
                        document.getElementById('lstm-next-training').innerText = "30 min";
                    }
                    
                    // Last Check - Format nicely
                    if (data.last_check !== undefined) {
                        try {
                            const dt = new Date(data.last_check);
                            const formatted = dt.toLocaleString('pl-PL', {
                                year: 'numeric',
                                month: 'short',
                                day: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit',
                                second: '2-digit'
                            });
                            document.getElementById('lstm-last-check').innerText = formatted;
                        } catch(e) {
                            document.getElementById('lstm-last-check').innerText = data.last_check;
                        }
                    }
                })
                .then(data => {
                    // Handle fallback data if needed
                    if (data && data.accuracy_rate && document.getElementById('lstm-accuracy').innerText === '--%') {
                         document.getElementById('lstm-accuracy').innerText = data.accuracy_rate + "%";
                    }
                })
                .catch(err => console.error("Error fetching stats:", err));
        }
        setInterval(updateStats, 5000);
        updateStats(); // Initial call
        
        // --- RL AGENT STATS UPDATER (NEW!) ---
        function updateRLStats() {
            fetch('api/data.php?file=rl_brain_stats.json&t=' + Date.now())
                .then(response => response.json())
                .then(data => {
                    // Training Status
                    if (data.training_status !== undefined) {
                        const statusEl = document.getElementById('rl-training-status');
                        statusEl.textContent = data.training_status;
                        
                        // Color coding
                        if (data.training_status === 'ACTIVE') {
                            statusEl.style.color = 'var(--success)';
                        } else if (data.training_status === 'TRAINING IN PROGRESS' || data.training_status === 'IN_PROGRESS') {
                            statusEl.style.color = 'var(--warning)';
                        } else if (data.training_status === 'NOT TRAINED') {
                            statusEl.style.color = 'var(--error)';
                        } else {
                            statusEl.style.color = 'var(--text-muted)';
                        }
                    }
                    
                    // Win Rate (Accuracy)
                    if (data.accuracy !== undefined) {
                        const accVal = parseFloat(data.accuracy);
                        const displayAcc = (accVal <= 1) ? (accVal * 100).toFixed(2) : accVal.toFixed(2);
                        document.getElementById('rl-win-rate').innerText = displayAcc + "%";
                    }
                    
                    // Hits / Misses
                    if (data.hits !== undefined && data.misses !== undefined) {
                        document.getElementById('rl-hits-misses').innerText = data.hits + " / " + data.misses;
                    }
                    
                    // Last Decision (use last_check as proxy)
                    if (data.last_check) {
                        const lastTime = new Date(data.last_check).toLocaleTimeString();
                        document.getElementById('rl-last-decision').innerText = lastTime;
                    }
                    
                    // Next Training
                    if (data.next_training) {
                        const nextTime = new Date(data.next_training);
                        const now = new Date();
                        const diff = nextTime - now;
                        
                        if (diff > 0) {
                            const days = Math.floor(diff / (1000 * 60 * 60 * 24));
                            const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                            const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
                            
                            let timeStr = '';
                            if (days > 0) timeStr += `${days}d `;
                            if (hours > 0) timeStr += `${hours}h `;
                            timeStr += `${minutes}m`;
                            
                            document.getElementById('rl-next-training').innerText = timeStr;
                        } else {
                            document.getElementById('rl-next-training').innerText = 'Soon';
                        }
                    }
                })
                .catch(err => {
                    console.error('rl_brain_stats.json failed:', err);
                    // Set defaults on error
                    document.getElementById('rl-training-status').innerText = 'NOT TRAINED';
                    document.getElementById('rl-training-status').style.color = 'var(--text-muted)';
                });
        }
        setInterval(updateRLStats, 5000);  // Update every 5 seconds
        updateRLStats(); // Initial call

        // --- HOLISTIC GUARDIAN WIDGET ---
        async function updateHolisticGuardian() {
            try {
                const res = await fetch('api/data.php?file=holistic_status.json&t=' + Date.now());
                if (!res.ok) return;
                const data = await res.json();

                // Check if data is valid
                if (!data || data.status === 'waiting_for_data') return;

                const guardianCard = document.getElementById('guardian-card');
                if (!guardianCard) {
                    // Create card dynamically if it doesn't exist
                    const container = document.querySelector('.right-column'); // Use right column
                    if (container) {
                        const div = document.createElement('div');
                        div.className = 'card mb-4';
                        div.id = 'guardian-card';
                        div.style.marginBottom = '1.5rem';
                        div.innerHTML = `
                            <div class="card-header">
                                <div class="card-title"><i class="fas fa-shield-alt"></i> Holistic Guardian</div>
                            </div>
                            <div class="card-body text-center">
                                <h3 id="guardian-mode" class="mb-2">LOADING...</h3>
                                <div class="progress" style="height: 10px; background: #334155; border-radius: 5px; margin-bottom: 10px;">
                                    <div id="guardian-bar" class="progress-bar" style="width: 50%; background: #94a3b8;"></div>
                                </div>
                                <div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: #94a3b8;">
                                    <span id="guardian-trend">Trend: --%</span>
                                    <span id="guardian-score">Risk: --</span>
                                </div>
                                <div id="guardian-reason" style="margin-top: 10px; font-size: 0.8rem; color: #cbd5e1; font-style: italic;">
                                    Initializing safety protocols...
                                </div>
                            </div>
                        `;
                        container.insertBefore(div, container.firstChild); // Add to top of right column
                    }
                }

                // Update Data
                const modeEl = document.getElementById('guardian-mode');
                const barEl = document.getElementById('guardian-bar');
                const trendEl = document.getElementById('guardian-trend');
                const scoreEl = document.getElementById('guardian-score');
                const reasonEl = document.getElementById('guardian-reason');

                if (modeEl && data.mode) {
                    modeEl.textContent = data.mode.replace('_', ' ');

                    let color = '#94a3b8'; // Default grey
                    if (data.mode === 'GROWTH' || data.mode === 'ALT_SEASON') color = '#10b981'; // Green
                    if (data.mode === 'CAUTION') color = '#f59e0b'; // Orange
                    if (data.mode === 'CRITICAL_DEFENSE') color = '#ef4444'; // Red

                    modeEl.style.color = color;
                    barEl.style.background = color;

                    // Risk Score 0-100.
                    // If Risk is High (80), Bar should be Low (Health) or High (Danger)?
                    // "Guardian" implies protection/health.
                    // Let's do: Bar = Health = 100 - Risk.
                    const health = Math.max(0, 100 - (data.risk_score || 50));
                    barEl.style.width = health + '%';

                    trendEl.textContent = `Trend: ${(data.market_trend || 0).toFixed(1)}%`;
                    scoreEl.textContent = `Risk Score: ${data.risk_score || 0}`;
                    reasonEl.textContent = data.reason || 'Monitoring...';
                }

            } catch(e) {
                // console.warn("Guardian data waiting...");
            }
        }

        // Global variable for PnL Chart
        let pnlChart = null;
        let matrixChartInstance = null;

        async function updateMatrixScout() {
            try {
                const res = await fetch('api/data.php?file=correlation_matrix.json&t=' + Date.now());
                if(!res.ok) return;
                const data = await res.json();

                // Clear loading state if we got data or even empty data, just to show it's alive
                const matrixLoaderEl = document.querySelector("#matrix-heatmap");
                // Only clear if it contains the "Loading..." text
                if (matrixLoaderEl.innerHTML.includes('Loading Matrix...')) {
                    matrixLoaderEl.innerHTML = "";
                }

                if(data.timestamp) {
                    const timeEl = document.getElementById('matrix-time');
                    if(timeEl) timeEl.innerText = "Last: " + data.timestamp;
                }

                if(!data.series || data.series.length === 0) return;

                const options = {
                    series: data.series,
                    chart: {
                        height: 450,
                        type: 'heatmap',
                        background: 'transparent',
                        toolbar: { show: false }
                    },
                    plotOptions: {
                        heatmap: {
                            shadeIntensity: 0.5,
                            radius: 0,
                            useFillColorAsStroke: true,
                            colorScale: {
                                ranges: [{
                                    from: -1.0,
                                    to: 0.29,
                                    name: 'Inverse/Low',
                                    color: '#ef4444' // Red
                                }, {
                                    from: 0.3,
                                    to: 0.79,
                                    name: 'Neutral',
                                    color: '#94a3b8' // Grey
                                }, {
                                    from: 0.8,
                                    to: 1.0,
                                    name: 'Correlated',
                                    color: '#10b981' // Green
                                }]
                            }
                        }
                    },
                    dataLabels: {
                        enabled: true,
                        style: { colors: ['#fff'] }
                    },
                    stroke: { width: 1 },
                    theme: { mode: 'dark' },
                    xaxis: {
                        labels: { style: { colors: '#94a3b8' } }
                    },
                    yaxis: {
                        labels: { style: { colors: '#94a3b8' } }
                    },
                    title: {
                         text: undefined
                    }
                };

                const matrixChartEl = document.querySelector("#matrix-heatmap");
                if (matrixChartInstance) {
                    matrixChartInstance.updateOptions({
                        series: data.series
                    });
                } else {
                    // Clear loading text
                    matrixChartEl.innerHTML = "";
                    matrixChartInstance = new ApexCharts(matrixChartEl, options);
                    matrixChartInstance.render();
                }

            } catch(e) {
                console.warn("Matrix data waiting...");
            }
        }

        async function updateDailyPnL() {
            try {
                const res = await fetch('api/data.php?file=daily_stats.json&t=' + Date.now());
                if (!res.ok) return; // File might not exist yet
                const data = await res.json();

                // Prepare Data series
                const dates = data.map(item => item.date.substring(5)); // Show MM-DD only
                const values = data.map(item => parseFloat(item.pnl.toFixed(2)));

                // Define Chart Options
                const options = {
                    series: [{
                        name: 'Daily PnL',
                        data: values
                    }],
                    chart: {
                        type: 'bar',
                        height: 250,
                        background: 'transparent',
                        toolbar: { show: false },
                        animations: { enabled: false } // Disable animation for clearer updates
                    },
                    plotOptions: {
                        bar: {
                            colors: {
                                ranges: [{
                                    from: -100000,
                                    to: -0.01,
                                    color: '#ef4444' // Red for Loss
                                }, {
                                    from: 0,
                                    to: 100000,
                                    color: '#10b981' // Green for Profit
                                }]
                            },
                            columnWidth: '50%',
                            borderRadius: 4
                        }
                    },
                    dataLabels: {
                        enabled: true,
                        formatter: function (val) {
                            return (val > 0 ? '+' : '') + val + ' zł';
                        },
                        style: {
                            colors: ['#e2e8f0'],
                            fontSize: '10px'
                        },
                        offsetY: -20
                    },
                    xaxis: {
                        categories: dates,
                        axisBorder: { show: false },
                        axisTicks: { show: false },
                        labels: {
                            style: { colors: '#94a3b8', fontSize: '10px' }
                        }
                    },
                    yaxis: {
                        labels: {
                            style: { colors: '#94a3b8' },
                            formatter: (value) => { return value.toFixed(0) + ' zł' }
                        }
                    },
                    grid: {
                        borderColor: '#334155',
                        strokeDashArray: 4,
                        yaxis: { lines: { show: true } }
                    },
                    theme: { mode: 'dark' },
                    tooltip: {
                        theme: 'dark',
                        y: {
                            formatter: function (val) {
                                return val.toFixed(2) + " PLN";
                            }
                        }
                    }
                };

                // Render or Update
                if (pnlChart) {
                    pnlChart.updateOptions({
                        xaxis: { categories: dates },
                        series: [{ data: values }]
                    });
                } else {
                    pnlChart = new ApexCharts(document.querySelector("#daily-pnl-chart"), options);
                    pnlChart.render();
                }

            } catch (e) {
                console.warn("PnL Chart waiting for data...");
            }
        }

        function updateScout() {
            fetch('api/data.php?file=scout_results.json&t=' + Date.now())
                .then(r => r.json())
                .then(data => {
                    document.getElementById('scout-time').innerText = "Last: " + data.timestamp;
                    const tbody = document.getElementById('scout-list');
                    tbody.innerHTML = '';

                    if(!data.scouts || data.scouts.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">Scanning...</td></tr>';
                        return;
                    }
                data.scouts.forEach(coin => {
                    // Correlation Bar Logic
                    let corr = coin.correlation_btc || 0;
                    if (corr > 1) corr = 1;
                    if (corr < -1) corr = -1;

                    let barColor = corr >= 0 ? '#10b981' : '#ef4444';
                    let barWidth = Math.abs(corr) * 50;
                    let leftPos = corr >= 0 ? '50%' : (50 - barWidth) + '%';

                    let statusClass = 'bg-secondary';
                    if (coin.status === 'HEDGE') statusClass = 'bg-danger';
                    if (coin.status === 'FOLLOWER') statusClass = 'bg-success';

                    let row = `<tr>
                        <td class="fw-bold" style="vertical-align: middle;">${coin.symbol}</td>
                        <td style="vertical-align: middle;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <div style="width: 80px; height: 6px; background: #334155; position: relative; border-radius: 3px; flex-shrink: 0;">
                                    <div style="position: absolute; left: 50%; top: 0; bottom: 0; width: 1px; background: #64748b;"></div>
                                    <div style="position: absolute; top: 0; bottom: 0; left: ${leftPos}; width: ${barWidth}%; background: ${barColor}; border-radius: 2px;"></div>
                                </div>
                                <span style="font-size: 0.7rem; color: #94a3b8; min-width: 30px;">${corr.toFixed(2)}</span>
                            </div>
                        </td>
                        <td style="vertical-align: middle;"><span class="badge ${statusClass}">${coin.status}</span></td>
                        <td style="vertical-align: middle;">$${formatPrice(coin.price)}</td>
                    </tr>`;
                    tbody.innerHTML += row;
                });
            }).catch(e => console.log("Scout data waiting..."));
        } setInterval(updateScout, 10000); updateScout();

        function downloadMatrixData() {
            fetch('api/data.php?file=correlation_matrix.json&t=' + Date.now())
                .then(r => r.json())
                .then(data => {
                    if (!data || !data.series) {
                        alert("No matrix data available to download.");
                        return;
                    }

                    let txtContent = "Market Matrix Correlation Data\n";
                    txtContent += "Timestamp: " + (data.timestamp || new Date().toISOString()) + "\n\n";

                    // Header row (Tickers)
                    // The series logic in heatmap usually is: series[i].name = Y-axis ticker, series[i].data[j].x = X-axis ticker
                    // Let's iterate rows

                    data.series.forEach(row => {
                         const yTicker = row.name;
                         txtContent += `[${yTicker}] correlations:\n`;
                         row.data.forEach(cell => {
                             const xTicker = cell.x;
                             const val = cell.y;
                             txtContent += `  vs ${xTicker}: ${val}\n`;
                         });
                         txtContent += "\n";
                    });

                    const blob = new Blob([txtContent], { type: 'text/plain' });
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `market_matrix_${Date.now()}.txt`;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                })
                .catch(e => {
                    console.error(e);
                    alert("Failed to download matrix data.");
                });
        }
    </script>

<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-16 mb-24">
    <div class="bg-gray-900 border-2 border-indigo-900/50 rounded-2xl shadow-[0_0_60px_rgba(79,70,229,0.15)] overflow-hidden relative">
        
        <div class="absolute top-0 right-0 bg-indigo-600 text-white text-[10px] px-3 py-1 rounded-bl-xl font-bold tracking-wider z-10 shadow-lg">
            MODUŁ STRATEGICZNY • 7-DAY CYCLE
        </div>

        <div class="bg-gradient-to-r from-gray-900 via-[#1e1b4b] to-gray-900 px-8 py-6 border-b border-indigo-900/30">
            <div class="flex flex-col md:flex-row justify-between items-center gap-4">
                <div>
                    <h2 class="text-3xl font-black text-white flex items-center gap-3">
                        <span class="text-4xl filter drop-shadow-[0_0_10px_rgba(167,139,250,0.5)]">🛰️</span> 
                        <span class="text-transparent bg-clip-text bg-gradient-to-r from-indigo-300 to-purple-300">Satelita Crypto</span>
                    </h2>
                    <p class="text-indigo-200/40 text-sm mt-2 ml-1 font-mono">
                        ANALIZA MAKRO (2015-2026) • LOG REGRESSION + RANDOM FOREST
                    </p>
                </div>
                
                <div class="text-center">
                    <div class="text-[10px] text-gray-500 uppercase tracking-[0.2em] mb-1">DIAGNOZA RYNKU</div>
                    <div id="sat-phase-display" class="text-2xl font-black text-white px-8 py-3 bg-black/50 rounded-xl border border-white/5 backdrop-blur-sm shadow-inner transition-all duration-500">
                        INICJALIZACJA...
                    </div>
                </div>
            </div>
        </div>

        <div class="bg-black/40 px-8 py-2 border-b border-gray-800 flex items-center gap-4">
            <span class="text-[10px] text-gray-500 font-mono whitespace-nowrap">CYCLE STATUS:</span>
            <div class="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden relative">
                <div id="sat-progress-bar" class="h-full bg-indigo-500 shadow-[0_0_10px_#6366f1] w-0 transition-all duration-1000"></div>
            </div>
            <span id="sat-timer" class="text-[10px] text-indigo-400 font-mono whitespace-nowrap">--d --h</span>
        </div>

        <div class="p-6 bg-gradient-to-b from-gray-900 to-[#0f172a] relative">
            <div id="satelliteChart" style="min-height: 500px;"></div>
            
            <div class="absolute top-6 left-6 bg-black/60 backdrop-blur-md border border-gray-700 p-4 rounded-lg max-w-xs shadow-xl hidden md:block">
                <h4 class="text-indigo-400 text-xs font-bold uppercase mb-2">💡 Wnioski Strategiczne</h4>
                <p id="sat-conclusion" class="text-gray-300 text-sm leading-relaxed">
                    Ładowanie analizy AI...
                </p>
            </div>
        </div>

        <div class="grid grid-cols-2 md:grid-cols-4 gap-px bg-gray-800 border-t border-gray-800">
            <div class="bg-gray-900/95 p-6 flex flex-col items-center justify-center group hover:bg-gray-800 transition-all">
                <span class="text-gray-600 text-[10px] uppercase tracking-widest mb-2 group-hover:text-gray-400">Aktualna Cena</span>
                <span id="sat-price-val" class="text-2xl font-bold text-white font-mono tracking-tight">--</span>
            </div>
            <div class="bg-gray-900/95 p-6 flex flex-col items-center justify-center group hover:bg-gray-800 transition-all">
                <span class="text-gray-600 text-[10px] uppercase tracking-widest mb-2 group-hover:text-gray-400">Mayer Multiple</span>
                <span id="sat-mayer-val" class="text-2xl font-bold text-yellow-400 font-mono">--</span>
                <span id="sat-mayer-desc" class="text-[9px] text-gray-600 mt-1 uppercase">Średnia 200D</span>
            </div>
            <div class="bg-gray-900/95 p-6 flex flex-col items-center justify-center group hover:bg-gray-800 transition-all">
                <span class="text-gray-600 text-[10px] uppercase tracking-widest mb-2 group-hover:text-gray-400">Dni od Halvingu</span>
                <span id="sat-halving-val" class="text-2xl font-bold text-blue-400 font-mono">--</span>
                <span class="text-[9px] text-gray-600 mt-1">CYKL 4-LETNI</span>
            </div>
            <div class="bg-gray-900/95 p-6 flex flex-col items-center justify-center group hover:bg-gray-800 transition-all">
                <span class="text-gray-600 text-[10px] uppercase tracking-widest mb-2 group-hover:text-gray-400">Pewność Modelu AI</span>
                <div id="sat-confidence-val" class="w-full text-center space-y-1">
                    <span class="text-xs text-gray-500">--</span>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
async function initSatellite() {
    try {
        const response = await fetch('api/satellite_data.json');
        if (!response.ok) throw new Error("Brak danych satelity");
        const data = await response.json();

        // 1. Interpretacja Fazy (Tłumaczenie na Ludzki)
        const phaseEl = document.getElementById('sat-phase-display');
        const concEl = document.getElementById('sat-conclusion');
        let phaseText = data.current_phase;
        let conclusion = "";
        let colorClass = "";

        // Logika tłumaczenia
        const mayer = data.mayer_multiple;
        
        if (data.current_phase.includes('BESSA') || data.current_phase.includes('Bear')) {
            if (mayer < 1.0) {
                phaseText = "STREFA AKUMULACJI 🛒"; // Brzmi lepiej niż Bessa
                colorClass = "text-green-400 border-green-500/30 shadow-[0_0_15px_rgba(74,222,128,0.2)]";
                conclusion = "Cena znajduje się poniżej średniej 200-dniowej (Mayer < 1.0). Historycznie jest to doskonały moment na uśrednianie ceny (DCA). Rynek odpoczywa przed wzrostami.";
            } else {
                phaseText = "SPADKI / KOREKTA 📉";
                colorClass = "text-red-400 border-red-500/30";
                conclusion = "Rynek w trendzie spadkowym. Zalecana ostrożność i czekanie na potwierdzenie dna.";
            }
        } else if (data.current_phase.includes('HOSSA') || data.current_phase.includes('Bull')) {
            phaseText = "HOSSA / WZROSTY 🚀";
            colorClass = "text-blue-400 border-blue-500/30 shadow-[0_0_15px_rgba(96,165,250,0.2)]";
            conclusion = "Silny trend wzrostowy. Utrzymuj pozycje (HODL). Nie próbuj shortować silnego rynku.";
        } else if (data.current_phase.includes('EUFORIA')) {
            phaseText = "EUFORIA (SZCZYT?) ⚠️";
            colorClass = "text-orange-500 border-orange-500/50 animate-pulse";
            conclusion = "Rynek jest skrajnie przegrzany. Statystyka sugeruje realizację zysków. Ryzyko nagłego załamania.";
        } else if (data.current_phase.includes('DEPRESJA')) {
            phaseText = "GENERATIONAL BUY 💎";
            colorClass = "text-emerald-400 border-emerald-500/50";
            conclusion = "Matematyczne dno cyklu. Najlepszy możliwy moment na wejście w rynek w perspektywie 2-3 lat.";
        }

        phaseEl.innerText = phaseText;
        phaseEl.className = `text-2xl font-black px-8 py-3 bg-black/50 rounded-xl border backdrop-blur-sm shadow-inner transition-all duration-500 ${colorClass}`;
        concEl.innerText = conclusion;

        // 2. Wypełnij Metryki
        document.getElementById('sat-price-val').innerText = "$" + data.current_price.toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0});
        document.getElementById('sat-mayer-val').innerText = data.mayer_multiple + "x";
        
        // Mayer Desc color
        const mayerDesc = document.getElementById('sat-mayer-desc');
        if(mayer < 1.0) { mayerDesc.innerText = "OKAZJA (TANIO)"; mayerDesc.className = "text-[9px] text-green-400 mt-1 font-bold uppercase"; }
        else if(mayer > 2.4) { mayerDesc.innerText = "BAŃKA (DROGO)"; mayerDesc.className = "text-[9px] text-red-400 mt-1 font-bold uppercase"; }
        else { mayerDesc.innerText = "WARTOŚĆ UCZCIWA"; mayerDesc.className = "text-[9px] text-gray-500 mt-1 uppercase"; }

        document.getElementById('sat-halving-val').innerText = data.days_from_halving + " dni";

        // Pewność AI
        let aiHtml = "";
        const sortedConf = Object.entries(data.ai_confidence).sort(([,a],[,b]) => b-a);
        sortedConf.slice(0, 2).forEach(([key, val]) => {
            let col = val > 50 ? 'text-green-400' : 'text-gray-500';
            // Skróć nazwy
            let shortKey = key.split(' ')[0];
            aiHtml += `<div class="flex justify-between text-xs w-full px-2"><span class="text-gray-400">${shortKey}</span> <span class="${col} font-mono font-bold">${val}%</span></div>`;
        });
        document.getElementById('sat-confidence-val').innerHTML = aiHtml;

        // 3. Timer (Cycle Countdown)
        updateCountdown(data.next_update_ts, data.days_to_statistical_peak, data.recommended_mode);
        
        // 4. Wykres (Wersja Rainbow)
        renderRainbowChart(data.chart_history, data.halving_dates, data.current_price);

    } catch (e) {
        console.warn("Satelita Init Error:", e);
        document.getElementById('sat-phase-display').innerText = "OFFLINE";
    }
}

function updateCountdown(targetTs, daysToPeak, recommendedMode) {
    // Modified to show Cycle Peak Countdown instead of Update Timer
    const peakDays = daysToPeak !== undefined ? daysToPeak : 0;
    const mode = recommendedMode || 'NEUTRAL';
    
    // Total cycle length approx 1460 days, Peak usually around day 800-900 of cycle. 
    // Here we visualize progress towards the 700-day post-halving peak.
    // Let's assume the window is 0 to 800 days for the progress bar context.
    // If daysToPeak is e.g. 600, it means we have 600 days LEFT to peak.
    // So passed days = 700 - 600 = 100.
    // Progress = (700 - peakDays) / 700 * 100
    
    // Safety check
    let displayDays = peakDays;
    let label = "DO SZCZYTU";
    let progress = 0;
    let color = "bg-indigo-500";

    if (displayDays > 0) {
        progress = Math.max(0, Math.min(100, ((700 - displayDays) / 700) * 100));
        if (progress > 80) color = "bg-red-500"; // Close to peak
        else if (progress > 50) color = "bg-yellow-500";
    } else {
        displayDays = Math.abs(displayDays);
        label = "PO SZCZYCIE";
        progress = 100;
        color = "bg-red-600";
    }

    const bar = document.getElementById('sat-progress-bar');
    bar.style.width = `${progress}%`;
    bar.className = `h-full ${color} shadow-[0_0_10px_currentColor] transition-all duration-1000`;
    
    document.getElementById('sat-timer').innerHTML = `<span style="color:var(--text-muted)">${label}:</span> <span style="color:#fff; font-weight:bold">${displayDays} DNI</span> <span class="badge" style="font-size:0.6rem; margin-left:5px; background:${mode==='SPOT'?'var(--success)':'var(--danger)'}">${mode}</span>`;
}

function renderRainbowChart(historyData, halvingDates, currentPrice) {
    // Przygotowanie danych
    // Rozdzielamy historię od prognozy
    const prices = [];
    const topBand = [];
    const botBand = [];
    const forecast = [];

    historyData.forEach(d => {
        const ts = new Date(d.date).getTime();
        
        // Zawsze dodajemy bandy
        topBand.push([ts, d.rainbow_top]);
        botBand.push([ts, d.rainbow_bot]);

        if (d.is_projection) {
            // To jest prognoza
            forecast.push([ts, d.projected_fair]);
        } else {
            // To jest historia
            prices.push([ts, d.price]);
        }
    });

    // Annotations Logic
    const halvingAnnotations = (halvingDates || []).map(date => ({
        x: new Date(date).getTime(),
        borderColor: '#f59e0b',
        strokeDashArray: 4,
        label: {
            text: 'HALVING',
            orientation: 'horizontal',
            style: {
                color: '#fff',
                background: '#f59e0b',
                fontSize: '10px',
                fontWeight: 'bold'
            },
            offsetY: -15
        }
    }));

    const pointAnnotations = currentPrice ? [{
        x: new Date().getTime(),
        y: currentPrice,
        marker: {
            size: 6,
            fillColor: '#3b82f6',
            strokeColor: '#fff',
            radius: 2
        },
        label: {
            text: 'TU JESTEŚ',
            style: {
                background: '#3b82f6',
                color: '#fff',
                fontSize: '11px',
                fontWeight: 'bold',
                padding: { left:5, right:5, top:2, bottom:2 }
            },
            offsetY: 0
        }
    }] : [];

    const options = {
        annotations: {
            xaxis: halvingAnnotations,
            points: pointAnnotations
        },
        chart: {
            type: 'area', // Zmieniamy na AREA dla efektu tęczy
            height: 500,
            fontFamily: 'Inter, sans-serif',
            background: 'transparent',
            toolbar: { show: false },
            animations: { enabled: false }
        },
        theme: { mode: 'dark' },
        colors: ['#ef4444', '#ffffff', '#ffffff', '#3b82f6'], // Czerwony (Top), Biały (Cena), Biały/Kreskowany (Prognoza), Niebieski (Bot)
        
        series: [
            {
                name: 'Strefa Bańki (Max)',
                data: topBand,
                type: 'area' 
            },
            {
                name: 'Cena BTC',
                data: prices,
                type: 'line' // Cena jako linia na wierzchu
            },
            {
                name: 'Prognoza 100D (Fair Value)',
                data: forecast,
                type: 'line' 
            },
            {
                name: 'Strefa Okazji (Min)',
                data: botBand,
                type: 'area'
            }
        ],
        
        stroke: {
            width: [0, 2, 2, 0], // Cena i Prognoza mają linię
            curve: 'smooth',
            dashArray: [0, 0, 5, 0] // Trzecia seria (Prognoza) jest przerywana
        },
        fill: {
            type: ['gradient', 'solid', 'gradient'],
            gradient: {
                shadeIntensity: 1,
                opacityFrom: 0.3,
                opacityTo: 0.05,
                stops: [0, 100]
            }
        },
        dataLabels: { enabled: false },
        xaxis: {
            type: 'datetime',
            tooltip: { enabled: false },
            axisBorder: { show: false },
            axisTicks: { show: false }
        },
        yaxis: {
            logarithmic: true, // Ważne dla skali 10-letniej
            tickAmount: 5,
            labels: {
                formatter: (val) => { return val >= 1000 ? (val/1000).toFixed(0) + 'k' : val },
                style: { colors: '#475569' }
            }
        },
        grid: {
            borderColor: '#1e293b',
            strokeDashArray: 4,
            xaxis: { lines: { show: false } } 
        },
        tooltip: {
            theme: 'dark',
            x: { format: 'dd MMM yyyy' },
            y: { formatter: (val) => "$" + val.toLocaleString() }
        }
    };

    const chart = new ApexCharts(document.querySelector("#satelliteChart"), options);
    chart.render();
}

document.addEventListener('DOMContentLoaded', initSatellite);
</script>
</body>
</html>
