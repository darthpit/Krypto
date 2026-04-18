<?php
header('Content-Type: application/json');

// Get raw POST data
$input = file_get_contents('php://input');
$data = json_decode($input, true);

if (!$data || !isset($data['action'])) {
    echo json_encode(['success' => false, 'error' => 'Brak wymaganych danych.']);
    exit;
}

$action = $data['action'];

try {
    switch ($action) {
        case 'resume_ppo':
            $lockfile = __DIR__ . '/../models/.rl_training.lock';
            if (file_exists($lockfile)) {
                unlink($lockfile);
            }
            // Zabij ewentualnego zombie process trenowania PPO
            exec("pkill -f process_rl_trainer.py");

            // Usunięcie informacji o statusie awarii z właściwej bazy przez Pythona
            $pythonCode = "
import os, sys
sys.path.append('" . addslashes(realpath(__DIR__ . '/..')) . "')
from src.database import Database
db = Database()
db.execute(\"UPDATE system_status SET value = '{\\\"status\\\": \\\"IDLE\\\", \\\"action\\\": \\\"RESUME_PPO\\\"}' WHERE key = 'rl_training_status'\")
";
            // Run inline to avoid race condition of temp files
            exec("python3 -c " . escapeshellarg($pythonCode));

            echo json_encode(['success' => true, 'message' => 'Agent PPO został wznowiony. Usunięto ewentualne blokady.']);
            break;

        case 'reset_ppo':
            // 1. Usunięcie locka
            $lockfile = __DIR__ . '/../models/.rl_training.lock';
            if (file_exists($lockfile)) {
                unlink($lockfile);
            }

            // 2. Zabicie procesu
            exec("pkill -f process_rl_trainer.py");

            // 3. Wyczyszczenie katalogu checkpoints i modelu
            exec("rm -rf " . __DIR__ . "/../models/checkpoints/*");
            exec("rm -rf " . __DIR__ . "/../models/ppo_trading_agent*");
            exec("rm -f " . __DIR__ . "/../models/rl_training_info.json");

            // 4. Wyczyszczenie bazy (stats)
            // Znalezienie właściwej bazy dancyh (sqlite lub pgsql) - uzyjemy wywołania python skryptu dla bezpieczeństwa
            $pythonCode = "
import os, sys
sys.path.append('" . addslashes(realpath(__DIR__ . '/..')) . "')
from src.database import Database
db = Database()
db.execute('DELETE FROM rl_brain_stats')
db.execute(\"INSERT INTO system_status (key, value) VALUES ('rl_training_status', '{\\\"status\\\": \\\"IDLE\\\", \\\"action\\\": \\\"RESET_PPO\\\"}') ON CONFLICT (key) DO UPDATE SET value = '{\\\"status\\\": \\\"IDLE\\\", \\\"action\\\": \\\"RESET_PPO\\\"}'\")
";
            exec("python3 -c " . escapeshellarg($pythonCode));

            // 5. Wyczyszczenie logu
            $logFile = __DIR__ . '/../logs/PPO.log';
            if (file_exists($logFile)) {
                file_put_contents($logFile, "[RESET] Logs cleared by user\n");
            }

            echo json_encode(['success' => true, 'message' => 'Hard Reset PPO wykonany pomyślnie. Wymusisz nowy trening całego modelu.']);
            break;

        case 'resume_lstm':
            $lockfile = __DIR__ . '/../models/.lstm_training.lock';
            if (file_exists($lockfile)) {
                unlink($lockfile);
            }
            // Zabij i wznów
            exec("pkill -f process_trainer.py");

            // Zresetuj status w ModelMonitor, by supervisor natychmiast go podjął
            $pythonCode = "
import os, sys
sys.path.append('" . addslashes(realpath(__DIR__ . '/..')) . "')
from src.utils.model_monitor import ModelMonitor
m = ModelMonitor()
m.update_error('lstm', 'Wznowiono ręcznie - oczekiwanie na nową pętlę')
";
            exec("python3 -c " . escapeshellarg($pythonCode));

            echo json_encode(['success' => true, 'message' => 'Trening LSTM wznowiony. Pętle rozpoczną się wkrótce automatycznie.']);
            break;

        case 'reset_lstm':
            // 1. Usuń locki i zabij proces
            $lockfile = __DIR__ . '/../models/.lstm_training.lock';
            if (file_exists($lockfile)) {
                unlink($lockfile);
            }
            exec("pkill -f process_trainer.py");

            // 2. Usuń modele
            exec("rm -f " . __DIR__ . "/../models/model_BTC_USDT_Ensemble_*.pkl");
            exec("rm -f " . __DIR__ . "/../models/ensemble_model");

            // Zresetuj status w ModelMonitor, by supervisor natychmiast rozpoczął nowy trening
            $pythonCode = "
import os, sys
sys.path.append('" . addslashes(realpath(__DIR__ . '/..')) . "')
from src.utils.model_monitor import ModelMonitor
m = ModelMonitor()
m.update_error('lstm', 'Twardy reset - wymuszenie ponownego treningu')
";
            exec("python3 -c " . escapeshellarg($pythonCode));

            // 3. Wyczyszczenie logu
            $logFile = __DIR__ . '/../logs/LSTM.log';
            if (file_exists($logFile)) {
                file_put_contents($logFile, "[RESET] Logs cleared by user\n");
            }

            echo json_encode(['success' => true, 'message' => 'Hard Reset LSTM wykonany pomyślnie. System wygeneruje nowy model przy najbliższej okazji.']);
            break;

        default:
            echo json_encode(['success' => false, 'error' => 'Nieznana akcja.']);
            break;
    }
} catch (Exception $e) {
    echo json_encode(['success' => false, 'error' => 'Wystąpił błąd: ' . $e->getMessage()]);
}
