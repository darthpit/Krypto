<?php
// api/data.php - Unified Bridge & Smart Router (v4.5 - PostgreSQL)
// WERSJA FINALNA: Oryginalna logika + Naprawa Wykresów (Candles)

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

// Force UTC for consistent time comparisons (HARD OVERRIDE)
date_default_timezone_set('UTC');

// Helper: Safe JSON Output
function send_json($data) {
    echo json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
    exit;
}

// Helper: Error Output
function send_error($msg, $code = 404) {
    http_response_code($code);
    echo json_encode(['error' => $msg, 'status' => 'error']);
    exit;
}

try {
    // 1. Load Config & Connect to PostgreSQL
    $configPath = __DIR__ . '/../config.json';
    if (!file_exists($configPath)) {
        send_error("Config file not found", 500);
    }

    $config = json_decode(file_get_contents($configPath), true);
    if (!$config || !isset($config['database'])) {
        send_error("Invalid database configuration", 500);
    }

    $dbConf = $config['database'];
    // Default to localhost/postgres if missing
    $host = $dbConf['host'] ?? 'localhost';
    // FIX DOCKER vs WINDOWS: Jeśli host to 'postgres', a działamy lokalnie, zmień na localhost
    if ($host === 'postgres' && ($_SERVER['SERVER_NAME'] === 'localhost' || $_SERVER['SERVER_NAME'] === '127.0.0.1')) {
        // Opcjonalne: odkomentuj jeśli masz problemy z połączeniem z XAMPP
        $host = 'localhost'; 
    }
    
    $port = $dbConf['port'] ?? 5432;
    $dbname = $dbConf['dbname'] ?? 'pilot_db';
    $user = $dbConf['user'] ?? 'postgres';
    $pass = $dbConf['password'] ?? 'password';

    $dsn = "pgsql:host=$host;port=$port;dbname=$dbname";

    $pdo = new PDO($dsn, $user, $pass);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

    // =================================================================
    // 🛑 WKLEJ TO TUTAJ (Linia ok. 58) - BEZ TEGO WYKRES NIE RUSZY!
    // =================================================================
    $endpoint = $_GET['endpoint'] ?? '';
    
    if ($endpoint === 'candles') {
        $ticker = $_GET['ticker'] ?? 'BTC/USDT';
        $limit = isset($_GET['limit']) ? (int)$_GET['limit'] : 1000;

        // Pobieramy świece z bazy PostgreSQL
        $stmt = $pdo->prepare("SELECT timestamp, open, high, low, close, volume FROM candles WHERE ticker = ? ORDER BY timestamp DESC LIMIT ?");
        $stmt->execute([$ticker, $limit]);
        $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

        // Sortujemy od najstarszej do najnowszej (dla wykresu)
        $rows = array_reverse($rows);

        $out = [];
        foreach ($rows as $r) {
            $out[] = [
                strtotime($r['timestamp']) * 1000,
                (float)$r['open'],
                (float)$r['high'],
                (float)$r['low'],
                (float)$r['close'],
                (float)$r['volume']
            ];
        }
        send_json($out);
    }
    
    // RL Predictions endpoint (for chart visualization)
    if ($endpoint === 'rl_predictions') {
        $ticker = $_GET['ticker'] ?? 'BTC/USDT';
        $limit = isset($_GET['limit']) ? (int)$_GET['limit'] : 100;
        
        // Get RL predictions with hits/misses
        $stmt = $pdo->prepare("
            SELECT 
                timestamp, 
                predicted_price, 
                actual_price, 
                hit,
                created_at
            FROM rl_predictions 
            WHERE ticker = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        ");
        $stmt->execute([$ticker, $limit]);
        $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
        
        $rows = array_reverse($rows);
        
        $out = [];
        foreach ($rows as $r) {
            $out[] = [
                'timestamp' => strtotime($r['timestamp']) * 1000,
                'predicted' => (float)$r['predicted_price'],
                'actual' => $r['actual_price'] ? (float)$r['actual_price'] : null,
                'hit' => $r['hit'],
                'created_at' => $r['created_at']
            ];
        }
        send_json($out);
    }
    
    // Statistics endpoint
    if ($endpoint === 'stats') {
        $type = $_GET['type'] ?? '';
        
        if ($type === 'prediction_count') {
            $stmt = $pdo->prepare("SELECT COUNT(*) as count FROM predictions");
            $stmt->execute();
            $row = $stmt->fetch(PDO::FETCH_ASSOC);
            send_json(['count' => (int)$row['count']]);
        }
        
        send_error('Unknown stats type', 400);
    }
    
    // Positions endpoint
    if ($endpoint === 'positions') {
        $stmt = $pdo->prepare("SELECT value FROM system_status WHERE key = 'paper_all_positions'");
        $stmt->execute();
        $row = $stmt->fetch(PDO::FETCH_ASSOC);
        send_json($row && $row['value'] ? json_decode($row['value'], true) : []);
    }
    
    // Trades summary endpoint
    if ($endpoint === 'trades_summary') {
        $stmt = $pdo->query("SELECT COUNT(*) as total_trades FROM trades");
        $row = $stmt->fetch(PDO::FETCH_ASSOC);
        send_json(['total_trades' => (int)$row['total_trades'], 'realized_pnl' => 0]);
    }
    // =================================================================
    // KONIEC WKLEJANIA
    // =================================================================

    // 2. Request Router
    $file = $_GET['file'] ?? '';
    
    // Check for history files first (before switch)
    if (preg_match('/^history_([A-Z]+)_(LITE|FULL)\.json$/', $file, $matches)) {
        $ticker_clean = $matches[1];  // e.g. "BTCUSDT"
        $mode = $matches[2];           // "LITE" or "FULL"
        
        // Convert BTCUSDT -> BTC/USDT
        $ticker = preg_replace('/^([A-Z]+)(USDT)$/', '$1/$2', $ticker_clean);
        
        // LITE = 2000 candles (~20 days), FULL = all available (increased for LSTM training)
        $limit = ($mode === 'FULL') ? 5000 : 2000;
        
        // Fetch from database
        $stmt = $pdo->prepare("SELECT timestamp, open, high, low, close, volume FROM candles WHERE ticker = ? ORDER BY timestamp DESC LIMIT ?");
        $stmt->execute([$ticker, $limit]);
        $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
        
        // Reverse to get oldest->newest for chart
        $rows = array_reverse($rows);
        
        $out = [];
        foreach ($rows as $r) {
            $out[] = [
                strtotime($r['timestamp']) * 1000,  // timestamp in ms
                (float)$r['open'],
                (float)$r['high'],
                (float)$r['low'],
                (float)$r['close'],
                (float)$r['volume']
            ];
        }
        send_json($out);
    }

    // Switch Logic (Smart Router)
    switch ($file) {
        
        // --- 1. SYSTEM STATUS (HEARTBEAT) ---
        case 'status.json':
            // Check 'heartbeat' in system_status (Written by TraderProcess)
            $stmt = $pdo->prepare("SELECT value, updated_at FROM system_status WHERE key = ?");
            $stmt->execute(['heartbeat']);
            $row = $stmt->fetch(PDO::FETCH_ASSOC);

            $online = false;
            $msg = "Offline";
            $updated = 0;

            if ($row) {
                // Logic Fix: Use timestamp from JSON payload (Epoch) to avoid timezone issues with DB strings
                $hbData = json_decode($row['value'], true);

                // 1. Try Heartbeat Payload (Python time.time() is UTC Epoch)
                if (isset($hbData['timestamp']) && is_numeric($hbData['timestamp'])) {
                    $updated = (float)$hbData['timestamp'];
                }
                // 2. Fallback to Latest Results if Heartbeat invalid
                else {
                    $stmt2 = $pdo->prepare("SELECT value, updated_at FROM system_status WHERE key = ?");
                    $stmt2->execute(['latest_results']);
                    $row2 = $stmt2->fetch(PDO::FETCH_ASSOC);

                    if ($row2) {
                        $lrData = json_decode($row2['value'], true);
                        if (isset($lrData['timestamp'])) {
                            // Python ISO format (usually local time if naive, but let's trust strtotime)
                            $updated = strtotime($lrData['timestamp']);
                        } else {
                            $updated = strtotime($row2['updated_at'] . ' UTC');
                        }
                    } else {
                         // 3. Last Resort: DB Column
                         $updated = strtotime($row['updated_at'] . ' UTC');
                    }
                }

                $now = time(); // PHP is set to UTC at top of script

                // 120s tolerance
                if (($now - $updated) < 120) {
                    $online = true;
                    $msg = "Online";
                }
            }

            send_json([
                'online' => $online,
                'message' => $msg,
                'timestamp' => $row ? $row['updated_at'] : null,
                'debug_diff' => isset($now) ? ($now - $updated) : 0
            ]);
            break;

        // --- 2. WALLET / PORTFOLIO ---
        case 'paper_wallet.json':
            $response = [
                "USDT" => 100.0,
                "initial_balance" => 100.0,
                "pln_value" => 400.0,
                "trades" => []
            ];

            // A. Fetch Balances
            $stmt = $pdo->query("SELECT currency, amount FROM wallet_balances");
            $balances = $stmt->fetchAll(PDO::FETCH_KEY_PAIR);

            if ($balances) {
                $response = array_merge($response, $balances);
            }

            // A2. Fetch Short Positions (JSON from system_status)
            $stmt = $pdo->prepare("SELECT value FROM system_status WHERE key = 'paper_short_positions'");
            $stmt->execute();
            $row = $stmt->fetch(PDO::FETCH_ASSOC);
            if ($row) {
                $shorts = json_decode($row['value'], true);
                if (is_array($shorts)) {
                    $response = array_merge($response, $shorts);
                }
            }

            // B. Fetch Trades
            // Check if trades table exists first (it should)
            $stmt = $pdo->query("SELECT * FROM trades ORDER BY timestamp DESC"); // Newest first
            $trades = $stmt->fetchAll(PDO::FETCH_ASSOC);

            if ($trades) {
                $cleanTrades = [];
                $realized_pnl = 0.0;
                $vol_buy = 0.0;
                $vol_sell = 0.0;
                $total_fees = 0.0;

                foreach ($trades as $t) {
                    // Restore complex data if in raw_data
                    $tradeObj = !empty($t['raw_data']) ? json_decode($t['raw_data'], true) : $t;
                    // Fallback to columns
                    if (!$tradeObj) $tradeObj = $t;

                    // Ensure numeric types
                    $tradeObj['price'] = (float)($tradeObj['price'] ?? 0);
                    $tradeObj['amount'] = (float)($tradeObj['amount'] ?? 0);
                    $tradeObj['pnl'] = (float)($tradeObj['pnl'] ?? 0);
                    $tradeObj['fee'] = (float)($t['fee'] ?? 0); // Use raw column

                    $cleanTrades[] = $tradeObj;

                    // Aggregates
                    $total_fees += $tradeObj['fee'];

                    if ($t['action'] === 'BUY') {
                        $vol_buy += $tradeObj['price'] * $tradeObj['amount'];
                    } elseif ($t['action'] === 'SELL' || $t['action'] === 'SHORT_CLOSE') {
                        $vol_sell += $tradeObj['price'] * $tradeObj['amount'];
                        $realized_pnl += $tradeObj['pnl'];
                    }
                }

                $response['trades'] = $cleanTrades;
                $response['realized_pnl'] = $realized_pnl;
                $response['total_fees_paid'] = $total_fees;
                $response['total_volume_bought'] = $vol_buy;
                $response['total_volume_sold'] = $vol_sell;
            }

            // C. Calculate PLN Value (Dynamic)
            $usdt = $response['USDT'] ?? 0;
            $response['pln_value'] = $usdt * 4.0;

            send_json($response);
            break;

        // --- 3. DAILY PNL STATS ---
        case 'daily_stats.json':
            // Aggregate PnL by day
            // PostgreSQL: to_char(timestamp, 'YYYY-MM-DD')
            $sql = "SELECT to_char(timestamp, 'YYYY-MM-DD') as date, SUM(pnl) as pnl
                    FROM trades
                    WHERE action IN ('SELL', 'SHORT_CLOSE')
                    GROUP BY date
                    ORDER BY date DESC
                    LIMIT 30";

            $stmt = $pdo->query($sql);
            $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

            // Return array of {date, pnl}
            foreach ($rows as &$r) {
                $r['pnl'] = (float)$r['pnl'];
            }
            $rows = array_reverse($rows);

            send_json($rows);
            break;

        // --- 4. GENERIC SYSTEM STATUS BLOBS ---
        case 'latest_results.json':
            // Support ticker-specific fetch
            if (isset($_GET['ticker']) && !empty($_GET['ticker'])) {
                $tickerKey = 'latest_results_' . $_GET['ticker'];
                $stmt = $pdo->prepare("SELECT value FROM system_status WHERE key = ?");
                $stmt->execute([$tickerKey]);
                $row = $stmt->fetch(PDO::FETCH_ASSOC);
                if ($row) {
                    echo $row['value'];
                    exit;
                }
                // Fallthrough to default if specific not found (or return empty default?)
                // Let's fallthrough to generic 'latest_results' which usually holds BTC or primary
            }
            // Standard Flow continues...

        case 'ai_context.json':
        case 'engine_status.json':
        case 'radar_scan.json':
        case 'correlation_matrix.json':
        case 'trader_state.json':
        case 'trader_intent.json':
        case 'model_stats.json':
        case 'scout_results.json':
        case 'holistic_status.json':
        case 'sync_status.json':
        case 'brain_stats.json':
        case 'quant_metrics.json':
            // Map file name to DB key
            $keyMap = [
                'latest_results.json' => 'latest_results',
                'ai_context.json' => 'latest_results', // Derive from latest_results or separate?
                'engine_status.json' => 'pulse', // Special handling needed
                'radar_scan.json' => 'radar_scan',
                'correlation_matrix.json' => 'correlation_matrix',
                'trader_state.json' => 'trader_state',
                'trader_intent.json' => 'trader_intent',
                'model_stats.json' => 'model_stats',
                'scout_results.json' => 'scout_results',
                'holistic_status.json' => 'holistic_status',
                'sync_status.json' => 'sync_status',
                'brain_stats.json' => 'brain_stats',
                'quant_metrics.json' => 'quant_metrics'
            ];

            $key = $keyMap[$file] ?? str_replace('.json', '', $file);

            // SPECIAL CASE: brain_stats.json must be explicitly handled if not in switch cases
            if ($file === 'brain_stats.json') {
                $stmt = $pdo->prepare('SELECT value FROM system_status WHERE key = ?');
                $stmt->execute(['brain_stats']);
                $row = $stmt->fetch(PDO::FETCH_ASSOC);
                if ($row) {
                    echo $row['value'];
                    exit;
                }
                send_json(['status' => 'waiting_for_data']);
            }
            
            // SPECIAL CASE: rl_brain_stats.json for RL Agent dashboard panel
            if ($file === 'rl_brain_stats.json') {
                $stmt = $pdo->prepare('SELECT * FROM rl_brain_stats ORDER BY id DESC LIMIT 1');
                $stmt->execute();
                $row = $stmt->fetch(PDO::FETCH_ASSOC);
                if ($row) {
                    echo json_encode([
                        'training_status' => $row['training_status'] ?? 'IDLE',
                        'accuracy' => (float)($row['total_accuracy'] ?? 0),
                        'hits' => (int)($row['total_hits'] ?? 0),
                        'misses' => (int)($row['total_misses'] ?? 0),
                        'last_check' => $row['last_check'] ?? null,
                        'next_training' => $row['next_training_time'] ?? null,
                        'model_version' => $row['model_version'] ?? 'v1.0.0',
                        'status' => 'active'
                    ]);
                    exit;
                }
                send_json(['status' => 'waiting_for_data', 'training_status' => 'NOT_TRAINED']);
            }

            // Special Handler for engine_status (aggregates pulses)
            if ($file === 'engine_status.json') {
                $pulses = ['pulse_1m', 'pulse_5m', 'pulse_30m'];
                $resp = [];
                foreach ($pulses as $p) {
                    $stmt = $pdo->prepare("SELECT value FROM system_status WHERE key = ?");
                    $stmt->execute([$p]);
                    $row = $stmt->fetch(PDO::FETCH_ASSOC);
                    $resp[$p] = $row ? json_decode($row['value'], true) : ["status" => "idle"];
                }
                send_json($resp);
            }

            // Special Handler for ai_context (extract from latest_results if missing)
            if ($file === 'ai_context.json') {
                 // Try specific key first
                 $stmt = $pdo->prepare("SELECT value FROM system_status WHERE key = ?");
                 $stmt->execute(['ai_context']);
                 $row = $stmt->fetch(PDO::FETCH_ASSOC);
                 if ($row) send_json(json_decode($row['value'], true));

                 // Fallback to latest_results extraction
                 $stmt->execute(['latest_results']);
                 $row = $stmt->fetch(PDO::FETCH_ASSOC);
                 if ($row) {
                     $d = json_decode($row['value'], true);
                     send_json([
                         "signal" => $d['signal'] ?? 'NEUTRAL',
                         "reason" => "Market Regime: " . ($d['fvg_status'] ?? 'Unknown'),
                         "timestamp" => $d['timestamp'] ?? date('c')
                     ]);
                 }
                 // Default
                 send_json(["signal" => "NEUTRAL", "reason" => "Initializing..."]);
            }

            // Special Handler for holistic_status (Fallback Logic)
            if ($file === 'holistic_status.json') {
                // Try specific key first
                $stmt = $pdo->prepare("SELECT value FROM system_status WHERE key = ?");
                $stmt->execute(['holistic_status']);
                $row = $stmt->fetch(PDO::FETCH_ASSOC);

                if ($row) {
                    echo $row['value'];
                    exit;
                }

                // If missing, synthesize from latest_results (Risk) and radar_scan (Breadth)
                $risk_score = 50; // Neutral default
                $mode = "MONITORING";
                $trend = 50;

                // 1. Get Trader Results (Signal/FVG)
                $stmt->execute(['latest_results']);
                $resRow = $stmt->fetch(PDO::FETCH_ASSOC);
                if ($resRow) {
                    $d = json_decode($resRow['value'], true);
                    if (($d['signal'] ?? '') === 'BUY') {
                         $risk_score -= 20; // Lower risk
                         $mode = "GROWTH";
                    } elseif (($d['signal'] ?? '') === 'SELL') {
                         $risk_score += 20;
                         $mode = "CAUTION";
                    }
                    if (strpos($d['fvg_status'] ?? '', 'BEARISH') !== false) {
                        $risk_score += 10;
                    }
                }

                // 2. Get Radar Breadth
                $stmt->execute(['radar_scan']);
                $radRow = $stmt->fetch(PDO::FETCH_ASSOC);
                if ($radRow) {
                    $r = json_decode($radRow['value'], true);
                    $gems = $r['gems'] ?? [];
                    $bullish = 0;
                    foreach($gems as $g) {
                        if (($g['trend'] ?? '') === 'BULLISH') $bullish++;
                    }
                    if (count($gems) > 0) {
                        $trend = ($bullish / count($gems)) * 100;
                    }
                    if ($trend > 60) {
                         $mode = ($mode === 'GROWTH') ? "ALT_SEASON" : "GROWTH";
                         $risk_score -= 10;
                    }
                }

                // Clamp
                $risk_score = max(0, min(100, $risk_score));

                send_json([
                    "mode" => $mode,
                    "risk_score" => $risk_score,
                    "market_trend" => round($trend, 1),
                    "reason" => "Synthesized from AI Signals & Market Breadth",
                    "timestamp" => date('c')
                ]);
            }

            // Generic Fetch
            $stmt = $pdo->prepare("SELECT value FROM system_status WHERE key = ?");
            $stmt->execute([$key]);
            $row = $stmt->fetch(PDO::FETCH_ASSOC);

            if ($row) {
                echo $row['value']; // Already JSON
                exit;
            } else {
                // Return safe default
                send_json(["status" => "waiting_for_data", "timestamp" => null]);
            }
            break;

        // --- 5. MARKET WATCH ---
        case 'market_watch.json':
            // Added condition_score and history_days
            $stmt = $pdo->query("SELECT ticker, price, change_24h, volume_24h, condition_score, history_days FROM market_watch");
            $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

            // Helper: compute history_days from candles table (fallback when market_watch is empty or stale)
            $compute_history_days = function($ticker) use ($pdo) {
                try {
                    $s = $pdo->prepare("SELECT MIN(timestamp) as min_ts, MAX(timestamp) as max_ts FROM candles WHERE ticker = ?");
                    $s->execute([$ticker]);
                    $r = $s->fetch(PDO::FETCH_ASSOC);
                    if (!$r || empty($r['min_ts']) || empty($r['max_ts'])) return 0;
                    $min = strtotime($r['min_ts'] . ' UTC');
                    $max = strtotime($r['max_ts'] . ' UTC');
                    if (!$min || !$max || $max <= $min) return 0;
                    // +1 so same-day data shows as 1d, not 0d
                    return max(1, (int)floor(($max - $min) / 86400) + 1);
                } catch (Exception $e) {
                    return 0;
                }
            };

            foreach ($rows as &$r) {
                // Robust casting to float, default 0.0 if null
                $r['price'] = isset($r['price']) ? (float)$r['price'] : 0.0;
                $r['change_24h'] = isset($r['change_24h']) ? (float)$r['change_24h'] : 0.0;
                $r['volume_24h'] = isset($r['volume_24h']) ? (float)$r['volume_24h'] : 0.0;
                $r['condition_score'] = isset($r['condition_score']) ? (int)$r['condition_score'] : 0;
                $r['history_days'] = isset($r['history_days']) ? (int)$r['history_days'] : 0;
                if ($r['history_days'] <= 0 && !empty($r['ticker'])) {
                    $r['history_days'] = $compute_history_days($r['ticker']);
                }
            }

            // FALLBACK: If market_watch is empty, use latest_results for current ticker
            if (empty($rows)) {
                $stmt = $pdo->prepare("SELECT value FROM system_status WHERE key = ?");
                $stmt->execute(['latest_results']);
                $row = $stmt->fetch(PDO::FETCH_ASSOC);

                if ($row) {
                    $data = json_decode($row['value'], true);
                    if (isset($data['ticker']) && isset($data['current_price'])) {
                        $hd = $compute_history_days($data['ticker']);
                        $rows = [[
                            'ticker' => $data['ticker'],
                            'price' => (float)$data['current_price'],
                            'change_24h' => 0.0,
                            'volume_24h' => 0.0,
                            'condition_score' => 0,
                            'history_days' => $hd
                        ]];
                    }
                }
            }

            send_json($rows ?: []);
            break;

        // --- 6. ACTIVE STRATEGIES ---
        case 'active_strategies.json':
            $stmt = $pdo->query("SELECT ticker, params FROM active_strategies WHERE status='ACTIVE'");
            $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
            $out = [];
            foreach ($rows as $r) {
                $out[$r['ticker']] = json_decode($r['params'], true);
            }
            send_json($out);
            break;

        // --- 7. REFEREE HISTORY (VALIDATION POINTS) ---
        case 'referee_history.json':
            // Fetch from system_status where referee_history is stored (cleaned HIT/MISS only)
            $stmt = $pdo->prepare('SELECT value FROM system_status WHERE key = ?');
            $stmt->execute(['referee_history']);
            $row = $stmt->fetch(PDO::FETCH_ASSOC);
            
            if ($row && $row['value']) {
                send_json(json_decode($row['value'], true));
            } else {
                send_json(['BTC/USDT' => []]);
            }
            break;
        
        // DEPRECATED: Old referee_history from predictions table
        case 'referee_history_raw.json':
            // Fetch directly from predictions table (includes PENDING)
            // Using 'timestamp' column which is prediction time
            $stmt = $pdo->query("SELECT ticker, timestamp, predicted_price, entry_price, result, direction FROM predictions ORDER BY timestamp DESC LIMIT 100");
            $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

            $formatted = [];
            foreach ($rows as $r) {
                $t = $r['ticker'];
                if (!isset($formatted[$t])) $formatted[$t] = [];

                // Convert timestamp to milliseconds
                $ts = strtotime($r['timestamp'] . ' UTC') * 1000;

                $formatted[$t][] = [
                    't' => $ts,
                    'p' => (float)$r['predicted_price'],
                    'entry_price' => isset($r['entry_price']) ? (float)$r['entry_price'] : 0.0,
                    'result' => $r['result'] ?? 'PENDING',
                    'direction' => (int)($r['direction'] ?? 0)
                ];
            }
            send_json($formatted);
            break;

        // --- 8. CANDLE HISTORY ---
        default:
            if (strpos($file, 'history_') === 0) {
                // Parse ticker
                // history_BTCUSDT_LITE.json
                $base = str_replace(['history_', '_LITE.json', '_FULL.json', '.json'], '', $file);
                // Try to format ticker as AAA/BBB
                $ticker = $base;
                if (strpos($base, '/') === false && substr($base, -4) === 'USDT') {
                    $ticker = substr($base, 0, -4) . '/USDT';
                }

                $limit = (strpos($file, 'LITE') !== false) ? 200 : 5000;

                $stmt = $pdo->prepare("SELECT timestamp, open, high, low, close, volume FROM candles WHERE ticker = ? ORDER BY timestamp DESC LIMIT ?");
                $stmt->execute([$ticker, $limit]);
                $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

                // Sort back to ASC for chart
                $rows = array_reverse($rows);

                $out = [];
                foreach ($rows as $r) {
                    $out[] = [
                        strtotime($r['timestamp']) * 1000,
                        (float)$r['open'],
                        (float)$r['high'],
                        (float)$r['low'],
                        (float)$r['close'],
                        (float)$r['volume']
                    ];
                }
                send_json($out);
            }
            // --- 9. CONFIG & LOGS (Filesystem) ---
            elseif ($file === 'config.json') {
                $path = __DIR__ . '/../config.json';
                if (file_exists($path)) {
                    header('Content-Type: application/json');
                    readfile($path);
                    exit;
                }
                send_json(['error' => 'Config missing']);
            }
            elseif (strpos($file, 'logs/') === 0) {
                $path = __DIR__ . '/../' . $file;
                if (file_exists($path) && realpath($path) === realpath(__DIR__ . '/../' . $file)) {
                    header('Content-Type: text/plain');
                    readfile($path);
                    exit;
                }
                send_error('Log not found');
            }
            else {
                send_error('Unknown file request');
            }
            break;
    }

} catch (PDOException $e) {
    // If DB fails, try to return a valid JSON structure for Wallet so dashboard doesn't die completely
    if ($file === 'paper_wallet.json') {
         send_json([
            "USDT" => 100.0,
            "initial_balance" => 100.0,
            "pln_value" => 400.0,
            "trades" => [],
            "error" => "DB Connection Failed"
         ]);
    }

    send_error('Database Error: ' . $e->getMessage(), 500);
}
?>