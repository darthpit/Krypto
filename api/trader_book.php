<?php
// api/trader_book.php - Trader Book API Endpoint
// Returns trade history with decision analysis

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

// Force UTC for consistent time
date_default_timezone_set('UTC');

// Helper: Safe JSON Output
function send_json($data) {
    echo json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
    exit;
}

// Helper: Error Output
function send_error($msg, $code = 500) {
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
    $host = $dbConf['host'] ?? 'localhost';
    
    // FIX DOCKER vs WINDOWS: If host is 'postgres' and we're on local XAMPP
    if ($host === 'postgres' && ($_SERVER['SERVER_NAME'] === 'localhost' || $_SERVER['SERVER_NAME'] === '127.0.0.1')) {
        $host = 'localhost'; 
    }
    
    $port = $dbConf['port'] ?? 5432;
    $dbname = $dbConf['dbname'] ?? 'mexc_futures_db';
    $user = $dbConf['user'] ?? 'postgres';
    $pass = $dbConf['password'] ?? 'password';

    $dsn = "pgsql:host=$host;port=$port;dbname=$dbname;connect_timeout=2";
    
    // Try to connect with 2 second timeout
    try {
        $pdo = new PDO($dsn, $user, $pass, [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_TIMEOUT => 2
        ]);
    } catch (PDOException $e) {
        // If connection fails, return mock data for testing
        send_json([
            'status' => 'success_mock',
            'trades' => [
                [
                    'symbol' => 'BTC/USDT',
                    'side' => 'LONG',
                    'entry_price' => 89500.00,
                    'exit_price' => 90200.00,
                    'invested_usdt' => 100.00,
                    'realized_pnl_usdt' => 0.78,
                    'realized_pnl_pct' => 0.78,
                    'max_possible_pnl_pct' => 1.20,
                    'entry_time' => '2026-01-23 10:30',
                    'exit_time' => '2026-01-23 11:45',
                    'duration_minutes' => 75,
                    'strategy' => 'PSND-AI'
                ],
                [
                    'symbol' => 'BTC/USDT',
                    'side' => 'SHORT',
                    'entry_price' => 89800.00,
                    'exit_price' => 89200.00,
                    'invested_usdt' => 100.00,
                    'realized_pnl_usdt' => 0.67,
                    'realized_pnl_pct' => 0.67,
                    'max_possible_pnl_pct' => 1.50,
                    'entry_time' => '2026-01-23 12:00',
                    'exit_time' => '2026-01-23 13:20',
                    'duration_minutes' => 80,
                    'strategy' => 'PSND-AI'
                ]
            ],
            'total_trades' => 2,
            'timestamp' => date('Y-m-d H:i:s'),
            'note' => 'Using mock data - database connection failed'
        ]);
    }

    // 2. Fetch trades from database
    // Get all trades ordered by timestamp
    $stmt = $pdo->query("
        SELECT 
            id,
            timestamp,
            action,
            ticker,
            price,
            amount,
            cost,
            fee,
            pnl,
            strategy
        FROM trades
        ORDER BY timestamp DESC
        LIMIT 100
    ");
    
    $allTrades = $stmt->fetchAll();
    
    if (empty($allTrades)) {
        send_json([
            'status' => 'success',
            'trades' => [],
            'message' => 'No trades found'
        ]);
    }

    // 3. Group trades into complete transactions (LONG+CLOSE_LONG or SHORT+CLOSE_SHORT)
    $completedTrades = [];
    $openPositions = [];
    
    // Parse trades and match entries with exits
    foreach ($allTrades as $trade) {
        $action = $trade['action'];
        $ticker = $trade['ticker'];
        
        // Entry actions: LONG or SHORT
        if ($action === 'LONG' || $action === 'SHORT') {
            // Store as open position
            $openPositions[] = [
                'entry_trade' => $trade,
                'side' => $action
            ];
        }
        // Exit actions: CLOSE_LONG or CLOSE_SHORT
        elseif ($action === 'CLOSE_LONG' || $action === 'CLOSE_SHORT') {
            $expectedSide = ($action === 'CLOSE_LONG') ? 'LONG' : 'SHORT';
            
            // Find matching open position (FIFO - First In First Out)
            $foundIndex = -1;
            foreach ($openPositions as $index => $pos) {
                if ($pos['side'] === $expectedSide && $pos['entry_trade']['ticker'] === $ticker) {
                    $foundIndex = $index;
                    break;
                }
            }
            
            if ($foundIndex !== -1) {
                $entryTrade = $openPositions[$foundIndex]['entry_trade'];
                $exitTrade = $trade;
                $side = $openPositions[$foundIndex]['side'];
                
                // Remove from open positions
                array_splice($openPositions, $foundIndex, 1);
                
                // Calculate metrics
                $entryPrice = floatval($entryTrade['price']);
                $exitPrice = floatval($exitTrade['price']);
                $investedUsdt = floatval($entryTrade['cost']);
                $amount = floatval($entryTrade['amount']);
                
                // Calculate realized PnL
                if ($side === 'LONG') {
                    $realizedPnlUsdt = ($exitPrice - $entryPrice) * $amount;
                } else { // SHORT
                    $realizedPnlUsdt = ($entryPrice - $exitPrice) * $amount;
                }
                
                $realizedPnlPct = ($investedUsdt > 0) ? ($realizedPnlUsdt / $investedUsdt) * 100 : 0;
                
                // Calculate max possible PnL (optimized - use single aggregation query)
                $entryTime = strtotime($entryTrade['timestamp']);
                $exitTime = strtotime($exitTrade['timestamp']);
                
                // Optimized: Get only the max/min price in one query instead of fetching all candles
                try {
                    if ($side === 'LONG') {
                        // For LONG: find highest high
                        $peakStmt = $pdo->prepare("
                            SELECT MAX(high) as peak_price
                            FROM candles
                            WHERE ticker = :ticker
                              AND timestamp BETWEEN :start AND :end
                            LIMIT 1
                        ");
                    } else {
                        // For SHORT: find lowest low
                        $peakStmt = $pdo->prepare("
                            SELECT MIN(low) as peak_price
                            FROM candles
                            WHERE ticker = :ticker
                              AND timestamp BETWEEN :start AND :end
                            LIMIT 1
                        ");
                    }
                    
                    $peakStmt->execute([
                        'ticker' => $ticker,
                        'start' => date('Y-m-d H:i:s', $entryTime),
                        'end' => date('Y-m-d H:i:s', $exitTime)
                    ]);
                    $peakResult = $peakStmt->fetch();
                    
                    if ($peakResult && $peakResult['peak_price'] !== null) {
                        $peakPrice = floatval($peakResult['peak_price']);
                        
                        if ($side === 'LONG') {
                            $maxPossiblePnlPct = (($peakPrice - $entryPrice) / $entryPrice) * 100;
                        } else {
                            $maxPossiblePnlPct = (($entryPrice - $peakPrice) / $entryPrice) * 100;
                        }
                    } else {
                        // No candles found, use realized as fallback
                        $maxPossiblePnlPct = $realizedPnlPct;
                    }
                } catch (Exception $e) {
                    // If query fails, just use realized PnL
                    $maxPossiblePnlPct = $realizedPnlPct;
                }
                
                // Ensure max possible is at least as good as realized (in case of data issues)
                if ($maxPossiblePnlPct < $realizedPnlPct) {
                    $maxPossiblePnlPct = $realizedPnlPct;
                }
                
                // Format timestamps
                $entryTimeFormatted = date('Y-m-d H:i', $entryTime);
                $exitTimeFormatted = date('Y-m-d H:i', $exitTime);
                
                // Add to completed trades
                $completedTrades[] = [
                    'symbol' => $ticker,
                    'side' => $side,
                    'entry_price' => $entryPrice,
                    'exit_price' => $exitPrice,
                    'invested_usdt' => $investedUsdt,
                    'realized_pnl_usdt' => $realizedPnlUsdt,
                    'realized_pnl_pct' => $realizedPnlPct,
                    'max_possible_pnl_pct' => $maxPossiblePnlPct,
                    'entry_time' => $entryTimeFormatted,
                    'exit_time' => $exitTimeFormatted,
                    'duration_minutes' => round(($exitTime - $entryTime) / 60, 1),
                    'strategy' => $entryTrade['strategy'] ?? 'Unknown'
                ];
            }
        }
    }
    
    // 4. Sort by exit time (most recent first) and limit to 50
    usort($completedTrades, function($a, $b) {
        return strtotime($b['exit_time']) - strtotime($a['exit_time']);
    });
    
    $completedTrades = array_slice($completedTrades, 0, 50);
    
    // 5. Return JSON response
    send_json([
        'status' => 'success',
        'trades' => $completedTrades,
        'total_trades' => count($completedTrades),
        'timestamp' => date('Y-m-d H:i:s')
    ]);

} catch (PDOException $e) {
    send_error("Database error: " . $e->getMessage(), 500);
} catch (Exception $e) {
    send_error("Server error: " . $e->getMessage(), 500);
}
